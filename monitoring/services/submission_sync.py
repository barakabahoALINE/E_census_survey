from collections import Counter
from dataclasses import dataclass

from django.db import transaction

from monitoring.models import Candidate, Submission

from .external_submissions import DISTRICT_CODE_TO_NAME, ExternalSubmission


class DuplicateExternalNationalIDs(Exception):
    def __init__(self, duplicate_count: int):
        self.duplicate_count = duplicate_count
        super().__init__(f"Found {duplicate_count} duplicate external National ID value(s).")


class DuplicateCandidateNationalIDs(Exception):
    pass


@dataclass(frozen=True)
class SubmissionSyncResult:
    external_records_read: int
    matched_candidates: int
    unmatched_external_records: int
    created: int
    already_existing: int
    stale_removed: int
    district_mismatches: int
    unmapped_district_codes: int


def synchronize_submissions(
    external_records: list[ExternalSubmission], *, prune_stale: bool = False
) -> SubmissionSyncResult:
    external_ids = [
        record.national_id.strip()
        for record in external_records
        if record.national_id and record.national_id.strip()
    ]
    duplicate_count = sum(count > 1 for count in Counter(external_ids).values())
    if duplicate_count:
        raise DuplicateExternalNationalIDs(duplicate_count)

    candidates = list(
        Candidate.objects.using("default").values(
            "national_id", "full_name", "district", "registered_location"
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

    matched_records = [
        (record, candidates_by_id[record.national_id.strip()])
        for record in external_records
        if record.national_id
        and record.national_id.strip() in candidates_by_id
    ]
    matched_national_ids = {candidate["national_id"] for _, candidate in matched_records}
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
    stale_removed = 0
    with transaction.atomic(using="default"):
        for _, candidate in matched_records:
            _, was_created = Submission.objects.using("default").update_or_create(
                national_id=candidate["national_id"],
                defaults={
                    "full_name": candidate["full_name"],
                    "district": candidate["district"],
                    "submitted_location": (
                        candidate["registered_location"] or candidate["district"]
                    ),
                    "score": None,
                    "submitted_at": None,
                },
            )
            if was_created:
                created += 1
            else:
                already_existing += 1

        if prune_stale:
            stale_submissions = Submission.objects.using("default").exclude(
                national_id__in=matched_national_ids
            )
            stale_removed = stale_submissions.count()
            stale_submissions.delete()

    return SubmissionSyncResult(
        external_records_read=len(external_records),
        matched_candidates=len(matched_records),
        unmatched_external_records=len(external_records) - len(matched_records),
        created=created,
        already_existing=already_existing,
        stale_removed=stale_removed,
        district_mismatches=district_mismatches,
        unmapped_district_codes=unmapped_district_codes,
    )