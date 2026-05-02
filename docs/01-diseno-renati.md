# Diseño RENATI Scraping

## Diagnóstico

RENATI carga la búsqueda simple con `htmx`. El HTML visible solo contiene el contenedor:

```html
<section id="data-busqueda" hx-get="/busqueda/simple/data?q=...">
```

Por eso el notebook original falla: intenta parsear tarjetas desde la shell de la página o usa selectores demasiado débiles para la respuesta parcial.

## Decisión

Se crea un proyecto local standalone, inspirado en la estructura de `bcrp-scraping`, pero sin copiar módulos innecesarios. Para Sprint 2 se prioriza:

- `requests` + BeautifulSoup para CSV/detalle simple.
- `undetected-chromedriver` para RENATI vivo cuando aparece Anubis.
- Parser tolerante para HTML de RENATI y fallback para CSV exportado.
- Filtros locales por año, grado, universidad y región.
- Excel final de una sola pestaña.

## Región

RENATI no expone región como filtro robusto en la búsqueda simple. La alternativa viable es inferir región desde la universidad con un catálogo local en `core/regions.py`. El catálogo inicial cubre universidades frecuentes y puede ampliarse sin tocar el scraper.

## Resumen

El resumen es indispensable y no está en el listado. La implementación entra a la página `/item/...` o handle de cada trabajo, parsea metadatos/HTML y guarda el resultado en el Excel. Para casos donde `requests` no alcanza, el CLI permite `--detail-browser-fallback`.
