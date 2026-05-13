from __future__ import annotations

import json
from collections.abc import Iterable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from hot_products.models import ProductSignal
from hot_products.scoring import sold_count_to_score
from hot_products.sources.base import ProductSource


class TikTokShopSearchSource(ProductSource):
    def __init__(self, urls: list[str], timeout_seconds: int) -> None:
        self.urls = urls
        self.timeout_seconds = timeout_seconds

    def collect(self) -> Iterable[ProductSignal]:
        for url in self.urls:
            html = self._fetch(url)
            yield from self._parse(url, html)

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
    def _fetch(self, url: str) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        }
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def _parse(self, source_url: str, html: str) -> Iterable[ProductSignal]:
        soup = BeautifulSoup(html, "html.parser")

        yield from self._parse_json_ld(source_url, soup)

        # Best-effort fallback for public pages. TikTok frequently changes markup.
        for card in soup.select("[data-e2e*='product'], a[href*='/shop/pdp/']")[:50]:
            text = " ".join(card.get_text(" ", strip=True).split())
            href = card.get("href") if card.name == "a" else None
            link = urljoin(source_url, href) if href else source_url
            if len(text) < 8:
                continue
            sold_count = self._extract_sold_count(text)
            yield ProductSignal(
                platform="tiktok",
                market=self._market_from_url(source_url),
                product_name=text[:180],
                product_url=link,
                sold_count=sold_count,
                engagement_score=sold_count_to_score(sold_count),
                source_url=source_url,
                raw_signal=text[:500],
            )

    def _parse_json_ld(self, source_url: str, soup: BeautifulSoup) -> Iterable[ProductSignal]:
        for script in soup.select("script[type='application/ld+json']"):
            raw = script.string or ""
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") not in {"Product", "ItemList"}:
                    continue
                yield from self._json_ld_item_to_signal(source_url, item)

    def _json_ld_item_to_signal(self, source_url: str, item: dict) -> Iterable[ProductSignal]:
        if item.get("@type") == "Product":
            offer = item.get("offers") or {}
            yield ProductSignal(
                platform="tiktok",
                market=self._market_from_url(source_url),
                product_name=str(item.get("name") or "").strip(),
                product_url=str(item.get("url") or source_url),
                price=str(offer.get("price") or ""),
                currency=str(offer.get("priceCurrency") or ""),
                source_url=source_url,
                raw_signal=json.dumps(item, ensure_ascii=False)[:500],
            )
            return

        for element in item.get("itemListElement") or []:
            product = element.get("item") if isinstance(element, dict) else None
            if isinstance(product, dict):
                yield from self._json_ld_item_to_signal(source_url, product)

    def _extract_sold_count(self, text: str) -> str:
        lowered = text.lower()
        markers = ["sold", "已售", "售出"]
        for marker in markers:
            index = lowered.find(marker)
            if index == -1:
                continue
            start = max(0, index - 16)
            end = min(len(text), index + 16)
            return text[start:end].strip()
        return ""

    def _market_from_url(self, url: str) -> str:
        if "/us/" in url:
            return "US"
        if "/tw/" in url:
            return "TW"
        return ""
