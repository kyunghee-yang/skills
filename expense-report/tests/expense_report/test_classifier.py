from expense_report.classifier import classify, Classification
from expense_report.matcher import NotionEntry
from expense_report.parser import Transaction


def _txn(merchant, time, amount):
    return Transaction(
        date="2026.03.27", time=time, merchant=merchant,
        card_number="4201-****-****-7592", usage_type="국내일반",
        amount=amount, transaction_type="국내 일시불",
        approval_number="12345678", purchase_status="매입",
        purchase_date="2026-03-28", installment="-", vat="0", status="정상")


# Rule 1: Notion 매칭
def test_rule1_notion_match():
    txn = _txn("바나프레소", "13:00", 27200)
    notion = NotionEntry(date="2026-03-27", amount=27200, companions=["양경희", "김보민"])
    r = classify(txn, notion_match=notion)
    assert r.usage == "팀 커피" and r.expense_amount == 27200
    assert r.account == "복리후생비[회식비]" and r.companion == "양경희,김보민" and r.rule_number == 1


# Rule 2: 택시 가승인 취소
def test_rule2_taxi_preauth():
    r = classify(_txn("카카오T택시_가승인", "22:16", 39900))
    assert r.usage == "택시 카드 선승인 취소 건" and r.expense_amount == 0 and r.rule_number == 2


# Rule 3: 법인택시
def test_rule3_corporate_taxi():
    r = classify(_txn("카카오T일반택시(법인)_0", "23:01", 40100))
    assert r.usage == "야근 택시비(배포)" and r.expense_amount == 40100 and r.rule_number == 3
    assert r.route == "본사(강남) -> 집(김포)"


# Rule 4: 일반 택시
def test_rule4_general_taxi():
    r = classify(_txn("카카오T일반택시_0", "23:30", 15000))
    assert r.usage == "야근 택시비(배포)" and r.expense_amount == 15000
    assert r.account == "여비교통비[택시]"
    assert r.route == "본사(강남) -> 집(김포)" and r.rule_number == 4
    assert not r.is_manual


# Rule 5: 카페 (Notion 미매칭)
def test_rule5_cafe_no_notion():
    r = classify(_txn("스타벅스코리아", "16:07", 11300))
    assert r.usage == "팀 커피(확인필요)" and r.expense_amount == 11300
    assert r.account == "복리후생비[회식비]" and r.rule_number == 5


def test_rule5_cafe_lunch_hours():
    r = classify(_txn("바나프레소 강남효성점", "13:12", 2000))
    assert r.usage == "팀 커피(확인필요)" and r.rule_number == 5


def test_rule5_cafe_morning():
    r = classify(_txn("컴포즈커피(간편결제)_2_KICC", "10:12", 3600))
    assert r.usage == "팀 커피(확인필요)" and r.rule_number == 5


def test_rule5_cafe_afternoon_gap():
    r = classify(_txn("CAFE868(카페868)", "15:05", 10000))
    assert r.usage == "팀 커피(확인필요)" and r.rule_number == 5


# Rule 6: 점심 식대
def test_rule6_lunch_under_cap():
    r = classify(_txn("신복면관", "12:30", 9800))
    assert r.usage == "점심 식대" and r.expense_amount == 9800
    assert r.account == "복리후생비[식비]" and r.companion == "양경희" and r.rule_number == 6


def test_rule6_lunch_over_cap():
    assert classify(_txn("레스토랑", "12:00", 15000)).expense_amount == 10000


def test_rule6_lunch_double_cap():
    assert classify(_txn("고급식당", "12:30", 25000)).companion == "양경희,확인필요"


def test_rule6_lunch_pg_confirm():
    r = classify(_txn("네이버페이", "12:30", 9000))
    assert r.usage == "점심 식대(확인필요)" and r.rule_number == 6


# Rule 7: 저녁 식대
def test_rule7_dinner_under_cap():
    r = classify(_txn("맥도날드", "19:00", 10000))
    assert r.usage == "저녁 식대" and r.expense_amount == 10000 and r.rule_number == 7


def test_rule7_dinner_over_cap():
    assert classify(_txn("맥도날드", "20:00", 16000)).expense_amount == 12000


def test_rule7_dinner_double_cap():
    assert classify(_txn("고급식당", "18:00", 30000)).companion == "양경희,확인필요"


def test_rule7_dinner_pg_confirm():
    r = classify(_txn("네이버페이", "19:32", 11800))
    assert r.usage == "저녁 식대(확인필요)" and r.rule_number == 7


def test_rule7_dinner_cutoff_2030():
    """20:30 이후는 저녁 식대가 아닌 수기(R8)"""
    r = classify(_txn("맥도날드", "20:30", 10000))
    assert r.rule_number == 8


def test_rule7_dinner_before_cutoff():
    """20:29까지는 저녁 식대"""
    r = classify(_txn("맥도날드", "20:29", 10000))
    assert r.rule_number == 7


# Rule 8: 수기
def test_rule8_manual():
    r = classify(_txn("네이버페이", "09:00", 50000))
    assert r.is_manual and r.rule_number == 8


def test_rule8_pg_outside_meal_hours():
    r = classify(_txn("네이버페이", "20:30", 39000))
    assert r.rule_number == 8


# Edge: Notion priority
def test_notion_takes_priority_over_taxi():
    txn = _txn("카카오T택시", "22:00", 5000)
    notion = NotionEntry(date="2026-03-27", amount=5000, companions=["양경희"])
    assert classify(txn, notion_match=notion).rule_number == 1


def test_notion_takes_priority_over_cafe():
    txn = _txn("스타벅스코리아", "14:00", 15000)
    notion = NotionEntry(date="2026-03-27", amount=15000, companions=["양경희", "김보민"])
    r = classify(txn, notion_match=notion)
    assert r.rule_number == 1 and r.usage == "팀 커피"
