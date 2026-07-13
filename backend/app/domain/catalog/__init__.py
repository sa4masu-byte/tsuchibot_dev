from backend.app.domain.catalog.analysis import ProductAnalysis
from backend.app.domain.catalog.duplicates import (
    DuplicateDecision,
    DuplicateDecisionKind,
    DuplicateDetectionService,
)
from backend.app.domain.catalog.models import (
    Availability,
    ChangeKind,
    NormalizedSourceProduct,
    ProductChange,
    SourceProductState,
    detect_change,
)

__all__ = [
    "Availability",
    "ChangeKind",
    "NormalizedSourceProduct",
    "ProductChange",
    "SourceProductState",
    "detect_change",
    "DuplicateDecision",
    "DuplicateDecisionKind",
    "DuplicateDetectionService",
    "ProductAnalysis",
]
