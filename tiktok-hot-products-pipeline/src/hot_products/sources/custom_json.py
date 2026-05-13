from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from hot_products.models import ProductSignal
from hot_products.sources.base import ProductSource


class CustomJsonSource(ProductSource):
    def __init__(
        self,
        endpoint: str,
        auth_header: str,
        platform: str,
        timeout_seconds: int,
    ) -> None:
        self.endpoint = endpoint
        self.auth_header = auth_header
        self.platform = platform
        self.timeout_seconds = timeout_seconds

    def collect(self) -> Iterable[ProductSignal]:
        if not self.endpoint:
            return []

        headers = {}
        if self.auth_header:
            name, _, value = self.auth_header.partition(":")
            if name and value:
                headers[name.strip()] = value.strip()

        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = client.get(self.endpoint)
            response.raise_for_status()
            payload = response.json()

        records = payload if isinstance(payload, list) else payload.get("items", [])
        return [self._record_to_signal(record) for record in records if isinstance(record, dict)]

    def _record_to_signal(self, record: dict[str, Any]) -> ProductSignal:
        return ProductSignal(
            platform=str(record.get("platform") or self.platform),
            market=str(record.get("market") or ""),
            product_name=str(record.get("product_name") or record.get("title") or record.get("name") or ""),
            product_url=str(record.get("product_url") or record.get("url") or ""),
            price=str(record.get("price") or ""),
            currency=str(record.get("currency") or ""),
            sold_count=str(record.get("sold_count") or record.get("sales") or ""),
            engagement_score=float(record.get("engagement_score") or record.get("score") or 0),
            source_url=str(record.get("source_url") or self.endpoint),
            raw_signal=str(record)[:500],
        )
