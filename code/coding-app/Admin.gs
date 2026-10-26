/**
 * Admin.gs — funciones del investigador. Se ejecutan desde el menú «Codificación» de la hoja
 * o desde el editor de Apps Script (desplegable de funciones → Ejecutar).
 */

const LIMITE_MS = 4.5 * 60 * 1000; // margen bajo los 6 minutos de ejecución
const ALFABETO_TOKEN = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Codificación')
    .addItem('1. Crear pestañas', 'crearHojas')
    .addItem('2. Importar casos (casos.csv)', 'importarCasos')
    .addItem('3. Importar fotos', 'importarFotos')
    .addItem('4. Generar tokens', 'generarTokens')
    .addItem('5. Ver enlaces personales', 'verEnlaces')
    .addSeparator()
    .addItem('Exportar respuestas (CSV)', 'exportarCSV')
    .addItem('Borrar respuestas de prueba', 'limpiarPruebas')
    .addToUi();
}

/**
 * Cualquier función global sin «_» puede llamarse desde el navegador con google.script.run.
 * Las de administración exigen el contexto de la hoja (menú «Codificación»): getUi() falla en la web app.
 */
function soloDesdeLaHoja_() {
  try {
    SpreadsheetApp.getUi();
  } catch (e) {
    throw new Error('Ejecuta esta función desde el menú «Codificación» de la hoja.');
  }
}

function avisar_(mensaje) {
  try {
    SpreadsheetApp.getUi().alert(mensaje);
  } catch (e) {
    console.log(mensaje); // ejecutado desde el editor
  }
}

function carpetaDelLibro_() {
  const padres = DriveApp.getFileById(libro_().getId()).getParents();
  if (!padres.hasNext()) throw new Error('La hoja no está dentro de una carpeta de Drive.');
  return padres.next();
}

/** Crea las pestañas que falten con sus encabezados y carga los casos de práctica. Se puede repetir. */
function crearHojas() {
  soloDesdeLaHoja_();
  const ss = libro_();
  Object.keys(HOJAS).forEach(function (k) {
    const h = ss.getSheetByName(HOJAS[k]) || ss.insertSheet(HOJAS[k]);
    const enc = ENCABEZADOS[k];
    const actual = h.getRange(1, 1, 1, enc.length).getValues()[0];
    if (actual.join('') === '') {
      h.getRange(1, 1, 1, enc.length).setValues([enc]).setFontWeight('bold');
      h.setFrozenRows(1);
    }
  });
  const prac = ss.getSheetByName(HOJAS.practica);
  if (prac.getLastRow() < 2) {
    prac.getRange(2, 1, PRACTICA_INICIAL.length, PRACTICA_INICIAL[0].length).setValues(PRACTICA_INICIAL);
  }
  const hoja1 = ss.getSheetByName('Hoja 1') || ss.getSheetByName('Sheet1');
  if (hoja1 && hoja1.getLastRow() === 0 && ss.getSheets().length > 1) ss.deleteSheet(hoja1);
  limpiarCache_();
  avisar_('Pestañas listas: ' + Object.keys(HOJAS).map(function (k) { return HOJAS[k]; }).join(', ') + '.');
}

/** Lee casos.csv de la misma carpeta de Drive que la hoja y rellena la pestaña `casos`, conservando ids de fotos ya importados. */
function importarCasos() {
  soloDesdeLaHoja_();
  if (hoja_(HOJAS.respuestas).getLastRow() > 1) {
    const ui = SpreadsheetApp.getUi();
    const r = ui.alert('Ya hay respuestas',
      'Cambiar la lista de casos cambia el orden de cada codificador y desalinea las rondas ya respondidas. ¿Continuar igualmente?',
      ui.ButtonSet.YES_NO);
    if (r !== ui.Button.YES) return;
  }
  const archivos = carpetaDelLibro_().getFilesByName('casos.csv');
  if (!archivos.hasNext()) throw new Error('No encuentro casos.csv en la carpeta de la hoja.');
  const filas = Utilities.parseCsv(archivos.next().getBlob().getDataAsString('UTF-8'));
  const enc = filas[0].map(function (s) { return String(s).replace(/^﻿/, '').trim(); });
  const prohibidas = ['id_censo', 'estrato', 'tipo_restaurante_original', 'reemplaza_a'];
  if (enc.some(function (h) { return prohibidas.indexOf(h) >= 0; })) {
    throw new Error('casos.csv contiene columnas privadas. Usa el archivo generado por prepara_casos.py.');
  }
  const previos = {};
  leer_(HOJAS.casos).forEach(function (c) { previos[c.codigo_ciego] = c; });
  const destino = ENCABEZADOS.casos;
  const datos = filas.slice(1).filter(function (r) { return r.join('') !== ''; }).map(function (r) {
    const o = {};
    enc.forEach(function (h, i) { o[h] = r[i]; });
    const p = previos[o.codigo_ciego] || {};
    o.ids_fotos = o.ids_fotos || p.ids_fotos || '';
    o.tipos_fotos = o.tipos_fotos || p.tipos_fotos || '';
    return destino.map(function (h) { return o[h] || ''; });
  });
  const h = hoja_(HOJAS.casos);
  if (h.getLastRow() > 1) h.getRange(2, 1, h.getLastRow() - 1, h.getLastColumn()).clearContent();
  h.getRange(1, 1, 1, destino.length).setValues([destino]);
  if (datos.length) h.getRange(2, 1, datos.length, destino.length).setNumberFormat('@').setValues(datos);
  limpiarCache_();
  avisar_(datos.length + ' casos importados.');
}

/**
 * Lee la carpeta «fotos» (junto a la hoja) y rellena ids_fotos y tipos_fotos en orden (00, 01…).
 * Admite dos formas: subcarpetas fotos/<codigo_ciego>/00_ficha.jpg o archivos planos fotos/<codigo>__00_ficha.jpg.
 * Si se acerca al límite de tiempo, guarda lo hecho y pide volver a ejecutarla: continúa donde quedó.
 */
function importarFotos() {
  soloDesdeLaHoja_();
  const inicio = Date.now();
  const carpetas = carpetaDelLibro_().getFoldersByName('fotos');
  if (!carpetas.hasNext()) throw new Error('No encuentro la carpeta «fotos» junto a la hoja.');
  const fotos = carpetas.next();

  // Archivos planos: un solo recorrido agrupado por código.
  const planos = {};
  const it = fotos.getFiles();
  while (it.hasNext()) {
    const f = it.next();
    const partes = separarNombrePlano(f.getName());
    if (!partes || !/^image\//.test(f.getMimeType())) continue;
    (planos[partes.codigo] = planos[partes.codigo] || []).push({ nombre: partes.archivo, id: f.getId() });
  }

  const h = hoja_(HOJAS.casos);
  const valores = h.getDataRange().getValues();
  const enc = valores[0].map(String);
  const jCod = enc.indexOf('codigo_ciego');
  const jIds = enc.indexOf('ids_fotos');
  const jTipos = enc.indexOf('tipos_fotos');
  let hechos = 0;
  const faltan = [];
  let cortado = false;
  for (let i = 1; i < valores.length; i++) {
    if (valores[i][jIds]) continue;
    if (Date.now() - inicio > LIMITE_MS) { cortado = true; break; }
    const codigo = String(valores[i][jCod]);
    let lista = planos[codigo] || [];
    if (!lista.length) {
      const sub = fotos.getFoldersByName(codigo);
      if (sub.hasNext()) {
        const it2 = sub.next().getFiles();
        while (it2.hasNext()) {
          const f = it2.next();
          if (/^image\//.test(f.getMimeType())) lista.push({ nombre: f.getName(), id: f.getId() });
        }
      }
    }
    if (!lista.length) { faltan.push(codigo); continue; }
    lista = lista.slice().sort(function (a, b) { return a.nombre < b.nombre ? -1 : 1; });
    valores[i][jIds] = lista.map(function (f) { return f.id; }).join('|');
    valores[i][jTipos] = lista.map(function (f) { return tipoDeArchivo(f.nombre); }).join('|');
    hechos++;
  }
  h.getRange(1, 1, valores.length, enc.length).setValues(valores);
  limpiarCache_();
  const pendientes = valores.slice(1).filter(function (r) { return !r[jIds]; }).length;
  avisar_(hechos + ' casos con fotos importadas.' +
    (faltan.length ? ' Sin fotos: ' + faltan.join(', ') + '.' : '') +
    (cortado ? ' Se alcanzó el límite de tiempo: vuelve a ejecutar importarFotos.' : '') +
    (pendientes ? ' Pendientes: ' + pendientes + '.' : ' Todos los casos tienen fotos.'));
}

function tokenAleatorio_() {
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, Utilities.getUuid() + Utilities.getUuid());
  let t = '';
  for (let i = 0; i < 12; i++) t += ALFABETO_TOKEN[(bytes[i] + 256) % ALFABETO_TOKEN.length];
  return t;
}

function semillaAleatoria_() {
  const b = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, Utilities.getUuid());
  return (((b[0] & 0x7f) << 24) | ((b[1] & 0xff) << 16) | ((b[2] & 0xff) << 8) | (b[3] & 0xff)) || 1;
}

/** Crea token y semilla para C1, C2, C3, J y los de prueba (T1, T2). No toca los que ya existen. */
function generarTokens() {
  soloDesdeLaHoja_();
  const existentes = leer_(HOJAS.codificadores).map(function (c) { return String(c.codigo); });
  const nuevos = CODIFICADORES_PREVISTOS.filter(function (c) { return existentes.indexOf(c.codigo) < 0; })
    .map(function (c) { return [c.codigo, tokenAleatorio_(), c.nombre, semillaAleatoria_(), c.prueba, true, '', '', '', '']; });
  if (nuevos.length) {
    const h = hoja_(HOJAS.codificadores);
    h.getRange(h.getLastRow() + 1, 1, nuevos.length, nuevos[0].length).setValues(nuevos);
  }
  limpiarCache_();
  avisar_(nuevos.length ? 'Tokens creados para: ' + nuevos.map(function (n) { return n[0]; }).join(', ') +
    '. Cambia la columna «nombre» por el nombre real de cada chef.' : 'Todos los codificadores ya tenían token.');
}

/** Muestra los enlaces personales (requiere haber implementado la aplicación web). */
function verEnlaces() {
  soloDesdeLaHoja_();
  const url = ScriptApp.getService().getUrl();
  if (!url) throw new Error('Primero implementa la aplicación web (Implementar → Nueva implementación).');
  const filas = leer_(HOJAS.codificadores).map(function (c) {
    const enlace = url + '?t=' + encodeURIComponent(c.token);
    return '<tr><td>' + esc_(c.codigo) + (c.prueba === true ? ' (prueba)' : '') + '</td><td>' + esc_(c.nombre) +
      '</td><td><input readonly style="width:100%" value="' + esc_(enlace) + '" onclick="this.select()"></td></tr>';
  }).join('');
  const html = HtmlService.createHtmlOutput('<style>body{font:14px sans-serif}td{padding:4px}</style>' +
    '<p>URL base: ' + esc_(url) + '</p><table>' + filas + '</table>' +
    '<p>Comprueba que la URL termina en <b>/exec</b>, no en /dev.</p>').setWidth(760).setHeight(360);
  SpreadsheetApp.getUi().showModalDialog(html, 'Enlaces personales');
}

function esc_(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

/**
 * Prepara dos CSV y los descarga en el ordenador del investigador:
 * respuestas_<fecha>.csv (última respuesta por codificador y caso, sin pruebas) y respuestas_historial_<fecha>.csv (todas las versiones).
 * Se descarga desde el navegador para no pedir permiso de escritura sobre todo Drive.
 */
function exportarCSV() {
  soloDesdeLaHoja_();
  const prueba = {};
  leer_(HOJAS.codificadores).forEach(function (c) { prueba[c.codigo] = c.prueba === true; });
  const todas = leer_(HOJAS.respuestas).filter(function (r) { return !prueba[r.codificador]; });
  const enc = ENCABEZADOS.respuestas;
  const fecha = Utilities.formatDate(new Date(), 'America/Guayaquil', 'yyyy-MM-dd');
  const archivos = [
    { nombre: 'respuestas_' + fecha + '.csv', csv: aCsv(enc, ultimaPorCaso(todas)) },
    { nombre: 'respuestas_historial_' + fecha + '.csv', csv: aCsv(enc, todas) },
  ];
  const t = HtmlService.createTemplateFromFile('exportar');
  t.archivosJson = JSON.stringify(archivos).replace(/</g, '\\u003c');
  t.n = todas.length;
  SpreadsheetApp.getUi().showModalDialog(t.evaluate().setWidth(420).setHeight(200), 'Exportar respuestas');
}

/** Borra las respuestas de los codificadores marcados como prueba (T1, T2) y reinicia su progreso. */
function limpiarPruebas() {
  soloDesdeLaHoja_();
  const ui = SpreadsheetApp.getUi();
  const ok = ui.alert('Borrar respuestas de prueba',
    'Se borrarán todas las respuestas de los codificadores marcados como prueba. ¿Continuar?', ui.ButtonSet.YES_NO);
  if (ok !== ui.Button.YES) return;
  const prueba = leer_(HOJAS.codificadores).filter(function (c) { return c.prueba === true; })
    .map(function (c) { return String(c.codigo); });
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const h = hoja_(HOJAS.respuestas);
    const valores = h.getDataRange().getValues();
    const conservar = valores.filter(function (r, i) { return i === 0 || prueba.indexOf(String(r[1])) < 0; });
    const borradas = valores.length - conservar.length;
    h.getRange(1, 1, valores.length, valores[0].length).clearContent();
    h.getRange(1, 1, conservar.length, conservar[0].length).setValues(conservar);
    prueba.forEach(function (codigo) {
      actualizarCodificador_(codigo, { inicio: '', practica_ok: '', insignias: '', fin: '' });
    });
    avisar_(borradas + ' filas de prueba borradas (' + prueba.join(', ') + ').');
  } finally {
    lock.releaseLock();
  }
}
