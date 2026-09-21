from typing import Protocol

from monitoring.models import Submission


class SubmissionRepository(Protocol):
    def national_ids(self) -> set[str]: ...

    def by_national_id(self, national_id: str) -> Submission | None: ...


class DjangoSubmissionRepository:
    """Temporary source boundary for submissions."""

    def national_ids(self) -> set[str]:
        return set(Submission.objects.values_list("national_id", flat=True))

    def by_national_id(self, national_id: str) -> Submission | None:
        return Submission.objects.filter(national_id=national_id).first()
