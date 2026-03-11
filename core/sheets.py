import os
import json
import logging
import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def get_google_client():
    """
    Authenticate via OAuth2 User credentials (tài khoản cá nhân).
    Cần 2 env vars:
      - GOOGLE_CREDENTIALS: nội dung credentials.json (OAuth Client ID/Secret)
      - GOOGLE_TOKEN: nội dung token.json (access + refresh token)
    Hoặc file trên disk: credentials.json + token.json
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    try:
        creds = None

        # 1) Load token từ env var hoặc file
        token_json = os.environ.get("GOOGLE_TOKEN")
        if token_json:
            token_data = json.loads(token_json.strip())
            creds = Credentials.from_authorized_user_info(token_data, scopes)
        elif os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", scopes)

        # 2) Refresh nếu expired
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Lưu lại token mới vào file (local dev)
            if os.path.exists("token.json"):
                with open("token.json", "w") as f:
                    f.write(creds.to_json())

        if not creds or not creds.valid:
            logging.error("Google OAuth token không hợp lệ hoặc chưa có. Chạy auth_setup.py để tạo token.")
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
