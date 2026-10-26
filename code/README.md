# Code · Código

**[English](#english)** · **[Español](#español)**

---

## English

| Folder | Language | What it does |
|---|---|---|
| [`analysis/`](analysis/) | Python | Original analysis pipeline of the article |
| [`revision-R1/`](revision-R1/) | Python | Analyses added in the first revision ([details](revision-R1/README.md)) |
| [`data-collection/`](data-collection/) | Google Apps Script | Geocoding, coordinate validation and Google Maps ratings during the census (June 2026) |
| [`interactive-map/`](interactive-map/) | Google Apps Script | Generates the two interactive maps (English and Spanish) from the research spreadsheet |
| [`coding-app/`](coding-app/) | Google Apps Script | Web app used by the chefs to code the typology blind (Supplementary S6) |

### `analysis/`

- **`analisis_espacial_quito_v2_capital_digital.py`** — the full analysis: descriptive statistics, the composite digital index (principal component analysis), the stratification gradient, kernel density surfaces, Getis-Ord Gi* and Moran's I on a regular grid, the negative binomial regression and the franchise comparison. It writes every table (CSV), a complete log (`informe_analisis.txt`) and the figures.

  ```bash
  python code/analysis/analisis_espacial_quito_v2_capital_digital.py \
         --csv data/restaurantes_quito_CH_clean.csv --outdir outputs/
  ```

- **`figuras_paper_frontiers.py`** — draws the seven figures of the article at journal size (vector PDF and 600 dpi PNG), reusing the functions of the script above. It optionally reads two municipal shapefiles (`zet_centro_historico_a.shp`, `catastro_turismo_p.shp`) from the open data portal of Quito; they are not redistributed here, and the figures are drawn without them if they are absent.

Both scripts fix the random seed, so permutation tests give the same results on every run.

### `data-collection/collection-validation.gs`

Bound to the data collection spreadsheet. It geocodes each establishment (Geocoding API with the exact address first, then Places search with name and address), checks that the point falls inside the Historic Centre, and reads the Google Maps rating and review count. **The API key is never written in the code.** It is read at run time from cell A1 of a sheet tab called `Configuracion`.

### `interactive-map/Code.gs`

Bound to the research spreadsheet. `generarMapaHtml()` writes the Spanish map and `generarMapaHtmlEn()` the English one, as self-contained Leaflet pages. Category names are translated for display (`Desconocido` → *Unclassified* / *Sin clasificar*; `Comida Ecuatoriana` → *Regional Ecuadorian cuisine* / *Cocina ecuatoriana regional*); the data are not changed.

### `coding-app/`

The web app that four independent chefs used to code a blind sample of 67 establishments from Google Maps photographs. Each coder opens a personal link with a token; the server checks the token on every call and decides which case to show. The app includes a practice round, the codebook (`libro.html`) and instructions (`instrucciones.html`). Coders are identified only as C1–C4 and J.

To deploy a copy: create a Google Sheet, open *Extensions → Apps Script*, add the files, and run the steps of the **Codificación** menu (create tabs, import cases, import photos, generate tokens). Deploy as a web app executed as the owner. The cases, photographs and the key that links blind codes to establishments are not included.

---

## Español

| Carpeta | Lenguaje | Qué hace |
|---|---|---|
| [`analysis/`](analysis/) | Python | Flujo de análisis original del artículo |
| [`revision-R1/`](revision-R1/) | Python | Análisis añadidos en la primera revisión ([detalle](revision-R1/README.md#español)) |
| [`data-collection/`](data-collection/) | Google Apps Script | Geocodificación, validación de coordenadas y calificaciones de Google Maps durante el censo (junio de 2026) |
| [`interactive-map/`](interactive-map/) | Google Apps Script | Genera los dos mapas interactivos (inglés y español) desde la hoja de cálculo de la investigación |
| [`coding-app/`](coding-app/) | Google Apps Script | Aplicación web con la que los chefs codificaron a ciegas la tipología (Suplementario S6) |

### `analysis/`

- **`analisis_espacial_quito_v2_capital_digital.py`** — el análisis completo: estadística descriptiva, índice digital compuesto (análisis de componentes principales), gradiente de estratificación, superficies de densidad por núcleo, Getis-Ord Gi* e I de Moran sobre una malla regular, regresión binomial negativa y comparación de franquicias. Escribe todas las tablas (CSV), un registro completo (`informe_analisis.txt`) y las figuras.

  ```bash
  python code/analysis/analisis_espacial_quito_v2_capital_digital.py \
         --csv data/restaurantes_quito_CH_clean.csv --outdir outputs/
  ```

- **`figuras_paper_frontiers.py`** — dibuja las siete figuras del artículo al tamaño de la revista (PDF vectorial y PNG a 600 dpi), reutilizando las funciones del script anterior. Puede leer, de forma opcional, dos shapefiles municipales (`zet_centro_historico_a.shp`, `catastro_turismo_p.shp`) del portal de datos abiertos de Quito; no se redistribuyen aquí y, si no están, las figuras se dibujan sin ellos.

Los dos scripts fijan la semilla aleatoria, así que las pruebas de permutación dan los mismos resultados en cada ejecución.

### `data-collection/collection-validation.gs`

Vinculado a la hoja de recolección. Geocodifica cada establecimiento (primero la Geocoding API con la dirección exacta, luego la búsqueda de Places con nombre y dirección), comprueba que el punto cae dentro del Centro Histórico y lee la calificación y el número de reseñas de Google Maps. **La API key nunca se escribe en el código.** Se lee al ejecutar desde la celda A1 de una pestaña llamada `Configuracion`.

### `interactive-map/Code.gs`

Vinculado a la hoja de la investigación. `generarMapaHtml()` escribe el mapa en español y `generarMapaHtmlEn()` el mapa en inglés, como páginas Leaflet autónomas. Los nombres de categoría se traducen solo para mostrarlos (`Desconocido` → *Sin clasificar* / *Unclassified*; `Comida Ecuatoriana` → *Cocina ecuatoriana regional* / *Regional Ecuadorian cuisine*); los datos no cambian.

### `coding-app/`

La aplicación web con la que cuatro chefs independientes codificaron una muestra ciega de 67 establecimientos a partir de fotografías de Google Maps. Cada codificador abre un enlace personal con un token; el servidor comprueba el token en cada llamada y decide qué caso mostrar. Incluye una ronda de práctica, el libro de códigos (`libro.html`) y las instrucciones (`instrucciones.html`). Los codificadores se identifican solo como C1–C4 y J.

Para desplegar una copia: cree una hoja de Google, abra *Extensiones → Apps Script*, añada los archivos y ejecute los pasos del menú **Codificación** (crear pestañas, importar casos, importar fotos, generar tokens). Implemente como aplicación web ejecutada como el propietario. Los casos, las fotografías y la llave que vincula los códigos ciegos con los establecimientos no se incluyen.
