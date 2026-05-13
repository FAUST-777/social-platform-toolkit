from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class ProductSignal:
    platform: str
    product_name: str
    product_url: str = ""
    market: str = ""
    price: str = ""
    currency: str = ""
    sold_count: str = ""
    engagement_score: float = 0.0
    source_url: str = ""
    raw_signal: str = ""
    collected_at: datetime | None = None

    def to_sheet_row(self) -> list[str | float]:
        collected_at = self.collected_at or datetime.now(timezone.utc)
        return [
            collected_at.isoformat(timespec="seconds"),
            self.platform,
            self.market,
            self.product_name,
            self.product_url,
            self.price,
            self.currency,
            self.sold_count,
            self.engagement_score,
            self.source_url,
            self.raw_signal,
        ]


SHEET_HEADERS = [
    "collected_at",
    "platform",
    "market",
    "product_name",
    "product_url",
    "price",
    "currency",
    "sold_count",
    "engagement_score",
    "source_url",
    "raw_signal",
]
