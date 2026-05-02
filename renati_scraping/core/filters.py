from __future__ import annotations

from dataclasses import dataclass

from .models import SearchResult
from .normalize import map_degree, normalize_for_match
from .regions import infer_region


@dataclass(slots=True)
class FilterConfig:
    start_year: int | None = None
    end_year: int | None = None
    degrees: set[str] | None = None
    regions: set[str] | None = None
    universities: set[str] | None = None


def matches_filters(item: SearchResult, config: FilterConfig) -> bool:
    year = item.year
    if config.start_year is not None and (year is None or year < config.start_year):
        return False
    if config.end_year is not None and (year is None or year > config.end_year):
        return False

    if config.degrees:
        degree = normalize_for_match(map_degree(item.renati_level) or item.degree_name)
        allowed = {normalize_for_match(value) for value in config.degrees}
        if degree not in allowed:
            return False

    if config.regions:
        region = normalize_for_match(infer_region(item.university))
        allowed = {normalize_for_match(value) for value in config.regions}
        if region not in allowed:
            return False

    if config.universities:
        university = normalize_for_match(item.university)
        allowed_universities = [normalize_for_match(value) for value in config.universities]
        if not any(value and value in university for value in allowed_universities):
            return False

    return True
