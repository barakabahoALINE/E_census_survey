from django.test import TestCase
from django.contrib.auth import get_user_model

from .models import Candidate, Submission
from .services.candidate_status import candidate_status_queryset, district_counts, filter_candidates
from .services.dashboard import build_dashboard_summary
from .services.reports import build_csv_response, build_report_context


class DashboardSummaryTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(email="staff@example.com", password="Strong-password-123", is_staff=True)
        Candidate.objects.create(national_id="1199000000000001", full_name="Gasabo Submitted", district="Gasabo", registered_location="Site A")
        Candidate.objects.create(national_id="1199000000000002", full_name="Gasabo Waiting", district="Gasabo", registered_location="Site A")
        Candidate.objects.create(national_id="1199000000000003", full_name="Huye Complete", district="Huye", registered_location="Site B")
        Submission.objects.create(national_id="1199000000000001", full_name="Gasabo Submitted", district="Gasabo", score=0)
        Submission.objects.create(national_id="1199000000000003", full_name="Huye Complete", district="Huye", score=78)

    def test_zero_score_is_a_valid_submission(self):
        summary = build_dashboard_summary()

        gasabo = next(row for row in summary["districts"] if row["district"] == "Gasabo")
        self.assertEqual(gasabo["submitted_count"], 1)
        self.assertEqual(gasabo["not_submitted_count"], 1)
        self.assertEqual(gasabo["submission_percentage"], 50)

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
        self.assertIn("Gasabo Waiting", csv_text)
        self.assertNotIn("Gasabo Submitted", csv_text)
        self.assertNotIn("Huye Complete", csv_text)

        self.client.login(email="staff@example.com", password="Strong-password-123")
        response = self.client.get("/reports/export.csv", {"district": "Gasabo", "status": "not_submitted"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Gasabo Waiting", response.content.decode())
