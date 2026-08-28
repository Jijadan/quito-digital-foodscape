/**
 * ╔══════════════════════════════════════════════════════════════╗
 * ║  Territorios Alimentarios Digitales — Centro Histórico Quito ║
 * ║  Genera un mapa interactivo Leaflet a partir de hoja "Mapa"  ║
 * ╚══════════════════════════════════════════════════════════════╝
 *
 * Este script se ejecuta vinculado al Google Sheet que contiene
 * el dataset limpio y validado de establecimientos (hoja "Mapa").
 *
 * NOTA SOBRE EL PIPELINE COMPLETO:
 * Este archivo contiene únicamente la lógica de generación del mapa.
 * Los scripts de geocodificación, validación de coordenadas y
 * extracción de reseñas/estrellas que alimentan la hoja "Mapa"
 * viven en un repositorio separado de reproducibilidad del análisis,
 * ya que corresponden a la fase de recolección de datos, no a la
 * publicación del mapa en sí.
 *
 * Columnas leídas (A–T) de la hoja "Mapa":
 *   A  Nombre            B  Dirección          C  Latitud
 *   D  Longitud          E  Estrellas           F  Cantidad de Reseñas
 *   G  URL IG (raw)      H  Instagram (display) I  Tiene IG (0/1)
 *   J  Seguidores IG     K  URL TikTok (raw)    L  TikTok (display)
 *   M  Tiene TikTok      N  Seguidores TT       O  Likes TT
 *   P  Tipo Restaurante  Q  Franquicia
 *   R  dead lat          S  dead long           T  COMPROBACION
 *
 * NOTA: Los handles y links se extraen de las columnas raw G y K,
 *       ignorando las fórmulas HYPERLINK de H y L.
 *
 * NOTA SOBRE CONTEO DE FILAS:
 *   DATA_END = 421 corresponde a 420 establecimientos (fila 2 a 421),
 *   que es el n oficial y citable del dataset limpio usado en el
 *   artículo. Los scripts de recolección/validación (repo separado)
 *   manejan rangos más amplios (422–427 filas) porque operan sobre
 *   la hoja de trabajo interna antes de la depuración final; esa
 *   diferencia es intencional y está documentada en el paper.
 */

/**
 * Menú de la barra de herramientas — solo funciones de generación de mapa.
 */
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('🗺️ Mapa Digital')
    .addItem('🗺️ Generar Mapa (ES)', 'generarMapaHtml')
    .addItem('🗺️ Generate Map (EN)', 'generarMapaHtmlEn')
    .addToUi();
}

/* ──────────────────────────────────────────────────────────────
   CONSTANTES
────────────────────────────────────────────────────────────── */
const CONFIG = {
  SHEET_NAME : 'Mapa',
  DATA_START : 2,          // primera fila de datos
  DATA_END   : 421,        // última fila de datos (420 restaurantes, n oficial)
  TOTAL      : 420,        // total oficial para porcentajes
  // Bounding box del área metropolitana de Quito (excluye coords erróneas)
  LAT_MIN    : -0.42,
  LAT_MAX    : -0.05,
  LNG_MIN    : -78.60,
  LNG_MAX    : -78.42,
  // Dimensiones del modal
  MODAL_W    : 1440,
  MODAL_H    : 920,
};

/**
 * Traducción de tipos de restaurante ES → EN.
 * Usada en generarMapaHtmlEn() para que el JSON ya tenga los
 * nombres en inglés y coincidan con TYPE_NAMES de Index_en.html.
 */
const TIPO_EN = {
  'Desconocido'      : 'Other',
  'Otro'             : 'Other',
  'Fast Food'        : 'Fast Food',
  'Bar'              : 'Bar',
  'Comida Ecuatoriana': 'Ecuadorian Food',
  'Cafetería'        : 'Café',
  'Tradicional'      : 'Traditional',
  'Nuevo Tradicional': 'New Traditional',
  'Parilla'          : 'Grill',
  'Catering'         : 'Catering',
  'Internacional'    : 'International',
  'Casa Cultural'    : 'Cultural House',
  'Hostal'           : 'Hostel',
  'Saludable'        : 'Healthy'
};

/* ──────────────────────────────────────────────────────────────
   HELPER: parsea una fila del sheet y devuelve el objeto JSON
────────────────────────────────────────────────────────────── */
function _parseRow(row, translateTipo) {
  const nombre = String(row[0] || '').trim();
  if (!nombre) return null;

  // ── Coordenadas ─────────────────────────────────────────
  const latC  = parseFloat(row[2]);
  const lngC  = parseFloat(row[3]);
  const latRS = parseFloat(row[17]);
  const lngRS = parseFloat(row[18]);

  const mainOk = (
    !isNaN(latC) && !isNaN(lngC) &&
    latC >= CONFIG.LAT_MIN && latC <= CONFIG.LAT_MAX &&
    lngC >= CONFIG.LNG_MIN && lngC <= CONFIG.LNG_MAX
  );
  const backupOk = (
    !isNaN(latRS) && !isNaN(lngRS) && latRS !== 0 && lngRS !== 0 &&
    latRS >= CONFIG.LAT_MIN && latRS <= CONFIG.LAT_MAX &&
    lngRS >= CONFIG.LNG_MIN && lngRS <= CONFIG.LNG_MAX
  );

  const lat      = mainOk ? latC : (backupOk ? latRS : NaN);
  const lng      = mainOk ? lngC : (backupOk ? lngRS : NaN);
  const coordsOk = mainOk || backupOk;

  // ── Estrellas ────────────────────────────────────────────
  // IMPORTANTE: row[4] puede ser el número 0 (falsy en JS).
  // No usar `row[4] || ''` porque convierte 0 en cadena vacía.
  const rawStars = row[4];
  const starsRaw = (rawStars === 0 || rawStars === '0')
    ? '0'
    : String(rawStars !== null && rawStars !== undefined ? rawStars : '').trim();
  let stars = null;
  if (starsRaw !== '' &&
      starsRaw !== 'No existe registro' &&
      starsRaw !== 'Sin opiniones') {
    const sv = parseFloat(starsRaw);
    if (!isNaN(sv) && sv >= 0 && sv <= 5) stars = sv;
  }

  // ── Reseñas ──────────────────────────────────────────────
  const reviews = Math.max(0, parseInt(row[5]) || 0);

  // ── Instagram (fuente: col G raw URL) ───────────────────
  const urlIG  = String(row[6] || '').trim();
  const hasIG  = (row[8] === 1 || row[8] === '1' || row[8] === true) ? 1 : 0;
  const figIG  = Math.max(0, parseInt(row[9])  || 0);
  let igUrl = null, igH = '';
  if (urlIG.toLowerCase().startsWith('http')) {
    igUrl = urlIG;
    const m = urlIG.match(/instagram\.com\/([^/?#\s]+)/i);
    if (m) igH = m[1].replace(/\/+$/, '');
  }

  // ── TikTok (fuente: col K raw URL) ──────────────────────
  const urlTT  = String(row[10] || '').trim();
  const hasTT  = (row[12] === 1 || row[12] === '1' || row[12] === true) ? 1 : 0;
  const figTT  = Math.max(0, parseInt(row[13]) || 0);
  const likTT  = Math.max(0, parseInt(row[14]) || 0);
  let ttUrl = null, ttH = '';
  if (urlTT.toLowerCase().startsWith('http')) {
    ttUrl = urlTT;
    const m = urlTT.match(/tiktok\.com\/@?([^/?#\s]+)/i);
    if (m) ttH = m[1].replace(/\/+$/, '');
  }

  // ── Tipo y franquicia ────────────────────────────────────
  const tipoRaw    = (String(row[15] || '').trim() || 'Desconocido');
  const tipo       = translateTipo ? (TIPO_EN[tipoRaw] || 'Other') : tipoRaw;
  const franquicia = (String(row[16] || '').trim() === 'Franquicia') ? 1 : 0;

  return {
    n    : nombre,
    d    : String(row[1] || '').trim(),
    lat  : coordsOk ? lat : null,
    lng  : coordsOk ? lng : null,
    noGM : (coordsOk && !mainOk) ? 1 : 0,
    stars: stars,
    rev  : reviews,
    hasIG: hasIG,
    igUrl: igUrl,
    igH  : igH,
    figIG: figIG,
    hasTT: hasTT,
    ttUrl: ttUrl,
    ttH  : ttH,
    figTT: figTT,
    likTT: likTT,
    tipo : tipo,
    fr   : franquicia
  };
}

/* ──────────────────────────────────────────────────────────────
   FUNCIÓN PRINCIPAL — VERSIÓN EN ESPAÑOL
────────────────────────────────────────────────────────────── */
function generarMapaHtml() {
  _generarMapa('Index', false,
    'Territorios Alimentarios Digitales — CHQ',
    'Territorios Alimentarios Digitales — Centro Histórico de Quito');
}

/* ──────────────────────────────────────────────────────────────
   FUNCIÓN PRINCIPAL — VERSIÓN EN INGLÉS
────────────────────────────────────────────────────────────── */
function generarMapaHtmlEn() {
  _generarMapa('Index_en', true,
    'Digital Food Territories — CHQ',
    'Digital Food Territories — Historic Center of Quito');
}

/* ──────────────────────────────────────────────────────────────
   FUNCIÓN INTERNA: genera y muestra el mapa (ES o EN)
────────────────────────────────────────────────────────────── */
function _generarMapa(templateName, translateTipo, shortTitle, modalTitle) {
  const ui = SpreadsheetApp.getUi();

  const sheet = SpreadsheetApp.getActiveSpreadsheet()
                               .getSheetByName(CONFIG.SHEET_NAME);
  if (!sheet) {
    ui.alert('⚠️ Sheet "' + CONFIG.SHEET_NAME + '" not found.\n' +
             'Make sure the tab is named exactly "Mapa".');
    return;
  }

  const numRows = CONFIG.DATA_END - CONFIG.DATA_START + 1;
  const raw = sheet.getRange(CONFIG.DATA_START, 1, numRows, 20).getValues();

  const restaurants = [];
  raw.forEach(function(row) {
    const obj = _parseRow(row, translateTipo);
    if (obj) restaurants.push(obj);
  });

  try {
    const tmpl = HtmlService.createTemplateFromFile(templateName);
    tmpl.restaurantData = JSON.stringify(restaurants);

    const output = tmpl.evaluate()
      .setWidth(CONFIG.MODAL_W)
      .setHeight(CONFIG.MODAL_H)
      .setTitle(shortTitle);

    SpreadsheetApp.getUi().showModalDialog(output, modalTitle);

  } catch (err) {
    ui.alert('Error generating map:\n' + err.message +
             '\n\nVerify that "' + templateName + '.html" exists in the project.');
  }
}
