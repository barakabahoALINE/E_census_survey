from django.core.management.base import BaseCommand

from monitoring.services.dummy_submissions import seed_dummy_submissions


class Command(BaseCommand):
    help = "Create realistic dummy submissions for imported candidates."

    def add_arguments(self, parser):
        parser.add_argument("--submitted-rate", type=float, default=0.72)
        parser.add_argument("--seed", type=int, default=20260921)
        parser.add_argument("--replace", action="store_true")

    def handle(self, *args, **options):
        submitted, candidate_count = seed_dummy_submissions(
            submitted_rate=options["submitted_rate"],
            seed=options["seed"],
            replace=options["replace"],
        )
        if not candidate_count:
            self.stdout.write(self.style.WARNING("No candidates found. Import the Excel workbook first."))
            return
        self.stdout.write(self.style.SUCCESS(f"Seeded {submitted} dummy submissions for {candidate_count} candidates."))
