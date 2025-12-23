from __future__ import annotations

import gspread
from oauth2client.service_account import ServiceAccountCredentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


class SheetsClient:
    def __init__(self, spreadsheet_id: str, credentials_file: str):
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            credentials_file, SCOPES
        )
        self._gc = gspread.authorize(creds)
        self._sh = self._gc.open_by_key(spreadsheet_id)

    def worksheet(self, name: str):
        return self._sh.worksheet(name)
