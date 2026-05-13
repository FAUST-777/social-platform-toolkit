from __future__ import annotations

from datetime import datetime, timezone

from hot_products.models import ProductSignal
from hot_products.settings import Settings
from hot_products.sheets import GoogleSheetsWriter
from hot_products.sources import build_sources


def collect_signals(config: dict, settings: Settings) -> list[ProductSignal]:
    collected_at = datetime.now(timezone.utc)
    signals: list[ProductSignal] = []

    for source in build_sources(config, settings):
        for signal in source.collect():
            if not signal.product_name:
                continue
            signal.collected_at = collected_at
            signals.append(signal)

    return dedupe(signals)


def dedupe(signals: list[ProductSignal]) -> list[ProductSignal]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[ProductSignal] = []
    for signal in signals:
        key = (
            signal.platform.lower(),
            signal.product_url.lower(),
            signal.product_name.lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(signal)
    return unique


def write_signals(settings: Settings, signals: list[ProductSignal]) -> None:
    writer = GoogleSheetsWriter(
        service_account_file=settings.google_service_account_file,
        sheet_id=settings.google_sheet_id,
        tab_name=settings.google_sheet_tab,
    )
    writer.append(signals)
