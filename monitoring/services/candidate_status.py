from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Subquery

from monitoring.models import Candidate, Submission


PAGE_SIZE = 25


def candidate_status_queryset():
    """Return candidates annotated with their matching submission details."""
    matching_submissions = Submission.objects.filter(national_id=OuterRef("national_id"))
    return Candidate.objects.annotate(
        has_submission=Exists(matching_submissions),
        submission_score=Subquery(matching_submissions.values("score")[:1]),
        submission_submitted_at=Subquery(matching_submissions.values("submitted_at")[:1]),
    )


def filter_candidates(queryset, *, district="", status="all", search=""):
    if district:
        queryset = queryset.filter(district=district)
    if status == "submitted":
        queryset = queryset.filter(has_submission=True)
    elif status == "not_submitted":
        queryset = queryset.filter(has_submission=False)
    if search:
        queryset = queryset.filter(full_name__icontains=search) | queryset.filter(national_id__icontains=search)
    return queryset.order_by("full_name", "national_id")


def district_summary_rows(queryset=None):
    queryset = queryset or candidate_status_queryset()
    districts = []
    for district in queryset.values_list("district", flat=True).distinct().order_by("district"):
        district_candidates = queryset.filter(district=district)
        expected_count = district_candidates.count()
        submitted_count = district_candidates.filter(has_submission=True).count()
        districts.append(build_counts(district, expected_count, submitted_count))
    return districts


def build_counts(district, expected_count, submitted_count):
    not_submitted_count = expected_count - submitted_count
    percentage = (submitted_count / expected_count * 100) if expected_count else 0
    return {
        "district": district,
        "expected_count": expected_count,
        "submitted_count": submitted_count,
        "not_submitted_count": not_submitted_count,
        "submission_percentage": percentage,
        "status": "Complete" if not_submitted_count == 0 else "Pending",
    }


def district_counts(district):
    district_candidates = candidate_status_queryset().filter(district=district)
    return build_counts(
        district,
        district_candidates.count(),
        district_candidates.filter(has_submission=True).count(),
    )


def paginate_candidates(queryset, page_number):
    return Paginator(queryset, PAGE_SIZE).get_page(page_number)
