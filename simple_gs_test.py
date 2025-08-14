# pip install --upgrade gspread google-auth requests

import requests
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",  # read/write Sheets
    "https://www.googleapis.com/auth/drive.file",    # create new files
]

SPREADSHEET_ID = "1AM29wtnBMGiSrxmCxaQ-DQIKUmWNENG-mUrIuYqBzWo"
CREDENTIALS_FILE = "data/google_sheet_key.json"


class TimeoutSession(AuthorizedSession):
    """AuthorizedSession that enforces a default timeout on all HTTP requests."""
    def __init__(self, credentials, timeout=15):
        super().__init__(credentials)
        self._timeout = timeout

    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", self._timeout)
        return super().request(method, url, **kwargs)


# Build creds + session with timeout and hand it to gspread
creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
session = TimeoutSession(creds, timeout=15)   # <- no more infinite hangs
gc = gspread.Client(auth=creds, session=session)

print("1")

# Quick connectivity check (optional)
try:
    r = requests.get("https://www.googleapis.com/discovery/v1/apis", timeout=5)
    r.raise_for_status()
    print("Connectivity OK")
except Exception as e:
    print("Connectivity check failed:", e)
    raise

print("2")

# This will now respect the timeout in the session
sh = gc.open_by_key(SPREADSHEET_ID)
print("3")

ws_config = sh.worksheet("Configurações")
ws_deposit = sh.worksheet("Inserir Depósito")
ws_tracking = sh.worksheet("Acompanhamento")

print("Worksheets loaded.")
