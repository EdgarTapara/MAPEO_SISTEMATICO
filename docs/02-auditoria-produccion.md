# Auditoria de Produccion - RENATI Scraping

Fecha: 2026-05-02

## Estado Auditado

El proyecto ya no debe tratarse como notebook experimental. Ahora tiene estructura local:

- `cli.py`: interfaz de ejecucion.
- `renati_scraping/core/`: cliente, navegador, parser, detalle, filtros y exportador.
- `tests/`: pruebas unitarias/offline.
- `data/output/renati_resultados_{tema}.xlsx`: salida por tema en una sola pestaña.

## Problemas Encontrados

1. Se generaban varios Excel por corrida. Eso era malo para produccion porque fragmentaba resultados y confundia la validacion.
2. Algunas corridas permitian `--skip-summary`, dejando la columna `resumen` vacia.
3. El modo `requests` contra RENATI esta bloqueado por Anubis; no debe ser la ruta principal.
4. La paginacion HTML es fragil para llegar a 300 registros porque depende del tamano de pagina que RENATI renderice.
5. Filtro por region no existe de forma nativa en RENATI; solo es viable inferirlo desde universidad.
6. La carpeta contenia artefactos temporales de pytest y Excels de prueba. Los Excels separados se limpiaron; las carpetas `pytest-cache-files-*` quedaron bloqueadas por permisos del sistema/OneDrive.

## Mejoras Implementadas

1. Salida por tema: `data/output/renati_resultados_pobreza.xlsx`, `data/output/renati_resultados_economia.xlsx`, etc.
2. Deduplicacion dentro del archivo del tema por `enlace_documento_original`.
3. Deduplicacion adicional por `titulo + universidad`, porque el mismo trabajo puede aparecer con URL RENATI y URL del repositorio.
4. Si existen duplicados, el archivo del tema conserva la fila con resumen mas largo.
5. IDs estables por tema: `RENATI-pobreza-00001`, etc.
6. Modo principal `browser-export`: usa navegador para pasar Anubis y descarga el CSV oficial de RENATI antes de filtrar.
7. El detalle/resumen es obligatorio por defecto. Las filas sin resumen se omiten, salvo uso explicito de `--allow-missing-summary`.
8. Fallback de navegador para detalle activado por defecto.
9. Tests ampliados para consolidacion, preferencia por filas con resumen y preferencia por resumen mas largo.

## Criterio de Produccion

Usar:

```powershell
python cli.py --source browser-export --topic pobreza --limit 300 --no-interactive
```

No usar en produccion:

```powershell
--skip-summary
```

Ese flag solo existe para pruebas tecnicas.

## Riesgos Residuales

- Algunos repositorios institucionales pueden no publicar resumen en HTML. Por defecto esas filas no entran al Excel.
- `undetected-chromedriver` depende de Chrome instalado. Si falla la version, definir `RENATI_CHROME_VERSION_MAIN`.
- La region es inferida por nombre de universidad, no una variable oficial RENATI.
