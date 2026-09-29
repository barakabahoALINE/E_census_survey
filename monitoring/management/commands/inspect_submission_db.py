from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = "Read a small, privacy-conscious sample from the external exam_rec table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=5,
            choices=range(1, 11),
            help="Number of sample rows to read (1-10; default: 5).",
        )

    def handle(self, *args, **options):
        connection = connections["submissions_db"]
        try:
            connection.ensure_connection()
        except Exception as exc:
            raise CommandError(
                "Could not connect to the submissions_db database. "
                "Check its environment variables and read-only credentials."
            ) from exc

        fields = (
            ("exam_rec", "exam_rec-id"),
            ("exam_rec", "level-1-id"),
            ("exam_rec", "names"),
            ("level-1", "id_number"),
            ("exam_rec", "prov1"),
            ("exam_rec", "dist1"),
            ("exam_rec", "sect1"),
            ("exam_rec", "cell1"),
            ("exam_rec", "vill1"),
            ("exam_rec", "vill2"),
            ("exam_rec", "date_of_exam"),
        )
        quote = connection.ops.quote_name
        select_clause = ", ".join(
            f"{quote(table)}.{quote(field)} AS {quote(field)}"
            for table, field in fields
        )
        query = (
            f"SELECT {select_clause} "
            f"FROM {quote('exam_rec')} "
            f"LEFT JOIN {quote('level-1')} "
            f"ON {quote('exam_rec')}.{quote('level-1-id')} "
            f"= {quote('level-1')}.{quote('level-1-id')} "
            f"ORDER BY {quote('exam_rec')}.{quote('exam_rec-id')} "
            f"LIMIT {options['limit']}"
        )
        with connection.cursor() as cursor:
            try:
                cursor.execute(query)
                rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
            except Exception as exc:
                raise CommandError(
                    "Could not read the selected exam_rec sample fields. "
                    "Check the external schema and read-only credentials."
                ) from exc

        self.stdout.write(self.style.SUCCESS(f"Read {len(rows)} exam_rec sample row(s)."))
        for index, row in enumerate(rows, start=1):
            self.stdout.write(f"\nRecord {index}:")
            for column, value in zip(columns, row):
                if column == "names" and value:
                    value = "[redacted]"
                elif column == "id_number" and value:
                    value = f"{'*' * max(0, len(str(value)) - 4)}{str(value)[-4:]}"
                self.stdout.write(f"  {column}: {value}")
        self.stdout.write("\nRead-only SELECT; no data was changed.")