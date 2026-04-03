import json
import os

USER_CONFIG_PATH = os.path.expanduser("~/.config/expense-report/config.json")

# --- 사용자별 설정 (USER_CONFIG_PATH에서 오버라이드 가능) ---
DRAFTER_NAME = "양경희"
DEPARTMENT = "R&D본부"
CARD_LAST4 = "7592"
NOTION_USER_ID = "0f90d063-d2bb-4e09-9b39-f7bdc4883d2b"
NOTION_USER_URI = f"user://{NOTION_USER_ID}"
TAXI_HOME_ROUTE = "본사(강남) -> 집(김포)"
OUTPUT_FILENAME_TEMPLATE = "{yy}년{mm}월_법인카드_하나_양경희.xlsx"

# --- 공통 상수 (모든 사용자 동일) ---
NOTION_DB_URL = "https://www.notion.so/wefun-platform/263270b243d0800faadbffde6ba5c9b0?v=263270b243d08023b856000c03fa97a0"

LUNCH_CAP = 10000
DINNER_CAP = 12000
LUNCH_HOURS = (11 * 60, 14 * 60)          # 11:00 ~ 13:59 (분 단위)
DINNER_HOURS = (17 * 60, 20 * 60 + 30)    # 17:00 ~ 20:29 (분 단위)
DOUBLE_MULTIPLIER = 2

CAFE_KEYWORDS = (
    "스타벅스", "투썸", "바나프레소", "컴포즈", "커피", "카페",
    "CAFE", "로스터리", "이디야", "할리스", "메가커피", "빽다방",
    "커핀그루나루", "드롭탑", "파스쿠찌", "엔제리너스", "탐앤탐스",
)
PG_KEYWORDS = ("네이버페이",)

TEMPLATE_PATH = "/Users/ykh/Documents/drive/개인경비 지출결의서/양식_법인카드_하나 20250716_개정.xlsx"

RECEIPT_MAX_WIDTH_INCHES = 4.29
RECEIPT_MAX_WIDTH_EMU = int(4.29 * 914400)
RECEIPT_EXTENSIONS = {".jpg", ".jpeg", ".png"}
RECEIPT_ROW_GAP = 2

CONFIRM_TAG = "확인필요"


def _load_user_config():
    if not os.path.exists(USER_CONFIG_PATH):
        return
    with open(USER_CONFIG_PATH) as f:
        cfg = json.load(f)

    global DRAFTER_NAME, DEPARTMENT, CARD_LAST4
    global NOTION_USER_ID, NOTION_USER_URI
    global TAXI_HOME_ROUTE, OUTPUT_FILENAME_TEMPLATE

    DRAFTER_NAME = cfg.get("drafter_name", DRAFTER_NAME)
    DEPARTMENT = cfg.get("department", DEPARTMENT)
    CARD_LAST4 = cfg.get("card_last4", CARD_LAST4)
    if cfg.get("notion_user_id"):
        NOTION_USER_ID = cfg["notion_user_id"]
        NOTION_USER_URI = f"user://{NOTION_USER_ID}"
    if cfg.get("taxi_destination"):
        TAXI_HOME_ROUTE = f"본사(강남) -> 집({cfg['taxi_destination']})"
    OUTPUT_FILENAME_TEMPLATE = "{yy}년{mm}월_법인카드_하나_" + DRAFTER_NAME + ".xlsx"


_load_user_config()

XLS_DATA_START_ROW = 9
XLS_COL_DATE = 0
XLS_COL_TIME = 3
XLS_COL_MERCHANT = 6
XLS_COL_CARD_NUMBER = 7
XLS_COL_TYPE = 8
XLS_COL_AMOUNT = 9
XLS_COL_TRANSACTION_TYPE = 10
XLS_COL_APPROVAL_NUMBER = 11
XLS_COL_PURCHASE = 14
XLS_COL_PURCHASE_DATE = 15
XLS_COL_INSTALLMENT = 17
XLS_COL_VAT_OR_STATUS = 18

SHEET1_COL_DATE = 1
SHEET1_COL_TIME = 4
SHEET1_COL_MERCHANT = 7
SHEET1_COL_CARD = 8
SHEET1_COL_TYPE = 9
SHEET1_COL_AMOUNT = 10
SHEET1_COL_TXN_TYPE = 11
SHEET1_COL_APPROVAL = 12
SHEET1_COL_PURCHASE = 15
SHEET1_COL_PURCHASE_DATE = 16
SHEET1_COL_INSTALLMENT = 18
SHEET1_COL_VAT = 19
SHEET1_DATA_START_ROW = 10

SHEET2_COL_DRAFTER = 1
SHEET2_COL_DEPT = 2
SHEET2_COL_EXPENSE = 7
SHEET2_COL_PROJECT = 8
SHEET2_COL_USAGE = 10
SHEET2_COL_COMPANION = 11
SHEET2_COL_ROUTE = 12
SHEET2_COL_VEHICLE = 13
SHEET2_COL_ACCOUNT = 14
SHEET2_DATA_START_ROW = 6
