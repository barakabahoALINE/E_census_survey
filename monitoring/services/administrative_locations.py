import csv
import re
import unicodedata
from collections import defaultdict
from functools import lru_cache
from pathlib import Path


REFERENCE_PATH = Path(__file__).resolve().parents[1] / "data" / "rwanda_admin_locations.csv"


def normalize_location_label(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def normalize_location_code(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else text


class RwandaAdministrativeLocationResolver:
    def __init__(self, reference_path: Path = REFERENCE_PATH):
        self._districts = defaultdict(set)
        self._sectors = defaultdict(set)
        self._cells = defaultdict(set)

        with reference_path.open(encoding="utf-8-sig", newline="") as reference_file:
            for row in csv.DictReader(reference_file):
                district_code = normalize_location_code(row["district_code"])
                sector_code = normalize_location_code(row["sector_code"])
                cell_code = normalize_location_code(row["cell_code"])
                district = row["district"].strip()
                sector = row["sector"].strip()
                cell = row["cell"].strip()

                if district_code and district:
                    self._districts[district_code].add(district)
                if district_code and sector_code and sector:
                    self._sectors[(district_code, sector_code)].add(sector)
                if district_code and sector_code and cell_code and cell:
                    self._cells[(district_code, sector_code, cell_code)].add(cell)

    @staticmethod
    def _unique_label(labels: set[str]) -> str | None:
        normalized_labels = {normalize_location_label(label): label for label in labels}
        if len(normalized_labels) != 1:
            return None
        return next(iter(normalized_labels.values()))

    def resolve(
        self, district_code: object, sector_code: object, cell_code: object
    ) -> tuple[str, str, str] | None:
        district_key = normalize_location_code(district_code)
        sector_key = normalize_location_code(sector_code)
        cell_key = normalize_location_code(cell_code)
        district = self._unique_label(self._districts.get(district_key, set()))
        sector = self._unique_label(
            self._sectors.get((district_key, sector_key), set())
        )
        cell = self._unique_label(
            self._cells.get((district_key, sector_key, cell_key), set())
        )
        if not district or not sector or not cell:
            return None
        return district, sector, cell


@lru_cache(maxsize=1)
def get_rwanda_location_resolver() -> RwandaAdministrativeLocationResolver:
    return RwandaAdministrativeLocationResolver()