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


def match_transactions(
    transactions: list[Transaction],
    notion_entries: list[NotionEntry],
) -> dict[int, NotionEntry]:
    notion_lookup: dict[tuple[str, int], NotionEntry] = {}
    for entry in notion_entries:
        key = (_normalize_date(entry.date), int(entry.amount))
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
        companion_raw = record.get("동반자", "[]")
        if isinstance(companion_raw, str):
            companion_ids = json.loads(companion_raw)
        else:
            companion_ids = companion_raw
        companions = [user_map.get(uid, uid) for uid in companion_ids]
        entries.append(NotionEntry(date=date, amount=amount, companions=companions))
    return entries
