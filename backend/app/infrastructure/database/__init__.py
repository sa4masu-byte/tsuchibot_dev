from backend.app.infrastructure.database.catalog import InMemoryCatalogRepository
from backend.app.infrastructure.database.postgres_analysis import PostgresAnalysisRepository
from backend.app.infrastructure.database.postgres_canonical import (
    PostgresCanonicalProductRepository,
)
from backend.app.infrastructure.database.postgres_catalog import PostgresCatalogRepository
from backend.app.infrastructure.database.postgres_research import PostgresResearchRepository
from backend.app.infrastructure.database.postgres_research_candidate import (
    PostgresResearchCandidateRepository,
    ProductResearchCandidate,
)
from backend.app.infrastructure.database.postgres_runs import PostgresRunRepository
from backend.app.infrastructure.database.postgres_visual_search import (
    PostgresVisualSearchRepository,
)
from backend.app.infrastructure.database.research import InMemoryResearchRepository

__all__ = [
    "InMemoryCatalogRepository",
    "PostgresAnalysisRepository",
    "PostgresCanonicalProductRepository",
    "PostgresCatalogRepository",
    "PostgresRunRepository",
    "PostgresVisualSearchRepository",
    "PostgresResearchRepository",
    "PostgresResearchCandidateRepository",
    "ProductResearchCandidate",
    "InMemoryResearchRepository",
]
