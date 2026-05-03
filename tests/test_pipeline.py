from pathlib import Path

import pandas as pd

from renati_scraping.core.detail import DetailData, parse_detail_html
from renati_scraping.core.exporter import build_export_rows, export_excel, merge_consolidated_rows
from renati_scraping.core.filters import FilterConfig, matches_filters
from renati_scraping.core.search import read_results_csv
from renati_scraping.webapp import build_cli_command


ROOT = Path(__file__).resolve().parents[1]


def test_read_existing_csv_and_filter_by_year_degree():
    items = read_results_csv(ROOT / "resultado_busqueda.csv", limit=20)
    assert items
    config = FilterConfig(start_year=2018, end_year=2025, degrees={"Licenciatura/Titulo profesional"})
    filtered = [item for item in items if matches_filters(item, config)]
    assert filtered
    assert all(item.year is not None and 2018 <= item.year <= 2025 for item in filtered)


def test_build_export_rows_contains_required_schema():
    items = read_results_csv(ROOT / "resultado_busqueda.csv", limit=2)
    details = {items[0].document_url: DetailData(summary="Resumen de prueba", keywords="pobreza; economia")}
    rows = build_export_rows(items, topic="economia", details=details)
    row = rows[0]
    expected = {
        "id",
        "tipo_acceso",
        "palabras_clave",
        "fecha_publicacion",
        "enlace_documento_original",
        "resumen",
        "universidad",
        "grado_tesis",
        "anio_publicacion",
        "mes_publicacion",
    }
    assert expected.issubset(row)
    assert "renati_level_original" not in row
    assert "renati_type_original" not in row
    assert row["id"].startswith("RENATI-economia-")
    assert row["resumen"] == "Resumen de prueba"


def test_export_excel_creates_single_sheet():
    items = read_results_csv(ROOT / "resultado_busqueda.csv", limit=3)
    output_dir = ROOT / "tests" / "_output"
    path = export_excel(items, topic="pobreza", output_dir=output_dir, file_name="renati_test.xlsx", append=False)
    assert path.exists()
    assert path.suffix == ".xlsx"
    path.unlink()


def test_export_excel_defaults_to_topic_file_name():
    items = read_results_csv(ROOT / "resultado_busqueda.csv", limit=1)
    output_dir = ROOT / "tests" / "_output"
    path = export_excel(items, topic="economia digital", output_dir=output_dir, append=False)
    assert path.name == "renati_resultados_economia-digital.xlsx"
    path.unlink()


def test_merge_consolidated_prefers_row_with_summary():
    items = read_results_csv(ROOT / "resultado_busqueda.csv", limit=1)
    empty = build_export_rows(items, topic="pobreza")
    filled = build_export_rows(
        items,
        topic="pobreza",
        details={items[0].document_url: DetailData(summary="Resumen completo")},
    )
    merged = merge_consolidated_rows(
        pd.DataFrame(empty),
        pd.DataFrame(filled),
    )
    assert len(merged) == 1
    assert merged.iloc[0]["resumen"] == "Resumen completo"
    assert merged.iloc[0]["id"] == "RENATI-pobreza-00001"


def test_merge_consolidated_prefers_longer_summary_for_same_work():
    items = read_results_csv(ROOT / "resultado_busqueda.csv", limit=1)
    short = build_export_rows(
        items,
        topic="pobreza",
        details={items[0].document_url: DetailData(summary="Resumen corto")},
    )
    long = build_export_rows(
        items,
        topic="pobreza",
        details={items[0].document_url: DetailData(summary="Resumen largo " * 20)},
    )
    merged = merge_consolidated_rows(pd.DataFrame(long), pd.DataFrame(short))
    assert len(merged) == 1
    assert len(merged.iloc[0]["resumen"]) > len("Resumen corto")


def test_parse_detail_html_extracts_summary_from_meta():
    summary = (
        "Este es el resumen de la tesis con suficiente contenido academico para superar la validacion "
        "minima y evitar confundir enlaces o codigos cortos con resumen real."
    )
    html = """
    <html><head>
      <meta name="DC.description.abstract" content="%s" />
      <meta name="DC.subject" content="Pobreza; Economia" />
    </head><body></body></html>
    """ % summary
    detail = parse_detail_html(html)
    assert detail.summary == summary
    assert detail.keywords == "Pobreza; Economia"


def test_parse_detail_html_ignores_uri_as_summary_and_uses_meta_description():
    html = """
    <html><head>
      <meta name="description" content="Esta investigacion analiza la pobreza regional con una metodologia cuantitativa y presenta resultados academicos relevantes para la politica publica peruana." />
      <meta name="DC.description.uri" content="https://hdl.handle.net/20.500/123" />
      <meta name="DC.subject" content="Pobreza" />
      <meta name="DC.subject" content="https://purl.org/pe-repo/ocde/ford#5.02.04" />
    </head><body></body></html>
    """
    detail = parse_detail_html(html)
    assert detail.summary.startswith("Esta investigacion analiza")
    assert detail.keywords == "Pobreza"


def test_parse_detail_html_extracts_scoped_sections_without_following_links():
    html = """
    <html><body>
      <div><h6>Resumen</h6><div>El objetivo de esta tesis es estudiar la economia digital en el Peru con evidencia institucional, metodologia documentaria y resultados utiles para investigadores universitarios.</div></div>
      <div><h6>Palabras clave</h6><div><a href="/browse?value=Economia digital">Economia digital</a><a href="/browse?value=Tributacion">Tributacion</a></div></div>
      <div><h6>Identificador unico</h6><div><a href="https://hdl.handle.net/20.500/999">https://hdl.handle.net/20.500/999</a></div></div>
    </body></html>
    """
    detail = parse_detail_html(html)
    assert "Identificador unico" not in detail.summary
    assert "handle.net" not in detail.keywords
    assert detail.keywords == "Economia digital; Tributacion"


def test_webapp_builds_cli_command_for_topic_file_flow():
    command = build_cli_command(
        {
            "topic": "pobreza",
            "limit": "25",
            "source": "browser-export",
            "start_year": "2018",
            "region": "Arequipa",
            "headless": True,
        }
    )
    assert "--topic" in command
    assert "pobreza" in command
    assert "--start-year" in command
    assert "--region" in command
    assert "--headless" in command
    assert "--no-interactive" in command
