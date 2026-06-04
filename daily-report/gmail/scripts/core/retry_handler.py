"""Exponential Backoff Retry Handler.

Gmail API 오류 처리를 위한 지수 백오프 재시도 로직.

Retry-able Errors:
- 429: Rate Limit Exceeded (Too Many Requests)
- 500: Internal Server Error
- 502: Bad Gateway
- 503: Service Unavailable
- 504: Gateway Timeout

Non-retry-able Errors:
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found

Reference:
    https://developers.google.com/workspace/gmail/api/guides/handle-errors
"""

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Callable, Optional, TypeVar, Any

from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 재시도 가능한 HTTP 상태 코드
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass
class RetryConfig:
    """재시도 설정."""

    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


def calculate_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> float:
    """지수 백오프 지연 시간 계산.

    Args:
        attempt: 현재 시도 횟수 (0부터 시작)
        base_delay: 기본 지연 시간 (초)
        max_delay: 최대 지연 시간 (초)
        exponential_base: 지수 배수
        jitter: 무작위 지터 추가 여부

    Returns:
        계산된 지연 시간 (초)
    """
    delay = base_delay * (exponential_base**attempt)

    if jitter:
        # 0.5 ~ 1.5 범위의 지터 추가
        delay *= 0.5 + random.random()

    # max_delay 는 상한 계약이므로 지터까지 반영한 최종 값을 캡한다.
    # (과거에는 캡을 지터 이전에 적용해 결과가 max_delay 를 최대 1.5배 초과했다.)
    return min(delay, max_delay)


def retry_after_seconds(error: Exception) -> Optional[float]:
    """오류 응답의 Retry-After 헤더(초)를 반환한다. 없거나 파싱 불가면 None.

    Google API 는 429/503 에서 Retry-After 를 줄 수 있고, 모범사례는 지수 백오프보다 이
    값을 우선 존중하는 것이다(서버가 알려준 회복 시점). 정수 초만 해석하고, HTTP-date 형식이나
    음수/비정상은 무시한다.
    """
    resp = getattr(error, "resp", None)
    if resp is None:
        return None
    # httplib2 Response 는 헤더 키가 소문자인 dict 류
    try:
        value = resp.get("retry-after")
    except AttributeError:
        value = None
    if value is None:
        return None
    # 형식 1: delay-seconds (정수 초)
    try:
        secs = float(value)
        return secs if secs >= 0 else None
    except (ValueError, TypeError):
        pass
    # 형식 2: HTTP-date (RFC 7231) → 지금부터 그 시점까지의 초
    try:
        from email.utils import parsedate_to_datetime

        when = parsedate_to_datetime(str(value))
        if when is None:
            return None
        now = datetime.now(when.tzinfo) if when.tzinfo else datetime.now()
        delta = (when - now).total_seconds()
        return delta if delta >= 0 else 0.0
    except (TypeError, ValueError):
        return None


def is_retryable_error(error: Exception) -> bool:
    """재시도 가능한 오류인지 확인.

    Args:
        error: 발생한 예외

    Returns:
        재시도 가능하면 True
    """
    if isinstance(error, HttpError):
        return error.resp.status in RETRYABLE_STATUS_CODES
    return False


def exponential_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> Callable:
    """지수 백오프 데코레이터.

    Gmail API 호출 시 rate limiting 및 일시적 오류를
    자동으로 처리합니다.

    Args:
        max_retries: 최대 재시도 횟수
        base_delay: 기본 지연 시간 (초)
        max_delay: 최대 지연 시간 (초)
        exponential_base: 지수 배수
        jitter: 무작위 지터 추가 여부
        on_retry: 재시도 시 호출될 콜백 (attempt, error, delay)

    Returns:
        데코레이터 함수

    Usage:
        @exponential_backoff(max_retries=5)
        def get_message(service, message_id):
            return service.users().messages().get(
                userId='me', id=message_id
            ).execute()

        # 콜백과 함께 사용
        def log_retry(attempt, error, delay):
            print(f"Retry {attempt}: {error}, waiting {delay:.1f}s")

        @exponential_backoff(max_retries=3, on_retry=log_retry)
        def list_messages(service, query):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except HttpError as e:
                    last_exception = e

                    if not is_retryable_error(e):
                        # 재시도 불가능한 오류는 즉시 발생
                        raise

                    if attempt == max_retries:
                        # 최대 재시도 횟수 도달
                        logger.error(
                            f"최대 재시도 횟수({max_retries}) 도달. "
                            f"함수: {func.__name__}, 오류: {e}"
                        )
                        raise

                    # 서버가 Retry-After 를 줬으면 그 값을 우선 존중(상한 적용)한다.
                    ra = retry_after_seconds(e)
                    if ra is not None:
                        delay = min(ra, max_delay)
                    else:
                        delay = calculate_delay(
                            attempt,
                            base_delay,
                            max_delay,
                            exponential_base,
                            jitter,
                        )

                    if on_retry:
                        on_retry(attempt, e, delay)

                    logger.warning(
                        f"재시도 {attempt + 1}/{max_retries}: "
                        f"HTTP {e.resp.status}, {delay:.1f}초 대기"
                    )
                    time.sleep(delay)
                except Exception:
                    # HttpError가 아닌 예외는 그대로 발생
                    raise

            # 이 코드에 도달하면 안 됨
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in retry logic")

        return wrapper

    return decorator


class RetryableOperation:
    """재시도 가능한 작업을 위한 컨텍스트 매니저.

    데코레이터 대신 명시적으로 재시도 로직을 사용할 때 유용합니다.

    Usage:
        with RetryableOperation(max_retries=5) as op:
            while op.should_retry():
                try:
                    result = service.users().messages().get(
                        userId='me', id=message_id
                    ).execute()
                    op.success()
                    break
                except HttpError as e:
                    op.handle_error(e)

        # 또는 execute 사용
        def fetch_message():
            return service.users().messages().get(...).execute()

        result = RetryableOperation(max_retries=5).execute(fetch_message)
    """

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.config = RetryConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
        )
        self.attempt = 0
        self.succeeded = False
        self.last_error: Optional[Exception] = None

    def __enter__(self) -> "RetryableOperation":
        self.attempt = 0
        self.succeeded = False
        self.last_error = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def should_retry(self) -> bool:
        """재시도 해야 하는지 확인."""
        return not self.succeeded and self.attempt <= self.config.max_retries

    def success(self) -> None:
        """작업 성공 표시."""
        self.succeeded = True

    def handle_error(self, error: Exception) -> None:
        """오류 처리 및 대기.

        Args:
            error: 발생한 예외

        Raises:
            Exception: 재시도 불가능하거나 최대 횟수 도달 시
        """
        self.last_error = error

        if not is_retryable_error(error):
            raise error

        if self.attempt >= self.config.max_retries:
            raise error

        ra = retry_after_seconds(error)
        if ra is not None:
            delay = min(ra, self.config.max_delay)
        else:
            delay = calculate_delay(
                self.attempt,
                self.config.base_delay,
                self.config.max_delay,
                self.config.exponential_base,
                self.config.jitter,
            )

        logger.warning(
            f"재시도 {self.attempt + 1}/{self.config.max_retries}: "
            f"{type(error).__name__}, {delay:.1f}초 대기"
        )

        time.sleep(delay)
        self.attempt += 1

    def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """함수를 재시도 로직과 함께 실행.

        Args:
            func: 실행할 함수
            *args: 함수 인자
            **kwargs: 함수 키워드 인자

        Returns:
            함수 실행 결과

        Raises:
            Exception: 최대 재시도 후에도 실패 시
        """
        with self as op:
            while op.should_retry():
                try:
                    result = func(*args, **kwargs)
                    op.success()
                    return result
                except Exception as e:
                    op.handle_error(e)

        # 이 코드에 도달하면 안 됨
        if self.last_error:
            raise self.last_error
        raise RuntimeError("Unexpected state in retry operation")


def retry_api_call(
    func: Callable[..., T],
    *args,
    max_retries: int = 5,
    **kwargs,
) -> T:
    """단순 재시도 헬퍼 함수.

    데코레이터나 컨텍스트 매니저 없이 간단히 사용할 수 있습니다.

    Args:
        func: 실행할 함수
        *args: 함수 인자
        max_retries: 최대 재시도 횟수
        **kwargs: 함수 키워드 인자

    Returns:
        함수 실행 결과

    Usage:
        result = retry_api_call(
            service.users().messages().get,
            userId='me',
            id=message_id,
            max_retries=3
        )
    """
    return RetryableOperation(max_retries=max_retries).execute(
        func, *args, **kwargs
    )


if __name__ == "__main__":
    # 테스트

    # 성공 케이스
    @exponential_backoff(max_retries=3)
    def always_succeeds():
        return "success"

    print(f"Success test: {always_succeeds()}")

    # 재시도 후 성공 케이스 시뮬레이션
    call_count = 0

    @exponential_backoff(max_retries=3, base_delay=0.1)
    def succeed_on_third_try():
        global call_count
        call_count += 1
        if call_count < 3:
            # 임시 오류 시뮬레이션
            from unittest.mock import MagicMock

            error = HttpError(MagicMock(status=429), b"Rate limited")
            raise error
        return f"success on try {call_count}"

    try:
        call_count = 0
        result = succeed_on_third_try()
        print(f"Retry test: {result}")
    except HttpError as e:
        print(f"Retry test failed: {e}")

    # RetryableOperation 테스트
    print("\nRetryableOperation test:")
    op = RetryableOperation(max_retries=3, base_delay=0.1)
    result = op.execute(lambda: "direct execute")
    print(f"Direct execute: {result}")
