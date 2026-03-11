"""
Script chạy 1 lần trên máy local để tạo token.json.
Sau khi có token.json, copy nội dung vào env var GOOGLE_TOKEN trên Render.

Cách dùng:
    python auth_setup.py
"""
import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def main():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                print("❌ Không tìm thấy credentials.json!")
                print("👉 Tải từ Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs → Download JSON")
                return

            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as f:
            f.write(creds.to_json())

    print("✅ token.json đã sẵn sàng!")
    print()
    print("📋 Copy nội dung bên dưới vào env var GOOGLE_TOKEN trên Render:")
    print("─" * 60)
    with open("token.json") as f:
        print(f.read())
    print("─" * 60)

if __name__ == "__main__":
    main()
