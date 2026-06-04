"""Gmail API 클라이언트.

여러 Google 계정의 Gmail을 조회/발송하기 위한 클라이언트.
저장된 refresh token을 사용하여 매번 인증 없이 API 호출.

Features:
    - 다중 계정 지원 (work, personal 등)
    - Rate Limiting & Quota Management (P0)
    - Exponential Backoff for Error Handling (P0)
    - Batch Processing for Bulk Operations (P1)
    - Local Caching for API Optimization (P1)

Environment Variables:
    GMAIL_SKILL_PATH: Skill 루트 경로 (기본값: 이 파일의 부모의 부모)
    GMAIL_TIMEOUT: API 요청 타임아웃 초 (기본값: 30)
    GMAIL_CACHE_DIR: 캐시 디렉토리 (기본값: .cache/gmail)
    GMAIL_ENABLE_CACHE: 캐시 활성화 여부 (기본값: true)
    GMAIL_ENABLE_QUOTA: 할당량 관리 활성화 여부 (기본값: true)
"""

import base64
import html
import json
import logging
import mimetypes
import os
from email import encoders
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Core modules for enhanced functionality
try:
    from .core import (
        QuotaManager,
        QuotaUnit,
        exponential_backoff,
        EmailCache,
        BatchProcessor,
    )
except ImportError:
    # Fallback for direct script execution
    from core import (
        QuotaManager,
        QuotaUnit,
        exponential_backoff,
        EmailCache,
        BatchProcessor,
    )

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = int(os.environ.get("GMAIL_TIMEOUT", "30"))
ENABLE_CACHE = os.environ.get("GMAIL_ENABLE_CACHE", "true").lower() == "true"
ENABLE_QUOTA = os.environ.get("GMAIL_ENABLE_QUOTA", "true").lower() == "true"


def _sanitize_header(value: str) -> str:
    """이메일 헤더 값에서 CR/LF 를 제거한다(헤더 인젝션 방어 + 직렬화 크래시 방지).

    to/subject/cc 등에 개행이 섞이면 (1) 공격자가 추가 헤더(Bcc 등)를 주입하려는 시도이거나
    (2) 실수로 들어간 개행이며, 어느 쪽이든 email 직렬화가 HeaderParseError 로 발송을
    중단시킨다. 개행을 공백으로 접어 안전하게 만든다.
    """
    if value is None:
        return value
    return str(value).replace("\r", " ").replace("\n", " ")


def _decode_mime_header(value: str) -> str:
    """RFC2047 인코딩된 헤더(=?UTF-8?B?..?=)를 사람이 읽는 텍스트로 디코딩한다.

    Gmail API 는 헤더 값을 원본(인코딩) 그대로 주므로, 한글 등 비ASCII 제목/발신자가
    그대로 노출되면 깨져 보인다. 디코딩 실패 시 원본을 반환한다.
    """
    if not value:
        return value
    try:
        from email.header import decode_header, make_header

        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _charset_from_headers(headers: list) -> str | None:
    """파트 headers 의 Content-Type 에서 charset 을 추출한다(예: 'euc-kr'). 없으면 None."""
    for h in headers or []:
        if h.get("name", "").lower() == "content-type":
            value = h.get("value", "")
            for part in value.split(";"):
                part = part.strip()
                if part.lower().startswith("charset="):
                    return part.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def _b64url_decode(data: str) -> bytes:
    """base64url 디코딩 시 누락된 패딩을 보정한다.

    Gmail API 는 메시지 본문/첨부 data 를 패딩 없는 base64url 로 줄 때가 있어,
    그대로 urlsafe_b64decode 하면 binascii.Error("Incorrect padding")로 크래시한다.
    길이를 4의 배수로 맞춰 안전하게 디코딩한다.
    """
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


class GmailClient:
    """단일 Google 계정의 Gmail 클라이언트.

    Enhanced with:
        - Rate limiting & quota management
        - Exponential backoff for error handling
        - Local caching for API optimization
        - Batch processing support
    """

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.modify",  # 읽기/수정/삭제
        "https://www.googleapis.com/auth/gmail.send",    # 메일 발송
        "https://www.googleapis.com/auth/gmail.labels",  # 라벨 관리
    ]

    def __init__(
        self,
        account_name: str,
        base_path: Optional[Path] = None,
        timeout: int = DEFAULT_TIMEOUT,
        enable_cache: bool = ENABLE_CACHE,
        enable_quota: bool = ENABLE_QUOTA,
    ):
        """
        Args:
            account_name: 계정 식별자 (예: 'work', 'personal')
            base_path: skill 루트 경로
            timeout: API 요청 타임아웃 (초)
            enable_cache: 캐시 활성화 여부
            enable_quota: 할당량 관리 활성화 여부
        """
        self.account_name = account_name
        self.timeout = timeout
        self.enable_cache = enable_cache
        self.enable_quota = enable_quota

        if base_path:
            self.base_path = base_path
        elif os.environ.get("GMAIL_SKILL_PATH"):
            self.base_path = Path(os.environ["GMAIL_SKILL_PATH"])
        else:
            self.base_path = Path(__file__).parent.parent

        self.creds = self._load_credentials()
        self._service = None

        # Initialize core components
        self._cache: Optional[EmailCache] = None
        self._quota_manager: Optional[QuotaManager] = None
        self._batch_processor: Optional[BatchProcessor] = None

        if enable_cache:
            cache_dir = os.environ.get("GMAIL_CACHE_DIR") or str(
                self.base_path / ".cache" / "gmail"
            )
            self._cache = EmailCache(cache_dir=cache_dir)

        if enable_quota:
            self._quota_manager = QuotaManager()

    @property
    def service(self):
        """Lazy-load Gmail service."""
        if self._service is None:
            self._service = build("gmail", "v1", credentials=self.creds)
        return self._service

    @property
    def cache(self) -> Optional[EmailCache]:
        """Get cache manager instance."""
        return self._cache

    @property
    def quota_manager(self) -> Optional[QuotaManager]:
        """Get quota manager instance."""
        return self._quota_manager

    @property
    def batch_processor(self) -> BatchProcessor:
        """Get batch processor instance (lazy-loaded)."""
        if self._batch_processor is None:
            self._batch_processor = BatchProcessor(
                service=self.service,
                quota_manager=self._quota_manager,
                user=self.account_name,
            )
        return self._batch_processor

    def _record_quota(self, units: int) -> None:
        """Record quota usage if quota management is enabled."""
        if self._quota_manager:
            self._quota_manager.record_usage(self.account_name, units)

    def _wait_for_quota(self, units: int) -> None:
        """Wait for quota availability if quota management is enabled."""
        if self._quota_manager:
            self._quota_manager.wait_for_quota(self.account_name, units)

    def _load_credentials(self):
        """저장된 refresh token으로 credentials 로드 및 갱신."""
        token_path = self.base_path / f"accounts/{self.account_name}.json"

        if not token_path.exists():
            raise FileNotFoundError(
                f"계정 '{self.account_name}'의 토큰이 없습니다. "
                f"먼저 setup_auth.py --account {self.account_name} 실행 필요"
            )

        with open(token_path) as f:
            token_data = json.load(f)

        if "client_id" in token_data and "type" not in token_data:
            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=self.SCOPES,
            )
            quota_project = token_data.get("quota_project_id", "automate-491505")
            creds = creds.with_quota_project(quota_project)
        else:
            creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w") as f:
                json.dump(json.loads(creds.to_json()), f, indent=2)

        return creds

    # =========================================================================
    # Messages
    # =========================================================================

    def list_messages(
        self,
        query: str = "",
        max_results: int = 20,
        label_ids: Optional[list[str]] = None,
        include_spam_trash: bool = False,
        use_cache: bool = True,
    ) -> list[dict]:
        """메시지 목록 조회.

        Args:
            query: Gmail 검색 쿼리 (예: "from:user@example.com", "is:unread")
            max_results: 최대 결과 수
            label_ids: 필터할 라벨 ID 목록
            include_spam_trash: 스팸/휴지통 포함 여부
            use_cache: 캐시 사용 여부 (기본값: True)

        Returns:
            메시지 목록 (id, threadId 포함)
        """
        # Check cache first
        if use_cache and self._cache:
            cached = self._cache.get_list(self.account_name, query, label_ids)
            if cached is not None:
                logger.debug(f"Cache hit for list query: {query}")
                return cached[:max_results]

        messages = []
        page_token = None

        @exponential_backoff(max_retries=5)
        def _list_page(**kwargs):
            return self.service.users().messages().list(**kwargs).execute()

        while len(messages) < max_results:
            kwargs = {
                "userId": "me",
                "maxResults": min(max_results - len(messages), 500),  # Gmail list 최대 500
                "includeSpamTrash": include_spam_trash,
            }
            if query:
                kwargs["q"] = query
            if label_ids:
                kwargs["labelIds"] = label_ids
            if page_token:
                kwargs["pageToken"] = page_token

            # Wait for quota before API call
            self._wait_for_quota(QuotaUnit.MESSAGES_LIST)

            result = _list_page(**kwargs)

            # Record quota usage
            self._record_quota(QuotaUnit.MESSAGES_LIST)

            for msg in result.get("messages", []):
                messages.append(msg)

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        # 서버가 maxResults 를 초과 반환할 수 있으므로(문서상 maxResults 는 페이지 크기
        # 힌트이며, 실제 maxResults=1 에도 전체를 반환하는 사례가 보고됨) 계약대로 상한을
        # 강제한다. 캐시 히트 경로(cached[:max_results])와 동일하게 맞춘다.
        messages = messages[:max_results]

        # Cache the results
        if use_cache and self._cache and messages:
            self._cache.set_list(self.account_name, query, messages, label_ids)

        return messages

    def get_message(
        self,
        message_id: str,
        format: str = "full",
        use_cache: bool = True,
    ) -> dict:
        """메시지 상세 조회.

        Args:
            message_id: 메시지 ID
            format: 응답 형식 (minimal, full, raw, metadata)
            use_cache: 캐시 사용 여부 (기본값: True)

        Returns:
            메시지 상세 정보
        """
        # Check cache first (only for full/metadata formats)
        if use_cache and self._cache and format in ("full", "metadata"):
            cached = self._cache.get_message(
                self.account_name,
                message_id,
                metadata_only=(format == "metadata"),
            )
            if cached is not None:
                logger.debug(f"Cache hit for message: {message_id}")
                return cached

        @exponential_backoff(max_retries=5)
        def _get_message():
            return (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format=format)
                .execute()
            )

        # Wait for quota before API call
        self._wait_for_quota(QuotaUnit.MESSAGES_GET)

        result = _get_message()

        # Record quota usage
        self._record_quota(QuotaUnit.MESSAGES_GET)

        parsed = self._parse_message(result)

        # full 만 캐시한다. metadata 응답은 본문 data 가 없어 parsed["body"]가 비는데,
        # metadata/full 이 같은 캐시 파일을 공유하므로 metadata 를 저장하면 이후 full 조회가
        # 빈 본문을 돌려받는 오염이 생긴다. full 은 metadata 의 상위집합이라 metadata 조회도
        # full 캐시로 안전하게 충족된다.
        if use_cache and self._cache and format == "full":
            self._cache.set_message(self.account_name, message_id, parsed)

        return parsed

    def _parse_message(self, msg: dict) -> dict:
        """API 응답을 파싱하여 읽기 쉬운 형식으로 변환."""
        headers = {}
        # from/to/cc/subject 는 비ASCII(한글 등)면 RFC2047 인코딩되어 오므로 디코딩한다.
        # date/message-id 는 ASCII 라 원본 유지.
        _decode_names = ("from", "to", "cc", "bcc", "subject")
        for header in msg.get("payload", {}).get("headers", []):
            name = header["name"].lower()
            if name in ("from", "to", "cc", "bcc", "subject", "date", "message-id"):
                value = header["value"]
                headers[name] = _decode_mime_header(value) if name in _decode_names else value

        body = ""
        attachments = []

        payload = msg.get("payload", {})
        body, attachments = self._extract_body_and_attachments(payload, msg["id"])

        return {
            "id": msg["id"],
            "thread_id": msg["threadId"],
            "label_ids": msg.get("labelIds", []),
            # Gmail snippet 은 HTML 이스케이프되어 오므로(&#39; &amp; 등) 언이스케이프해
            # 리포트/요약에 사람이 읽기 좋은 텍스트로 표시한다.
            # `or ""`: snippet 키가 null 로 와도(None) html.unescape 크래시를 막는다.
            "snippet": html.unescape(msg.get("snippet") or ""),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "cc": headers.get("cc", ""),
            "subject": headers.get("subject", "(제목 없음)"),
            "date": headers.get("date", ""),
            "message_id": headers.get("message-id", ""),
            "body": body,
            "attachments": attachments,
            "size_estimate": msg.get("sizeEstimate", 0),
            "internal_date": msg.get("internalDate", ""),
        }

    def _extract_body_and_attachments(
        self, payload: dict, message_id: str
    ) -> tuple[str, list[dict]]:
        """메시지 본문과 첨부파일 추출."""
        body = ""
        attachments = []

        mime_type = payload.get("mimeType", "")

        if mime_type.startswith("multipart/"):
            for part in payload.get("parts", []):
                part_body, part_attachments = self._extract_body_and_attachments(
                    part, message_id
                )
                # 첫 비어있지 않은 본문을 유지한다. multipart/alternative 는 단순→충실 순서라
                # text/plain 이 먼저 오므로, 마지막(보통 html)로 덮어쓰지 않고 읽기 좋은
                # plain 을 택한다. plain 이 없으면 html 이 그대로 채택된다.
                if part_body and not body:
                    body = part_body
                attachments.extend(part_attachments)
        else:
            if payload.get("filename"):
                attachments.append(
                    {
                        "filename": payload["filename"],
                        "mime_type": mime_type,
                        "size": payload.get("body", {}).get("size", 0),
                        "attachment_id": payload.get("body", {}).get("attachmentId"),
                    }
                )
            elif mime_type in ("text/plain", "text/html"):
                data = payload.get("body", {}).get("data", "")
                if data:
                    # 본문 charset 은 utf-8 이 아닐 수 있다(euc-kr/cp949 한국 메일이 흔함).
                    # 파트의 Content-Type charset 으로 디코딩하고, 없거나 알 수 없으면 utf-8.
                    # errors="replace" 로 비정상 바이트가 전체 파싱을 죽이지 않게 한다.
                    charset = _charset_from_headers(payload.get("headers", [])) or "utf-8"
                    raw_bytes = _b64url_decode(data)
                    try:
                        decoded = raw_bytes.decode(charset, errors="replace")
                    except LookupError:  # 알 수 없는 charset 이름
                        decoded = raw_bytes.decode("utf-8", errors="replace")
                    if mime_type == "text/plain" or not body:
                        body = decoded

        return body, attachments

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """첨부파일 다운로드.

        Args:
            message_id: 메시지 ID
            attachment_id: 첨부파일 ID

        Returns:
            첨부파일 바이너리 데이터
        """
        result = (
            self.service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        return _b64url_decode(result["data"])

    def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html: bool = False,
        attachments: Optional[list[str]] = None,
        reply_to_message_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> dict:
        """메일 발송.

        Args:
            to: 수신자 (쉼표로 구분 가능)
            subject: 제목
            body: 본문
            cc: 참조
            bcc: 숨은 참조
            html: HTML 형식 여부
            attachments: 첨부파일 경로 목록
            reply_to_message_id: 답장할 메시지 ID (In-Reply-To 헤더용)
            thread_id: 스레드 ID (답장 시)

        Returns:
            발송된 메시지 정보
        """
        if attachments:
            message = MIMEMultipart()
            message.attach(MIMEText(body, "html" if html else "plain", "utf-8"))
            for filepath in attachments:
                self._attach_file(message, filepath)
        else:
            message = MIMEText(body, "html" if html else "plain", "utf-8")

        message["to"] = _sanitize_header(to)
        message["subject"] = _sanitize_header(subject)
        if cc:
            message["cc"] = _sanitize_header(cc)
        if bcc:
            message["bcc"] = _sanitize_header(bcc)
        if reply_to_message_id:
            message["In-Reply-To"] = _sanitize_header(reply_to_message_id)
            message["References"] = _sanitize_header(reply_to_message_id)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        body_data = {"raw": raw}
        if thread_id:
            body_data["threadId"] = thread_id

        @exponential_backoff(max_retries=5)
        def _send():
            return (
                self.service.users().messages().send(userId="me", body=body_data).execute()
            )

        # Wait for quota before API call (send uses 100 units)
        self._wait_for_quota(QuotaUnit.MESSAGES_SEND)

        result = _send()

        # Record quota usage
        self._record_quota(QuotaUnit.MESSAGES_SEND)

        # Invalidate list cache after sending
        if self._cache:
            self._cache.invalidate_lists(self.account_name)

        return {
            "id": result["id"],
            "thread_id": result["threadId"],
            "label_ids": result.get("labelIds", []),
            "status": "sent",
        }

    def _attach_file(self, message: MIMEMultipart, filepath: str) -> None:
        """파일을 메시지에 첨부."""
        path = Path(filepath)
        content_type, encoding = mimetypes.guess_type(str(path))

        if content_type is None:
            content_type = "application/octet-stream"

        main_type, sub_type = content_type.split("/", 1)

        with open(path, "rb") as f:
            data = f.read()

        if main_type == "text":
            try:
                attachment = MIMEText(data.decode("utf-8"), _subtype=sub_type)
            except UnicodeDecodeError:
                # 비UTF-8 텍스트 파일은 MIMEText 로 디코딩하면 크래시한다. 바이트를 보존하는
                # 바이너리(base64) 첨부로 폴백해 전송이 실패하지 않게 한다.
                attachment = MIMEBase(main_type, sub_type)
                attachment.set_payload(data)
                encoders.encode_base64(attachment)
        elif main_type == "image":
            attachment = MIMEImage(data, _subtype=sub_type)
        elif main_type == "audio":
            attachment = MIMEAudio(data, _subtype=sub_type)
        else:
            attachment = MIMEBase(main_type, sub_type)
            attachment.set_payload(data)
            encoders.encode_base64(attachment)

        attachment.add_header(
            "Content-Disposition", "attachment", filename=path.name
        )
        message.attach(attachment)

    def modify_message(
        self,
        message_id: str,
        add_label_ids: Optional[list[str]] = None,
        remove_label_ids: Optional[list[str]] = None,
    ) -> dict:
        """메시지 라벨 수정.

        Args:
            message_id: 메시지 ID
            add_label_ids: 추가할 라벨 ID
            remove_label_ids: 제거할 라벨 ID

        Returns:
            수정된 메시지 정보
        """
        body = {}
        if add_label_ids:
            body["addLabelIds"] = add_label_ids
        if remove_label_ids:
            body["removeLabelIds"] = remove_label_ids

        @exponential_backoff(max_retries=5)
        def _modify():
            return (
                self.service.users()
                .messages()
                .modify(userId="me", id=message_id, body=body)
                .execute()
            )

        # Wait for quota before API call
        self._wait_for_quota(QuotaUnit.MESSAGES_MODIFY)

        result = _modify()

        # Record quota usage
        self._record_quota(QuotaUnit.MESSAGES_MODIFY)

        # 메시지 캐시와 목록 캐시를 모두 무효화한다. 목록은 라벨(UNREAD/INBOX 등)로
        # 필터되므로 라벨 변경 후 목록 캐시가 stale 해진다(send_message 와 동일한 패턴).
        if self._cache:
            self._cache.invalidate_message(self.account_name, message_id)
            self._cache.invalidate_lists(self.account_name)

        return {
            "id": result["id"],
            "thread_id": result["threadId"],
            "label_ids": result.get("labelIds", []),
            "status": "modified",
        }

    def mark_as_read(self, message_id: str) -> dict:
        """읽음으로 표시."""
        return self.modify_message(message_id, remove_label_ids=["UNREAD"])

    def mark_as_unread(self, message_id: str) -> dict:
        """읽지 않음으로 표시."""
        return self.modify_message(message_id, add_label_ids=["UNREAD"])

    def star_message(self, message_id: str) -> dict:
        """별표 추가."""
        return self.modify_message(message_id, add_label_ids=["STARRED"])

    def unstar_message(self, message_id: str) -> dict:
        """별표 제거."""
        return self.modify_message(message_id, remove_label_ids=["STARRED"])

    def archive_message(self, message_id: str) -> dict:
        """보관처리 (INBOX 라벨 제거)."""
        return self.modify_message(message_id, remove_label_ids=["INBOX"])

    def trash_message(self, message_id: str) -> dict:
        """휴지통으로 이동."""
        @exponential_backoff(max_retries=5)
        def _trash():
            return (
                self.service.users()
                .messages()
                .trash(userId="me", id=message_id)
                .execute()
            )

        self._wait_for_quota(QuotaUnit.MESSAGES_TRASH)
        result = _trash()
        self._record_quota(QuotaUnit.MESSAGES_TRASH)

        # Invalidate cache
        if self._cache:
            self._cache.invalidate_message(self.account_name, message_id)
            self._cache.invalidate_lists(self.account_name)

        return {
            "id": result["id"],
            "status": "trashed",
        }

    def untrash_message(self, message_id: str) -> dict:
        """휴지통에서 복원."""
        @exponential_backoff(max_retries=5)
        def _untrash():
            return (
                self.service.users()
                .messages()
                .untrash(userId="me", id=message_id)
                .execute()
            )

        self._wait_for_quota(QuotaUnit.MESSAGES_UNTRASH)
        result = _untrash()
        self._record_quota(QuotaUnit.MESSAGES_UNTRASH)

        # Invalidate cache
        if self._cache:
            self._cache.invalidate_message(self.account_name, message_id)
            self._cache.invalidate_lists(self.account_name)

        return {
            "id": result["id"],
            "status": "untrashed",
        }

    def delete_message(self, message_id: str) -> dict:
        """메시지 영구 삭제 (복구 불가)."""
        @exponential_backoff(max_retries=5)
        def _delete():
            self.service.users().messages().delete(userId="me", id=message_id).execute()

        self._wait_for_quota(QuotaUnit.MESSAGES_DELETE)
        _delete()
        self._record_quota(QuotaUnit.MESSAGES_DELETE)

        # Invalidate cache
        if self._cache:
            self._cache.invalidate_message(self.account_name, message_id)
            self._cache.invalidate_lists(self.account_name)

        return {
            "id": message_id,
            "status": "deleted",
        }

    # =========================================================================
    # Threads
    # =========================================================================

    def list_threads(
        self,
        query: str = "",
        max_results: int = 20,
        label_ids: Optional[list[str]] = None,
    ) -> list[dict]:
        """스레드 목록 조회."""
        threads = []
        page_token = None

        while len(threads) < max_results:
            kwargs = {
                "userId": "me",
                "maxResults": min(max_results - len(threads), 500),  # Gmail list 최대 500
            }
            if query:
                kwargs["q"] = query
            if label_ids:
                kwargs["labelIds"] = label_ids
            if page_token:
                kwargs["pageToken"] = page_token

            result = self.service.users().threads().list(**kwargs).execute()

            for thread in result.get("threads", []):
                threads.append(thread)

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return threads

    def get_thread(self, thread_id: str, format: str = "full") -> dict:
        """스레드 상세 조회."""
        result = (
            self.service.users()
            .threads()
            .get(userId="me", id=thread_id, format=format)
            .execute()
        )

        messages = [self._parse_message(msg) for msg in result.get("messages", [])]

        return {
            "id": result["id"],
            "messages": messages,
            "message_count": len(messages),
        }

    def trash_thread(self, thread_id: str) -> dict:
        """스레드 휴지통으로 이동."""
        result = (
            self.service.users()
            .threads()
            .trash(userId="me", id=thread_id)
            .execute()
        )
        return {
            "id": result["id"],
            "status": "trashed",
        }

    # =========================================================================
    # Labels
    # =========================================================================

    def list_labels(self, use_cache: bool = True) -> list[dict]:
        """라벨 목록 조회.

        Args:
            use_cache: 캐시 사용 여부 (기본값: True)

        Returns:
            라벨 목록
        """
        # Check cache first
        if use_cache and self._cache:
            cached = self._cache.get_labels(self.account_name)
            if cached is not None:
                logger.debug("Cache hit for labels")
                return cached

        @exponential_backoff(max_retries=5)
        def _list_labels():
            return self.service.users().labels().list(userId="me").execute()

        self._wait_for_quota(QuotaUnit.LABELS_LIST)
        result = _list_labels()
        self._record_quota(QuotaUnit.LABELS_LIST)

        labels = []
        for label in result.get("labels", []):
            labels.append(
                {
                    "id": label["id"],
                    "name": label["name"],
                    "type": label.get("type", "user"),
                    "message_list_visibility": label.get("messageListVisibility"),
                    "label_list_visibility": label.get("labelListVisibility"),
                }
            )

        # Cache the results
        if use_cache and self._cache:
            self._cache.set_labels(self.account_name, labels)

        return labels

    def get_label(self, label_id: str) -> dict:
        """라벨 상세 조회."""
        result = (
            self.service.users().labels().get(userId="me", id=label_id).execute()
        )
        return {
            "id": result["id"],
            "name": result["name"],
            "type": result.get("type", "user"),
            "messages_total": result.get("messagesTotal", 0),
            "messages_unread": result.get("messagesUnread", 0),
            "threads_total": result.get("threadsTotal", 0),
            "threads_unread": result.get("threadsUnread", 0),
        }

    def create_label(
        self,
        name: str,
        message_list_visibility: str = "show",
        label_list_visibility: str = "labelShow",
    ) -> dict:
        """라벨 생성.

        Args:
            name: 라벨 이름
            message_list_visibility: 메시지 목록에서 표시 여부 (show, hide)
            label_list_visibility: 라벨 목록에서 표시 여부 (labelShow, labelHide)

        Returns:
            생성된 라벨 정보
        """
        body = {
            "name": name,
            "messageListVisibility": message_list_visibility,
            "labelListVisibility": label_list_visibility,
        }

        result = (
            self.service.users().labels().create(userId="me", body=body).execute()
        )

        # 라벨 목록 캐시(1h TTL)를 무효화해 새 라벨이 즉시 반영되게 한다.
        if self._cache:
            self._cache.invalidate_labels(self.account_name)

        return {
            "id": result["id"],
            "name": result["name"],
            "status": "created",
        }

    def update_label(
        self,
        label_id: str,
        name: Optional[str] = None,
        message_list_visibility: Optional[str] = None,
        label_list_visibility: Optional[str] = None,
    ) -> dict:
        """라벨 수정."""
        result = (
            self.service.users().labels().get(userId="me", id=label_id).execute()
        )

        if name:
            result["name"] = name
        if message_list_visibility:
            result["messageListVisibility"] = message_list_visibility
        if label_list_visibility:
            result["labelListVisibility"] = label_list_visibility

        updated = (
            self.service.users()
            .labels()
            .update(userId="me", id=label_id, body=result)
            .execute()
        )

        if self._cache:
            self._cache.invalidate_labels(self.account_name)

        return {
            "id": updated["id"],
            "name": updated["name"],
            "status": "updated",
        }

    def delete_label(self, label_id: str) -> dict:
        """라벨 삭제."""
        self.service.users().labels().delete(userId="me", id=label_id).execute()

        if self._cache:
            self._cache.invalidate_labels(self.account_name)

        return {
            "id": label_id,
            "status": "deleted",
        }

    # =========================================================================
    # Drafts
    # =========================================================================

    def list_drafts(self, max_results: int = 20) -> list[dict]:
        """초안 목록 조회."""
        drafts = []
        page_token = None

        while len(drafts) < max_results:
            kwargs = {
                "userId": "me",
                "maxResults": min(max_results - len(drafts), 500),  # Gmail list 최대 500
            }
            if page_token:
                kwargs["pageToken"] = page_token

            result = self.service.users().drafts().list(**kwargs).execute()

            for draft in result.get("drafts", []):
                drafts.append(draft)

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return drafts

    def get_draft(self, draft_id: str) -> dict:
        """초안 상세 조회."""
        result = (
            self.service.users()
            .drafts()
            .get(userId="me", id=draft_id, format="full")
            .execute()
        )

        return {
            "id": result["id"],
            "message": self._parse_message(result["message"]),
        }

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html: bool = False,
    ) -> dict:
        """초안 생성.

        Args:
            to: 수신자
            subject: 제목
            body: 본문
            cc: 참조
            bcc: 숨은 참조
            html: HTML 형식 여부

        Returns:
            생성된 초안 정보
        """
        message = MIMEText(body, "html" if html else "plain", "utf-8")
        message["to"] = _sanitize_header(to)
        message["subject"] = _sanitize_header(subject)
        if cc:
            message["cc"] = _sanitize_header(cc)
        if bcc:
            message["bcc"] = _sanitize_header(bcc)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        result = (
            self.service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )

        return {
            "id": result["id"],
            "message_id": result["message"]["id"],
            "status": "created",
        }

    def send_draft(self, draft_id: str) -> dict:
        """초안 발송."""
        result = (
            self.service.users()
            .drafts()
            .send(userId="me", body={"id": draft_id})
            .execute()
        )

        # 발송으로 메시지 목록이 바뀌므로 목록 캐시를 무효화한다(send_message 와 동일).
        if self._cache:
            self._cache.invalidate_lists(self.account_name)

        return {
            "id": result["id"],
            "thread_id": result["threadId"],
            "label_ids": result.get("labelIds", []),
            "status": "sent",
        }

    def delete_draft(self, draft_id: str) -> dict:
        """초안 삭제."""
        self.service.users().drafts().delete(userId="me", id=draft_id).execute()
        return {
            "id": draft_id,
            "status": "deleted",
        }

    # =========================================================================
    # Profile
    # =========================================================================

    def get_profile(self) -> dict:
        """계정 프로필 조회."""
        @exponential_backoff(max_retries=5)
        def _get_profile():
            return self.service.users().getProfile(userId="me").execute()

        self._wait_for_quota(QuotaUnit.PROFILE_GET)
        result = _get_profile()
        self._record_quota(QuotaUnit.PROFILE_GET)

        return {
            "email": result["emailAddress"],
            "messages_total": result.get("messagesTotal", 0),
            "threads_total": result.get("threadsTotal", 0),
            "history_id": result.get("historyId", ""),
        }

    # =========================================================================
    # Batch Operations (P1)
    # =========================================================================

    def batch_get_messages(
        self,
        message_ids: list[str],
        format: str = "metadata",
    ) -> dict:
        """메시지 일괄 조회.

        Args:
            message_ids: 조회할 메시지 ID 목록
            format: 응답 형식 (minimal, full, raw, metadata)

        Returns:
            BatchResult 객체 (total, succeeded, failed, results, errors)
        """
        return self.batch_processor.batch_get_messages(message_ids, format)

    def batch_modify_labels(
        self,
        message_ids: list[str],
        add_labels: Optional[list[str]] = None,
        remove_labels: Optional[list[str]] = None,
    ) -> dict:
        """라벨 일괄 수정.

        Args:
            message_ids: 수정할 메시지 ID 목록
            add_labels: 추가할 라벨 ID
            remove_labels: 제거할 라벨 ID

        Returns:
            BatchResult 객체
        """
        result = self.batch_processor.batch_modify_labels(
            message_ids, add_labels, remove_labels
        )

        # Invalidate cache for modified messages
        if self._cache:
            for msg_id in message_ids:
                self._cache.invalidate_message(self.account_name, msg_id)
            self._cache.invalidate_lists(self.account_name)

        return result

    def batch_trash_messages(self, message_ids: list[str]) -> dict:
        """메시지 일괄 휴지통 이동.

        Args:
            message_ids: 휴지통으로 이동할 메시지 ID 목록

        Returns:
            BatchResult 객체
        """
        result = self.batch_processor.batch_trash_messages(message_ids)

        # Invalidate cache
        if self._cache:
            for msg_id in message_ids:
                self._cache.invalidate_message(self.account_name, msg_id)
            self._cache.invalidate_lists(self.account_name)

        return result

    def batch_delete_messages(self, message_ids: list[str]) -> dict:
        """메시지 일괄 영구 삭제.

        주의: 이 작업은 되돌릴 수 없습니다!

        Args:
            message_ids: 삭제할 메시지 ID 목록

        Returns:
            BatchResult 객체
        """
        result = self.batch_processor.batch_delete_messages(message_ids)

        # Invalidate cache
        if self._cache:
            for msg_id in message_ids:
                self._cache.invalidate_message(self.account_name, msg_id)
            self._cache.invalidate_lists(self.account_name)

        return result

    def mark_all_as_read(
        self,
        query: str = "is:unread",
        max_messages: int = 500,
    ) -> dict:
        """조건에 맞는 메시지 전체 읽음 처리.

        Args:
            query: 검색 쿼리 (기본: 읽지 않음)
            max_messages: 최대 처리 메시지 수

        Returns:
            BatchResult 객체
        """
        result = self.batch_processor.mark_all_as_read(query, max_messages)

        # Invalidate cache
        if self._cache:
            self._cache.invalidate_lists(self.account_name)

        return result

    def archive_all(
        self,
        query: str = "",
        max_messages: int = 500,
    ) -> dict:
        """조건에 맞는 메시지 전체 보관처리.

        Args:
            query: 검색 쿼리
            max_messages: 최대 처리 메시지 수

        Returns:
            BatchResult 객체
        """
        result = self.batch_processor.archive_all(query, max_messages)

        # Invalidate cache
        if self._cache:
            self._cache.invalidate_lists(self.account_name)

        return result

    # =========================================================================
    # Cache & Quota Management
    # =========================================================================

    def get_quota_status(self) -> dict:
        """현재 할당량 사용 현황 조회.

        Returns:
            할당량 사용 현황 딕셔너리
        """
        if self._quota_manager:
            return self._quota_manager.get_usage(self.account_name)
        return {"message": "Quota management is disabled"}

    def get_cache_stats(self) -> dict:
        """캐시 통계 조회.

        Returns:
            캐시 통계 딕셔너리
        """
        if self._cache:
            return self._cache.get_stats(self.account_name)
        return {"message": "Caching is disabled"}

    def clear_cache(self) -> None:
        """이 계정의 캐시 전체 삭제."""
        if self._cache:
            self._cache.invalidate_account(self.account_name)
            logger.info(f"Cache cleared for account: {self.account_name}")


class ADCGmailClient:
    """Application Default Credentials를 사용하는 Gmail 클라이언트.

    gcloud auth application-default login으로 인증된 계정 사용.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.labels",
    ]

    def __init__(self, account_name: str = "default", timeout: int = DEFAULT_TIMEOUT):
        self.account_name = account_name
        self.timeout = timeout
        self.creds, self.project = google.auth.default(scopes=self.SCOPES)
        self._service = None

    @property
    def service(self):
        if self._service is None:
            self._service = build("gmail", "v1", credentials=self.creds)
        return self._service

    def list_messages(
        self,
        query: str = "",
        max_results: int = 20,
        label_ids: Optional[list[str]] = None,
        include_spam_trash: bool = False,
    ) -> list[dict]:
        messages = []
        page_token = None

        while len(messages) < max_results:
            kwargs = {
                "userId": "me",
                "maxResults": min(max_results - len(messages), 500),  # Gmail list 최대 500
                "includeSpamTrash": include_spam_trash,
            }
            if query:
                kwargs["q"] = query
            if label_ids:
                kwargs["labelIds"] = label_ids
            if page_token:
                kwargs["pageToken"] = page_token

            result = self.service.users().messages().list(**kwargs).execute()

            for msg in result.get("messages", []):
                messages.append(msg)

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return messages[:max_results]  # 서버 초과 반환 대비 상한 강제

    def get_profile(self) -> dict:
        result = self.service.users().getProfile(userId="me").execute()
        return {
            "email": result["emailAddress"],
            "messages_total": result.get("messagesTotal", 0),
            "threads_total": result.get("threadsTotal", 0),
        }


def get_all_accounts(base_path: Optional[Path] = None) -> list[str]:
    """등록된 모든 계정 이름 반환."""
    base_path = base_path or Path(__file__).parent.parent
    accounts_dir = base_path / "accounts"

    if not accounts_dir.exists():
        return []

    return [
        f.stem for f in accounts_dir.glob("*.json") if f.stem not in ("credentials",)
    ]


def get_client(
    account_name: Optional[str] = None,
    use_adc: bool = False,
    base_path: Optional[Path] = None,
) -> GmailClient:
    """Gmail 클라이언트 팩토리.

    Args:
        account_name: 계정 이름 (None이면 첫 번째 계정 사용)
        use_adc: ADC 사용 여부
        base_path: skill 루트 경로

    Returns:
        GmailClient 또는 ADCGmailClient 인스턴스
    """
    if use_adc:
        return ADCGmailClient(account_name or "default")

    if account_name:
        return GmailClient(account_name, base_path)

    accounts = get_all_accounts(base_path)
    if not accounts:
        raise ValueError(
            "등록된 계정이 없습니다. setup_auth.py --account <이름> 실행 필요"
        )

    return GmailClient(accounts[0], base_path)
