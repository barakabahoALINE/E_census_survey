import random
from datetime import timedelta

from django.utils import timezone

from monitoring.models import Candidate, Submission


def seed_dummy_submissions(submitted_rate: float = 0.72, seed: int = 20260921, replace: bool = False) -> tuple[int, int]:
    candidates = list(Candidate.objects.order_by("national_id"))
    if replace:
        Submission.objects.all().delete()

    randomizer = random.Random(seed)
    submitted = 0
    now = timezone.now()
    for candidate in candidates:
        if randomizer.random() > submitted_rate:
            continue
        Submission.objects.update_or_create(
            national_id=candidate.national_id,
            defaults={
                "full_name": candidate.full_name,
                "district": candidate.district,
                "submitted_location": candidate.registered_location or candidate.district,
                "score": randomizer.choice([0, 0, 35, 48, 62, 71, 84, 91]),
                "submitted_at": now - timedelta(minutes=randomizer.randint(10, 420)),
            },
        )
        submitted += 1
    return submitted, len(candidates)
