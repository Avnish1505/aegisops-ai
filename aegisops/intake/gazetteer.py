"""A Lucknow gazetteer built from OpenStreetMap, and a deterministic geocoder over it.

Entries come from named OSM features inside the district: places (suburbs, neighbourhoods,
villages), landmarks (stations, hospitals, schools, temples and mosques, parks, bridges, markets)
and named roads (placed at the centroid of their geometry, which can be far from a given spot, so
roads rank last). Names are indexed in every script OSM carries (name, name:en, name:hi, alt_name,
old_name, official_name). ``CURATED_ALIASES`` adds Hindi/Hinglish spellings for the exercise
localities that OSM lacks; each points at an OSM feature and is marked as curated.

No paid or online geocoding API is used. Data (c) OpenStreetMap contributors, ODbL 1.0.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from rapidfuzz import fuzz, process

Kind = Literal["place", "landmark", "road"]
KIND_RANK: dict[str, int] = {"place": 0, "landmark": 1, "road": 2}
NAME_KEYS = ("name", "name:en", "name:hi", "alt_name", "old_name", "official_name", "short_name")
DEFAULT_GAZETTEER = Path(__file__).with_name("lucknow_gazetteer.json")
MIN_ALIAS_LENGTH = 4  # Latin script; Devanagari names are shorter in code points ("चौक" is 3)
MIN_ALIAS_LENGTH_OTHER_SCRIPTS = 3
FUZZY_CUTOFF = 88.0

# Spellings reporters use that OSM does not carry. Keys are OSM place names in the gazetteer.
CURATED_ALIASES: dict[str, tuple[str, ...]] = {
    "Charbagh": ("चारबाग", "charbag", "char bagh"),
    "Hazratganj": ("हजरतगंज", "हज़रतगंज", "hazrat ganj", "hazratgunj"),
    "Aminabad": ("अमीनाबाद", "aminabaad"),
    "Chowk": ("चौक", "chauk"),
    "Aliganj": ("अलीगंज", "ali ganj"),
    "Gomti Nagar": ("गोमती नगर", "gomtinagar", "gomati nagar"),
    "Indira Nagar": ("इंदिरा नगर", "इन्दिरा नगर", "indiranagar"),
    "Alambagh": ("आलमबाग", "alam bagh"),
    "Qaisarbagh": ("कैसरबाग", "kaiserbagh", "kaisarbagh", "kaiser bagh", "qaiserbagh"),
}


@dataclass(frozen=True, slots=True)
class GazetteerEntry:
    name: str
    aliases: tuple[str, ...]
    kind: Kind
    lat: float
    lon: float
    osm: str  # e.g. "node/123"
    curated_aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GeocodeResult:
    lat: float
    lon: float
    name: str
    osm: str
    kind: Kind
    method: Literal["exact", "fuzzy"]
    score: float
    matched_text: str


def normalise(text: str) -> str:
    """NFKC, case-fold, drop punctuation (keeping letters in any script and digits)."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = "".join(ch if (ch.isalnum() or unicodedata.category(ch).startswith("M")) else " "
                   for ch in text)
    return re.sub(r"\s+", " ", text).strip()


def _min_length(text: str) -> int:
    return MIN_ALIAS_LENGTH if text.isascii() else MIN_ALIAS_LENGTH_OTHER_SCRIPTS


class Gazetteer:
    def __init__(self, entries: list[GazetteerEntry]) -> None:
        self.entries = entries
        self._index: dict[str, list[int]] = {}
        for number, entry in enumerate(entries):
            for alias in {entry.name, *entry.aliases, *entry.curated_aliases}:
                key = normalise(alias)
                if len(key) >= _min_length(key):
                    self._index.setdefault(key, []).append(number)
        self._aliases = list(self._index)
        self._longest = max((len(a.split()) for a in self._aliases), default=1)

    @classmethod
    def load(cls, path: Path) -> Gazetteer:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            [
                GazetteerEntry(
                    name=item["name"],
                    aliases=tuple(item["aliases"]),
                    kind=item["kind"],
                    lat=item["lat"],
                    lon=item["lon"],
                    osm=item["osm"],
                    curated_aliases=tuple(item.get("curated_aliases", ())),
                )
                for item in raw["entries"]
            ]
        )

    def dump(self, path: Path, source: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "licence": "Data (c) OpenStreetMap contributors, ODbL 1.0",
                    "source": source,
                    "entries": [asdict(entry) for entry in self.entries],
                },
                ensure_ascii=False,
                indent=0,
            )
            + "\n",
            encoding="utf-8",
        )

    def _best(self, indices: list[int]) -> GazetteerEntry:
        return min(
            (self.entries[i] for i in indices), key=lambda e: (KIND_RANK[e.kind], e.osm)
        )

    def geocode(self, text: str) -> GeocodeResult | None:
        """Longest exact alias found in the text wins (places before landmarks before roads);
        failing that, the best fuzzy match of any word span against the aliases."""
        tokens = normalise(text).split()
        if not tokens:
            return None
        spans = [
            (" ".join(tokens[start:start + size]), size)
            for size in range(min(self._longest, len(tokens)), 0, -1)
            for start in range(len(tokens) - size + 1)
        ]
        exact = [(span, size) for span, size in spans if span in self._index]
        if exact:
            span, size = min(
                exact,
                key=lambda item: (
                    -item[1],
                    KIND_RANK[self._best(self._index[item[0]]).kind],
                ),
            )
            return self._result(self._best(self._index[span]), "exact", 100.0, span)
        best: tuple[float, str, str] | None = None
        for span, _ in spans:
            if len(span) < _min_length(span):
                continue
            match = process.extractOne(
                span, self._aliases, scorer=fuzz.ratio, score_cutoff=FUZZY_CUTOFF
            )
            if match is not None and (best is None or match[1] > best[0]):
                best = (match[1], match[0], span)
        if best is None:
            return None
        score, alias, span = best
        return self._result(self._best(self._index[alias]), "fuzzy", score, span)

    @staticmethod
    def _result(
        entry: GazetteerEntry, method: Literal["exact", "fuzzy"], score: float, span: str
    ) -> GeocodeResult:
        return GeocodeResult(
            lat=entry.lat,
            lon=entry.lon,
            name=entry.name,
            osm=entry.osm,
            kind=entry.kind,
            method=method,
            score=score,
            matched_text=span,
        )


LANDMARK_KEYS = {
    "amenity": {"hospital", "police", "fire_station", "school", "college", "university",
                "place_of_worship", "marketplace", "bus_station", "clinic", "townhall"},
    "railway": {"station", "halt"},
    "tourism": None,
    "historic": None,
    "leisure": {"park", "stadium", "garden"},
    "man_made": {"bridge"},
    "bridge": None,
}
ROAD_TYPES = {"trunk", "primary", "secondary", "tertiary", "residential", "unclassified"}


def classify(tags: dict[str, str]) -> Kind | None:
    if tags.get("place"):
        return "place"
    for key, values in LANDMARK_KEYS.items():
        if key in tags and (values is None or tags[key] in values):
            return "landmark"
    if tags.get("highway") in ROAD_TYPES:
        return "road"
    return None


def aliases_from(tags: dict[str, str]) -> tuple[str, ...]:
    names: list[str] = []
    for key in NAME_KEYS:
        for value in tags.get(key, "").split(";"):
            if value.strip() and value.strip() not in names:
                names.append(value.strip())
    return tuple(names)
