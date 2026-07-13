import re
import unicodedata
from dataclasses import dataclass

_HYPHENATED_MODEL = re.compile(r"\b[A-Z]{1,8}[A-Z0-9]*-\d{2,}[A-Z0-9-]*\b")
_COMPACT_MODEL = re.compile(r"\b[A-Z]{2,6}\d{3,}[A-Z0-9-]*\b")
_YEAR = re.compile(r"^(?:19|20)\d{2}$")


@dataclass(frozen=True, slots=True)
class VisualSearchHit:
    title: str
    url: str
    source: str


@dataclass(frozen=True, slots=True)
class ModelIdentityCandidate:
    value: str
    confidence: float
    evidence: tuple[str, ...]
    sources: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("model candidate value cannot be empty")
        if not 0 <= self.confidence <= 1:
            raise ValueError("model candidate confidence must be between 0 and 1")


def normalize_model_number(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).upper().strip()
    return normalized.replace("‐", "-").replace("–", "-").replace("—", "-")


def needs_visual_search(
    candidates: tuple[ModelIdentityCandidate, ...],
    threshold: float = 0.7,
) -> bool:
    if not 0 <= threshold <= 1:
        raise ValueError("visual-search threshold must be between 0 and 1")
    return not candidates or max(candidate.confidence for candidate in candidates) < threshold


def extract_visual_model_candidates(
    hits: tuple[VisualSearchHit, ...],
) -> tuple[ModelIdentityCandidate, ...]:
    evidence_by_value: dict[str, list[VisualSearchHit]] = {}
    for hit in hits:
        normalized_title = normalize_model_number(hit.title)
        values = set(_HYPHENATED_MODEL.findall(normalized_title))
        values.update(_COMPACT_MODEL.findall(normalized_title))
        for value in values:
            if _YEAR.fullmatch(value):
                continue
            evidence_by_value.setdefault(value, []).append(hit)

    candidates = []
    for value, evidence in evidence_by_value.items():
        distinct_sources = tuple(sorted({hit.source for hit in evidence}))
        occurrence_count = len(evidence)
        confidence = min(
            0.9,
            0.35
            + min(3, occurrence_count) * 0.12
            + min(2, len(distinct_sources)) * 0.08,
        )
        candidates.append(
            ModelIdentityCandidate(
                value=value,
                confidence=round(confidence, 6),
                evidence=tuple(hit.title for hit in evidence[:5]),
                sources=distinct_sources,
            )
        )
    return tuple(sorted(candidates, key=lambda item: (-item.confidence, item.value)))


def merge_model_candidates(
    primary: tuple[ModelIdentityCandidate, ...],
    visual: tuple[ModelIdentityCandidate, ...],
) -> tuple[ModelIdentityCandidate, ...]:
    merged: dict[str, ModelIdentityCandidate] = {}
    for candidate in (*primary, *visual):
        key = normalize_model_number(candidate.value)
        previous = merged.get(key)
        if previous is None:
            merged[key] = ModelIdentityCandidate(
                value=key,
                confidence=candidate.confidence,
                evidence=candidate.evidence,
                sources=candidate.sources,
            )
            continue
        source_agreement_bonus = 0.08 if set(previous.sources) != set(candidate.sources) else 0
        merged[key] = ModelIdentityCandidate(
            value=key,
            confidence=min(
                0.98,
                max(previous.confidence, candidate.confidence) + source_agreement_bonus,
            ),
            evidence=tuple(dict.fromkeys((*previous.evidence, *candidate.evidence)))[:8],
            sources=tuple(sorted(set(previous.sources) | set(candidate.sources))),
        )
    return tuple(sorted(merged.values(), key=lambda item: (-item.confidence, item.value)))
