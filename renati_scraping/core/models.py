from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class SearchResult:
    sequence: int
    author: str = ""
    title: str = ""
    publication_date: str = ""
    university: str = ""
    document_url: str = ""
    keywords: str = ""
    degree_grantor: str = ""
    degree_name: str = ""
    renati_level: str = ""
    renati_type: str = ""
    source: str = "renati"

    @property
    def year(self) -> int | None:
        return extract_year(self.publication_date)

    @property
    def month(self) -> int | None:
        return extract_month(self.publication_date)

    def as_raw_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "author": self.author,
            "title": self.title,
            "publication_date": self.publication_date,
            "university": self.university,
            "document_url": self.document_url,
            "keywords": self.keywords,
            "degree_grantor": self.degree_grantor,
            "degree_name": self.degree_name,
            "renati_level": self.renati_level,
            "renati_type": self.renati_type,
            "source": self.source,
        }


def extract_year(value: str) -> int | None:
    if not value:
        return None
    for token in value.replace("/", "-").split("-"):
        token = token.strip()
        if len(token) == 4 and token.isdigit():
            year = int(token)
            if 1900 <= year <= datetime.now().year + 1:
                return year
    digits = "".join(ch if ch.isdigit() else " " for ch in value).split()
    for token in digits:
        if len(token) == 4:
            year = int(token)
            if 1900 <= year <= datetime.now().year + 1:
                return year
    return None


def extract_month(value: str) -> int | None:
    if not value:
        return None
    normalized = value.strip().lower().replace("/", "-")
    parts = normalized.split("-")
    if len(parts) >= 2 and parts[1].isdigit():
        month = int(parts[1])
        if 1 <= month <= 12:
            return month
    months = {
        "ene": 1,
        "enero": 1,
        "feb": 2,
        "febrero": 2,
        "mar": 3,
        "marzo": 3,
        "abr": 4,
        "abril": 4,
        "may": 5,
        "mayo": 5,
        "jun": 6,
        "junio": 6,
        "jul": 7,
        "julio": 7,
        "ago": 8,
        "agosto": 8,
        "sep": 9,
        "set": 9,
        "septiembre": 9,
        "oct": 10,
        "octubre": 10,
        "nov": 11,
        "noviembre": 11,
        "dic": 12,
        "diciembre": 12,
    }
    for token in parts:
        token = token.strip(". ")
        if token in months:
            return months[token]
    return None
