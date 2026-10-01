from io import StringIO
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import MagicMock, patch
from django.core.management import call_command

from .models import Candidate, Submission
from .services.administrative_locations import get_rwanda_location_resolver
from .services.candidate_matching import (
    CandidateMatchType,
    analyze_candidate_matches,
)
from .services.candidate_status import candidate_status_queryset, district_counts, filter_candidates
from .services.dashboard import build_dashboard_summary
from .services.external_submissions import ExternalSubmission, ExternalSubmissionReader
from .services.reports import build_csv_response, build_report_context
from .services.submission_sync import (
    synchronize_submissions,
)


class DashboardSummaryTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(email="staff@example.com", password="Strong-password-123", is_staff=True)
        Candidate.objects.create(national_id="1199000000000001", full_name="Gasabo Submitted", district="Gasabo", registered_location="Site A")
        Candidate.objects.create(national_id="1199000000000002", full_name="Gasabo Waiting", district="Gasabo", registered_location="Site A")
        Candidate.objects.create(national_id="1199000000000003", full_name="Huye Complete", district="Huye", registered_location="Site B")
        Submission.objects.create(
            national_id="1199000000000001",
            full_name="Gasabo Submitted",
            district="Nyarugenge",
            submitted_location="Gitega / Akabahizi",
        )
        Submission.objects.create(
            national_id="1199000000000003",
            full_name="Huye Complete",
            district="Nyanza",
            submitted_location="Busasamana / Rwesero",
        )

    def test_submission_status_does_not_depend_on_score(self):
        summary = build_dashboard_summary()

        gasabo = next(row for row in summary["districts"] if row["district"] == "Gasabo")
        self.assertEqual(gasabo["submitted_count"], 1)
        self.assertEqual(gasabo["not_submitted_count"], 1)
        self.assertEqual(gasabo["submission_percentage"], 50)
        self.assertTrue(candidate_status_queryset().get(national_id="1199000000000001").has_submission)

    def test_summary_and_candidate_rows_separate_expected_and_submission_districts(self):
        summary = build_dashboard_summary()
        candidate = candidate_status_queryset().get(national_id="1199000000000001")

        self.assertEqual(candidate.district, "Gasabo")
        self.assertEqual(candidate.submission_district, "Nyarugenge")
        self.assertEqual(candidate.submission_location, "Gitega / Akabahizi")
        self.assertEqual(
            summary["submission_districts"],
            [
                {"district": "Nyanza", "submitted_count": 1},
                {"district": "Nyarugenge", "submitted_count": 1},
            ],
        )

    def test_unmatched_expected_candidate_is_not_submitted(self):
        summary = build_dashboard_summary()

        self.assertEqual(summary["total_expected"], 3)
        self.assertEqual(summary["total_submitted"], 2)
        self.assertEqual(summary["total_not_submitted"], 1)
        for row in summary["districts"]:
            self.assertEqual(row["expected_count"], row["submitted_count"] + row["not_submitted_count"])

    def test_district_status_and_search_filters(self):
        queryset = filter_candidates(
            candidate_status_queryset(),
            district="Gasabo",
            status="not_submitted",
            search="Waiting",
        )

        self.assertEqual(list(queryset.values_list("full_name", flat=True)), ["Gasabo Waiting"])

    def test_fully_submitted_district_is_complete(self):
        summary = district_counts("Huye")

        self.assertEqual(summary["expected_count"], 1)
        self.assertEqual(summary["submitted_count"], 1)
        self.assertEqual(summary["not_submitted_count"], 0)
        self.assertEqual(summary["submission_percentage"], 100)
        self.assertEqual(summary["status"], "Complete")

    def test_monitoring_pages_are_protected_and_filterable(self):
        self.client.login(email="staff@example.com", password="Strong-password-123")

        self.assertEqual(self.client.get("/sites/").status_code, 200)
        response = self.client.get("/sites/Gasabo/", {"status": "not_submitted", "search": "1199000000000002"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gasabo Waiting")
        self.assertNotContains(response, "Gasabo Submitted")
        self.assertNotContains(response, "Score")
        self.assertNotContains(response, "Submitted at")

        self.assertEqual(self.client.get("/reports/").status_code, 200)
        self.assertContains(self.client.get("/reports/"), "Expected district / site submission summary")
        self.assertEqual(self.client.get("/settings/").status_code, 200)
        self.assertContains(self.client.get("/settings/"), "Signed-in staff account")
        self.assertEqual(self.client.get("/candidates/").status_code, 404)
        self.assertEqual(self.client.get("/not-submitted/").status_code, 404)

    def test_dashboard_requires_login(self):
        response = self.client.get("/")

        self.assertRedirects(response, "/accounts/login/?next=/")

    def test_logged_in_staff_can_view_dashboard(self):
        self.client.login(email="staff@example.com", password="Strong-password-123")

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "staff@example.com")

    def test_report_summary_counts_and_percentage_are_consistent(self):
        report = build_report_context()

        self.assertEqual(report["summary"]["expected_count"], 3)
        self.assertEqual(report["summary"]["submitted_count"], 2)
        self.assertEqual(report["summary"]["not_submitted_count"], 1)
        self.assertEqual(report["summary"]["submission_percentage"], 2 / 3 * 100)
        for row in report["districts"]:
            self.assertEqual(row["expected_count"], row["submitted_count"] + row["not_submitted_count"])

    def test_report_combined_filters_apply_to_summary_and_candidates(self):
        report = build_report_context(district="Gasabo", status="not_submitted")

        self.assertEqual(report["summary"]["expected_count"], 1)
        self.assertEqual(report["summary"]["submitted_count"], 0)
        self.assertEqual(list(report["candidates"].values_list("full_name", flat=True)), ["Gasabo Waiting"])

        report = build_report_context(status="submitted", search="Gasabo")
        self.assertEqual(list(report["candidates"].values_list("full_name", flat=True)), ["Gasabo Submitted"])

    def test_report_csv_contains_only_filtered_candidates(self):
        csv_text = build_csv_response(build_report_context(district="Gasabo", status="not_submitted")["candidates"])

        self.assertIn("Candidate Name,National ID,Expected District/Site,Submission District", csv_text)
        self.assertNotIn("Score", csv_text)
        self.assertNotIn("Submitted At", csv_text)
        self.assertIn("Gasabo Waiting", csv_text)
        self.assertNotIn("Gasabo Submitted", csv_text)
        self.assertNotIn("Huye Complete", csv_text)

        self.client.login(email="staff@example.com", password="Strong-password-123")
        response = self.client.get("/reports/export.csv", {"district": "Gasabo", "status": "not_submitted"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Gasabo Waiting", response.content.decode())


class ExternalSubmissionReaderTests(TestCase):
    def test_uses_submissions_database_and_only_selects_monitoring_fields(self):
        connection = MagicMock()
        connection.ops.quote_name.side_effect = lambda name: f"`{name}`"
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            ("1199000000000001", 11, "External Candidate", "078 123-456", 1, 1, 42)
        ]

        with patch("monitoring.services.external_submissions.connections") as connections_mock:
            connections_mock.__getitem__.return_value = connection
            rows = ExternalSubmissionReader().read()

        connections_mock.__getitem__.assert_called_once_with("submissions_db")
        query = cursor.execute.call_args.args[0]
        self.assertTrue(query.lstrip().upper().startswith("SELECT"))
        for forbidden in ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "SCORE", "MARK", "EXAM_END"):
            self.assertNotIn(forbidden, query.upper())
        self.assertEqual(
            rows,
            [
                ExternalSubmission(
                    "1199000000000001",
                    "11",
                    "External Candidate",
                    "078 123-456",
                    "Nyarugenge",
                    "Gitega",
                    "Akabahizi",
                    42,
                )
            ],
        )
        self.assertTrue(rows[0].location_resolved)


class CandidateMatchingTests(TestCase):
    def make_candidate(self, national_id, **overrides):
        candidate = {
            "national_id": national_id,
            "full_name": "Expected Candidate",
            "phone_number": "078 123-456",
            "district": "Nyarugenge",
            "sector": "Gitega",
            "cell": "Akabahizi",
        }
        candidate.update(overrides)
        return candidate

    def make_external(self, national_id, **overrides):
        record = ExternalSubmission(
            national_id,
            "11",
            " expected   candidate ",
            "078123456",
            "NYARUGENGE",
            " gitega ",
            "Akabahizi",
        )
        return ExternalSubmission(
            record.national_id,
            record.district_code,
            overrides.get("full_name", record.full_name),
            overrides.get("phone_number", record.phone_number),
            overrides.get("district", record.district),
            overrides.get("sector", record.sector),
            overrides.get("cell", record.cell),
        )

    def test_unique_secondary_match_requires_all_normalized_fields(self):
        candidate = self.make_candidate("1199000000000001")
        external = self.make_external("1199000000000099")

        result = analyze_candidate_matches([candidate], [external])

        self.assertEqual(len(result.corrected_id_matches), 1)
        self.assertEqual(
            result.corrected_id_matches[0].candidate_national_id,
            candidate["national_id"],
        )
        self.assertIs(
            result.corrected_id_matches[0].match_type,
            CandidateMatchType.CORRECTED_ID_MATCH,
        )
        self.assertFalse(result.ambiguous_external_submissions)
        self.assertFalse(result.unmatched_external_submissions)

    def test_exact_match_prevents_secondary_rematching(self):
        candidate = self.make_candidate("1199000000000001")
        exact = self.make_external(candidate["national_id"])
        alternative = self.make_external("1199000000000099")

        result = analyze_candidate_matches([candidate], [exact, alternative])

        self.assertEqual(len(result.exact_id_matches), 1)
        self.assertEqual(len(result.corrected_id_matches), 0)
        self.assertEqual(len(result.ambiguous_external_submissions), 1)
        self.assertEqual(len(result.unmatched_external_submissions), 0)

    def test_duplicate_expected_identity_is_ambiguous(self):
        candidates = [
            self.make_candidate("1199000000000001"),
            self.make_candidate("1199000000000002"),
        ]

        result = analyze_candidate_matches(
            candidates, [self.make_external("1199000000000099")]
        )

        self.assertEqual(len(result.corrected_id_matches), 0)
        self.assertEqual(len(result.ambiguous_external_submissions), 1)

    def test_multiple_external_submissions_for_one_identity_are_ambiguous(self):
        candidate = self.make_candidate("1199000000000001")
        records = [
            self.make_external("1199000000000098"),
            self.make_external("1199000000000099"),
        ]

        result = analyze_candidate_matches([candidate], records)

        self.assertEqual(len(result.corrected_id_matches), 0)
        self.assertEqual(len(result.ambiguous_external_submissions), 2)
        self.assertEqual(len(result.unmatched_external_submissions), 0)

    def test_name_punctuation_is_not_removed(self):
        candidate = self.make_candidate("1199000000000001", full_name="John-Doe")
        external = self.make_external("1199000000000099", full_name="John Doe")

        result = analyze_candidate_matches([candidate], [external])

        self.assertEqual(len(result.corrected_id_matches), 0)
        self.assertEqual(len(result.unmatched_external_submissions), 1)


class AdministrativeLocationResolverTests(TestCase):
    def test_codes_are_resolved_with_their_hierarchical_parents(self):
        resolver = get_rwanda_location_resolver()

        self.assertEqual(
            resolver.resolve(11, 1, 1),
            ("Nyarugenge", "Gitega", "Akabahizi"),
        )
        self.assertEqual(
            resolver.resolve(12, 1, 1),
            ("Gasabo", "Bumbogo", "Kinyaga"),
        )


class SubmissionMatchAnalysisCommandTests(TestCase):
    def test_command_reports_corrected_match_without_changing_candidate_population(self):
        candidate = Candidate.objects.create(
            national_id="1199000000000001",
            full_name="Expected Candidate",
            district="Nyarugenge",
            sector="Gitega",
            cell="Akabahizi",
            phone_number="078 123-456",
        )
        output = StringIO()
        external = ExternalSubmission(
            "1199000000000099",
            "11",
            " expected candidate ",
            "078123456",
            "Nyarugenge",
            "Gitega",
            "Akabahizi",
        )

        with patch(
            "monitoring.management.commands.analyze_submission_matches.ExternalSubmissionReader"
        ) as reader:
            reader.return_value.read.return_value = [external]
            call_command("analyze_submission_matches", stdout=output)

        report = output.getvalue()
        self.assertIn("Total expected candidates: 1", report)
        self.assertIn("Corrected-ID matches: 1", report)
        self.assertIn("Final submitted candidates: 1", report)
        self.assertIn("Final not-submitted candidates: 0", report)
        self.assertIn("Expected population invariant: 1 + 0 = 1", report)
        self.assertIn("External rows with duplicate IDs: 0 groups, 0 additional rows", report)
        self.assertIn("External submissions with unresolved location codes: 0", report)
        self.assertIn("external ID ending ************0099", report)
        self.assertNotIn("1199000000000099", report)
        self.assertEqual(Candidate.objects.count(), 1)
        self.assertFalse(Submission.objects.exists())


class SubmissionSyncTests(TestCase):
    def setUp(self):
        self.candidate = Candidate.objects.create(
            national_id="1199000000000001",
            full_name="Expected Candidate",
            district="Rulindo",
            registered_location="Expected Site",
        )

    def test_matching_external_id_stores_external_district_without_changing_candidate(self):
        result = synchronize_submissions([ExternalSubmission("1199000000000001", "11")])

        candidate = candidate_status_queryset().get(national_id=self.candidate.national_id)
        submission = Submission.objects.get(national_id=self.candidate.national_id)
        self.assertTrue(candidate.has_submission)
        self.assertIsNone(submission.score)
        self.assertIsNone(submission.submitted_at)
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.district, "Rulindo")
        self.assertEqual(submission.district, "Nyarugenge")
        self.assertEqual(result.district_mismatches, 1)

    def test_candidate_without_external_match_is_not_submitted(self):
        synchronize_submissions([])

        candidate = candidate_status_queryset().get(national_id=self.candidate.national_id)
        self.assertFalse(candidate.has_submission)

    def test_unique_corrected_identity_creates_submission_for_expected_id(self):
        self.candidate.full_name = "Expected Candidate"
        self.candidate.district = "Nyarugenge"
        self.candidate.sector = "Gitega"
        self.candidate.cell = "Akabahizi"
        self.candidate.phone_number = "078 123-456"
        self.candidate.save()
        corrected_external_id = "1199000000000099"

        external_records = [
            ExternalSubmission(
                corrected_external_id,
                "11",
                " expected   candidate ",
                "078123456",
                "NYARUGENGE",
                "gitega",
                "Akabahizi",
                88,
            )
        ]
        result = synchronize_submissions(external_records)
        repeated_result = synchronize_submissions(external_records)

        self.assertEqual(result.exact_id_matches, 0)
        self.assertEqual(result.corrected_id_matches, 1)
        self.assertEqual(result.matched_candidates, 1)
        self.assertEqual(repeated_result.corrected_id_matches, 1)
        self.assertEqual(repeated_result.created, 0)
        self.assertEqual(repeated_result.updated, 0)
        self.assertEqual(repeated_result.unchanged, 1)
        self.assertTrue(
            candidate_status_queryset().get(
                national_id=self.candidate.national_id
            ).has_submission
        )
        self.assertTrue(Submission.objects.filter(national_id=self.candidate.national_id).exists())
        submission = Submission.objects.get(national_id=self.candidate.national_id)
        self.assertEqual(submission.source_national_id, corrected_external_id)
        self.assertEqual(submission.full_name, " expected   candidate ")
        self.assertEqual(submission.phone_number, "078123456")
        self.assertEqual(submission.district, "NYARUGENGE")
        self.assertEqual(submission.submitted_location, "gitega / Akabahizi")
        self.assertEqual(submission.source_record_id, 88)
        self.assertFalse(Submission.objects.filter(national_id=corrected_external_id).exists())
        self.assertEqual(Candidate.objects.count(), 1)

    def test_ambiguous_corrected_identity_does_not_create_submission(self):
        self.candidate.full_name = "Expected Candidate"
        self.candidate.district = "Nyarugenge"
        self.candidate.sector = "Gitega"
        self.candidate.cell = "Akabahizi"
        self.candidate.phone_number = "078 123-456"
        self.candidate.save()
        Candidate.objects.create(
            national_id="1199000000000002",
            full_name="Expected Candidate",
            district="Nyarugenge",
            sector="Gitega",
            cell="Akabahizi",
            phone_number="078123456",
        )

        result = synchronize_submissions(
            [
                ExternalSubmission(
                    "1199000000000099",
                    "11",
                    "Expected Candidate",
                    "078123456",
                    "Nyarugenge",
                    "Gitega",
                    "Akabahizi",
                )
            ]
        )

        self.assertEqual(result.corrected_id_matches, 0)
        self.assertEqual(result.ambiguous_external_records, 1)
        self.assertEqual(result.matched_candidates, 0)
        self.assertEqual(Submission.objects.count(), 0)
        self.assertEqual(Candidate.objects.count(), 2)

    def test_running_sync_twice_does_not_create_duplicates(self):
        external_records = [ExternalSubmission("1199000000000001", "12")]

        first_result = synchronize_submissions(external_records)
        second_result = synchronize_submissions(external_records)

        self.assertEqual(first_result.created, 1)
        self.assertEqual(second_result.created, 0)
        self.assertEqual(second_result.already_existing, 1)
        self.assertEqual(second_result.updated, 0)
        self.assertEqual(second_result.unchanged, 1)
        self.assertEqual(Submission.objects.filter(national_id=self.candidate.national_id).count(), 1)

    def test_repeated_exact_id_rows_count_as_one_candidate_submission(self):
        duplicate_records = [
            ExternalSubmission("1199000000000001", "11", "Older", "078111111", "Nyarugenge", "Gitega", "Akabahizi", 41),
            ExternalSubmission("1199000000000001", "11", "Latest", "078222222", "Nyarugenge", "Gitega", "Akabeza", 43),
            ExternalSubmission("1199000000000001", "11", "Middle", "078333333", "Nyarugenge", "Gitega", "Akabahizi", 42),
        ]

        result = synchronize_submissions(duplicate_records)
        repeated_result = synchronize_submissions(duplicate_records)

        self.assertEqual(result.exact_id_matches, 1)
        self.assertEqual(result.duplicate_exact_id_records, 2)
        self.assertEqual(result.matched_candidates, 1)
        self.assertEqual(repeated_result.created, 0)
        self.assertEqual(repeated_result.updated, 0)
        self.assertEqual(repeated_result.unchanged, 1)
        self.assertEqual(Submission.objects.count(), 1)
        submission = Submission.objects.get(national_id=self.candidate.national_id)
        self.assertEqual(submission.full_name, "Latest")
        self.assertEqual(submission.phone_number, "078222222")
        self.assertEqual(submission.source_record_id, 43)

    def test_prune_stale_removes_unmatched_local_submissions(self):
        Submission.objects.create(national_id="1199000000000099", full_name="Dummy row")

        result = synchronize_submissions(
            [ExternalSubmission("1199000000000001", "11")],
            prune_stale=True,
        )

        self.assertEqual(result.stale_removed, 1)
        self.assertFalse(Submission.objects.filter(national_id="1199000000000099").exists())

    def test_prune_stale_preserves_candidates_in_ambiguous_corrected_match(self):
        self.candidate.full_name = "Expected Candidate"
        self.candidate.district = "Nyarugenge"
        self.candidate.sector = "Gitega"
        self.candidate.cell = "Akabahizi"
        self.candidate.phone_number = "078123456"
        self.candidate.save()
        other_candidate = Candidate.objects.create(
            national_id="1199000000000002",
            full_name="Expected Candidate",
            district="Nyarugenge",
            sector="Gitega",
            cell="Akabahizi",
            phone_number="078123456",
        )
        Submission.objects.create(national_id=self.candidate.national_id)
        Submission.objects.create(national_id=other_candidate.national_id)
        Submission.objects.create(national_id="1199000000000098", full_name="Stale row")

        result = synchronize_submissions(
            [
                ExternalSubmission(
                    "1199000000000099",
                    "11",
                    "Expected Candidate",
                    "078123456",
                    "Nyarugenge",
                    "Gitega",
                    "Akabahizi",
                )
            ],
            prune_stale=True,
        )

        self.assertEqual(result.ambiguous_expected_candidates, 2)
        self.assertEqual(result.stale_removed, 1)
        self.assertTrue(Submission.objects.filter(national_id=self.candidate.national_id).exists())
        self.assertTrue(Submission.objects.filter(national_id=other_candidate.national_id).exists())
        self.assertFalse(Submission.objects.filter(national_id="1199000000000098").exists())

    def test_sync_command_reports_counts_without_printing_national_ids(self):
        records = [
            ExternalSubmission("1199000000000001", "11"),
            ExternalSubmission("1199000000000099", "21"),
        ]
        output = StringIO()
        with patch("monitoring.management.commands.sync_submissions.ExternalSubmissionReader") as reader:
            reader.return_value.read.return_value = records
            call_command("sync_submissions", stdout=output)

        report = output.getvalue()
        self.assertIn("External submission records read: 2", report)
        self.assertIn("Matched expected candidates: 1", report)
        self.assertIn("Exact-ID matches: 1", report)
        self.assertIn("Corrected-ID matches: 0", report)
        self.assertIn("Unmatched external records: 1", report)
        self.assertIn("Local submissions created: 1", report)
        self.assertNotIn("1199000000000001", report)

    def test_sync_command_skips_when_another_run_holds_the_lock(self):
        output = StringIO()
        connection = MagicMock()
        connection.vendor = "mysql"
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = (0,)

        with (
            patch(
                "monitoring.management.commands.sync_submissions.connections"
            ) as connections_mock,
            patch(
                "monitoring.management.commands.sync_submissions.ExternalSubmissionReader"
            ) as reader,
        ):
            connections_mock.__getitem__.return_value = connection
            call_command("sync_submissions", stdout=output)

        self.assertIn("Another synchronization is already running; skipped.", output.getvalue())
        reader.return_value.read.assert_not_called()
        cursor.close.assert_called_once()
