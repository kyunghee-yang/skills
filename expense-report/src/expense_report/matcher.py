from dataclasses import dataclass
import json

from expense_report.parser import Transaction


@dataclass
class NotionEntry:
    date: str
    amount: float
    companions: list[str]


def _normalize_date(date_str: str) -> str:
    return date_str.replace(".", "-")


def _to_amount_int(value):
    """금액을 정수로 정규화. Notion 금액이 정수/실수/쉼표포함 문자열로 올 수 있다.

    파싱 불가하면 None(해당 엔트리는 매칭 키를 만들 수 없으므로 건너뜀). 과거에는 여기서
    int("27,200")가 ValueError 로 매칭 전체를 죽였다.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(float(str(value).replace(",", "").replace("원", "").strip()))
    except (ValueError, TypeError):
        return None


def match_transactions(
    transactions: list[Transaction],
    notion_entries: list[NotionEntry],
) -> dict[int, NotionEntry]:
    notion_lookup: dict[tuple[str, int], NotionEntry] = {}
    for entry in notion_entries:
        amount = _to_amount_int(entry.amount)
        if amount is None:
            continue  # 금액 파싱 불가 엔트리는 매칭 대상에서 제외
        key = (_normalize_date(entry.date), amount)
        notion_lookup[key] = entry

    matches: dict[int, NotionEntry] = {}
    used_keys: set[tuple[str, int]] = set()
    for idx, txn in enumerate(transactions):
        key = (_normalize_date(txn.date), txn.amount)
        if key in notion_lookup and key not in used_keys:
            matches[idx] = notion_lookup[key]
            used_keys.add(key)
    return matches


def parse_notion_json(raw_results: list[dict], user_map: dict[str, str]) -> list[NotionEntry]:
    entries = []
    for record in raw_results:
        usage = record.get("사용내역", "")
        if usage != "커피":
            continue
        date = record.get("date:사용일:start", "")
        amount = record.get("금액", 0)
        if not date or not amount:
            continue
        # Notion 은 빈 people/relation 필드를 null 로 반환할 수 있고, 문자열이 비어
        # 있을 수도 있다. None/빈/비정상 입력을 빈 리스트로 흡수해 파싱이 죽지 않게 한다.
        companion_raw = record.get("동반자") or "[]"
        if isinstance(companion_raw, str):
            try:
                companion_ids = json.loads(companion_raw)
            except (json.JSONDecodeError, TypeError):
                companion_ids = []
        elif isinstance(companion_raw, list):
            companion_ids = companion_raw
        else:
            companion_ids = []
        companions = [user_map.get(uid, uid) for uid in companion_ids]
        entries.append(NotionEntry(date=date, amount=amount, companions=companions))
    return entries
