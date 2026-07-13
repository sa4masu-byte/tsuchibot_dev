from backend.app.application.identification import ResolveModelIdentity
from backend.app.domain.research import (
    ModelIdentityCandidate,
    VisualSearchHit,
    extract_visual_model_candidates,
    merge_model_candidates,
    needs_visual_search,
)


def test_visual_results_require_repeated_model_evidence() -> None:
    hits = (
        VisualSearchHit("DAIKO LEDペンダント DXL-81310", "https://example.com/1", "shop-a"),
        VisualSearchHit("大光電機 DXL-81310 照明", "https://example.com/2", "shop-b"),
        VisualSearchHit("MERCERO LT-7442", "https://example.com/3", "shop-c"),
    )

    candidates = extract_visual_model_candidates(hits)

    assert candidates[0].value == "DXL-81310"
    assert candidates[0].confidence > candidates[1].confidence
    assert candidates[0].confidence < 0.9


def test_visual_search_only_runs_below_confidence_threshold() -> None:
    strong = ModelIdentityCandidate("HAC-001", 0.9, ("label",), ("gemini",))
    weak = ModelIdentityCandidate("HAC-001", 0.5, ("shape",), ("gemini",))

    assert needs_visual_search((strong,)) is False
    assert needs_visual_search((weak,)) is True
    assert needs_visual_search(()) is True


def test_agreement_between_primary_and_visual_evidence_increases_confidence() -> None:
    primary = ModelIdentityCandidate("dxl-81310", 0.6, ("image text",), ("gemini",))
    visual = ModelIdentityCandidate(
        "DXL-81310",
        0.67,
        ("shop title",),
        ("google_lens",),
    )

    merged = merge_model_candidates((primary,), (visual,))

    assert len(merged) == 1
    assert merged[0].value == "DXL-81310"
    assert merged[0].confidence == 0.75
    assert merged[0].sources == ("gemini", "google_lens")


class _FailingVisualProvider:
    provider_name = "fixture_visual_provider"

    async def identify(self, image_url: str) -> tuple[VisualSearchHit, ...]:
        raise RuntimeError("visual provider unavailable")


async def test_visual_provider_failure_keeps_primary_candidates() -> None:
    primary = ModelIdentityCandidate("HAC-001", 0.5, ("partial label",), ("gemini",))

    result = await ResolveModelIdentity(_FailingVisualProvider()).execute(
        (primary,),
        ("https://example.com/product.jpg",),
    )

    assert result.status == "failed"
    assert result.error_category == "RuntimeError"
    assert result.error_message == "Visual identity provider was unavailable."
    assert result.candidates == (primary,)
    assert result.visual_search_used is True
