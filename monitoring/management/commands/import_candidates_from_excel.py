from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from monitoring.services.candidate_import import import_candidates


class Command(BaseCommand):
    help = "Import expected candidates from the district sheets in an XLSX workbook."

    def add_arguments(self, parser):
        parser.add_argument("workbook", type=Path)
        parser.add_argument("--exam-date", type=date.fromisoformat, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        workbook_path = options["workbook"]
        if not workbook_path.exists():
            raise CommandError(f"Workbook does not exist: {workbook_path}")
        try:
            imported, skipped, warnings = import_candidates(
                workbook_path, options["exam_date"], options["dry_run"]
            )
        except ImportError as exc:
            raise CommandError("Install openpyxl before importing the workbook.") from exc
        for warning in warnings:
            self.stdout.write(self.style.WARNING(warning))
        action = "would import" if options["dry_run"] else "imported"
        self.stdout.write(self.style.SUCCESS(f"{action.capitalize()} {imported} candidates; skipped {skipped} rows."))
