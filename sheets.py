import os
import json
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_google_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    json_creds = os.environ.get("GOOGLE_CREDENTIALS")
    try:
        if json_creds:
            creds_dict = json.loads(json_creds.strip())
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        elif os.path.exists("cred.json"):
            creds = ServiceAccountCredentials.from_json_keyfile_name("cred.json", scope)
        else:
            return None
        return gspread.authorize(creds)
    except Exception as e:
        logging.error(f"Lỗi Auth: {e}")
        return None

def ensure_sheet_total(ws):
    if not (ws.acell("F1").value or "").strip():
        ws.update_acell("F1", "TỔNG QUỸ:")

    g1_formula = ws.acell("G1", value_render_option="FORMULA").value
    if not g1_formula or not str(g1_formula).startswith("="):
        ws.update_acell("G1", "=SUM(C:C)")

def ensure_sheet_format(ws):
    if (ws.acell("A1").value or "").strip().lower() != "ngày":
        ws.update("A1:D1", [["Ngày", "Món", "Tiền", "Ghi chú"]])
    ensure_sheet_total(ws)
    if (ws.acell("H1").value or "").strip() != "BANK:":
        ws.update("H1:H3", [["BANK:"], ["STK:"], ["NAME:"]])

def format_vnd(x) -> str:
    """
    Nhận: int/float/None/str kiểu '92000', '92,000', '92.000 đ'...
    Trả: '92,000 đ'
    """
    if x is None:
        return "0 đ"

    # Nếu là số (int/float) → xử lý trực tiếp
    if isinstance(x, (int, float)):
        return f"{int(x):,} đ"

    s = str(x).strip()

    # Thử parse thẳng thành số (xử lý cả "10000.0", "92000")
    try:
        return f"{int(float(s)):,} đ"
    except (ValueError, OverflowError):
        pass

    # Fallback: lấy toàn bộ chữ số (bỏ dấu , . và chữ đ)
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return "0 đ"

    n = int(digits)
    return f"{n:,} đ"