# Manual de Uso - RENATI Scraping

## Objetivo

Construir un Excel por tema para mapeo sistematico de tesis/trabajos RENATI, con resumen obligatorio, filtros locales y una sola pestaña de resultados.

Archivo final:

```text
data/output/renati_resultados_{tema}.xlsx
```

## Instalacion

Desde PowerShell, dentro de la carpeta del proyecto:

```powershell
python -m pip install -r requirements.txt
```

Si `python` no esta en PATH, usar el Python disponible en la maquina o el runtime de Codex.

## Ejecucion Recomendada

```powershell
python cli.py --source browser-export --topic pobreza --limit 300 --no-interactive
```

Este modo:

1. Abre Chrome con `undetected-chromedriver`.
2. Pasa la proteccion Anubis de RENATI.
3. Descarga el CSV oficial de resultados.
4. Aplica filtros locales.
5. Entra al detalle de cada trabajo.
6. Exporta solo filas con resumen.
7. Actualiza el Excel del mismo tema sin duplicar enlaces.

## Ejecucion Interactiva

```powershell
python cli.py
```

El programa pregunta tema, cantidad y filtros.

## Interfaz Web Local

```powershell
python cli.py --web
```

El servidor abre:

```text
http://127.0.0.1:8765
```

Desde el panel se puede definir tema, cantidad, filtros, modo de fuente y ejecutar una corrida. El backend llama al mismo `cli.py`, por lo que las reglas de resumen obligatorio, Excel por tema y deduplicacion se mantienen.

Si el puerto esta ocupado:

```powershell
python cli.py --web --port 8770
```

## Filtros

### Por anio

```powershell
python cli.py --source browser-export --topic pobreza --limit 300 --start-year 2018 --end-year 2025 --no-interactive
```

### Por grado

```powershell
python cli.py --source browser-export --topic pobreza --degree "Maestria,Doctorado" --limit 300 --no-interactive
```

Valores usuales:

- `Bachiller`
- `Licenciatura/Titulo profesional`
- `Maestria`
- `Doctorado`

### Por universidad

```powershell
python cli.py --source browser-export --topic pobreza --university "Universidad Nacional de San Agustin" --limit 100 --no-interactive
```

### Por region inferida

```powershell
python cli.py --source browser-export --topic pobreza --region "Arequipa" --limit 100 --no-interactive
```

La region no viene como filtro oficial RENATI. Se infiere desde el nombre de la universidad.

## Columnas del Excel

- `id`
- `tema`
- `tipo_acceso`
- `palabras_clave`
- `fecha_publicacion`
- `enlace_documento_original`
- `resumen`
- `universidad`
- `region_inferida`
- `grado_tesis`
- `anio_publicacion`
- `mes_publicacion`
- `titulo`
- `autor`

## Reglas Importantes

1. El Excel se genera por tema: `renati_resultados_pobreza.xlsx`, `renati_resultados_economia.xlsx`, etc.
2. Cada Excel tiene una sola pestaña llamada `resultados`.
3. El resumen es obligatorio por defecto.
4. Si un trabajo no tiene resumen recuperable, se omite.
5. Si una corrida posterior del mismo tema encuentra resumen para un enlace previamente incompleto, el archivo conserva la version con resumen mas largo.
6. Los campos `resumen` y `palabras_clave` se extraen de secciones y metadatos reconocidos; URLs, codigos PURL/OCDE y bloques de navegacion se descartan.
7. No usar `--skip-summary` para produccion.

## Opciones Avanzadas

Permitir filas sin resumen:

```powershell
python cli.py --source browser-export --topic pobreza --limit 300 --allow-missing-summary --no-interactive
```

Desactivar fallback de navegador en detalle:

```powershell
python cli.py --source browser-export --topic pobreza --limit 300 --no-detail-browser-fallback --no-interactive
```

Definir version de Chrome si ChromeDriver falla:

```powershell
$env:RENATI_CHROME_VERSION_MAIN="147"
python cli.py --source browser-export --topic pobreza --limit 300 --no-interactive
```

Cambiar nombre del Excel:

```powershell
python cli.py --source browser-export --topic pobreza --output-file renati_mapeo_final.xlsx --limit 300 --no-interactive
```

## Validacion

Ejecutar pruebas:

```powershell
python -m pytest -q
```

Validar sintaxis:

```powershell
python -m compileall -q renati_scraping cli.py tests
```

## Problemas Comunes

### RENATI muestra Anubis o "not a bot"

Usar `--source browser-export`. No usar `--source renati` en produccion.

### ChromeDriver no coincide con Chrome

Definir:

```powershell
$env:RENATI_CHROME_VERSION_MAIN="147"
```

Cambiar `147` por la version principal de Chrome instalada.

### Salen menos registros que el limite

Eso significa que algunos candidatos no tenian resumen recuperable o fueron filtrados. Subir `--max-pages` no aplica al modo `browser-export`; relajar filtros o usar un tema mas amplio.

### Quiero revisar trabajos omitidos

Ejecutar con `--allow-missing-summary`, pero no usar ese Excel como version final si el resumen es requisito obligatorio.
