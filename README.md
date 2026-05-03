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

El Excel queda en `data/output/` con el nombre `renati_resultados_{tema}.xlsx`.

## Interfaz web local

```powershell
python cli.py --web
```

Abre un panel local en `http://127.0.0.1:8765` para configurar tema, filtros, limite y ejecutar el scraper sin escribir todos los argumentos.

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

El campo `resumen` se descarga desde la pagina de detalle de cada trabajo. Por defecto, las filas sin resumen recuperable no se exportan.

La extraccion de detalle es conservadora: si un repositorio universitario mezcla enlaces, codigos o navegacion dentro del HTML, esos textos se descartan para no contaminar `resumen` ni `palabras_clave`.

Manual completo: `MANUAL_USO.md`.
