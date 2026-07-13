from datetime import UTC, datetime
from pathlib import Path

from backend.app.domain.research import ListingStatus, ShippingResponsibility
from backend.app.infrastructure.sources.browser_research import (
    BrowserBlockedError,
    BrowserResearchSession,
    GoogleLensParser,
    MercariWebParser,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mercari"


def test_mercari_search_cards_are_normalized_without_live_access() -> None:
    parser = MercariWebParser()

    listings = parser.parse_search(
        (FIXTURES / "web_search.html").read_text(),
        ListingStatus.SOLD,
        50,
    )

    assert len(listings) == 2
    assert listings[0].external_listing_id == "m-sold-1"
    assert listings[0].displayed_price_jpy == 12000
    assert listings[0].image_url is not None
    assert listings[1].is_junk is True
    assert listings[1].is_bundle is True


def test_mercari_detail_adds_age_condition_and_shipping_evidence() -> None:
    parser = MercariWebParser()
    listing = parser.parse_search(
        (FIXTURES / "web_search.html").read_text(),
        ListingStatus.SOLD,
        1,
    )[0]
    observed_at = datetime(2026, 7, 13, tzinfo=UTC)

    detailed = parser.enrich_detail(
        (FIXTURES / "web_detail.html").read_text(),
        listing,
        observed_at,
    )

    assert detailed.listed_at == datetime(2026, 6, 13, tzinfo=UTC)
    assert detailed.condition == "good"
    assert detailed.estimated_shipping_jpy == 750
    assert detailed.shipping_method == "らくらくメルカリ便"
    assert detailed.shipping_responsibility is ShippingResponsibility.SELLER


def test_google_lens_parser_preserves_titles_and_sources() -> None:
    hits = GoogleLensParser().parse_hits(
        (FIXTURES / "google_lens.html").read_text(),
    )

    assert len(hits) == 2
    assert hits[0].title == "DAIKO LEDペンダント DXL-81310"
    assert hits[0].source == "shop-a.example"


class _FakePage:
    def __init__(self) -> None:
        self.current_url = ""
        self.visited: list[str] = []

    async def goto(self, url: str, *, wait_until: str) -> None:
        self.current_url = url
        self.visited.append(url)

    async def content(self) -> str:
        if "blocked.example" in self.current_url:
            return "<html>recaptcha</html>"
        return "<html>public result</html>"

    async def screenshot(self, **kwargs: object) -> None:
        return None


async def test_browser_block_stops_only_the_affected_origin(tmp_path: Path) -> None:
    session = BrowserResearchSession(
        headless=True,
        request_interval_seconds=2,
        navigation_timeout_seconds=1,
        diagnostic_directory=tmp_path,
    )
    page = _FakePage()
    session._page = page  # type: ignore[assignment]

    try:
        await session.navigate("https://blocked.example/search")
    except BrowserBlockedError:
        pass
    else:
        raise AssertionError("blocked page must stop navigation")
    try:
        await session.navigate("https://blocked.example/another")
    except BrowserBlockedError:
        pass
    else:
        raise AssertionError("blocked origin must remain stopped")

    html = await session.navigate("https://public.example/search")

    assert html == "<html>public result</html>"
    assert page.visited == [
        "https://blocked.example/search",
        "https://public.example/search",
    ]
