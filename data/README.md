# Data dictionary · Diccionario de datos

**[English](#english)** · **[Español](#español)**

---

## English

### Files

| File | Rows | Description |
|---|---:|---|
| [`restaurantes_quito_CH_clean.csv`](restaurantes_quito_CH_clean.csv) | 420 | Census of food establishments in the Historic Centre of Quito with their platform presence (June 2026). This is the file the analysis reads. |
| [`geo/historic_centre_limit_IMP2019.gpkg`](geo/) · `.geojson` | 1 | Limit of the Historic Centre (central core and buffer zone), digitized from Instituto Metropolitano de Patrimonio (2019, p. 98). WGS84 (EPSG:4326). 408 of the 420 establishments lie within it. |
| [`revision-R1/verification/online_verification_116_oct2026.csv`](revision-R1/verification/) | 116 | Online verification of the establishments with no platform presence (October 2026). Supplementary S7. |
| [`revision-R1/verification/tripadvisor_check_4_without_gmaps.csv`](revision-R1/verification/) | 4 | TripAdvisor check of the establishments with Instagram or TikTok but no Google Maps listing. |
| [`revision-R1/typology-coding/coder_responses_anonymized_2026-10-21.csv`](revision-R1/typology-coding/) | 335 | Blind coding of the typology by four independent chefs (C1–C4) and the first author (J). Supplementary S6. |
| [`revision-R1/typology-results/`](revision-R1/typology-results/) | — | Reliability results of the typology (agreement, confusion matrices, Instagram sensitivity). |
| [`revision-R1/sensitivity/`](revision-R1/sensitivity/) | — | Sensitivity analyses: bandwidth, grid, point level, edge effect, index variants, closure scenarios. Supplementary S7–S8. |

**Row identifier.** The census file has no explicit ID column. `census_id` (or `id_censo`) in the revision files is the 1-based row number of `restaurantes_quito_CH_clean.csv`.

### Main file: `restaurantes_quito_CH_clean.csv`

Column names are kept in Spanish, as used by the analysis code.

| Column | Type | Description |
|---|---|---|
| `Nombre` | text | Name as it appears in the municipal tourism registry |
| `Dirección` | text | Address from the registry, with ", Quito, Ecuador" appended |
| `lat`, `lon` | number | Coordinates, WGS84 (EPSG:4326) |
| `coord_source` | text | `primaria_C_D`: geocoded from name and address and validated inside the Historic Centre (290). `respaldo_R_S`: geocoded from the address only (130) |
| `dist_plaza_grande_km` | number | Straight-line distance to Plaza Grande (Plaza de la Independencia), km |
| `existe_gmaps` | boolean | Has a Google Maps listing (`True` 300, `False` 120) |
| `estrellas_num` | number | Mean Google Maps rating, 1–5. Empty if there is no listing. `0` if the listing has no reviews (24 cases); this is not a rating of zero |
| `Cantidad de Reseñas` | integer | Number of Google Maps reviews (0 if none or no listing) |
| `log1p_resenas` | number | log(1 + reviews) |
| `Tiene IG` | 0/1 | Has an Instagram account (99) |
| `Seguidores IG` | integer | Instagram followers (0 if no account) |
| `log1p_seguidores_ig` | number | log(1 + Instagram followers) |
| `Tiene TikTok` | 0/1 | Has a TikTok account (63) |
| `Seguidores TT` | integer | TikTok followers (0 if no account) |
| `log1p_seguidores_tt` | number | log(1 + TikTok followers) |
| `Likes TT` | integer | Cumulative TikTok likes. Not part of the main index because of extreme concentration; used only in the sensitivity specification (Supplementary S2) |
| `Tipo Restaurante` | text | Culinary typology developed by the research team (see below) |
| `tipo_restaurante_ui` | text | Same typology as used by the map generator (`Desconocido` shown as `Otro`) |
| `Franquicia` | text | `Franquicia` (franchise, 23) or `No posee` (independent, 397) |
| `franquicia_bin` | 0/1 | 1 = franchise |
| `marca_id` | text | Brand identifier. Establishments that share a brand account carry the same value |
| `cuenta_social_duplicada` | boolean | The social media account is shared with another row of the census (3 rows). Used in a robustness check without duplicated accounts |
| `AÑO REGISTRO` | year | Year of entry in the tourism registry (2 missing) |
| `CATEGORÍA` | text | Administrative category of the registry, by forks: `LUJO / 5 TENEDORES`, `PRIMERA / 4`, `SEGUNDA / 3`, `TERCERA / 2`, `CUARTA / 1 TENEDOR` (2 missing) |
| `Instagram` | text | Instagram handle, or `No tiene` |
| `URL IG` | text | Instagram profile URL, or `0` |
| `TikTok` | text | TikTok handle, or `No tiene` |
| `URL Tik Tok` | text | TikTok profile URL, or `0` |

### Culinary typology (`Tipo Restaurante`)

The typology was developed by the research team because the registry categories group business models and ways of cooking that have little in common. The article and the interactive maps use the display names in the second and third columns. The values in the CSV are unchanged.

| Value in CSV | Display name (EN) | Display name (ES) | n | Meaning |
|---|---|---|---:|---|
| `Tradicional` | Traditional | Tradicional | 100 | Highland Quito cuisine in an everyday register. Largely the *huecas*: small neighbourhood places known for one dish, with low prices. Coded from everyday tableware, dishes served by the portion and a short offer |
| `Nuevo Tradicional` | New traditional | Nuevo tradicional | 27 | A similar repertoire in a contemporary register: revised plating, a structured menu, a different form of service and higher prices. The two categories describe two ways of presenting heritage, not degrees of authenticity |
| `Comida Ecuatoriana` | Regional Ecuadorian cuisine | Cocina ecuatoriana regional | 43 | Ecuadorian cuisines from outside the highland Quito repertoire, mainly coastal |
| `Fast Food` | Fast food | Comida rápida | 56 | Fast food, including national and international chains |
| `Internacional` | International | Internacional | 35 | Non-Ecuadorian cuisines |
| `Bar` | Bar | Bar | 18 | Mainly drinks |
| `Cafetería` | Café | Cafetería | 13 | Cafés, breakfast and afternoon snacks |
| `Parrilla` | Grill | Parrilla | 6 | Grills and roasts |
| `Saludable` | Healthy | Saludable | 3 | Offer centred on healthy food |
| `Casa Cultural` | Cultural house | Casa cultural | 1 | Cultural venue with a secondary food offer |
| `Hostal` | Hostel | Hostal | 1 | Hostel with restaurant or café |
| `Catering` | Catering | Catering | 1 | Catering without on-site service |
| `Desconocido` | Unclassified | Sin clasificar | 116 | No type information could be assigned. Its coefficient in the regression has no substantive interpretation |

The codebook and the reliability assessment with four independent chefs are in Supplementary S6.

### Revision files

**`online_verification_116_oct2026.csv`** — one row per establishment without platforms. Values are in Spanish.

| Column | Description |
|---|---|
| `census_id`, `name`, `address`, `lat`, `lon` | Identification, as in the census |
| `type_june2026` | `Tipo Restaurante` in the census |
| `fork_category` | `CATEGORÍA` in the census |
| `status_oct2026` | `Operativo` (evidence of operation, 6), `Cerrado/trasladado` (closed or relocated, 13), `Sin evidencia` (no evidence found, 97) |
| `alternative_digital_presence` | Presence outside the three platforms: `Ninguna`, `Facebook`, `Google Maps (nueva)` (listing created after June), `Varias` |
| `web_evidence_of_operation` | Web evidence that it operates: `Sí`, `Dudoso` (doubtful), `No` |
| `web_most_recent_evidence` | Date of the most recent evidence found |
| `google_maps_listing_oct2026`, `google_maps_listing_status` | Listing found in October and its status (`Abierto`, `Cerrado permanentemente`, `Sin indicación`) |
| `facebook_page`, `facebook_last_post` | Facebook page and date of the last post |
| `whatsapp_business_evidence` | WhatsApp Business evidence |
| `tripadvisor_listing` | TripAdvisor listing |
| `streetview_image_date` | Date of the most recent Street View image (year-month) |
| `offer_validated_oct2026`, `offer_evidence` | Food offer as validated by the first author, and the evidence used (`Descripción textual`, `Solo nombre`, `Sin fuente`) |
| `sources_with_findings` | Sources that returned information: `GEN` general web search, `GM` Google Maps, `SV` Street View, `FB` Facebook |

**`coder_responses_anonymized_2026-10-21.csv`** — one row per answer (5 coders × 67 establishments).

| Column | Description |
|---|---|
| `timestamp` | Time of the answer (UTC) |
| `coder` | `C1`–`C4` independent chefs, `J` first author |
| `blind_code` | Blind code of the establishment. The key that links it to the census is withheld |
| `position` | Order in which the establishment was shown |
| `answer_level1` | First-level answer: `tradicional`, `nuevo_tradicional`, `regional`, `otra`, `no_determinable` |
| `answer` | Final category |
| `reason_not_determinable` | Reason when the category could not be determined |
| `confidence` | Self-reported confidence: `alta` (high), `media` (medium), `baja` (low); empty when not determinable |
| `knows_establishment` | Whether the coder knew the place |
| `time_ms` | Time spent on the item, milliseconds |
| `comment` | Free comment |

The tables in `typology-results/` and `sensitivity/` are outputs of the scripts in [`code/revision-R1/`](../code/revision-R1/). Their column names are in Spanish and they are described in Supplementary S6–S8.

### Notes

- **Dates.** Platform data were recorded manually during the first half of June 2026. They are not live values and may have changed.
- **Absence is not closure.** An establishment without platforms may be open but offline, closed, relocated, or present on platforms not examined. The online verification of October 2026 bounds this share.
- **Platform fields** are dated, aggregate, publicly visible values recorded by the research team. They are not an export or scrape of any platform, and they contain no platform content or personal user data.
- **Use.** For research and dissemination. Not a commercial directory or a recommendation.

---

## Español

### Archivos

| Archivo | Filas | Descripción |
|---|---:|---|
| [`restaurantes_quito_CH_clean.csv`](restaurantes_quito_CH_clean.csv) | 420 | Censo de establecimientos de comida del Centro Histórico de Quito con su presencia en plataformas (junio de 2026). Es el archivo que lee el análisis. |
| [`geo/historic_centre_limit_IMP2019.gpkg`](geo/) · `.geojson` | 1 | Límite del Centro Histórico (núcleo central y zona de amortiguamiento), digitalizado de Instituto Metropolitano de Patrimonio (2019, p. 98). WGS84 (EPSG:4326). 408 de los 420 establecimientos quedan dentro. |
| [`revision-R1/verification/online_verification_116_oct2026.csv`](revision-R1/verification/) | 116 | Verificación en línea de los establecimientos sin presencia en plataformas (octubre de 2026). Suplementario S7. |
| [`revision-R1/verification/tripadvisor_check_4_without_gmaps.csv`](revision-R1/verification/) | 4 | Comprobación en TripAdvisor de los establecimientos con Instagram o TikTok pero sin ficha en Google Maps. |
| [`revision-R1/typology-coding/coder_responses_anonymized_2026-10-21.csv`](revision-R1/typology-coding/) | 335 | Codificación ciega de la tipología por cuatro chefs independientes (C1–C4) y el primer autor (J). Suplementario S6. |
| [`revision-R1/typology-results/`](revision-R1/typology-results/) | — | Resultados de fiabilidad de la tipología (acuerdo, matrices de confusión, sensibilidad de Instagram). |
| [`revision-R1/sensitivity/`](revision-R1/sensitivity/) | — | Análisis de sensibilidad: ancho de banda, malla, nivel de punto, efecto de borde, variantes del índice, escenarios de cierre. Suplementario S7–S8. |

**Identificador de fila.** El censo no tiene una columna de ID. `census_id` (o `id_censo`) en los archivos de la revisión es el número de fila, empezando en 1, de `restaurantes_quito_CH_clean.csv`.

### Archivo principal: `restaurantes_quito_CH_clean.csv`

| Columna | Tipo | Descripción |
|---|---|---|
| `Nombre` | texto | Nombre tal como figura en el catastro turístico municipal |
| `Dirección` | texto | Dirección del catastro, con ", Quito, Ecuador" al final |
| `lat`, `lon` | número | Coordenadas, WGS84 (EPSG:4326) |
| `coord_source` | texto | `primaria_C_D`: geocodificada con nombre y dirección y validada dentro del Centro Histórico (290). `respaldo_R_S`: geocodificada solo con la dirección (130) |
| `dist_plaza_grande_km` | número | Distancia en línea recta a la Plaza Grande (Plaza de la Independencia), km |
| `existe_gmaps` | booleano | Tiene ficha en Google Maps (`True` 300, `False` 120) |
| `estrellas_num` | número | Calificación media en Google Maps, 1–5. Vacío si no hay ficha. `0` si la ficha no tiene reseñas (24 casos); no es una calificación de cero |
| `Cantidad de Reseñas` | entero | Número de reseñas en Google Maps (0 si no tiene o no hay ficha) |
| `log1p_resenas` | número | log(1 + reseñas) |
| `Tiene IG` | 0/1 | Tiene cuenta de Instagram (99) |
| `Seguidores IG` | entero | Seguidores en Instagram (0 si no tiene cuenta) |
| `log1p_seguidores_ig` | número | log(1 + seguidores en Instagram) |
| `Tiene TikTok` | 0/1 | Tiene cuenta de TikTok (63) |
| `Seguidores TT` | entero | Seguidores en TikTok (0 si no tiene cuenta) |
| `log1p_seguidores_tt` | número | log(1 + seguidores en TikTok) |
| `Likes TT` | entero | Likes acumulados en TikTok. No forma parte del índice principal por su concentración extrema; solo se usa en la especificación de sensibilidad (Suplementario S2) |
| `Tipo Restaurante` | texto | Tipología culinaria elaborada por el equipo (ver abajo) |
| `tipo_restaurante_ui` | texto | La misma tipología tal como la usa el generador del mapa (`Desconocido` aparece como `Otro`) |
| `Franquicia` | texto | `Franquicia` (23) o `No posee` (independiente, 397) |
| `franquicia_bin` | 0/1 | 1 = franquicia |
| `marca_id` | texto | Identificador de marca. Los establecimientos que comparten una cuenta de marca tienen el mismo valor |
| `cuenta_social_duplicada` | booleano | La cuenta en redes se comparte con otra fila del censo (3 filas). Se usa en una prueba de robustez sin cuentas duplicadas |
| `AÑO REGISTRO` | año | Año de inscripción en el catastro (2 vacíos) |
| `CATEGORÍA` | texto | Categoría administrativa del catastro, por tenedores: `LUJO / 5 TENEDORES`, `PRIMERA / 4`, `SEGUNDA / 3`, `TERCERA / 2`, `CUARTA / 1 TENEDOR` (2 vacíos) |
| `Instagram` | texto | Usuario de Instagram, o `No tiene` |
| `URL IG` | texto | URL del perfil de Instagram, o `0` |
| `TikTok` | texto | Usuario de TikTok, o `No tiene` |
| `URL Tik Tok` | texto | URL del perfil de TikTok, o `0` |

### Tipología culinaria (`Tipo Restaurante`)

El equipo elaboró esta tipología porque las categorías del catastro agrupan modelos de negocio y formas de cocinar que tienen poco en común. El artículo y los mapas interactivos usan los nombres de la segunda y tercera columna. Los valores del CSV no se han modificado.

| Valor en el CSV | Nombre (EN) | Nombre (ES) | n | Significado |
|---|---|---|---:|---|
| `Tradicional` | Traditional | Tradicional | 100 | Cocina quiteña de la Sierra en registro cotidiano. Sobre todo las *huecas*: pequeños locales de barrio conocidos por un plato, de precios bajos. Se codifica por la vajilla cotidiana, el plato servido por porción y una oferta corta |
| `Nuevo Tradicional` | New traditional | Nuevo tradicional | 27 | Un repertorio similar en registro contemporáneo: emplatado revisado, carta estructurada, otra forma de servicio y precios más altos. Las dos categorías describen dos formas de presentar el patrimonio, no grados de autenticidad |
| `Comida Ecuatoriana` | Regional Ecuadorian cuisine | Cocina ecuatoriana regional | 43 | Cocinas ecuatorianas ajenas al repertorio quiteño de la Sierra, sobre todo costeñas |
| `Fast Food` | Fast food | Comida rápida | 56 | Comida rápida, incluidas cadenas nacionales e internacionales |
| `Internacional` | International | Internacional | 35 | Cocinas no ecuatorianas |
| `Bar` | Bar | Bar | 18 | Predominio de bebidas |
| `Cafetería` | Café | Cafetería | 13 | Cafeterías, desayunos y meriendas |
| `Parrilla` | Grill | Parrilla | 6 | Parrilladas y asaderos |
| `Saludable` | Healthy | Saludable | 3 | Oferta centrada en comida saludable |
| `Casa Cultural` | Cultural house | Casa cultural | 1 | Espacio cultural con oferta gastronómica secundaria |
| `Hostal` | Hostel | Hostal | 1 | Hostal con restaurante o cafetería |
| `Catering` | Catering | Catering | 1 | Catering sin atención en el local |
| `Desconocido` | Unclassified | Sin clasificar | 116 | No se pudo asignar un tipo. Su coeficiente en la regresión no tiene interpretación sustantiva |

El libro de códigos y la evaluación de fiabilidad con cuatro chefs independientes están en el Suplementario S6.

### Archivos de la revisión

**`online_verification_116_oct2026.csv`** — una fila por establecimiento sin plataformas.

| Columna | Descripción |
|---|---|
| `census_id`, `name`, `address`, `lat`, `lon` | Identificación, como en el censo |
| `type_june2026` | `Tipo Restaurante` del censo |
| `fork_category` | `CATEGORÍA` del censo |
| `status_oct2026` | `Operativo` (6), `Cerrado/trasladado` (13), `Sin evidencia` (97) |
| `alternative_digital_presence` | Presencia fuera de las tres plataformas: `Ninguna`, `Facebook`, `Google Maps (nueva)` (ficha creada después de junio), `Varias` |
| `web_evidence_of_operation` | Evidencia en la web de que funciona: `Sí`, `Dudoso`, `No` |
| `web_most_recent_evidence` | Fecha de la evidencia más reciente encontrada |
| `google_maps_listing_oct2026`, `google_maps_listing_status` | Ficha encontrada en octubre y su estado (`Abierto`, `Cerrado permanentemente`, `Sin indicación`) |
| `facebook_page`, `facebook_last_post` | Página de Facebook y fecha de la última publicación |
| `whatsapp_business_evidence` | Evidencia de WhatsApp Business |
| `tripadvisor_listing` | Ficha en TripAdvisor |
| `streetview_image_date` | Fecha de la imagen más reciente de Street View (año-mes) |
| `offer_validated_oct2026`, `offer_evidence` | Oferta validada por el primer autor y la evidencia usada (`Descripción textual`, `Solo nombre`, `Sin fuente`) |
| `sources_with_findings` | Fuentes que dieron información: `GEN` búsqueda web general, `GM` Google Maps, `SV` Street View, `FB` Facebook |

**`coder_responses_anonymized_2026-10-21.csv`** — una fila por respuesta (5 codificadores × 67 establecimientos).

| Columna | Descripción |
|---|---|
| `timestamp` | Hora de la respuesta (UTC) |
| `coder` | `C1`–`C4` chefs independientes, `J` primer autor |
| `blind_code` | Código ciego del establecimiento. La llave que lo vincula al censo no se publica |
| `position` | Orden en que se mostró el establecimiento |
| `answer_level1` | Respuesta de primer nivel: `tradicional`, `nuevo_tradicional`, `regional`, `otra`, `no_determinable` |
| `answer` | Categoría final |
| `reason_not_determinable` | Motivo cuando no se pudo determinar la categoría |
| `confidence` | Confianza declarada: `alta`, `media`, `baja`; vacío cuando no fue determinable |
| `knows_establishment` | Si el codificador conocía el lugar |
| `time_ms` | Tiempo dedicado al ítem, milisegundos |
| `comment` | Comentario libre |

Las tablas de `typology-results/` y `sensitivity/` son salidas de los scripts de [`code/revision-R1/`](../code/revision-R1/). Sus columnas están en español y se describen en el Suplementario S6–S8.

### Notas

- **Fechas.** Los datos de plataformas se registraron manualmente en la primera quincena de junio de 2026. No son valores en tiempo real y pueden haber cambiado.
- **Ausencia no es cierre.** Un establecimiento sin plataformas puede estar abierto pero fuera de línea, cerrado, trasladado o presente en plataformas no examinadas. La verificación en línea de octubre de 2026 acota esta proporción.
- **Los campos de plataformas** son valores fechados, agregados y visibles públicamente, registrados por el equipo de investigación. No son una exportación ni un raspado de ninguna plataforma y no contienen contenido de las plataformas ni datos personales de usuarios.
- **Uso.** Para investigación y divulgación. No es un directorio comercial ni una recomendación.
