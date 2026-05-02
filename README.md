# RENATI Scraping

Scraper local para búsquedas temáticas en RENATI. La búsqueda se hace por tema y los filtros que RENATI no ofrece bien por URL se aplican localmente antes de exportar.

## Uso interactivo

```powershell
python cli.py
```

El programa pregunta:

- tema de búsqueda
- máximo de trabajos a exportar
- rango de años
- grado
- región
- universidades

El Excel queda en `data/output/`.

## Uso recomendado contra RENATI vivo

RENATI puede devolver Anubis anti-bot a `requests`. Para correr en vivo usa navegador:

```powershell
python cli.py --source browser-export --topic pobreza --limit 300 --no-interactive
```

Para una prueba rapida:

```powershell
python cli.py --source browser-export --topic pobreza --limit 1 --no-interactive
```

Si ChromeDriver detecta mal la versión de Chrome:

```powershell
$env:RENATI_CHROME_VERSION_MAIN="147"
python cli.py --source browser-export --topic pobreza --limit 300 --no-interactive
```

## Sprint implementado

- Sprint 1: cliente HTTP, descarga de listado RENATI y parser de resultados.
- Sprint 2: CLI interactivo, filtros locales, navegador `undetected-chromedriver`, resumen desde detalle y exportación Excel de una sola hoja.

El campo `resumen` se descarga desde la pagina de detalle de cada trabajo. Por defecto, las filas sin resumen recuperable no se exportan.

Manual completo: `MANUAL_USO.md`.
