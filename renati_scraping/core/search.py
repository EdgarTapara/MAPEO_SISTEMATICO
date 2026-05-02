from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlencode, urljoin

import requests

from .client import BASE_URL, RenatiClient
from .models import SearchResult
from .normalize import clean_text


CSV_FIELD_MAP = {
    "dc.contributor.author": "author",
    "dc.title": "title",
    "dc.date.issued": "publication_date",
    "dc.publisher": "university",
    "dc.identifier.uri": "document_url",
    "dc.subject": "keywords",
    "thesis.degree.grantor": "degree_grantor",
    "thesis.degress.name": "degree_name",
    "thesis.degree.name": "degree_name",
    "renati.level": "renati_level",
    "renati.type": "renati_type",
}


def read_results_csv(path: str | Path, limit: int | None = None) -> list[SearchResult]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        return parse_results_csv(fh.read(), limit=limit)


def fetch_export_csv_with_browser(query: str, browser, base_url: str = BASE_URL) -> str:
    browser.navigate(f"{base_url}/busqueda?{urlencode({'q': query})}", kind="listado")
    session = requests.Session()
    for cookie in browser.get_driver().get_cookies():
        session.cookies.set(cookie["name"], cookie["value"], domain=cookie.get("domain"))
    session.headers.update(
        {
            "User-Agent": browser.get_driver().execute_script("return navigator.userAgent;"),
            "Referer": f"{base_url}/busqueda?{urlencode({'q': query})}",
            "Accept": "text/csv,text/plain,*/*",
        }
    )
    url = f"{base_url}/busqueda/simple/exportar?{urlencode({'q': query})}"
    response = session.get(url, timeout=60)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    if "anubis_challenge" in response.text.lower():
        raise RuntimeError("RENATI devolvio Anubis al intentar exportar CSV.")
    return response.text


def parse_results_csv(content: str, limit: int | None = None) -> list[SearchResult]:
    reader = csv.DictReader(io.StringIO(content))
    results: list[SearchResult] = []
    for idx, row in enumerate(reader, start=1):
        kwargs = {
            "sequence": _parse_int(row.get("N°") or row.get("NÂ°") or row.get("N") or idx, idx),
            "source": "csv",
        }
        for original, target in CSV_FIELD_MAP.items():
            kwargs[target] = clean_text(row.get(original, ""))
        results.append(SearchResult(**kwargs))
        if limit is not None and len(results) >= limit:
            break
    return results


def parse_search_html(html: str, base_url: str = BASE_URL) -> list[SearchResult]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    renati_results = _parse_renati_articles(soup, base_url=base_url)
    if renati_results:
        return _deduplicate(renati_results)
    containers = _candidate_result_nodes(soup)
    results: list[SearchResult] = []
    for idx, node in enumerate(containers, start=1):
        text = clean_text(node.get_text(" ", strip=True))
        if not text:
            continue
        link_tag = node.find("a", href=True)
        document_url = urljoin(base_url, link_tag["href"]) if link_tag else ""
        title = _pick_title(node, text)
        author = _pick_by_label(text, ("Autor", "Autores", "Author"))
        date = _pick_date(text)
        university = _pick_by_label(text, ("Universidad", "Institucion", "Institución", "Publisher"))
        keywords = _pick_by_label(text, ("Palabras clave", "Materia", "Subject"))
        if not title and document_url:
            title = clean_text(link_tag.get_text(" ", strip=True))
        if not title:
            continue
        results.append(
            SearchResult(
                sequence=idx,
                author=author,
                title=title,
                publication_date=date,
                university=university,
                document_url=document_url,
                keywords=keywords,
                source="html",
            )
        )
    return _deduplicate(results)


def _parse_renati_articles(soup, base_url: str) -> list[SearchResult]:
    root = soup.select_one("#data-busqueda") or soup
    results: list[SearchResult] = []
    for idx, article in enumerate(root.select("article"), start=1):
        title_link = article.select_one("h6.primary-text a[href]") or article.select_one("h6 a[href]")
        if not title_link:
            continue
        title = clean_text(title_link.get_text(" ", strip=True))
        if not title or title.lower() in {"search", "busqueda avanzada", "búsqueda avanzada"}:
            continue
        date_tag = article.select_one(".center-align p")
        university_tag = article.select_one("p.bold")
        author_tags = article.select(".row.wrap a.underline strong, a.underline.secondary-text strong")
        keyword_tags = article.select("a.italic span, a.italic")
        type_img = article.select_one("img[alt]")
        access_tag = article.select_one(".chip span")
        results.append(
            SearchResult(
                sequence=idx,
                author=" | ".join(clean_text(tag.get_text(" ", strip=True)) for tag in author_tags),
                title=title,
                publication_date=clean_text(date_tag.get_text(" ", strip=True)) if date_tag else "",
                university=clean_text(university_tag.get_text(" ", strip=True)) if university_tag else "",
                document_url=urljoin(base_url, title_link["href"]),
                keywords=" | ".join(clean_text(tag.get_text(" ", strip=True)) for tag in keyword_tags),
                renati_level=type_img.get("alt", "") if type_img else "",
                renati_type=clean_text(access_tag.get_text(" ", strip=True)) if access_tag else "",
                source="html",
            )
        )
    return results


def iter_search_results(
    query: str,
    client: RenatiClient | None = None,
    max_pages: int = 20,
    rpp: int = 100,
) -> Iterable[SearchResult]:
    client = client or RenatiClient()
    sequence = 1
    seen_urls: set[str] = set()
    for page in range(max_pages):
        start = page * rpp
        html = client.fetch_search_page(query=query, start=start, rpp=rpp)
        page_results = parse_search_html(html, base_url=client.base_url)
        if not page_results:
            break
        yielded = 0
        for item in page_results:
            key = item.document_url or item.title
            if key in seen_urls:
                continue
            seen_urls.add(key)
            item.sequence = sequence
            sequence += 1
            yielded += 1
            yield item
        if yielded == 0:
            break


def iter_search_results_browser(
    query: str,
    browser,
    max_pages: int = 20,
    rpp: int = 100,
    base_url: str = BASE_URL,
) -> Iterable[SearchResult]:
    sequence = 1
    seen_urls: set[str] = set()
    for page in range(max_pages):
        start = page * rpp
        params = {"q": query}
        if start:
            params["start"] = start
        url = f"{base_url}/busqueda?{urlencode(params)}"
        driver = browser.navigate(url, kind="listado")
        _wait_for_results_or_static_page(driver, timeout=browser.timeout_elemento)
        page_results = parse_search_html(driver.page_source, base_url=base_url)
        if not page_results:
            break
        yielded = 0
        for item in page_results:
            key = item.document_url or item.title
            if key in seen_urls:
                continue
            seen_urls.add(key)
            item.sequence = sequence
            sequence += 1
            yielded += 1
            yield item
        if yielded == 0:
            break


def _wait_for_results_or_static_page(driver, timeout: int = 20) -> None:
    try:
        from selenium.webdriver.support.ui import WebDriverWait

        def loaded(drv):
            html = drv.page_source or ""
            return (
                "Resultados de búsqueda" in html
                or "Resultados por ítem" in html
                or "artifact-description" in html
                or "dc.title" in html
                or "No se encontraron" in html
            )

        WebDriverWait(driver, timeout).until(loaded)
    except Exception:
        return


def _candidate_result_nodes(soup: BeautifulSoup) -> list:
    selectors = [
        "article",
        ".card",
        ".item",
        ".artifact-description",
        ".ds-artifact-item",
        ".artifact-title",
        ".search-result",
        ".list-group-item",
        "li",
        "tr",
    ]
    nodes = []
    for selector in selectors:
        for node in soup.select(selector):
            text = clean_text(node.get_text(" ", strip=True))
            if len(text) < 30:
                continue
            if node.find("a", href=True) or any(token in text.lower() for token in ("universidad", "tesis", "dc.")):
                nodes.append(node)
        if nodes:
            break
    return nodes


def _pick_title(node, text: str) -> str:
    for selector in ("h1", "h2", "h3", "h4", "h5", "strong", "b", "a"):
        tag = node.find(selector)
        if tag:
            candidate = clean_text(tag.get_text(" ", strip=True))
            if candidate and len(candidate) > 5:
                return candidate
    parts = re.split(r"\s{2,}| Autor(?:es)?: | Universidad: | Fecha: ", text)
    return clean_text(parts[0]) if parts else ""


def _pick_by_label(text: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*:?\s*(.+?)(?:\s+(?:Autor(?:es)?|Universidad|Instituci[oó]n|Fecha|Publicado|Palabras clave|Materia|Subject)\s*:|$)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    return ""


def _pick_date(text: str) -> str:
    patterns = [
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
        r"\b\d{1,2}-[a-zA-Záéíóúñ]{3,10}-\d{4}\b",
        r"\b(19|20)\d{2}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(0))
    return ""


def _parse_int(value: object, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _deduplicate(results: list[SearchResult]) -> list[SearchResult]:
    deduped: list[SearchResult] = []
    seen: set[str] = set()
    for item in results:
        key = item.document_url or item.title
        if key in seen:
            continue
        seen.add(key)
        item.sequence = len(deduped) + 1
        deduped.append(item)
    return deduped
