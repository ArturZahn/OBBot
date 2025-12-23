from __future__ import annotations

from datetime import datetime

from app.processing.name_utils import encode_name
from app.sheets.client import SheetsClient


class SheetsService:
    def __init__(self, client: SheetsClient):
        self._client = client
        self._ws_config = self._client.worksheet("Configurações")
        self._ws_deposit = self._client.worksheet("Inserir Depósito")
        self._ws_spent = self._client.worksheet("Gastos")

    @staticmethod
    def _next_row(worksheet) -> int:
        values = worksheet.col_values(1)
        return len(values) + 1

    @staticmethod
    def _normalize_date(value: str) -> str | None:
        value = value.strip()
        if not value:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_amount(value) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return round(float(value), 2)
        text = str(value).strip()
        if not text:
            return None
        text = text.replace("R$", "").strip()
        text = text.replace(".", "").replace(",", ".")
        try:
            return round(float(text), 2)
        except ValueError:
            return None

    def _find_deposit_row(
        self, nickname: str, date_dmy: str, amount: float
    ) -> tuple[int, str] | None:
        values = self._ws_deposit.get_all_values()
        if not values:
            return None
        header = values[0]
        try:
            idx_name = header.index("Quem?")
            idx_date = header.index("Data")
            idx_amount = header.index("Valor")
            idx_status = header.index("Status")
        except ValueError:
            return None

        target_date = self._normalize_date(date_dmy)
        target_amount = round(float(amount), 2)

        for i, row in enumerate(values[1:], start=2):
            if len(row) <= max(idx_name, idx_date, idx_amount, idx_status):
                continue
            row_name = row[idx_name].strip()
            row_date = self._normalize_date(row[idx_date])
            row_amount = self._parse_amount(row[idx_amount])
            if (
                row_name == nickname
                and row_date == target_date
                and row_amount is not None
                and row_amount == target_amount
            ):
                return i, row[idx_status].strip()
        return None

    def get_payment_names(self) -> dict[str, str]:
        nicknames = self._ws_config.col_values(1)[1:]
        payment_names_list = self._ws_config.get(f"B2:B{len(nicknames)+1}")

        names_to_nicknames: dict[str, str] = {}
        for i in range(len(nicknames)):
            if len(payment_names_list[i]) == 0 or len(nicknames[i]) == 0:
                continue
            names = payment_names_list[i][0].split(",")
            for name in names:
                names_to_nicknames[encode_name(name)] = nicknames[i]
        return names_to_nicknames

    def get_categories(self) -> list[str]:
        column_names = self._ws_config.row_values(1)
        if "Categorias" not in column_names:
            return []
        column_index = column_names.index("Categorias") + 1
        return self._ws_config.col_values(column_index)[1:]

    def insert_deposit(self, nickname: str, date_dmy: str, amount: float) -> None:
        existing = self._find_deposit_row(nickname, date_dmy, amount)
        if existing:
            row, status = existing
            if status == "":
                self._ws_deposit.update(
                    f"E{row}",
                    [["botOK"]],
                    value_input_option="USER_ENTERED",
                )
            return
        row = self._next_row(self._ws_deposit)
        self._ws_deposit.update(
            f"A{row}:F{row}",
            [[
                nickname,
                date_dmy,
                amount,
                "Depósito na conta da casa",
                "bot",
                "Depósito",
            ]],
            value_input_option="USER_ENTERED",
        )

    def insert_spent(
        self, date_dmy: str, amount: float, description: str, category: str
    ) -> None:
        row = self._next_row(self._ws_spent)
        self._ws_spent.update(
            f"A{row}:G{row}",
            [[
                date_dmy,
                amount,
                description,
                "Cartão da casa",
                "",
                "bot",
                category,
            ]],
            value_input_option="USER_ENTERED",
        )
