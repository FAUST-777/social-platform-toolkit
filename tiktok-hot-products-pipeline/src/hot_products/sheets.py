from __future__ import annotations

from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from hot_products.models import SHEET_HEADERS, ProductSignal


class GoogleSheetsWriter:
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self, service_account_file: Path, sheet_id: str, tab_name: str) -> None:
        if not sheet_id:
            raise ValueError("GOOGLE_SHEET_ID is required")
        self.sheet_id = sheet_id
        self.tab_name = tab_name
        credentials = Credentials.from_service_account_file(service_account_file, scopes=self.scopes)
        self.service = build("sheets", "v4", credentials=credentials)

    def ensure_header(self) -> None:
        range_name = f"{self.tab_name}!A1:K1"
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            range=range_name,
        ).execute()
        values = result.get("values", [])
        if values and values[0] == SHEET_HEADERS:
            return
        self.service.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=range_name,
            valueInputOption="RAW",
            body={"values": [SHEET_HEADERS]},
        ).execute()

    def append(self, signals: list[ProductSignal]) -> None:
        if not signals:
            return
        self.ensure_header()
        self.service.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range=f"{self.tab_name}!A:K",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [signal.to_sheet_row() for signal in signals]},
        ).execute()
