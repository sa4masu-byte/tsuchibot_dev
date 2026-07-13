import re
import unicodedata

from backend.app.domain.research.models import ResearchTarget, SearchQuery, SearchStage

_WHITESPACE = re.compile(r"\s+")


def normalize_query(value: str) -> str:
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).casefold()).strip()


class StagedQueryGenerator:
    version = "mercari-query-v1"

    def generate(self, target: ResearchTarget) -> tuple[SearchQuery, ...]:
        candidates: list[tuple[SearchStage, str]] = []
        maker = target.brand or target.manufacturer
        product_type = target.product_type or target.category

        for model_number in target.model_numbers:
            candidates.append((SearchStage.EXACT_MODEL, model_number))
        if maker:
            for model_number in target.model_numbers:
                candidates.append(
                    (SearchStage.MANUFACTURER_MODEL, f"{maker} {model_number}")
                )
        if target.series and product_type:
            candidates.append(
                (SearchStage.SERIES_PRODUCT_TYPE, f"{target.series} {product_type}")
            )
        if maker and product_type:
            candidates.append(
                (SearchStage.MANUFACTURER_PRODUCT_TYPE, f"{maker} {product_type}")
            )
        similar_text = " ".join(target.search_terms[:3]) or target.source_title
        candidates.append((SearchStage.SIMILAR_PRODUCT, similar_text))

        queries: list[SearchQuery] = []
        seen: set[str] = set()
        for stage, text in candidates:
            normalized = normalize_query(text)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            queries.append(
                SearchQuery(
                    order=len(queries) + 1,
                    text=text.strip(),
                    stage=stage,
                    normalized_text=normalized,
                    generated_by=self.version,
                )
            )
        return tuple(queries)
