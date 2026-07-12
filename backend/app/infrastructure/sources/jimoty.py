import asyncio
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from backend.app.application.catalog import (
    RunContext,
    SourceCollectionResult,
    SourceConfig,
)
from backend.app.domain.catalog import Availability, NormalizedSourceProduct

PARSER_VERSION = "jimoty-profile-v1"
RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
ITEM_ID_PATTERN = re.compile(r"/article-([^/?#]+)")
CATEGORY_PATTERN = re.compile(r"/sale-([^/]+)/article-")


class SourceParsingError(RuntimeError):
    pass


class SourceBlockedError(RuntimeError):
    pass


class JimotyParser:
    def parse(
        self,
        html: str,
        config: SourceConfig,
        observed_at: datetime,
    ) -> tuple[tuple[NormalizedSourceProduct, ...], str | None]:
        soup = BeautifulSoup(html, "html.parser")
        if soup.select_one("#articles") is None:
            raise SourceParsingError("Jimoty articles container was not found")

        products = tuple(
            product
            for card in soup.select("a.portal_list_link")
            if (product := self._parse_card(card, config, observed_at)) is not None
        )
        next_link = soup.select_one('a[rel="next"]')
        next_url = self._attribute(next_link, "href")
        return products, urljoin(config.articles_url, next_url) if next_url else None

    def _parse_card(
        self,
        card: Tag,
        config: SourceConfig,
        observed_at: datetime,
    ) -> NormalizedSourceProduct | None:
        href = self._attribute(card, "href")
        if href is None or (item_match := ITEM_ID_PATTERN.search(href)) is None:
            return None
        canonical_url = urljoin(config.articles_url, href)
        category_match = CATEGORY_PATTERN.search(href)
        badge = self._text(card.select_one(".bace"))
        image_url = self._attribute(card.select_one("img"), "src")
        location = self._supplement_location(card)
        return NormalizedSourceProduct(
            source_type=config.source_type,
            source_location_id=config.location_id,
            source_item_id=item_match.group(1),
            canonical_url=canonical_url,
            title=self._optional_text(card.select_one(".portal_list_title")),
            displayed_price_jpy=self._price(card.select_one(".portal_list_supplement b")),
            category=category_match.group(1) if category_match else None,
            availability=self._availability(badge),
            listing_timestamp=self._listing_timestamp(
                self._optional_text(card.select_one(".portal_list_timestamp")),
                observed_at,
            ),
            image_urls=(urljoin(config.articles_url, image_url),) if image_url else (),
            raw_metadata={"badge": badge, "location": location},
            parser_version=PARSER_VERSION,
        )

    @staticmethod
    def _attribute(element: Tag | None, name: str) -> str | None:
        if element is None:
            return None
        value = element.get(name)
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _text(element: Tag | None) -> str:
        return " ".join(element.stripped_strings) if element else ""

    def _optional_text(self, element: Tag | None) -> str | None:
        value = self._text(element)
        return value or None

    def _supplement_location(self, card: Tag) -> str | None:
        supplement = card.select_one(".portal_list_supplement")
        if supplement is None:
            return None
        spans = supplement.select("span")
        return self._optional_text(spans[1]) if len(spans) > 1 else None

    def _price(self, element: Tag | None) -> int | None:
        text = self._text(element)
        if not text:
            return None
        if "無料" in text:
            return 0
        digits = re.sub(r"[^0-9]", "", text)
        return int(digits) if digits else None

    @staticmethod
    def _availability(badge: str) -> Availability:
        if badge == "売ります":
            return Availability.AVAILABLE
        if badge in {"受付終了", "終了", "売却済み"}:
            return Availability.UNAVAILABLE
        return Availability.UNKNOWN

    @staticmethod
    def _listing_timestamp(value: str | None, observed_at: datetime) -> datetime | None:
        if value is None or not re.fullmatch(r"\d{1,2}/\d{1,2}", value):
            return None
        month, day = (int(part) for part in value.split("/"))
        year = observed_at.year - 1 if month > observed_at.month else observed_at.year
        try:
            return observed_at.replace(
                year=year,
                month=month,
                day=day,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        except ValueError:
            return None


class JimotySpotAdapter:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        parser: JimotyParser | None = None,
        max_retries: int = 2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._parser = parser or JimotyParser()
        self._max_retries = max_retries
        self._sleep = sleep

    async def collect(
        self,
        config: SourceConfig,
        context: RunContext,
    ) -> SourceCollectionResult:
        products: list[NormalizedSourceProduct] = []
        seen_ids: set[str] = set()
        seen_pages: set[str] = set()
        duplicate_count = 0
        next_url: str | None = config.articles_url
        pages_fetched = 0

        while next_url and pages_fetched < config.max_pages and next_url not in seen_pages:
            if pages_fetched:
                await self._sleep(config.request_interval_seconds)
            seen_pages.add(next_url)
            html = await self._fetch(next_url)
            page_products, next_url = self._parser.parse(html, config, context.observed_at)
            pages_fetched += 1
            for product in page_products:
                if product.source_item_id in seen_ids:
                    duplicate_count += 1
                    continue
                seen_ids.add(product.source_item_id)
                products.append(product)

        return SourceCollectionResult(tuple(products), pages_fetched, duplicate_count)

    async def _fetch(self, url: str) -> str:
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Tsuchibot/0.1 managed-store-pricing-research",
        }
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._request(url, headers)
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt >= self._max_retries:
                    raise
                await self._sleep(2**attempt)
                continue
            if response.status_code in {401, 403}:
                raise SourceBlockedError(f"Jimoty returned HTTP {response.status_code}")
            if response.status_code in RETRYABLE_STATUSES and attempt < self._max_retries:
                await self._sleep(2**attempt)
                continue
            response.raise_for_status()
            return response.text
        raise RuntimeError("unreachable retry state")

    async def _request(self, url: str, headers: dict[str, str]) -> httpx.Response:
        if self._client is not None:
            return await self._client.get(url, headers=headers, timeout=20, follow_redirects=True)
        async with httpx.AsyncClient() as client:
            return await client.get(url, headers=headers, timeout=20, follow_redirects=True)
