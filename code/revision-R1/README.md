# Revision R1 scripts · Scripts de la revisión R1

**[English](#english)** · **[Español](#español)**

---

## English

These scripts produce the analyses added in the first round of peer review. None of them modifies the original pipeline or the June 2026 data. They import the functions of [`../analysis/`](../analysis/) read-only, so the kernel, the Gi* statistic and the index are exactly the ones used in the article, and block A of `R1_sensibilidad.py` checks that the submitted figures are reproduced before running any variant.

| Script | Output | Supplementary |
|---|---|---|
| `R1_digitalizar_limite_IMP.py` | Historic Centre limit digitized from the vector map in IMP (2019, p. 98), georeferenced from the local TM-Quito grid printed on the map → [`data/geo/`](../../data/geo/) | S8 |
| `R1_sensibilidad.py` | Blocks A–J: baseline reproduction, bandwidth (75–250 m), grid size and origin, point-level Gi* and local join counts, edge effect, index variants, closure scenarios for the 116, characterization of the 116 → [`data/revision-R1/sensitivity/`](../../data/revision-R1/sensitivity/) | S7, S8 |
| `R1_nucleo_robusto.py` | Share of the 20 grid arrangements in which each establishment lies in a significant hot cell; robust core (share ≥ 0.75) | S8 |
| `R1_tipologia_fiabilidad.py` | Krippendorff's α, pairwise agreement, consensus against the original label, confusion matrices → [`data/revision-R1/typology-results/`](../../data/revision-R1/typology-results/) | S6 |
| `R1_tipologia_sensibilidad_IG.py` | Instagram contrast (Traditional vs New traditional) under each alternative coding | S6 |
| `R1_tablas_suplementario.py` | LaTeX tables of the Supplementary Material, written from the results so that no figure is copied by hand | S1, S6–S8 |
| `R1_figuras.py` | Revised Figures 1, 4, 5 and 6 and Figure S8.1: OpenStreetMap basemap, coordinate grid and study limit, added at run time to the original figure code | — |

### Running them

The scripts were run from the authors' working folder, whose layout differs from this repository. Each one takes `--raiz` (project root) and builds its input paths from it. To run them here, place the inputs as follows or edit the path at the top of each script.

| Path expected by the scripts | File in this repository |
|---|---|
| `final_figures_CODE/restaurantes_quito_CH_clean.csv` | `data/restaurantes_quito_CH_clean.csv` |
| `final_figures_CODE/analisis_espacial_quito_v2_capital_digital.py` | `code/analysis/analisis_espacial_quito_v2_capital_digital.py` |
| `final_figures_CODE/figuras_paper_frontiers.py` | `code/analysis/figuras_paper_frontiers.py` |
| `R1_v2_borrador/datos/limite_CHQ_IMP2019_digitalizado.gpkg` (`--limite`) | `data/geo/historic_centre_limit_IMP2019.gpkg` |
| `revision_R1/datos/…verificacion_116…` | `data/revision-R1/verification/online_verification_116_oct2026.csv` (English column names) |
| `R1_v2_borrador/resultados/` | `data/revision-R1/sensitivity/` and `data/revision-R1/typology-results/` |

**What cannot be rerun from this repository.** `R1_tipologia_fiabilidad.py` and `R1_tipologia_sensibilidad_IG.py` need the key that links the chefs' blind codes to the establishments. The key is withheld to keep the coding blind and is not published. Their outputs are published in full in `data/revision-R1/typology-results/`, and the anonymized answers in `data/revision-R1/typology-coding/`.

`R1_figuras.py` downloads OpenStreetMap tiles or street geometry the first time it runs (© OpenStreetMap contributors, ODbL).

---

## Español

Estos scripts producen los análisis añadidos en la primera ronda de revisión por pares. Ninguno modifica el flujo original ni los datos de junio de 2026. Importan en modo lectura las funciones de [`../analysis/`](../analysis/), así que el núcleo, el estadístico Gi* y el índice son exactamente los del artículo, y el bloque A de `R1_sensibilidad.py` comprueba que las cifras enviadas se reproducen antes de ejecutar cualquier variante.

| Script | Salida | Suplementario |
|---|---|---|
| `R1_digitalizar_limite_IMP.py` | Límite del Centro Histórico digitalizado del mapa vectorial de IMP (2019, p. 98), georreferenciado con la cuadrícula local TM-Quito impresa en el mapa → [`data/geo/`](../../data/geo/) | S8 |
| `R1_sensibilidad.py` | Bloques A–J: reproducción de la línea base, ancho de banda (75–250 m), tamaño y origen de la malla, Gi* y recuento local de uniones a nivel de punto, efecto de borde, variantes del índice, escenarios de cierre de los 116, caracterización de los 116 → [`data/revision-R1/sensitivity/`](../../data/revision-R1/sensitivity/) | S7, S8 |
| `R1_nucleo_robusto.py` | Proporción de las 20 configuraciones de malla en que cada establecimiento cae en una celda caliente significativa; núcleo robusto (proporción ≥ 0,75) | S8 |
| `R1_tipologia_fiabilidad.py` | α de Krippendorff, acuerdo por pares, consenso frente a la etiqueta original, matrices de confusión → [`data/revision-R1/typology-results/`](../../data/revision-R1/typology-results/) | S6 |
| `R1_tipologia_sensibilidad_IG.py` | Contraste de Instagram (Tradicional frente a Nuevo tradicional) con cada codificación alternativa | S6 |
| `R1_tablas_suplementario.py` | Tablas LaTeX del Material Suplementario, escritas desde los resultados para que ninguna cifra se copie a mano | S1, S6–S8 |
| `R1_figuras.py` | Figuras 1, 4, 5 y 6 revisadas y Figura S8.1: mapa base de OpenStreetMap, retícula de coordenadas y límite del estudio, añadidos al ejecutar el código original de las figuras | — |

### Cómo ejecutarlos

Los scripts se ejecutaron desde la carpeta de trabajo de los autores, cuya estructura es distinta de la de este repositorio. Cada uno recibe `--raiz` (raíz del proyecto) y construye desde ella las rutas de entrada. Para ejecutarlos aquí, coloque los archivos como se indica o cambie la ruta al inicio de cada script.

| Ruta que esperan los scripts | Archivo en este repositorio |
|---|---|
| `final_figures_CODE/restaurantes_quito_CH_clean.csv` | `data/restaurantes_quito_CH_clean.csv` |
| `final_figures_CODE/analisis_espacial_quito_v2_capital_digital.py` | `code/analysis/analisis_espacial_quito_v2_capital_digital.py` |
| `final_figures_CODE/figuras_paper_frontiers.py` | `code/analysis/figuras_paper_frontiers.py` |
| `R1_v2_borrador/datos/limite_CHQ_IMP2019_digitalizado.gpkg` (`--limite`) | `data/geo/historic_centre_limit_IMP2019.gpkg` |
| `revision_R1/datos/…verificacion_116…` | `data/revision-R1/verification/online_verification_116_oct2026.csv` (columnas con nombres en inglés) |
| `R1_v2_borrador/resultados/` | `data/revision-R1/sensitivity/` y `data/revision-R1/typology-results/` |

**Lo que no se puede volver a ejecutar desde este repositorio.** `R1_tipologia_fiabilidad.py` y `R1_tipologia_sensibilidad_IG.py` necesitan la llave que vincula los códigos ciegos de los chefs con los establecimientos. La llave se retiene para mantener ciega la codificación y no se publica. Sus resultados se publican completos en `data/revision-R1/typology-results/`, y las respuestas anonimizadas en `data/revision-R1/typology-coding/`.

`R1_figuras.py` descarga teselas o la geometría de calles de OpenStreetMap la primera vez que se ejecuta (© colaboradores de OpenStreetMap, ODbL).
