from django.core.management.base import BaseCommand, CommandError

from monitoring.services.external_submissions import ExternalSubmissionReader
from monitoring.services.submission_sync import (
    DuplicateCandidateNationalIDs,
    DuplicateExternalNationalIDs,
    synchronize_submissions,
)


class Command(BaseCommand):
    help = "Synchronize real exam_rec submissions into the local monitoring database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prune-stale",
            action="store_true",
            help="Remove local Submission rows not present in the external source.",
        )

    def handle(self, *args, **options):
        try:
            external_records = ExternalSubmissionReader().read()
        except Exception as exc:
            raise CommandError(
                "Could not read exam_rec from submissions_db; local submissions were not changed."
            ) from exc

        try:
            result = synchronize_submissions(
                external_records,
                prune_stale=options["prune_stale"],
            )
        except (DuplicateExternalNationalIDs, DuplicateCandidateNationalIDs) as exc:
            raise CommandError(f"Synchronization stopped before local changes: {exc}") from exc

        self.stdout.write(f"External submission records read: {result.external_records_read}")
        self.stdout.write(f"Matched expected candidates: {result.matched_candidates}")
        self.stdout.write(f"Unmatched external records: {result.unmatched_external_records}")
        self.stdout.write(f"Local submissions created: {result.created}")
        self.stdout.write(f"Already existing/updated: {result.already_existing}")
        if options["prune_stale"]:
            self.stdout.write(f"Stale local submissions removed: {result.stale_removed}")
        if result.district_mismatches:
            self.stdout.write(self.style.WARNING(
                f"District code differs from expected Candidate district for "
                f"{result.district_mismatches} matched candidate(s); expected districts were retained."
            ))
        if result.unmapped_district_codes:
            self.stdout.write(self.style.WARNING(
                f"No district name mapping exists for "
                f"{result.unmapped_district_codes} matched external record(s)."
            ))
        self.stdout.write(self.style.SUCCESS("External database accessed with SELECT only."))