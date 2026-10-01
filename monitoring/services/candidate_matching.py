import re
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .administrative_locations import normalize_location_label
from .external_submissions import ExternalSubmission


class CandidateMatchType(str, Enum):
    EXACT_ID_MATCH = "EXACT_ID_MATCH"
    CORRECTED_ID_MATCH = "CORRECTED_ID_MATCH"


@dataclass(frozen=True)
class CandidateSubmissionMatch:
    candidate_national_id: str
    external_submission: ExternalSubmission
    match_type: CandidateMatchType


@dataclass(frozen=True)
class CandidateMatchAnalysis:
    matches: tuple[CandidateSubmissionMatch, ...]
    duplicate_exact_id_submissions: tuple[ExternalSubmission, ...]
    ambiguous_external_submissions: tuple[ExternalSubmission, ...]
    ambiguous_candidate_ids: tuple[str, ...]
    unmatched_external_submissions: tuple[ExternalSubmission, ...]

    @property
    def exact_id_matches(self) -> tuple[CandidateSubmissionMatch, ...]:
        return tuple(
            match
            for match in self.matches
            if match.match_type is CandidateMatchType.EXACT_ID_MATCH
        )

    @property
    def corrected_id_matches(self) -> tuple[CandidateSubmissionMatch, ...]:
        return tuple(
            match
            for match in self.matches
            if match.match_type is CandidateMatchType.CORRECTED_ID_MATCH
        )


def normalize_candidate_name(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def normalize_candidate_phone(value: str | None) -> str:
    return re.sub(r"[\s-]+", "", (value or "").strip())


def _candidate_key(candidate: Mapping[str, object]) -> tuple[str, ...] | None:
    values = (
        normalize_candidate_name(str(candidate.get("full_name") or "")),
        normalize_candidate_phone(str(candidate.get("phone_number") or "")),
        normalize_location_label(str(candidate.get("district") or "")),
        normalize_location_label(str(candidate.get("sector") or "")),
        normalize_location_label(str(candidate.get("cell") or "")),
    )
    return values if all(values) else None


def _external_key(record: ExternalSubmission) -> tuple[str, ...] | None:
    values = (
        normalize_candidate_name(record.full_name),
        normalize_candidate_phone(record.phone_number),
        normalize_location_label(record.district),
        normalize_location_label(record.sector),
        normalize_location_label(record.cell),
    )
    return values if all(values) else None


def analyze_candidate_matches(
    candidates: list[Mapping[str, object]],
    external_submissions: list[ExternalSubmission],
) -> CandidateMatchAnalysis:
    candidates_by_id = {
        str(candidate["national_id"]).strip(): candidate for candidate in candidates
    }
    candidates_by_key = defaultdict(list)
    for candidate in candidates:
        key = _candidate_key(candidate)
        if key:
            candidates_by_key[key].append(candidate)

    matches = []
    ambiguous_indices = set()
    ambiguous_candidate_ids = set()
    duplicate_exact_indices = set()
    used_indices = set()
    exact_candidate_ids = set()
    external_by_id = defaultdict(list)
    for index, record in enumerate(external_submissions):
        national_id = (record.national_id or "").strip()
        if national_id:
            external_by_id[national_id].append(index)

    for national_id, indices in external_by_id.items():
        if national_id not in candidates_by_id:
            continue
        exact_candidate_ids.add(national_id)
        first_index = max(
            indices,
            key=lambda index: (
                external_submissions[index].record_id is not None,
                external_submissions[index].record_id or 0,
            ),
        )
        matches.append(
            CandidateSubmissionMatch(
                candidate_national_id=national_id,
                external_submission=external_submissions[first_index],
                match_type=CandidateMatchType.EXACT_ID_MATCH,
            )
        )
        used_indices.add(first_index)
        if len(indices) > 1:
            duplicate_exact_indices.update(indices[1:])

    duplicate_non_exact_ids = {
        national_id
        for national_id, indices in external_by_id.items()
        if national_id not in candidates_by_id and len(indices) > 1
    }
    for national_id in duplicate_non_exact_ids:
        indices = external_by_id[national_id]
        ambiguous_indices.update(indices)
        for index in indices:
            key = _external_key(external_submissions[index])
            ambiguous_candidate_ids.update(
                str(candidate["national_id"]).strip()
                for candidate in candidates_by_key.get(key, [])
            )

    external_by_key = defaultdict(list)
    for index, record in enumerate(external_submissions):
        if (
            index in used_indices
            or index in ambiguous_indices
            or index in duplicate_exact_indices
        ):
            continue
        national_id = (record.national_id or "").strip()
        if not national_id or national_id in candidates_by_id:
            continue
        key = _external_key(record)
        if key:
            external_by_key[key].append(index)

    for key, indices in external_by_key.items():
        matching_candidates = candidates_by_key.get(key, [])
        unmatched_candidates = [
            candidate
            for candidate in matching_candidates
            if str(candidate["national_id"]).strip() not in exact_candidate_ids
        ]
        if not matching_candidates:
            continue
        if len(matching_candidates) == 1 and len(unmatched_candidates) == 1 and len(indices) == 1:
            index = indices[0]
            candidate = unmatched_candidates[0]
            matches.append(
                CandidateSubmissionMatch(
                    candidate_national_id=str(candidate["national_id"]).strip(),
                    external_submission=external_submissions[index],
                    match_type=CandidateMatchType.CORRECTED_ID_MATCH,
                )
            )
            used_indices.add(index)
        else:
            ambiguous_indices.update(indices)
            ambiguous_candidate_ids.update(
                str(candidate["national_id"]).strip()
                for candidate in matching_candidates
            )

    ambiguous_external_submissions = tuple(
        external_submissions[index] for index in sorted(ambiguous_indices)
    )
    unmatched_external_submissions = tuple(
        record
        for index, record in enumerate(external_submissions)
        if index not in used_indices
        and index not in ambiguous_indices
        and index not in duplicate_exact_indices
    )
    return CandidateMatchAnalysis(
        matches=tuple(matches),
        duplicate_exact_id_submissions=tuple(
            external_submissions[index] for index in sorted(duplicate_exact_indices)
        ),
        ambiguous_external_submissions=ambiguous_external_submissions,
        ambiguous_candidate_ids=tuple(sorted(ambiguous_candidate_ids)),
        unmatched_external_submissions=unmatched_external_submissions,
    )