from renati_scraping.core.models import extract_month, extract_year
from renati_scraping.core.normalize import map_access_type, map_degree


def test_extract_year_and_month_iso_date():
    assert extract_year("2018-09-19") == 2018
    assert extract_month("2018-09-19") == 9


def test_extract_month_spanish_date():
    assert extract_year("16-mar-2017") == 2017
    assert extract_month("16-mar-2017") == 3


def test_map_degree_from_renati_uri():
    assert map_degree("https://purl.org/pe-repo/renati/level#maestro") == "Maestria"
    assert map_degree("https://purl.org/pe-repo/renati/level#tituloProfesional") == "Licenciatura/Titulo profesional"


def test_map_access_type_from_renati_uri():
    assert map_access_type("https://purl.org/pe-repo/renati/type#tesis") == "Tesis"
