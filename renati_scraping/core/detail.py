from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

from .normalize import clean_text, normalize_for_match


@dataclass(slots=True)
class DetailData:
    summary: str = ""
    keywords: str = ""
    access_type: str = ""

    @property
    def has_summary(self) -> bool:
        return bool(self.summary and self.summary.strip())


class DetailFetcher:
    def __init__(self, cache_dir: str | Path = "data/raw", timeout: int = 30):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
            }
        )

    def fetch(self, url: str) -> DetailData:
        if not url:
            return DetailData()
        html = self._get_cached_or_download(url)
        return parse_detail_html(html)

    def fetch_with_browser(self, url: str, browser) -> DetailData:
        if not url:
            return DetailData()
        driver = browser.navigate(url, kind="detalle")
        html = driver.page_source or ""
        if html:
            self._cache_path(url, suffix="_browser").write_text(html, encoding="utf-8")
        return parse_detail_html(html)

    def _get_cached_or_download(self, url: str) -> str:
        browser_path = self._cache_path(url, suffix="_browser")
        if browser_path.exists():
            return browser_path.read_text(encoding="utf-8", errors="ignore")
        path = self._cache_path(url)
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")
        response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
        response.raise_for_status()
        html = response.text
        path.write_text(html, encoding="utf-8")
        return html

    def _cache_path(self, url: str, suffix: str = "") -> Path:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}{suffix}.html"


def parse_detail_html(html: str) -> DetailData:
    soup = BeautifulSoup(html, "html.parser")
    metadata = _extract_metadata_pairs(soup)
    text = clean_text(soup.get_text(" ", strip=True))
    summary = _first_valid_summary(
        [
            _first_present(metadata, ("dc.description.abstract", "description.abstract", "citation_abstract")),
            _section_after_heading(soup, ("Resumen", "Abstract", "dc.description.abstract")),
            _first_present(metadata, ("description", "resumen", "abstract")),
            _regex_after_label(text, ("Resumen", "Abstract")),
        ]
    )
    keywords = _first_valid_keywords(
        [
            _first_present(metadata, ("citation_keywords", "dc.subject", "subject", "palabras clave", "keywords")),
            _section_after_heading(soup, ("Palabras clave", "Keywords", "Materias", "Materia", "dc.subject")),
            _regex_after_label(text, ("Palabras clave", "Keywords", "Materia", "Materias")),
        ]
    )
    access_type = _first_present(metadata, ("dc.rights", "rights", "type", "dc.type", "tipo de acceso"))
    if not summary:
        summary = ""
    if not keywords:
        keywords = ""
    return DetailData(summary=summary, keywords=keywords, access_type=access_type)


def _extract_metadata_pairs(soup: BeautifulSoup) -> dict[str, str]:
    metadata_values: dict[str, list[str]] = {}
    for meta in soup.find_all("meta"):
        key = meta.get("name") or meta.get("property")
        value = meta.get("content")
        if key and value:
            _append_metadata(metadata_values, key, value)

    for row in soup.select("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        key = clean_text(cells[0].get_text(" ", strip=True)).rstrip(":").lower()
        value = clean_text(cells[1].get_text(" ", strip=True))
        if key and value:
            _append_metadata(metadata_values, key, value)

    for field in soup.select(".simple-item-view-other, .item-page-field-wrapper, .metadataField"):
        label = field.find(class_=re.compile("label", re.I)) or field.find(["h2", "h3", "h4", "h5", "h6"])
        value = field.find(class_=re.compile("value", re.I))
        if label and value:
            _append_metadata(metadata_values, label.get_text(" ", strip=True), value.get_text(" ", strip=True))
    return {key: _join_values(values) for key, values in metadata_values.items()}


def _append_metadata(metadata: dict[str, list[str]], key: str, value: str) -> None:
    normalized_key = clean_text(key).rstrip(":").lower()
    normalized_value = clean_text(value)
    if normalized_key and normalized_value:
        metadata.setdefault(normalized_key, []).append(normalized_value)


def _join_values(values: list[str]) -> str:
    seen: set[str] = set()
    cleaned = []
    for value in values:
        clean_value = _clean_extracted_value(value)
        key = normalize_for_match(clean_value)
        if not clean_value or key in seen:
            continue
        seen.add(key)
        cleaned.append(clean_value)
    return "; ".join(cleaned)


def _first_present(metadata: dict[str, str], keys: tuple[str, ...]) -> str:
    normalized = {key.lower(): value for key, value in metadata.items()}
    for key in keys:
        key_lower = key.lower()
        if key_lower in normalized:
            return _clean_extracted_value(normalized[key_lower])
    return ""


def _regex_after_label(text: str, labels: tuple[str, ...]) -> str:
    end_labels = (
        "Palabras clave|Keywords|Materias|Materia|Abstract|Resumen|URI|Identificador unico|"
        "Identificador único|Tipo de documento|Tipo de acceso|Fecha|Autor|Autores|Asesor|Editorial|Colecciones"
    )
    for label in labels:
        match = re.search(rf"{label}\s*:?\s*(.+?)(?:\s+(?:{end_labels})\s*:|$)", text, re.I)
        if match:
            value = _clean_extracted_value(match.group(1))
            if len(value) > 20:
                return value
    return ""


def _section_after_heading(soup: BeautifulSoup, labels: tuple[str, ...]) -> str:
    wanted = {_normalize_label(label) for label in labels}
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"]):
        if _normalize_label(heading.get_text(" ", strip=True)) not in wanted:
            continue
        container = heading.parent
        for node in list(heading.next_siblings):
            value = _node_text_without_nested_headings(node)
            if value:
                return _clean_extracted_value(value)
        if container:
            clone_texts = []
            passed_heading = False
            for child in container.children:
                if child is heading:
                    passed_heading = True
                    continue
                if not passed_heading:
                    continue
                value = _node_text_without_nested_headings(child)
                if value:
                    clone_texts.append(value)
            if clone_texts:
                return _clean_extracted_value(" ".join(clone_texts))
    return ""


def _node_text_without_nested_headings(node) -> str:
    if getattr(node, "name", None) in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return ""
    if not hasattr(node, "get_text"):
        return clean_text(str(node))
    if hasattr(node, "find_all"):
        for nested in node.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            nested.decompose()
        links = [clean_text(link.get_text(" ", strip=True)) for link in node.find_all("a")]
        links = [link for link in links if link]
        if len(links) >= 2:
            return "; ".join(links)
    return clean_text(node.get_text(" ", strip=True))


def _first_valid_summary(candidates: list[str]) -> str:
    for candidate in candidates:
        value = _clean_extracted_value(candidate)
        if _is_valid_summary(value):
            return value
    return ""


def _first_valid_keywords(candidates: list[str]) -> str:
    for candidate in candidates:
        value = _clean_keywords(candidate)
        if value:
            return value
    return ""


def _clean_keywords(value: str) -> str:
    value = _clean_extracted_value(value)
    if not value:
        return ""
    parts = re.split(r"\s*;\s*|\s*,\s*|\s*\|\s*", value)
    cleaned = []
    seen: set[str] = set()
    for part in parts:
        part = _clean_extracted_value(part)
        key = normalize_for_match(part)
        if not _is_valid_keyword(part) or key in seen:
            continue
        seen.add(key)
        cleaned.append(part)
    return "; ".join(cleaned)


def _clean_extracted_value(value: str | None) -> str:
    value = clean_text(value)
    if not value:
        return ""
    value = unquote(value)
    value = re.sub(r"\bhttps?://\S+", "", value)
    value = re.sub(r"\bwww\.\S+", "", value)
    return clean_text(value)


def _is_valid_summary(value: str) -> bool:
    normalized = normalize_for_match(value)
    if len(value) < 80:
        return False
    if _looks_like_url_or_code(value):
        return False
    bad_fragments = (
        "category_search",
        "por programa sobre renati",
        "identificador unico",
        "tipo de documento",
        "tipo de acceso",
        "pertenece a la coleccion",
    )
    return not any(fragment in normalized for fragment in bad_fragments)


def _is_valid_keyword(value: str) -> bool:
    normalized = normalize_for_match(value)
    if not value or len(value) < 3 or len(value) > 120:
        return False
    if _looks_like_url_or_code(value):
        return False
    rejected = (
        "info:eu-repo",
        "purl.org",
        "ocde/ford",
        "resource_type",
        "access_right",
        "identificador unico",
        "tipo de documento",
        "tipo de acceso",
        "pertenece a la coleccion",
        "category_search",
    )
    return not any(fragment in normalized for fragment in rejected)


def _looks_like_url_or_code(value: str) -> bool:
    normalized = normalize_for_match(value)
    return (
        normalized.startswith(("http://", "https://", "www."))
        or "://" in normalized
        or "purl.org" in normalized
        or normalized.startswith("info:eu-repo")
    )


def _normalize_label(value: str) -> str:
    return normalize_for_match(value).rstrip(":")
