from backend.app.domain.research.comparables import (
    ComparableRanker,
    calculate_price_statistics,
    calculate_shipping_statistics,
    default_evidence_period,
)
from backend.app.domain.research.identification import (
    ModelIdentityCandidate,
    VisualSearchHit,
    extract_visual_model_candidates,
    merge_model_candidates,
    needs_visual_search,
    normalize_model_number,
)
from backend.app.domain.research.models import (
    ComparableDecision,
    ComparableEvidence,
    ListingStatus,
    MarketplaceListing,
    PriceStatistics,
    ResearchTarget,
    SearchQuery,
    SearchStage,
    ShippingResponsibility,
    ShippingStatistics,
)
from backend.app.domain.research.queries import StagedQueryGenerator, normalize_query

__all__ = [
    "ComparableDecision",
    "ComparableEvidence",
    "ComparableRanker",
    "ListingStatus",
    "MarketplaceListing",
    "ModelIdentityCandidate",
    "PriceStatistics",
    "ResearchTarget",
    "SearchQuery",
    "SearchStage",
    "ShippingResponsibility",
    "ShippingStatistics",
    "StagedQueryGenerator",
    "VisualSearchHit",
    "calculate_price_statistics",
    "calculate_shipping_statistics",
    "default_evidence_period",
    "extract_visual_model_candidates",
    "merge_model_candidates",
    "needs_visual_search",
    "normalize_query",
    "normalize_model_number",
]
