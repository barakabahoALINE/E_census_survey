from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from monitoring.models import Candidate
from monitoring.services.candidate_matching import analyze_candidate_matches
from monitoring.services.external_submissions import ExternalSubmissionReader


def mask_identifier(value):
    identifier = str(value or "")
    if not identifier:
        return "[blank]"
    return f"{'*' * max(0, len(identifier) - 4)}{identifier[-4:]}"


class Command(BaseCommand):
    help = "Analyze exact and corrected-ID submission matches without changing data."

    def handle(self, *args, **options):
        candidates = list(
            Candidate.objects.values(
                "national_id",
                "full_name",
                "district",
                "sector",
                "cell",
                "phone_number",
            )
        )
        try:
            external_submissions = ExternalSubmissionReader().read()
        except Exception as exc:
            raise CommandError(
                "Could not read exam_rec using the read-only submissions_db connection."
            ) from exc

        analysis = analyze_candidate_matches(candidates, external_submissions)
        external_id_counts = Counter(
            record.national_id.strip()
            for record in external_submissions
            if record.national_id and record.national_id.strip()
        )
        exact_candidate_ids = {
            match.candidate_national_id for match in analysis.exact_id_matches
        }
        matched_candidate_ids = {
            match.candidate_national_id for match in analysis.matches
        }
        total_expected = len(candidates)
        final_submitted = len(matched_candidate_ids)
        final_not_submitted = total_expected - final_submitted

        self.stdout.write(f"Total expected candidates: {total_expected}")
        self.stdout.write(f"Total external exam submissions: {len(external_submissions)}")
        self.stdout.write(
            "External rows with duplicate IDs: "
            f"{sum(count > 1 for count in external_id_counts.values())} groups, "
            f"{sum(count - 1 for count in external_id_counts.values() if count > 1)} "
            "additional rows"
        )
        self.stdout.write(
            "External submissions with unresolved location codes: "
            f"{sum(not record.location_resolved for record in external_submissions)}"
        )
        self.stdout.write(f"Exact-ID matches: {len(exact_candidate_ids)}")
        self.stdout.write(
            "Repeated exact-ID rows ignored: "
            f"{len(analysis.duplicate_exact_id_submissions)}"
        )
        self.stdout.write(
            "Expected candidates remaining after exact matching: "
            f"{total_expected - len(exact_candidate_ids)}"
        )
        self.stdout.write(
            f"Corrected-ID matches: {len(analysis.corrected_id_matches)}"
        )
        self.stdout.write(
            f"Ambiguous external submissions: "
            f"{len(analysis.ambiguous_external_submissions)}"
        )
        self.stdout.write(
            "Expected candidates involved in ambiguous matches: "
            f"{len(analysis.ambiguous_candidate_ids)}"
        )
        self.stdout.write(
            f"Unmatched external submissions: "
            f"{len(analysis.unmatched_external_submissions)}"
        )
        self.stdout.write(f"Final submitted candidates: {final_submitted}")
        self.stdout.write(f"Final not-submitted candidates: {final_not_submitted}")
        self.stdout.write(
            "Expected population invariant: "
            f"{final_submitted} + {final_not_submitted} = {total_expected}"
        )
        self.stdout.write(
            "Match-count invariant: "
            f"{final_submitted} = {len(analysis.exact_id_matches)} + "
            f"{len(analysis.corrected_id_matches)}"
        )

        exact_match = next(iter(analysis.exact_id_matches), None)
        corrected_match = next(iter(analysis.corrected_id_matches), None)
        ambiguous = next(iter(analysis.ambiguous_external_submissions), None)
        unmatched = next(iter(analysis.unmatched_external_submissions), None)
        for label, record in (
            ("Direct ID example", exact_match.external_submission if exact_match else None),
            (
                "Corrected-ID example",
                corrected_match.external_submission if corrected_match else None,
            ),
            ("Ambiguous example", ambiguous),
            ("Unmatched example", unmatched),
        ):
            if record is not None:
                self.stdout.write(
                    f"{label}: external ID ending {mask_identifier(record.national_id)}"
                )
            else:
                self.stdout.write(f"{label}: none")

        self.stdout.write(self.style.SUCCESS("Read-only analysis; no records were changed."))