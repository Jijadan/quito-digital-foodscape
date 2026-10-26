# Changelog · Registro de cambios

All notable changes to this repository. Dates are YYYY-MM-DD.
Todos los cambios relevantes de este repositorio. Fechas en formato AAAA-MM-DD.

## [1.1.0] — 2026-10-26 · First revision (R1) · Primera revisión (R1)

The June 2026 census and the original analysis code are unchanged. Everything below was added or reorganized.
El censo de junio de 2026 y el código de análisis original no cambian. Todo lo que sigue se añadió o reorganizó.

### Added · Añadido

- `data/revision-R1/verification/` — online verification of the 116 establishments without platform presence (October 2026) and TripAdvisor check of the 4 without a Google Maps listing (Supplementary S7). · Verificación en línea de los 116 establecimientos sin presencia en plataformas y comprobación en TripAdvisor de los 4 sin ficha en Google Maps.
- `data/revision-R1/typology-coding/` — anonymized blind coding of the typology by four independent chefs (C1–C4) and the first author (J). · Codificación ciega anonimizada de la tipología.
- `data/revision-R1/typology-results/` and `data/revision-R1/sensitivity/` — reliability and sensitivity results (Supplementary S6–S8). · Resultados de fiabilidad y sensibilidad.
- `data/geo/` — Historic Centre limit digitized from Instituto Metropolitano de Patrimonio (2019), GeoPackage and GeoJSON. · Límite del Centro Histórico digitalizado.
- `code/revision-R1/` — scripts of the revision. · Scripts de la revisión.
- `code/coding-app/` — Google Apps Script web app used by the chefs. · Aplicación web usada por los chefs.
- `code/analysis/figuras_paper_frontiers.py` — figure script of the article. · Script de figuras del artículo.
- Bilingual README (`README.md`, `README.es.md`), data dictionary matching the actual CSV columns, code documentation, `CITATION.cff`, `requirements.txt`, landing page and banner. · README bilingüe, diccionario de datos acorde con las columnas reales del CSV, documentación del código, archivo de citación, dependencias, página de inicio y banner.

### Changed · Cambiado

- Interactive maps: categories shown with the article's names (*Unclassified* / *Sin clasificar*, *Regional Ecuadorian cuisine* / *Cocina ecuatoriana regional*, *Grill* / *Parrilla*); typo *Parilla* corrected; two unused external script calls removed; page description added. The data in the maps are unchanged. · Mapas interactivos: categorías con los nombres del artículo; corregida la errata *Parilla*; eliminadas dos llamadas a scripts externos sin uso; añadida descripción de página. Los datos de los mapas no cambian.
- `code/interactive-map/Code.gs` — same display names applied when the maps are regenerated. · Los mismos nombres al regenerar los mapas.
- Files reorganized into `code/` (`Code.gs` → `code/interactive-map/`, `collection-validation.gs` → `code/data-collection/`, analysis script → `code/analysis/`); `LICENCE.txt` → `LICENSE`. Map URLs are unchanged. · Archivos reorganizados en `code/`; las URL de los mapas no cambian.

### Removed · Eliminado

- Personal contact e-mail from the README. Questions go to the issues page or to the corresponding author. · Correo personal del README.

## [1.0.1] — 2026-08-28 · Public release · Versión pública

Archived on Zenodo: https://doi.org/10.5281/zenodo.22178448

- Census of 420 establishments (`data/restaurantes_quito_CH_clean.csv`), analysis script, map generator, data collection scripts and the two interactive maps (English and Spanish), as cited in the submitted manuscript. · Censo de 420 establecimientos, script de análisis, generador del mapa, scripts de recolección y los dos mapas interactivos, tal como se citan en el manuscrito enviado.
