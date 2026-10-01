from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from monitoring.services.external_submissions import ExternalSubmissionReader
from monitoring.services.submission_sync import (
    DuplicateCandidateNationalIDs,
    synchronize_submissions,
)


class Command(BaseCommand):
    help = "Synchronize real exam_rec submissions into the local monitoring database."
    lock_name = "establishment_census_exam_sync_submissions"

    def acquire_lock(self):
        connection = connections["default"]
        if connection.vendor != "mysql":
            return None

        cursor = connection.cursor()
        try:
            cursor.execute("SELECT GET_LOCK(%s, 0)", [self.lock_name])
            result = cursor.fetchone()[0]
        except Exception as exc:
            cursor.close()
            raise CommandError(
                "Could not acquire the sync lock from the local database."
            ) from exc

        if result is None:
            cursor.close()
            raise CommandError("The local database could not acquire the sync lock.")
        if result != 1:
            cursor.close()
            return None
        return cursor

    def release_lock(self, cursor):
        try:
            cursor.execute("SELECT RELEASE_LOCK(%s)", [self.lock_name])
        finally:
            cursor.close()

    def add_arguments(self, parser):
        parser.add_argument(
            "--prune-stale",
            action="store_true",
            help="Remove local Submission rows not present in the external source.",
        )

    def handle(self, *args, **options):
        connection = connections["default"]
        lock_cursor = self.acquire_lock()
        if connection.vendor == "mysql" and lock_cursor is None:
            self.stdout.write("Another synchronization is already running; skipped.")
            return

        try:
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
            except DuplicateCandidateNationalIDs as exc:
                raise CommandError(f"Synchronization stopped before local changes: {exc}") from exc
        finally:
            if lock_cursor is not None:
                self.release_lock(lock_cursor)

        self.stdout.write(f"External submission records read: {result.external_records_read}")
        self.stdout.write(f"Matched expected candidates: {result.matched_candidates}")
        self.stdout.write(f"Exact-ID matches: {result.exact_id_matches}")
        self.stdout.write(f"Corrected-ID matches: {result.corrected_id_matches}")
        self.stdout.write(
            f"Repeated exact-ID rows ignored: {result.duplicate_exact_id_records}"
        )
        self.stdout.write(
            f"Ambiguous external records: {result.ambiguous_external_records}"
        )
        self.stdout.write(
            "Expected candidates involved in ambiguous matches: "
            f"{result.ambiguous_expected_candidates}"
        )
        self.stdout.write(f"Unmatched external records: {result.unmatched_external_records}")
        self.stdout.write(f"Local submissions created: {result.created}")
        self.stdout.write(f"Already existing: {result.already_existing}")
        self.stdout.write(f"Existing submissions updated: {result.updated}")
        self.stdout.write(f"Existing submissions unchanged: {result.unchanged}")
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