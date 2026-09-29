from dataclasses import dataclass

from django.db import connections


DISTRICT_CODE_TO_NAME = {
    "11": "Nyarugenge",
    "12": "Gasabo",
    "13": "Kicukiro",
    "21": "Nyanza",
    "22": "Gisagara",
    "23": "Nyaruguru",
    "24": "Huye",
    "25": "Nyamagabe",
    "26": "Ruhango",
    "27": "Muhanga",
    "28": "Kamonyi",
    "31": "Karongi",
    "32": "Rutsiro",
    "33": "Rubavu",
    "34": "Nyabihu",
    "35": "Ngororero",
    "36": "Rusizi",
    "37": "Nyamasheke",
    "41": "Rulindo",
    "42": "Gakenke",
    "43": "Musanze",
    "44": "Burera",
    "45": "Gicumbi",
    "51": "Rwamagana",
    "52": "Nyagatare",
    "53": "Gatsibo",
    "54": "Kayonza",
    "55": "Kirehe",
    "56": "Ngoma",
    "57": "Bugesera",
}


@dataclass(frozen=True)
class ExternalSubmission:
    national_id: str | None
    district_code: str | None


class ExternalSubmissionReader:
    """Read monitoring identifiers from the external CSPro database."""

    def read(self) -> list[ExternalSubmission]:
        connection = connections["submissions_db"]
        quote = connection.ops.quote_name
        exam_rec = quote("exam_rec")
        level_one = quote("level-1")
        level_one_id = quote("level-1-id")
        id_number = quote("id_number")
        dist1 = quote("dist1")

        query = (
            f"SELECT TRIM(level_one.{id_number}), exam_rec.{dist1} "
            f"FROM {exam_rec} AS exam_rec "
            f"INNER JOIN {level_one} AS level_one "
            f"ON exam_rec.{level_one_id} = level_one.{level_one_id} "
        )

        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        return [
            ExternalSubmission(
                national_id=(str(national_id).strip() or None) if national_id is not None else None,
                district_code=str(int(district_code)) if district_code is not None else None,
            )
            for national_id, district_code in rows
        ]