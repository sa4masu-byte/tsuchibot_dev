from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from backend.app.application.catalog import observation_idempotency_key
from backend.app.domain.catalog import (
    NormalizedSourceProduct,
    ProductChange,
    SourceProductState,
)


@dataclass(frozen=True, slots=True)
class StoredObservation:
    product: NormalizedSourceProduct
    run_id: UUID
    observed_at: datetime
    change: ProductChange
    idempotency_key: str


class InMemoryCatalogRepository:
    def __init__(self) -> None:
        self.states: dict[tuple[str, str], SourceProductState] = {}
        self.observations: list[StoredObservation] = []
        self._idempotency_keys: set[str] = set()

    async def get_state(self, source_type: str, source_item_id: str) -> SourceProductState | None:
        return self.states.get((source_type, source_item_id))

    async def append_observation(
        self,
        product: NormalizedSourceProduct,
        run_id: UUID,
        observed_at: datetime,
        change: ProductChange,
    ) -> bool:
        idempotency_key = observation_idempotency_key(product, run_id, observed_at)
        if idempotency_key in self._idempotency_keys:
            return False
        self._idempotency_keys.add(idempotency_key)
        self.observations.append(
            StoredObservation(product, run_id, observed_at, change, idempotency_key)
        )
        self.states[product.identity] = SourceProductState(
            source_type=product.source_type,
            source_item_id=product.source_item_id,
            canonical_url=product.canonical_url,
            current_price_jpy=product.displayed_price_jpy,
            current_availability=product.availability,
        )
        return True
