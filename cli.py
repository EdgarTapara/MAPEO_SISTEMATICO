from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from renati_scraping.core.browser import BrowserManager
from renati_scraping.core.client import RenatiClient
from renati_scraping.core.detail import DetailData, DetailFetcher
from renati_scraping.core.exporter import export_excel
from renati_scraping.core.filters import FilterConfig, matches_filters
from renati_scraping.core.search import (
    fetch_export_csv_with_browser,
    iter_search_results,
    iter_search_results_browser,
    parse_results_csv,
    read_results_csv,
)


DEFAULT_LIMIT = 300
LOGGER = logging.getLogger("renati")


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    interactive = args.interactive and sys.stdin.isatty()
    topic = args.topic or (ask_text("Tema a buscar", default="pobreza") if interactive else "pobreza")
    limit = args.limit or (ask_int("Cuantos trabajos exportar por corrida", default=DEFAULT_LIMIT) if interactive else DEFAULT_LIMIT)

    filters = FilterConfig(
        start_year=args.start_year if args.start_year is not None else (ask_optional_int("Anio inicial", default=None) if interactive else None),
        end_year=args.end_year if args.end_year is not None else (ask_optional_int("Anio final", default=None) if interactive else None),
        degrees=parse_csv_set(args.degree) if args.degree else ask_set(
            "Grado(s): Bachiller, Licenciatura/Titulo profesional, Maestria, Doctorado",
        ) if interactive else None,
        regions=parse_csv_set(args.region) if args.region else (ask_set("Region(es) inferidas") if interactive else None),
        universities=parse_csv_set(args.university) if args.university else (ask_set("Universidad(es), texto parcial") if interactive else None),
    )

    source = args.source or (
        ask_choice("Fuente de datos", choices=("browser-export", "browser", "csv", "renati"), default="browser-export")
        if interactive
        else "browser-export"
    )
    csv_path = Path(args.csv_path)

    print("\nConfiguracion:")
    print(f"- Tema: {topic}")
    print(f"- Maximo exportable: {limit}")
    print(f"- Fuente: {source}")
    print("- Nota: el resumen se descarga entrando al detalle de cada handle; esto toma mas tiempo.\n")
    if args.skip_summary:
        print("Advertencia: --skip-summary deja la columna resumen vacia. Usalo solo para pruebas tecnicas.\n")

    if source == "csv":
        items = read_results_csv(csv_path)
        selected = [item for item in items if matches_filters(item, filters)][:limit]
        details = enrich_details(
            selected,
            required=not args.skip_summary,
            browser_fallback=not args.no_detail_browser_fallback,
            headless=args.headless,
        )
        selected, details = enforce_summary_policy(
            selected,
            details,
            allow_missing_summary=args.allow_missing_summary or args.skip_summary,
        )
    elif source == "browser-export":
        selected, details = collect_enriched_from_browser_export(
            topic=topic,
            filters=filters,
            limit=limit,
            headless=args.headless,
            require_summary=not args.skip_summary,
            allow_missing_summary=args.allow_missing_summary or args.skip_summary,
        )
    elif source == "browser":
        selected, details = collect_enriched_from_browser(
            topic=topic,
            filters=filters,
            limit=limit,
            max_pages=args.max_pages,
            headless=args.headless,
            require_summary=not args.skip_summary,
            allow_missing_summary=args.allow_missing_summary or args.skip_summary,
        )
    else:
        selected = collect_from_renati(topic=topic, filters=filters, limit=limit, max_pages=args.max_pages)
        details = enrich_details(
            selected,
            required=not args.skip_summary,
            browser_fallback=not args.no_detail_browser_fallback,
            headless=args.headless,
        )
        selected, details = enforce_summary_policy(
            selected,
            details,
            allow_missing_summary=args.allow_missing_summary or args.skip_summary,
        )

    if not selected:
        print("No se encontraron trabajos validos. Relaja filtros, sube max_pages o usa --allow-missing-summary.")
        return

    output = export_excel(selected, topic=topic, details=details, file_name=args.output_file)
    print(f"Excel generado: {output.resolve()}")
    print(f"Registros exportados: {len(selected)}")


def collect_from_renati(topic: str, filters: FilterConfig, limit: int, max_pages: int) -> list:
    client = RenatiClient()
    selected = []
    reviewed = 0
    for item in iter_search_results(topic, client=client, max_pages=max_pages):
        reviewed += 1
        if matches_filters(item, filters):
            selected.append(item)
            print(f"[{len(selected)}/{limit}] {item.year or ''} {item.university[:55]} - {item.title[:70]}")
        if len(selected) >= limit:
            break
    print(f"Trabajos revisados en listado: {reviewed}")
    return selected


def collect_from_browser(topic: str, filters: FilterConfig, limit: int, max_pages: int, headless: bool) -> list:
    selected = []
    reviewed = 0
    with BrowserManager(headless=headless) as browser:
        for item in iter_search_results_browser(topic, browser=browser, max_pages=max_pages):
            reviewed += 1
            if matches_filters(item, filters):
                selected.append(item)
                print(f"[{len(selected)}/{limit}] {item.year or ''} {item.university[:55]} - {item.title[:70]}")
            if len(selected) >= limit:
                break
    print(f"Trabajos revisados en listado: {reviewed}")
    return selected


def collect_enriched_from_browser_export(
    topic: str,
    filters: FilterConfig,
    limit: int,
    headless: bool,
    require_summary: bool,
    allow_missing_summary: bool,
) -> tuple[list, dict]:
    selected = []
    details = {}
    skipped_without_summary = 0
    fetcher = DetailFetcher()
    with BrowserManager(headless=headless) as browser:
        csv_content = fetch_export_csv_with_browser(topic, browser=browser)
        candidates = [item for item in parse_results_csv(csv_content) if matches_filters(item, filters)]
        print(f"Trabajos candidatos despues de filtros: {len(candidates)}")
        for item in candidates:
            detail = DetailData() if not require_summary else fetch_detail_for_item(
                fetcher=fetcher,
                item=item,
                browser=browser,
                use_browser_fallback=True,
            )
            if require_summary and not detail.has_summary and not allow_missing_summary:
                skipped_without_summary += 1
                print(f"[omitido_sin_resumen] {item.document_url} - {item.title[:70]}")
                continue
            selected.append(item)
            details[item.document_url] = detail
            status = "resumen_ok" if detail.has_summary else "sin_resumen"
            print(f"[{len(selected)}/{limit}] {status} {item.year or ''} {item.university[:45]} - {item.title[:70]}")
            if len(selected) >= limit:
                break
    if skipped_without_summary:
        print(f"Trabajos omitidos por no tener resumen: {skipped_without_summary}")
    return selected, details


def collect_enriched_from_browser(
    topic: str,
    filters: FilterConfig,
    limit: int,
    max_pages: int,
    headless: bool,
    require_summary: bool,
    allow_missing_summary: bool,
) -> tuple[list, dict]:
    selected = []
    details = {}
    reviewed = 0
    skipped_without_summary = 0
    fetcher = DetailFetcher()
    with BrowserManager(headless=headless) as browser:
        for item in iter_search_results_browser(topic, browser=browser, max_pages=max_pages):
            reviewed += 1
            if not matches_filters(item, filters):
                continue
            detail = DetailData() if not require_summary else fetch_detail_for_item(
                fetcher=fetcher,
                item=item,
                browser=browser,
                use_browser_fallback=True,
            )
            if require_summary and not detail.has_summary and not allow_missing_summary:
                skipped_without_summary += 1
                print(f"[omitido_sin_resumen] {item.document_url} - {item.title[:70]}")
                continue
            selected.append(item)
            details[item.document_url] = detail
            status = "resumen_ok" if detail.has_summary else "sin_resumen"
            print(f"[{len(selected)}/{limit}] {status} {item.year or ''} {item.university[:45]} - {item.title[:70]}")
            if len(selected) >= limit:
                break
    print(f"Trabajos revisados en listado: {reviewed}")
    if skipped_without_summary:
        print(f"Trabajos omitidos por no tener resumen: {skipped_without_summary}")
    return selected, details


def enrich_details(
    items: list,
    required: bool = True,
    browser_fallback: bool = False,
    headless: bool = False,
) -> dict:
    if not required:
        return {}
    fetcher = DetailFetcher()
    details = {}
    missing_summary = 0
    print("\nDescargando detalle/resumen:")
    browser = BrowserManager(headless=headless) if browser_fallback else None
    if browser is not None:
        browser.get_driver()
    try:
        for index, item in enumerate(items, start=1):
            detail = None
            status = "sin_resumen"
            detail = fetch_detail_for_item(fetcher, item, browser, use_browser_fallback=browser is not None)
            status = "ok" if detail.has_summary else "sin_resumen"
            details[item.document_url] = detail
            if not detail.summary:
                missing_summary += 1
            print(f"[{index}/{len(items)}] {status} - {item.document_url}")
    finally:
        if browser is not None:
            browser.close()
    if missing_summary:
        print(f"Advertencia: {missing_summary} trabajos quedaron sin resumen. Revisa esos handles manualmente.")
    return details


def fetch_detail_for_item(fetcher: DetailFetcher, item, browser=None, use_browser_fallback: bool = True):
    try:
        detail = fetcher.fetch(item.document_url)
    except Exception as exc:
        LOGGER.warning("No se pudo descargar detalle con requests: %s | %s", item.document_url, exc)
        detail = DetailData()
    if use_browser_fallback and browser is not None and not detail.has_summary:
        try:
            detail = fetcher.fetch_with_browser(item.document_url, browser)
        except Exception as exc:
            LOGGER.warning("No se pudo descargar detalle con navegador: %s | %s", item.document_url, exc)
    return detail


def enforce_summary_policy(items: list, details: dict, allow_missing_summary: bool) -> tuple[list, dict]:
    if allow_missing_summary:
        return items, details
    valid_items = []
    valid_details = {}
    skipped = 0
    for item in items:
        detail = details.get(item.document_url)
        if detail and detail.has_summary:
            valid_items.append(item)
            valid_details[item.document_url] = detail
        else:
            skipped += 1
    if skipped:
        print(f"Trabajos omitidos por resumen faltante: {skipped}")
    return valid_items, valid_details


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scraper interactivo RENATI")
    parser.add_argument("--topic", help="Tema de busqueda")
    parser.add_argument("--limit", type=int, help="Maximo de trabajos a exportar")
    parser.add_argument("--start-year", type=int, help="Anio inicial")
    parser.add_argument("--end-year", type=int, help="Anio final")
    parser.add_argument("--degree", help="Grados separados por coma")
    parser.add_argument("--region", help="Regiones separadas por coma")
    parser.add_argument("--university", help="Universidades o textos parciales separados por coma")
    parser.add_argument(
        "--source",
        choices=("browser-export", "browser", "renati", "csv"),
        help="Fuente: browser-export, browser, renati o csv",
    )
    parser.add_argument("--csv-path", default="resultado_busqueda.csv", help="CSV RENATI exportado")
    parser.add_argument("--output-file", default="renati_resultados_consolidados.xlsx", help="Nombre del Excel consolidado")
    parser.add_argument("--max-pages", type=int, default=30, help="Maximo de paginas RENATI a revisar")
    parser.add_argument("--headless", action="store_true", help="Ejecutar Chrome sin ventana visible")
    parser.add_argument("--skip-summary", action="store_true", help="No descargar resumen de detalle")
    parser.add_argument("--allow-missing-summary", action="store_true", help="Permitir filas sin resumen en el Excel")
    parser.add_argument("--detail-browser-fallback", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-detail-browser-fallback", action="store_true", help="Desactivar navegador para detalles sin resumen")
    parser.add_argument("--no-interactive", dest="interactive", action="store_false", help="No pedir datos por input")
    parser.add_argument("--log-level", default="WARNING", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    parser.set_defaults(interactive=True)
    return parser.parse_args()


def ask_text(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or (default or "")


def ask_int(prompt: str, default: int) -> int:
    value = input(f"{prompt} [{default}]: ").strip()
    if not value:
        return default
    return int(value)


def ask_optional_int(prompt: str, default: int | None = None) -> int | None:
    suffix = f" [{default}]" if default is not None else " [Enter = todos]"
    value = input(f"{prompt}{suffix}: ").strip()
    if not value:
        return default
    return int(value)


def ask_set(prompt: str) -> set[str] | None:
    value = input(f"{prompt} [Enter = todos]: ").strip()
    return parse_csv_set(value) if value else None


def ask_choice(prompt: str, choices: tuple[str, ...], default: str) -> str:
    value = input(f"{prompt} {choices} [{default}]: ").strip().lower()
    return value if value in choices else default


def parse_csv_set(value: str | None) -> set[str] | None:
    if not value:
        return None
    parsed = {part.strip() for part in value.split(",") if part.strip()}
    return parsed or None


if __name__ == "__main__":
    main()
