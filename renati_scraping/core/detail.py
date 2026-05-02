from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .normalize import clean_text


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
    summary = _first_present(
        metadata,
        (
            "dc.description.abstract",
            "description.abstract",
            "abstract",
            "resumen",
            "dc.description",
        ),
    )
    keywords = _first_present(
        metadata,
        (
            "dc.subject",
            "subject",
            "palabras clave",
            "keywords",
        ),
    )
    access_type = _first_present(metadata, ("dc.rights", "rights", "type", "dc.type"))
    if not summary:
        summary = _regex_after_label(text, ("Resumen", "Abstract"))
    if not keywords:
        keywords = _regex_after_label(text, ("Palabras clave", "Keywords", "Materia"))
    return DetailData(summary=summary, keywords=keywords, access_type=access_type)


def _extract_metadata_pairs(soup: BeautifulSoup) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for meta in soup.find_all("meta"):
        key = meta.get("name") or meta.get("property")
        value = meta.get("content")
        if key and value:
            metadata[clean_text(key).lower()] = clean_text(value)

    for row in soup.select("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        key = clean_text(cells[0].get_text(" ", strip=True)).rstrip(":").lower()
        value = clean_text(cells[1].get_text(" ", strip=True))
        if key and value:
            metadata[key] = value

    for field in soup.select(".simple-item-view-other, .item-page-field-wrapper, .metadataField"):
        label = field.find(class_=re.compile("label", re.I))
        value = field.find(class_=re.compile("value", re.I))
        if label and value:
            metadata[clean_text(label.get_text(" ", strip=True)).rstrip(":").lower()] = clean_text(
                value.get_text(" ", strip=True)
            )
    return metadata


def _first_present(metadata: dict[str, str], keys: tuple[str, ...]) -> str:
    normalized = {key.lower(): value for key, value in metadata.items()}
    for key in keys:
        key_lower = key.lower()
        if key_lower in normalized:
            return normalized[key_lower]
    for key, value in normalized.items():
        if any(candidate in key for candidate in keys):
            return value
    return ""


def _regex_after_label(text: str, labels: tuple[str, ...]) -> str:
    end_labels = "Palabras clave|Keywords|Abstract|Resumen|URI|Fecha|Autor|Asesor"
    for label in labels:
        match = re.search(rf"{label}\s*:?\s*(.+?)(?:\s+(?:{end_labels})\s*:|$)", text, re.I)
        if match:
            value = clean_text(match.group(1))
            if len(value) > 20:
                return value
    return ""
