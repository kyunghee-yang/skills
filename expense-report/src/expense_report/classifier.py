from __future__ import annotations
from dataclasses import dataclass, field
from expense_report.config import (
    CAFE_KEYWORDS, CONFIRM_TAG, DINNER_CAP, DINNER_HOURS,
    DOUBLE_MULTIPLIER, DRAFTER_NAME, LUNCH_CAP, LUNCH_HOURS,
    PG_KEYWORDS, TAXI_HOME_ROUTE,
)
from expense_report.matcher import NotionEntry
from expense_report.parser import Transaction


@dataclass
class Classification:
    usage: str = ""
    expense_amount: int = 0
    account: str = ""
    companion: str = ""
    route: str = ""
    is_manual: bool = False
    rule_number: int = 8
    manual_fields: list[str] = field(default_factory=list)


def _to_minutes(time_str: str) -> int:
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _is_in_range(time_str: str, minute_range: tuple) -> bool:
    minutes = _to_minutes(time_str)
    return minute_range[0] <= minutes < minute_range[1]


def _is_cafe(merchant: str) -> bool:
    upper = merchant.upper()
    return any(kw.upper() in upper for kw in CAFE_KEYWORDS)


def _is_pg(merchant: str) -> bool:
    return any(kw in merchant for kw in PG_KEYWORDS)


def classify(txn: Transaction, notion_match: NotionEntry | None = None) -> Classification:
    # Rule 1: Notion 팀활동비 매칭
    if notion_match is not None:
        return Classification(
            usage="팀 커피", expense_amount=txn.amount,
            account="복리후생비[회식비]",
            companion=",".join(notion_match.companions),
            rule_number=1,
        )
    merchant = txn.merchant
    # Rule 2: 카카오T택시_가승인
    if merchant == "카카오T택시_가승인":
        return Classification(
            usage="택시 카드 선승인 취소 건", expense_amount=0,
            account="여비교통비[택시]", companion=DRAFTER_NAME, rule_number=2,
        )
    # Rule 3: 카카오T일반택시(법인)
    if merchant.startswith("카카오T일반택시(법인)"):
        return Classification(
            usage="야근 택시비(배포)", expense_amount=txn.amount,
            account="여비교통비[택시]", companion=DRAFTER_NAME,
            route=TAXI_HOME_ROUTE, rule_number=3,
        )
    # Rule 4: 일반 택시 ("택시" 포함)
    if "택시" in merchant:
        return Classification(
            usage="야근 택시비(배포)", expense_amount=txn.amount,
            account="여비교통비[택시]", companion=DRAFTER_NAME,
            route=TAXI_HOME_ROUTE, rule_number=4,
        )
    # Rule 5: 카페 감지 (Notion 미매칭) → "팀 커피(확인필요)"
    if _is_cafe(merchant):
        return Classification(
            usage=f"팀 커피({CONFIRM_TAG})",
            expense_amount=txn.amount,
            account="복리후생비[회식비]",
            companion=DRAFTER_NAME,
            rule_number=5,
        )
    # Rule 6: 점심 식대 (11:00~14:00)
    if _is_in_range(txn.time, LUNCH_HOURS):
        companion = DRAFTER_NAME
        usage = "점심 식대"
        if _is_pg(merchant):
            usage = f"점심 식대({CONFIRM_TAG})"
        if txn.amount >= LUNCH_CAP * DOUBLE_MULTIPLIER:
            companion = f"{DRAFTER_NAME},{CONFIRM_TAG}"
        return Classification(
            usage=usage, expense_amount=min(txn.amount, LUNCH_CAP),
            account="복리후생비[식비]", companion=companion, rule_number=6,
        )
    # Rule 7: 저녁 식대 (17:00~20:30)
    if _is_in_range(txn.time, DINNER_HOURS):
        companion = DRAFTER_NAME
        usage = "저녁 식대"
        if _is_pg(merchant):
            usage = f"저녁 식대({CONFIRM_TAG})"
        if txn.amount >= DINNER_CAP * DOUBLE_MULTIPLIER:
            companion = f"{DRAFTER_NAME},{CONFIRM_TAG}"
        return Classification(
            usage=usage, expense_amount=min(txn.amount, DINNER_CAP),
            account="복리후생비[식비]", companion=companion, rule_number=7,
        )
    # Rule 8: 수기
    return Classification(
        is_manual=True, rule_number=8,
        manual_fields=["usage", "expense_amount", "account", "companion"],
    )
