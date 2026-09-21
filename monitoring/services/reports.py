import csv
from io import StringIO

from .candidate_status import build_counts, candidate_status_queryset, filter_candidates


def build_report_context(*, district="", status="all", search=""):
    candidates = filter_candidates(
        candidate_status_queryset(),
        district=district,
        status=status,
        search=search,
    )
    expected_count = candidates.count()
    submitted_count = candidates.filter(has_submission=True).count()
    summary = build_counts("All selected candidates", expected_count, submitted_count)

    district_rows = []
    for selected_district in candidates.values_list("district", flat=True).distinct().order_by("district"):
        district_candidates = candidates.filter(district=selected_district)
        district_expected = district_candidates.count()
        district_submitted = district_candidates.filter(has_submission=True).count()
        district_rows.append(build_counts(selected_district, district_expected, district_submitted))

    return {
        "summary": summary,
        "districts": district_rows,
        "candidates": candidates,
    }


def candidate_report_rows(candidates):
    for candidate in candidates:
        submitted = candidate.has_submission
        yield [
            candidate.full_name,
            candidate.national_id,
            candidate.district,
            candidate.registered_location or "-",
            "Submitted" if submitted else "Not Submitted",
            candidate.submission_score if submitted and candidate.submission_score is not None else "-",
            candidate.submission_submitted_at.strftime("%Y-%m-%d %H:%M") if submitted and candidate.submission_submitted_at else "-",
        ]


def build_csv_response(candidates):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Candidate Name",
        "National ID",
        "District/Site",
        "Registered Location",
        "Submission Status",
        "Score",
        "Submitted At",
    ])
    writer.writerows(candidate_report_rows(candidates))
    return output.getvalue()
