from __future__ import annotations

import json
import re
from collections.abc import Iterable

from hot_products.models import ProductSignal
from hot_products.sources.base import ProductSource

try:
    from playwright.sync_api import sync_playwright

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False


class TikTokProfileSource(ProductSource):
    """
    爬取公開 TikTok 頻道頁面的最新影片清單。
    不需登入，只能看公開數據（觀看數等）。

    需要安裝 Playwright：
      pip install playwright
      playwright install chromium
    """

    def __init__(self, usernames: list[str], max_videos: int, timeout_ms: int) -> None:
        self.usernames = usernames
        self.max_videos = max_videos
        self.timeout_ms = timeout_ms

    def collect(self) -> Iterable[ProductSignal]:
        if not _PLAYWRIGHT_AVAILABLE:
            print(
                "[TikTokProfileSource] Playwright 未安裝，跳過。\n"
                "  安裝方法：pip install playwright && playwright install chromium"
            )
            return []

        signals: list[ProductSignal] = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                locale="zh-TW",
            )
            for username in self.usernames:
                try:
                    signals.extend(self._scrape_profile(context, username))
                except Exception as exc:
                    print(f"[TikTokProfileSource] @{username} 失敗: {exc}")
            browser.close()
        return signals

    def _scrape_profile(self, context, username: str) -> list[ProductSignal]:
        url = f"https://www.tiktok.com/@{username}"
        page = context.new_page()
        signals: list[ProductSignal] = []

        try:
            page.goto(url, timeout=self.timeout_ms, wait_until="networkidle")
            page.wait_for_selector('[data-e2e="user-post-item"]', timeout=15_000)

            items = page.query_selector_all('[data-e2e="user-post-item"]')
            for item in items[: self.max_videos]:
                signal = self._extract_signal(item, username, url)
                if signal:
                    signals.append(signal)
        except Exception as exc:
            print(f"[TikTokProfileSource] 頁面載入失敗 (@{username}): {exc}")
        finally:
            page.close()

        return signals

    def _extract_signal(self, item, username: str, profile_url: str) -> ProductSignal | None:
        try:
            link_el = item.query_selector("a")
            video_url = link_el.get_attribute("href") if link_el else ""
            if video_url and not video_url.startswith("http"):
                video_url = f"https://www.tiktok.com{video_url}"

            # 觀看數通常在 strong[data-e2e="video-views"] 或 span
            views_el = item.query_selector('[data-e2e="video-views"], strong')
            views_text = views_el.inner_text().strip() if views_el else ""

            # 影片標題從 img alt 或 aria-label
            title_el = item.query_selector("img")
            title = ""
            if title_el:
                title = title_el.get_attribute("alt") or ""

            if not title and link_el:
                title = link_el.get_attribute("aria-label") or ""

            if not title and not video_url:
                return None

            return ProductSignal(
                platform="tiktok",
                market="TW",
                product_name=title[:180] or f"@{username} 影片",
                product_url=video_url or profile_url,
                sold_count="",
                engagement_score=_parse_view_count(views_text),
                source_url=profile_url,
                raw_signal=json.dumps(
                    {"username": username, "views": views_text, "title": title},
                    ensure_ascii=False,
                )[:500],
            )
        except Exception:
            return None


def _parse_view_count(text: str) -> float:
    if not text:
        return 0.0
    normalized = text.lower().replace(",", "").strip()
    multiplier = 1
    if "k" in normalized or "千" in normalized:
        multiplier = 1_000
    elif "m" in normalized or "萬" in normalized:
        multiplier = 10_000
    elif "b" in normalized or "億" in normalized:
        multiplier = 100_000_000
    match = re.search(r"(\d+(?:\.\d+)?)", normalized)
    if not match:
        return 0.0
    return float(match.group(1)) * multiplier
