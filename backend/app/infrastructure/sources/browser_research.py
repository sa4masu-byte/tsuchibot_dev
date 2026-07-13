import asyncio
import re
import time
from contextlib import suppress
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from backend.app.application.research import MarketplaceSearchResult
from backend.app.domain.research import (
    ListingStatus,
    MarketplaceListing,
    SearchQuery,
    ShippingResponsibility,
    VisualSearchHit,
)


class BrowserBlockedError(RuntimeError):
    pass


class BrowserResearchSession:
    def __init__(
        self,
        *,
        headless: bool,
        request_interval_seconds: float,
        navigation_timeout_seconds: float,
        diagnostic_directory: Path = Path("artifacts/browser"),
    ) -> None:
        if request_interval_seconds < 2:
            raise ValueError("browser request interval must be at least two seconds")
        self._headless = headless
        self._interval = request_interval_seconds
        self._timeout_ms = navigation_timeout_seconds * 1000
        self._diagnostic_directory = diagnostic_directory
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._last_navigation_at = 0.0
        self._navigation_lock = asyncio.Lock()
        self._blocked_origins: dict[str, BrowserBlockedError] = {}

    async def __aenter__(self) -> "BrowserResearchSession":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._context = await self._browser.new_context(locale="ja-JP")
        self._context.set_default_timeout(self._timeout_ms)
        self._page = await self._context.new_page()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def navigate(self, url: str, ready_selector: str | None = None) -> str:
        if self._page is None:
            raise RuntimeError("browser research session is not open")
        async with self._navigation_lock:
            origin = self._origin(url)
            if origin in self._blocked_origins:
                raise self._blocked_origins[origin]
            elapsed = time.monotonic() - self._last_navigation_at
            if elapsed < self._interval:
                await asyncio.sleep(self._interval - elapsed)
            try:
                await self._page.goto(url, wait_until="domcontentloaded")
                self._last_navigation_at = time.monotonic()
                if ready_selector:
                    with suppress(Exception):
                        await self._page.locator(ready_selector).first.wait_for(
                            state="attached"
                        )
                html = await self._page.content()
                self._raise_if_blocked(html)
                return html
            except BrowserBlockedError as error:
                self._blocked_origins[origin] = error
                await self._capture_diagnostic()
                raise
            except Exception:
                await self._capture_diagnostic()
                raise

    async def _capture_diagnostic(self) -> None:
        if self._page is None:
            return
        self._diagnostic_directory.mkdir(parents=True, exist_ok=True)
        filename = f"browser-failure-{int(time.time())}.png"
        with suppress(Exception):
            await self._page.screenshot(
                path=str(self._diagnostic_directory / filename),
                full_page=False,
            )

    @staticmethod
    def _raise_if_blocked(html: str) -> None:
        normalized = html.casefold()
        markers = (
            "unusual traffic",
            "recaptcha",
            "ロボットではないことを確認",
            "アクセスが制限されています",
            "アクセスが集中しています",
        )
        if any(marker in normalized for marker in markers):
            raise BrowserBlockedError("browser research was blocked and requires manual review")

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"


_PRICE = re.compile(r"[¥￥]\s*([\d,]+)")
_SHIPPING = re.compile(r"送料\s*[¥￥]\s*([\d,]+)")
_RELATIVE_AGE = re.compile(r"^(\d+)\s*(分|時間|日|か月|ヶ月|月|年)前$")


def _special_flags(title: str) -> tuple[bool, bool, bool]:
    lowered = title.casefold()
    is_bundle = any(value in lowered for value in ("まとめ", "セット", "個セット"))
    is_junk = any(value in lowered for value in ("ジャンク", "部品取り", "訳あり"))
    is_reserved = any(value in lowered for value in ("専用", "取り置き"))
    return is_bundle, is_junk, is_reserved


def _relative_datetime(value: str, observed_at: datetime) -> datetime | None:
    match = _RELATIVE_AGE.fullmatch(value.strip())
    if match is None:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "分":
        delta = timedelta(minutes=amount)
    elif unit == "時間":
        delta = timedelta(hours=amount)
    elif unit == "日":
        delta = timedelta(days=amount)
    elif unit in {"か月", "ヶ月", "月"}:
        delta = timedelta(days=30 * amount)
    else:
        delta = timedelta(days=365 * amount)
    return observed_at - delta


class MercariWebParser:
    parser_version = "mercari-web-v1"

    def parse_search(
        self,
        html: str,
        status: ListingStatus,
        limit: int,
    ) -> tuple[MarketplaceListing, ...]:
        soup = BeautifulSoup(html, "html.parser")
        listings: list[MarketplaceListing] = []
        seen: set[str] = set()
        for anchor in soup.select('a[data-testid="thumbnail-link"][href*="/item/"]'):
            if not isinstance(anchor, Tag):
                continue
            href = str(anchor.get("href") or "")
            listing_id = href.rstrip("/").split("/")[-1]
            if not listing_id or listing_id in seen:
                continue
            title_element = anchor.select_one('[data-testid="thumbnail-item-name"]')
            title = title_element.get_text(" ", strip=True) if title_element else ""
            price_match = _PRICE.search(anchor.get_text(" ", strip=True))
            if not title or price_match is None:
                continue
            image = anchor.select_one("img[src]")
            image_url = str(image.get("src")) if isinstance(image, Tag) else None
            is_bundle, is_junk, is_reserved = _special_flags(title)
            listings.append(
                MarketplaceListing(
                    external_listing_id=listing_id,
                    canonical_url=urljoin("https://jp.mercari.com", href),
                    title=title,
                    status=status,
                    displayed_price_jpy=int(price_match.group(1).replace(",", "")),
                    image_url=image_url,
                    is_bundle=is_bundle,
                    is_junk=is_junk,
                    is_reserved=is_reserved,
                    normalized_attributes={"evidence_source": "mercari_search_card"},
                )
            )
            seen.add(listing_id)
            if len(listings) >= limit:
                break
        return tuple(listings)

    def enrich_detail(
        self,
        html: str,
        listing: MarketplaceListing,
        observed_at: datetime,
    ) -> MarketplaceListing:
        soup = BeautifulSoup(html, "html.parser")
        article = soup.find("article") or soup
        text = article.get_text(" ", strip=True)
        age_text = next(
            (
                value.get_text(" ", strip=True)
                for value in article.find_all(["p", "span"])
                if _RELATIVE_AGE.fullmatch(value.get_text(" ", strip=True))
            ),
            None,
        )
        listed_at = _relative_datetime(age_text, observed_at) if age_text else None
        shipping_match = _SHIPPING.search(text)
        shipping_jpy = (
            int(shipping_match.group(1).replace(",", "")) if shipping_match else None
        )
        condition = self._value_after_heading(article, "商品の状態")
        responsibility_text = self._value_after_heading(article, "配送料の負担")
        shipping_method = self._value_after_heading(article, "配送の方法")
        responsibility = ShippingResponsibility.UNKNOWN
        if responsibility_text and "出品者負担" in responsibility_text:
            responsibility = ShippingResponsibility.SELLER
        elif responsibility_text and "購入者負担" in responsibility_text:
            responsibility = ShippingResponsibility.BUYER
        attributes = dict(listing.normalized_attributes or {})
        attributes.update(
            {
                "detail_checked": True,
                "listed_age_text": age_text,
                "sold_date_evidence": (
                    "listing_time_upper_bound" if listing.status is ListingStatus.SOLD else None
                ),
            }
        )
        return replace(
            listing,
            listed_at=listed_at,
            condition=self._normalize_condition(condition),
            shipping_method=shipping_method,
            shipping_responsibility=responsibility,
            estimated_shipping_jpy=shipping_jpy,
            normalized_attributes=attributes,
        )

    @staticmethod
    def _value_after_heading(container: Tag, heading_text: str) -> str | None:
        heading = container.find(
            lambda tag: isinstance(tag, Tag)
            and tag.name in {"h2", "h3"}
            and tag.get_text(" ", strip=True) == heading_text
        )
        if not isinstance(heading, Tag):
            return None
        parent = heading.parent
        if not isinstance(parent, Tag):
            return None
        value = parent.get_text(" ", strip=True).removeprefix(heading_text).strip()
        return value or None

    @staticmethod
    def _normalize_condition(value: str | None) -> str | None:
        if value is None:
            return None
        if any(text in value for text in ("新品", "未使用")):
            return "new_like"
        if "目立った傷" in value:
            return "good"
        if any(text in value for text in ("やや傷", "傷や汚れ")):
            return "fair"
        if any(text in value for text in ("状態が悪い", "全体的に状態が悪い")):
            return "poor"
        return "unknown"


class GoogleLensParser:
    parser_version = "google-lens-web-v1"

    def parse_hits(self, html: str, limit: int = 20) -> tuple[VisualSearchHit, ...]:
        soup = BeautifulSoup(html, "html.parser")
        hits: list[VisualSearchHit] = []
        seen: set[tuple[str, str]] = set()
        for heading in soup.select("main h3"):
            anchor = heading.find_parent("a", href=True)
            if not isinstance(anchor, Tag):
                continue
            title = heading.get_text(" ", strip=True)
            url = str(anchor.get("href") or "")
            parsed = urlparse(url)
            if not title or parsed.scheme not in {"http", "https"}:
                continue
            key = (title, url)
            if key in seen:
                continue
            hits.append(VisualSearchHit(title=title, url=url, source=parsed.netloc))
            seen.add(key)
            if len(hits) >= limit:
                break
        return tuple(hits)


class GoogleLensBrowserAdapter:
    provider_name = "google_lens_browser"

    def __init__(self, session: BrowserResearchSession) -> None:
        self._session = session
        self._parser = GoogleLensParser()

    async def identify(self, image_url: str) -> tuple[VisualSearchHit, ...]:
        url = f"https://lens.google.com/uploadbyurl?url={quote(image_url, safe='')}"
        html = await self._session.navigate(url, "main h3")
        return self._parser.parse_hits(html)


class BrowserMercariAdapter:
    provider_name = "mercari_browser"

    def __init__(
        self,
        session: BrowserResearchSession,
        detail_limit_per_query: int = 10,
    ) -> None:
        self._session = session
        self._detail_limit = detail_limit_per_query
        self._parser = MercariWebParser()
        self._detail_cache: dict[str, MarketplaceListing] = {}

    async def search(
        self,
        query: SearchQuery,
        sold_limit: int,
        active_limit: int,
    ) -> MarketplaceSearchResult:
        sold, sold_details = await self._search_status(
            query.text,
            ListingStatus.SOLD,
            sold_limit,
            self._detail_limit,
        )
        active, _ = await self._search_status(
            query.text,
            ListingStatus.ACTIVE,
            active_limit,
            max(0, self._detail_limit - sold_details),
        )
        return MarketplaceSearchResult(
            listings=(*sold, *active),
            parser_version=self._parser.parser_version,
            raw_result_ref=f"mercari-browser:{query.normalized_text}",
        )

    async def _search_status(
        self,
        query_text: str,
        status: ListingStatus,
        limit: int,
        detail_limit: int,
    ) -> tuple[tuple[MarketplaceListing, ...], int]:
        status_value = "sold_out" if status is ListingStatus.SOLD else "on_sale"
        url = (
            "https://jp.mercari.com/search?"
            f"keyword={quote(query_text, safe='')}&status={status_value}"
        )
        html = await self._session.navigate(url, 'a[data-testid="thumbnail-link"]')
        listings = self._parser.parse_search(html, status, limit)
        enriched: list[MarketplaceListing] = []
        details_fetched = 0
        for listing in listings:
            cached = self._detail_cache.get(listing.external_listing_id)
            if cached is not None:
                enriched.append(cached)
                continue
            if details_fetched >= detail_limit:
                enriched.append(listing)
                continue
            detail_html = await self._session.navigate(listing.canonical_url, "article")
            detailed = self._parser.enrich_detail(
                detail_html,
                listing,
                datetime.now().astimezone(),
            )
            self._detail_cache[listing.external_listing_id] = detailed
            enriched.append(detailed)
            details_fetched += 1
        return tuple(enriched), details_fetched
