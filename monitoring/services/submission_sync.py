from dataclasses import dataclass

from django.db import transaction

from monitoring.models import Candidate, Submission

from .candidate_matching import analyze_candidate_matches
from .external_submissions import DISTRICT_CODE_TO_NAME, ExternalSubmission


class DuplicateCandidateNationalIDs(Exception):
    pass


@dataclass(frozen=True)
class SubmissionSyncResult:
    external_records_read: int
    matched_candidates: int
    exact_id_matches: int
    corrected_id_matches: int
    duplicate_exact_id_records: int
    ambiguous_external_records: int
    ambiguous_expected_candidates: int
    unmatched_external_records: int
    created: int
    already_existing: int
    updated: int
    unchanged: int
    stale_removed: int
    district_mismatches: int
    unmapped_district_codes: int


def synchronize_submissions(
    external_records: list[ExternalSubmission], *, prune_stale: bool = False
) -> SubmissionSyncResult:
    candidates = list(
        Candidate.objects.using("default").values(
            "national_id",
            "full_name",
            "district",
            "registered_location",
            "sector",
            "cell",
            "phone_number",
        )
    )
    candidates_by_id = {}
    for candidate in candidates:
        national_id = candidate["national_id"].strip()
        if national_id in candidates_by_id:
            raise DuplicateCandidateNationalIDs(
                "Multiple expected candidates normalize to the same National ID."
            )
        candidates_by_id[national_id] = candidate

    analysis = analyze_candidate_matches(candidates, external_records)
    matched_records = [
        (
            match.external_submission,
            candidates_by_id[match.candidate_national_id],
        )
        for match in analysis.matches
    ]
    matched_national_ids = {
        candidate["national_id"] for _, candidate in matched_records
    }
    district_mismatches = 0
    unmapped_district_codes = 0
    for record, candidate in matched_records:
        district_name = DISTRICT_CODE_TO_NAME.get(record.district_code or "")
        if district_name is None:
            if record.district_code:
                unmapped_district_codes += 1
        elif district_name.casefold() != candidate["district"].strip().casefold():
            district_mismatches += 1

    created = 0
    already_existing = 0
    updated = 0
    unchanged = 0
    stale_removed = 0
    with transaction.atomic(using="default"):
        for record, candidate in matched_records:
            defaults = {
                "source_national_id": record.national_id or "",
                "source_record_id": record.record_id,
                "full_name": record.full_name,
                "phone_number": record.phone_number,
                "district": record.district
                or DISTRICT_CODE_TO_NAME.get(record.district_code or "", ""),
                "submitted_location": " / ".join(
                    value for value in (record.sector, record.cell) if value
                ),
                "score": None,
                "submitted_at": None,
            }
            submission, was_created = Submission.objects.using("default").get_or_create(
                national_id=candidate["national_id"],
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                already_existing += 1
                changed_fields = [
                    field
                    for field, value in defaults.items()
                    if getattr(submission, field) != value
                ]
                if changed_fields:
                    for field in changed_fields:
                        setattr(submission, field, defaults[field])
                    submission.save(
                        using="default",
                        update_fields=[*changed_fields, "updated_at"],
                    )
                    updated += 1
                else:
                    unchanged += 1

        if prune_stale:
            protected_national_ids = matched_national_ids | set(
                analysis.ambiguous_candidate_ids
            )
            stale_submissions = Submission.objects.using("default").exclude(
                national_id__in=protected_national_ids
            )
            stale_removed = stale_submissions.count()
            stale_submissions.delete()

    return SubmissionSyncResult(
        external_records_read=len(external_records),
        matched_candidates=len(matched_records),
        exact_id_matches=len(analysis.exact_id_matches),
        corrected_id_matches=len(analysis.corrected_id_matches),
        duplicate_exact_id_records=len(analysis.duplicate_exact_id_submissions),
        ambiguous_external_records=len(analysis.ambiguous_external_submissions),
        ambiguous_expected_candidates=len(analysis.ambiguous_candidate_ids),
        unmatched_external_records=len(analysis.unmatched_external_submissions),
        created=created,
        already_existing=already_existing,
        updated=updated,
        unchanged=unchanged,
        stale_removed=stale_removed,
        district_mismatches=district_mismatches,
        unmapped_district_codes=unmapped_district_codes,
    )