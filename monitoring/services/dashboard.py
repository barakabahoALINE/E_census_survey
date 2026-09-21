from .submissions import DjangoSubmissionRepository, SubmissionRepository
from .candidate_status import candidate_status_queryset, district_summary_rows


def build_dashboard_summary(repository: SubmissionRepository | None = None) -> dict:
    repository = repository or DjangoSubmissionRepository()
    submitted_ids = repository.national_ids()
    expected_ids = set(candidate_status_queryset().values_list("national_id", flat=True))
    return {
        "total_expected": len(expected_ids),
        "total_submitted": len(expected_ids & submitted_ids),
        "total_not_submitted": len(expected_ids - submitted_ids),
        "districts": district_summary_rows(),
    }
