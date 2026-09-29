from io import StringIO
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import MagicMock, patch
from django.core.management import call_command

from .models import Candidate, Submission
from .services.candidate_status import candidate_status_queryset, district_counts, filter_candidates
from .services.dashboard import build_dashboard_summary
from .services.external_submissions import ExternalSubmission, ExternalSubmissionReader
from .services.reports import build_csv_response, build_report_context
from .services.submission_sync import (
    DuplicateExternalNationalIDs,
    synchronize_submissions,
)


class DashboardSummaryTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(email="staff@example.com", password="Strong-password-123", is_staff=True)
        Candidate.objects.create(national_id="1199000000000001", full_name="Gasabo Submitted", district="Gasabo", registered_location="Site A")
        Candidate.objects.create(national_id="1199000000000002", full_name="Gasabo Waiting", district="Gasabo", registered_location="Site A")
        Candidate.objects.create(national_id="1199000000000003", full_name="Huye Complete", district="Huye", registered_location="Site B")
        Submission.objects.create(national_id="1199000000000001", full_name="Gasabo Submitted", district="Gasabo")
        Submission.objects.create(national_id="1199000000000003", full_name="Huye Complete", district="Huye")

    def test_submission_status_does_not_depend_on_score(self):
        summary = build_dashboard_summary()

        gasabo = next(row for row in summary["districts"] if row["district"] == "Gasabo")
        self.assertEqual(gasabo["submitted_count"], 1)
        self.assertEqual(gasabo["not_submitted_count"], 1)
        self.assertEqual(gasabo["submission_percentage"], 50)
        self.assertTrue(candidate_status_queryset().get(national_id="1199000000000001").has_submission)

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
        self.assertContains(self.client.get("/reports/"), "District / Site submission summary")
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

        self.assertIn("Candidate Name,National ID,District/Site", csv_text)
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
        cursor.fetchall.return_value = [("1199000000000001", 11)]

        with patch("monitoring.services.external_submissions.connections") as connections_mock:
            connections_mock.__getitem__.return_value = connection
            rows = ExternalSubmissionReader().read()

        connections_mock.__getitem__.assert_called_once_with("submissions_db")
        query = cursor.execute.call_args.args[0]
        self.assertTrue(query.lstrip().upper().startswith("SELECT"))
        for forbidden in ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "SCORE", "MARK", "EXAM_END"):
            self.assertNotIn(forbidden, query.upper())
        self.assertEqual(rows, [ExternalSubmission("1199000000000001", "11")])


class SubmissionSyncTests(TestCase):
    def setUp(self):
        self.candidate = Candidate.objects.create(
            national_id="1199000000000001",
            full_name="Expected Candidate",
            district="Rulindo",
            registered_location="Expected Site",
        )

    def test_matching_external_id_is_submitted_without_score_and_keeps_expected_district(self):
        result = synchronize_submissions([ExternalSubmission("1199000000000001", "11")])

        candidate = candidate_status_queryset().get(national_id=self.candidate.national_id)
        submission = Submission.objects.get(national_id=self.candidate.national_id)
        self.assertTrue(candidate.has_submission)
        self.assertIsNone(submission.score)
        self.assertIsNone(submission.submitted_at)
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.district, "Rulindo")
        self.assertEqual(submission.district, "Rulindo")
        self.assertEqual(result.district_mismatches, 1)

    def test_candidate_without_external_match_is_not_submitted(self):
        synchronize_submissions([])

        candidate = candidate_status_queryset().get(national_id=self.candidate.national_id)
        self.assertFalse(candidate.has_submission)

    def test_running_sync_twice_does_not_create_duplicates(self):
        external_records = [ExternalSubmission("1199000000000001", "12")]

        first_result = synchronize_submissions(external_records)
        second_result = synchronize_submissions(external_records)

        self.assertEqual(first_result.created, 1)
        self.assertEqual(second_result.created, 0)
        self.assertEqual(second_result.already_existing, 1)
        self.assertEqual(Submission.objects.filter(national_id=self.candidate.national_id).count(), 1)

    def test_duplicate_external_ids_abort_before_local_writes(self):
        duplicate_records = [
            ExternalSubmission("1199000000000001", "11"),
            ExternalSubmission("1199000000000001", "11"),
        ]

        with self.assertRaises(DuplicateExternalNationalIDs):
            synchronize_submissions(duplicate_records)

        self.assertEqual(Submission.objects.count(), 0)

    def test_prune_stale_removes_unmatched_local_submissions(self):
        Submission.objects.create(national_id="1199000000000099", full_name="Dummy row")

        result = synchronize_submissions(
            [ExternalSubmission("1199000000000001", "11")],
            prune_stale=True,
        )

        self.assertEqual(result.stale_removed, 1)
        self.assertFalse(Submission.objects.filter(national_id="1199000000000099").exists())

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
        self.assertIn("Unmatched external records: 1", report)
        self.assertIn("Local submissions created: 1", report)
        self.assertNotIn("1199000000000001", report)
