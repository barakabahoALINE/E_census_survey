from django.db.models import Count

from monitoring.models import Submission

from .submissions import DjangoSubmissionRepository, SubmissionRepository
from .candidate_status import candidate_status_queryset, district_summary_rows


def build_dashboard_summary(repository: SubmissionRepository | None = None) -> dict:
    repository = repository or DjangoSubmissionRepository()
    submitted_ids = repository.national_ids()
    expected_ids = set(candidate_status_queryset().values_list("national_id", flat=True))
    submission_districts = list(
        Submission.objects.filter(national_id__in=expected_ids)
        .exclude(district="")
        .values("district")
        .annotate(submitted_count=Count("id"))
        .order_by("district")
    )
    return {
        "total_expected": len(expected_ids),
        "total_submitted": len(expected_ids & submitted_ids),
        "total_not_submitted": len(expected_ids - submitted_ids),
        "districts": district_summary_rows(),
        "submission_districts": submission_districts,
    }
