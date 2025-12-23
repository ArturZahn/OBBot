from __future__ import annotations

from datetime import datetime


def iso_datetime_to_dmy(iso_dt: str) -> str:
    dt = datetime.strptime(iso_dt, "%Y-%m-%d %H:%M")
    return dt.strftime("%d/%m/%Y")
