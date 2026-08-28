# Diccionario de datos · Data Dictionary

---

## 🇪🇨 Español

### Archivo · `restaurantes_quito_CH_clean.csv`

Dataset limpio y validado del censo de establecimientos de patrimonio alimentario en el Centro Histórico de Quito (CHQ). Es la fuente de datos autoritativa que sustenta el análisis y las figuras del artículo asociado.

| Columna | Nombre descriptivo | Tipo | Valores posibles / Notas |
|---|---|---|---|
| `nombre` | Nombre del establecimiento | texto | Tal como figura en el catastro de turismo del MDMQ |
| `direccion` | Dirección postal | texto | Incluye ", Quito, Ecuador" al final |
| `latitud` | Latitud geográfica | numérico | WGS84 (EPSG:4326). Vacío si no fue posible geolocalizar |
| `longitud` | Longitud geográfica | numérico | WGS84 (EPSG:4326). Vacío si no fue posible geolocalizar |
| `estrellas` | Calificación promedio Google Maps | numérico | 0–5 · `"No existe registro"` si el establecimiento no tiene ficha en Google Maps · `"Sin opiniones"` si tiene ficha pero ninguna opinión |
| `resenas` | Número total de reseñas Google Maps | entero | 0 si no tiene reseñas o no tiene ficha |
| `url_instagram` | URL del perfil de Instagram | texto | URL completa (`https://...`) · vacío si no tiene cuenta |
| `seguidores_ig` | Seguidores en Instagram | entero | 0 si no tiene cuenta · relevado manualmente en junio 2026 |
| `tiene_ig` | Presencia en Instagram | binario | `1` = sí · `0` = no |
| `url_tiktok` | URL del perfil de TikTok | texto | URL completa (`https://...`) · vacío si no tiene cuenta |
| `seguidores_tt` | Seguidores en TikTok | entero | 0 si no tiene cuenta · relevado manualmente en junio 2026 |
| `likes_tt` | Likes totales en TikTok | entero | 0 si no tiene cuenta. **Nota:** esta variable no forma parte del índice de capital digital principal (PCA-A) por concentración extrema (Gini ≈ 0.96); aparece solo en el análisis de sensibilidad (PCA-B) |
| `tiene_tt` | Presencia en TikTok | binario | `1` = sí · `0` = no |
| `tipo` | Categoría gastronómica | texto | Ver tabla de categorías más abajo |
| `franquicia` | Naturaleza jurídica | texto | `"Franquicia"` o `""` (vacío = establecimiento independiente) |

### Categorías gastronómicas (`tipo`)

| Valor | Descripción |
|---|---|
| `Tradicional` | Establecimientos que ofrecen patrimonio alimentario ecuatoriano en registro de presentación vernáculo (menú del día, tiempos de mesa, servicio de mostrador) |
| `Nuevo Tradicional` | Mismo repertorio culinario que *Tradicional*, pero en registro de presentación contemporáneo (carta, montaje cuidado, orientación turística) |
| `Comida Ecuatoriana` | Comida ecuatoriana genérica que no se ajusta al perfil de los dos anteriores |
| `Cafetería` | Cafeterías y establecimientos de desayuno/merienda |
| `Bar` | Bares y establecimientos con predominio de bebidas |
| `Fast Food` | Comida rápida, incluyendo cadenas nacionales e internacionales |
| `Internacional` | Cocinas no ecuatorianas (italiana, china, árabe, etc.) |
| `Parilla` | Parrilladas y asaderos |
| `Saludable` | Establecimientos con propuesta centrada en alimentación saludable |
| `Casa Cultural` | Espacios culturales con oferta gastronómica secundaria |
| `Hostal` | Hostales con restaurante o cafetería integrada |
| `Catering` | Servicios de catering sin atención al público en el local |
| `Fast Food` | Comida rápida |
| `Otro` / `Desconocido` | No clasificado en las categorías anteriores |

### Notas metodológicas importantes

**Corte temporal.** Los datos de presencia digital (seguidores, likes, reseñas, calificaciones) corresponden a un relevamiento manual realizado en **junio de 2026**. No son datos en tiempo real; cualquier cifra puede haber variado desde esa fecha.

**Fuente de referencia.** El catastro de turismo del Distrito Metropolitano de Quito (MDMQ) se utilizó como marco de referencia para el censo territorial. El dataset resultante (n = 420) es el dataset depurado tras validación de coordenadas y depuración de duplicados; no debe confundirse con versiones intermedias de la hoja de trabajo (que podían contener hasta 427 filas antes de la limpieza final).

**Ausencia digital ≠ cierre.** El 27.6 % de establecimientos sin presencia en ninguna de las tres plataformas examinadas (Google Maps, Instagram, TikTok) puede incluir locales operativos no encontrados, locales cerrados o relocalizados, o locales con presencia en otras plataformas no relevadas (Facebook, WhatsApp Business). Esta cifra debe interpretarse como estimación de orden de magnitud, no como conteo definitivo.

**Plataformas no relevadas.** El dataset no incluye datos de Facebook ni WhatsApp Business, que pueden ser relevantes para ciertos segmentos del mercado informal. La ausencia de cuenta identificada en Instagram o TikTok no prueba ausencia de actividad digital del establecimiento.

**Uso de los datos.** Estos datos se proporcionan exclusivamente con fines de investigación y divulgación. No constituyen un directorio comercial ni una recomendación editorial de los establecimientos listados.

---

## 🇬🇧 English

### File · `restaurantes_quito_CH_clean.csv`

Cleaned and validated dataset from the census of food heritage establishments in Quito's Historic Center (CHQ). This is the authoritative data source underlying the analysis and figures of the associated article.

| Column | Descriptive name | Type | Possible values / Notes |
|---|---|---|---|
| `nombre` | Establishment name | text | As recorded in the MDMQ municipal tourism registry |
| `direccion` | Postal address | text | Includes ", Quito, Ecuador" at the end |
| `latitud` | Geographic latitude | numeric | WGS84 (EPSG:4326). Empty if geolocation was not possible |
| `longitud` | Geographic longitude | numeric | WGS84 (EPSG:4326). Empty if geolocation was not possible |
| `estrellas` | Google Maps average rating | numeric | 0–5 · `"No existe registro"` if the establishment has no Google Maps listing · `"Sin opiniones"` if it has a listing but no reviews |
| `resenas` | Total number of Google Maps reviews | integer | 0 if no reviews or no listing |
| `url_instagram` | Instagram profile URL | text | Full URL (`https://...`) · empty if no account |
| `seguidores_ig` | Instagram followers | integer | 0 if no account · manually collected June 2026 |
| `tiene_ig` | Instagram presence | binary | `1` = yes · `0` = no |
| `url_tiktok` | TikTok profile URL | text | Full URL (`https://...`) · empty if no account |
| `seguidores_tt` | TikTok followers | integer | 0 if no account · manually collected June 2026 |
| `likes_tt` | Total TikTok likes | integer | 0 if no account. **Note:** this variable is not part of the principal digital capital index (PCA-A) due to extreme concentration (Gini ≈ 0.96); it appears only in the sensitivity analysis (PCA-B) |
| `tiene_tt` | TikTok presence | binary | `1` = yes · `0` = no |
| `tipo` | Gastronomic category | text | See category table below |
| `franquicia` | Business type | text | `"Franquicia"` (franchise) or `""` (empty = independent establishment) |

### Gastronomic categories (`tipo`)

| Value | Description |
|---|---|
| `Tradicional` | Establishments offering Ecuadorian food heritage in a vernacular presentation register (daily set menu, counter service) |
| `Nuevo Tradicional` | Same culinary repertoire as *Tradicional*, but in a contemporary presentation register (à la carte menu, careful plating, tourist orientation) |
| `Comida Ecuatoriana` | Generic Ecuadorian food that does not fit either of the above profiles |
| `Cafetería` | Cafés and breakfast/snack establishments |
| `Bar` | Bars and drink-oriented establishments |
| `Fast Food` | Fast food, including national and international chains |
| `Internacional` | Non-Ecuadorian cuisines (Italian, Chinese, Arab, etc.) |
| `Parilla` | Grills and barbecue restaurants |
| `Saludable` | Establishments with a health-focused food offer |
| `Casa Cultural` | Cultural spaces with a secondary gastronomic offer |
| `Hostal` | Hostels with an integrated restaurant or café |
| `Catering` | Catering services with no public-facing venue |
| `Otro` / `Desconocido` | Not classified under the above categories |

### Important methodological notes

**Temporal snapshot.** Digital presence data (followers, likes, reviews, ratings) were collected through manual observation in **June 2026**. These are not real-time data; any figure may have changed since that date.

**Reference source.** The municipal tourism registry of the Metropolitan District of Quito (MDMQ) was used as the territorial census frame. The resulting dataset (n = 420) is the cleaned dataset after coordinate validation and duplicate removal; it should not be confused with intermediate working-sheet versions (which could contain up to 427 rows before final cleaning).

**Digital absence ≠ closure.** The 27.6% of establishments with no presence on any of the three platforms examined (Google Maps, Instagram, TikTok) may include operational establishments not found, closed or relocated ones, or establishments with a presence on other non-surveyed platforms (Facebook, WhatsApp Business). This figure should be interpreted as an order-of-magnitude estimate, not a definitive count.

**Platforms not surveyed.** The dataset does not include Facebook or WhatsApp Business data, which may be relevant for certain segments of the informal market. The absence of an identified account on Instagram or TikTok does not prove the absence of digital activity by the establishment.

**Data use.** These data are provided solely for research and dissemination purposes. They do not constitute a commercial directory or an editorial endorsement of the listed establishments.
