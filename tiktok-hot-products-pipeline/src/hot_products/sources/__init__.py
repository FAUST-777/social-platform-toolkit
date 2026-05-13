from __future__ import annotations

from hot_products.settings import Settings
from hot_products.sources.base import ProductSource
from hot_products.sources.custom_json import CustomJsonSource
from hot_products.sources.tiktok_profile import TikTokProfileSource
from hot_products.sources.tiktok_shop import TikTokShopSearchSource


def build_sources(config: dict, settings: Settings) -> list[ProductSource]:
    source_config = config.get("sources", {})
    sources: list[ProductSource] = []

    tiktok_config = source_config.get("tiktok_shop_search", {})
    if tiktok_config.get("enabled", False):
        sources.append(
            TikTokShopSearchSource(
                urls=list(tiktok_config.get("urls") or []),
                timeout_seconds=settings.request_timeout_seconds,
            )
        )

    profile_config = source_config.get("tiktok_profile", {})
    if profile_config.get("enabled", False):
        sources.append(
            TikTokProfileSource(
                usernames=list(profile_config.get("usernames") or []),
                max_videos=int(profile_config.get("max_videos") or 20),
                timeout_ms=settings.request_timeout_seconds * 1000,
            )
        )

    custom_config = source_config.get("custom_json", {})
    if custom_config.get("enabled", False):
        sources.append(
            CustomJsonSource(
                endpoint=settings.custom_json_endpoint,
                auth_header=settings.custom_json_auth_header,
                platform=str(custom_config.get("platform") or "vendor"),
                timeout_seconds=settings.request_timeout_seconds,
            )
        )

    return sources
