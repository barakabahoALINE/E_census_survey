from dataclasses import dataclass

from django.db import connections

from .administrative_locations import (
    get_rwanda_location_resolver,
    normalize_location_code,
)


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
    full_name: str = ""
    phone_number: str = ""
    district: str = ""
    sector: str = ""
    cell: str = ""
    record_id: int | None = None

    @property
    def location_resolved(self) -> bool:
        return bool(self.district and self.sector and self.cell)


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
        names = quote("names")
        phone_number = quote("phone_number")
        sect1 = quote("sect1")
        cell1 = quote("cell1")
        exam_rec_id = quote("exam_rec-id")

        query = (
            f"SELECT TRIM(level_one.{id_number}), exam_rec.{dist1}, "
            f"exam_rec.{names}, exam_rec.{phone_number}, "
            f"exam_rec.{sect1}, exam_rec.{cell1}, exam_rec.{exam_rec_id} "
            f"FROM {exam_rec} AS exam_rec "
            f"INNER JOIN {level_one} AS level_one "
            f"ON exam_rec.{level_one_id} = level_one.{level_one_id} "
            f"ORDER BY exam_rec.{exam_rec_id} "
        )

        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        resolver = get_rwanda_location_resolver()
        records = []
        for (
            national_id,
            district_code,
            full_name,
            phone,
            sector_code,
            cell_code,
            record_id,
        ) in rows:
            normalized_district_code = normalize_location_code(district_code) or None
            location = resolver.resolve(district_code, sector_code, cell_code)
            records.append(
                ExternalSubmission(
                    national_id=(str(national_id).strip() or None)
                    if national_id is not None
                    else None,
                    district_code=normalized_district_code,
                    full_name=str(full_name or "").strip(),
                    phone_number=str(phone or "").strip(),
                    district=location[0] if location else "",
                    sector=location[1] if location else "",
                    cell=location[2] if location else "",
                    record_id=int(record_id) if record_id is not None else None,
                )
            )
        return records