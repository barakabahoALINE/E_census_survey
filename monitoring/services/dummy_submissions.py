import random

from monitoring.models import Candidate, Submission


def seed_dummy_submissions(submitted_rate: float = 0.72, seed: int = 20260921, replace: bool = False) -> tuple[int, int]:
    candidates = list(Candidate.objects.order_by("national_id"))
    if replace:
        Submission.objects.all().delete()

    randomizer = random.Random(seed)
    submitted = 0
    for candidate in candidates:
        if randomizer.random() > submitted_rate:
            continue
        Submission.objects.update_or_create(
            national_id=candidate.national_id,
            defaults={
                "full_name": candidate.full_name,
                "district": candidate.district,
                "submitted_location": candidate.registered_location or candidate.district,
                "score": None,
                "submitted_at": None,
            },
        )
        submitted += 1
    return submitted, len(candidates)
