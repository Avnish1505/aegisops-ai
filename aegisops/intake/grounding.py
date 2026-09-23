"""Is a quote really in the report, and does it state the number claimed?"""

from __future__ import annotations

import re
import unicodedata

NUMBER_WORDS: dict[str, int] = {
    # English
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100, "dozen": 12, "a dozen": 12,
    # Hinglish (romanised Hindi)
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6,
    "cheh": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10, "barah": 12, "pandrah": 15,
    "bees": 20, "tees": 30, "chalis": 40, "pachas": 50, "pachaas": 50, "sau": 100,
    # Hindi (Devanagari)
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "सात": 7,
    "आठ": 8, "नौ": 9, "दस": 10, "बारह": 12, "पंद्रह": 15, "बीस": 20, "तीस": 30, "चालीस": 40,
    "पचास": 50, "सौ": 100,
}
_DIGITS = re.compile(r"\d+")
# A quote must point at the words that state a value. Quoting the whole report would make the
# substring check meaningless, so longer quotes do not count as grounding.
MAX_QUOTE_CHARS = 100


def normalise(text: str) -> str:
    """NFKC, case-fold and collapse whitespace; scripts are left as they are."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def quote_in_report(quote: str, report: str) -> bool:
    needle = normalise(quote).strip(" \"'“”‘’.,;:")
    return 1 <= len(needle) <= MAX_QUOTE_CHARS and needle in normalise(report)


def numbers_in(text: str) -> set[int]:
    """Digits in any script (Devanagari ४५ included) plus known number words."""
    ascii_text = "".join(
        str(unicodedata.digit(ch)) if unicodedata.category(ch) == "Nd" else ch for ch in text
    )
    found = {int(match) for match in _DIGITS.findall(ascii_text)}
    words = normalise(text)
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", words):
            found.add(value)
    return found


def number_stated(value: int, quote: str) -> bool:
    return value in numbers_in(quote)
