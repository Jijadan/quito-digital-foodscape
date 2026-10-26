/**
 * Code.gs — web app de codificación (doGet y funciones que llama el navegador).
 * Se implementa como «Ejecutar como: Yo» y «Acceso: cualquier persona»: el token del enlace es la única llave,
 * así que todas las funciones públicas lo validan y recalculan en el servidor qué caso corresponde.
 */

const TOKEN_RE = /^[A-Za-z0-9]{12}$/;
const CACHE_SEG = 300;
const MENSAJE_ERROR = 'No se pudo completar la operación. Vuelve a intentarlo en unos segundos.';

function doGet(e) {
  const token = String((e && e.parameter && e.parameter.t) || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 32);
  let estado;
  try {
    estado = getEstado(token);
  } catch (err) {
    registrarError_('doGet', '', err);
    estado = { ok: false, error: MENSAJE_ERROR };
  }
  const t = HtmlService.createTemplateFromFile('index');
  t.token = token;
  // JSON dentro de <script>: se escapa «<» para que nada cierre la etiqueta.
  t.estadoJson = JSON.stringify(estado).replace(/</g, '\\u003c');
  return t.evaluate()
    .setTitle('Reto Tipología CHQ')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover');
}

function include(nombre) {
  return HtmlService.createHtmlOutputFromFile(nombre).getContent();
}

// ---------- Acceso a datos ----------

function libro_() {
  return SpreadsheetApp.getActiveSpreadsheet();
}

function hoja_(nombre) {
  const h = libro_().getSheetByName(nombre);
  if (!h) throw new Error('Falta la pestaña «' + nombre + '». Ejecuta crearHojas().');
  return h;
}

function leer_(nombre) {
  return filasAObjetos(hoja_(nombre).getDataRange().getValues());
}

function leerConCache_(nombre) {
  const cache = CacheService.getScriptCache();
  const guardado = cache.get('hoja:' + nombre);
  if (guardado) return JSON.parse(guardado);
  const filas = leer_(nombre);
  try {
    cache.put('hoja:' + nombre, JSON.stringify(filas), CACHE_SEG);
  } catch (err) {
    // Si supera los 100 KB de CacheService, se lee de la hoja cada vez.
  }
  return filas;
}

function limpiarCache_() {
  CacheService.getScriptCache().removeAll(['hoja:' + HOJAS.casos, 'hoja:' + HOJAS.codificadores, 'hoja:' + HOJAS.practica]);
}

function codificadorPorToken_(token) {
  if (!TOKEN_RE.test(String(token || ''))) return null;
  // `activo` = FALSE desactiva un enlace (p. ej. T1 y T2 antes del trabajo de campo).
  return leerConCache_(HOJAS.codificadores).find(function (c) {
    return String(c.token) === token && c.activo !== false;
  }) || null;
}

function ordenDe_(codificador) {
  const casos = leerConCache_(HOJAS.casos);
  return ordenParaSemilla(casos.map(function (c) { return String(c.codigo_ciego); }), codificador.semilla_orden);
}

function respuestasDe_(codigo) {
  return leer_(HOJAS.respuestas).filter(function (r) { return String(r.codificador) === codigo; });
}

/** Escribe solo las celdas indicadas en la fila del codificador (columna por nombre), sin pisar el resto. */
function actualizarCodificador_(codigo, cambios) {
  const h = hoja_(HOJAS.codificadores);
  const valores = h.getDataRange().getValues();
  const enc = valores[0].map(String);
  const fila = valores.findIndex(function (r, i) { return i > 0 && String(r[0]) === codigo; });
  if (fila < 1) return;
  Object.keys(cambios).forEach(function (col) {
    const j = enc.indexOf(col);
    if (j >= 0) h.getRange(fila + 1, j + 1).setValue(cambios[col]);
  });
  CacheService.getScriptCache().remove('hoja:' + HOJAS.codificadores);
}

const MAX_FILAS_ERRORES = 5000;

function registrarError_(funcion, codificador, err) {
  console.error(funcion, codificador, err && err.stack ? err.stack : err);
  try {
    const h = hoja_(HOJAS.errores);
    if (h.getLastRow() > MAX_FILAS_ERRORES) return; // tope: el resto queda en el registro de ejecuciones
    h.appendRow([new Date(), funcion, codificador || '', String(err && err.message || err).slice(0, 500),
      String(err && err.stack || '').slice(0, 2000)]);
  } catch (e2) {
    console.error('No se pudo registrar el error', e2);
  }
}

/** Envuelve una función pública: los errores se registran y el navegador recibe un mensaje genérico. */
function seguro_(nombre, token, fn) {
  try {
    return fn();
  } catch (err) {
    const c = TOKEN_RE.test(String(token || '')) ? codificadorPorToken_(token) : null;
    // Solo se anotan en la hoja los fallos reales de codificadores válidos: un anónimo no puede llenarla.
    if (c && !(err && err.esUsuario)) registrarError_(nombre, c.codigo, err);
    else console.warn(nombre, err && err.message);
    const usuario = Boolean(err && err.esUsuario);
    return { ok: false, error: usuario ? err.message : MENSAJE_ERROR, reintentar: !usuario || Boolean(err.reintentar) };
  }
}

/** Error con mensaje para el chef. `reintentar` indica al navegador que puede volver a intentarlo solo. */
function errorUsuario_(mensaje, reintentar) {
  const e = new Error(mensaje);
  e.esUsuario = true;
  e.reintentar = Boolean(reintentar);
  return e;
}

// ---------- Funciones que llama el navegador ----------

function getEstado(token) {
  return seguro_('getEstado', token, function () {
    const c = codificadorPorToken_(token);
    if (!c) return { ok: false, invalido: true };
    const total = leerConCache_(HOJAS.casos).length;
    const filas = respuestasDe_(c.codigo);
    const res = resumenRespuestas(filas, total);
    return {
      ok: true,
      codificador: { codigo: String(c.codigo), nombre: String(c.nombre || '') },
      total: total,
      respondidas: res.respondidas,
      siguiente: res.siguiente,
      inicio: Boolean(c.inicio),
      practicaOk: Boolean(c.practica_ok),
      insignias: insigniasPara(res.respondidas),
      ultima: res.ultima ? { posicion: Number(res.ultima.posicion), n1: String(res.ultima.respuesta_n1) } : null,
      tiempoTotalMs: filas.reduce(function (s, r) { return s + (Number(r.tiempo_ms) || 0); }, 0),
    };
  });
}

/** Marca hitos del codificador: 'inicio' (leyó las instrucciones) o 'practica' (terminó la práctica). */
function registrarHito(token, tipo) {
  return seguro_('registrarHito', token, function () {
    const c = codificadorPorToken_(token);
    if (!c) return { ok: false, invalido: true };
    const col = { inicio: 'inicio', practica: 'practica_ok' }[tipo];
    if (!col) throw errorUsuario_('Hito no válido.');
    if (!c[col]) {
      const lock = LockService.getScriptLock();
      if (!lock.tryLock(15000)) throw errorUsuario_('El servidor está ocupado.', true);
      try {
        actualizarCodificador_(String(c.codigo), { [col]: new Date() });
      } finally {
        lock.releaseLock();
      }
    }
    return { ok: true };
  });
}

function getPractica(token) {
  return seguro_('getPractica', token, function () {
    if (!codificadorPorToken_(token)) return { ok: false, invalido: true };
    return { ok: true, casos: leerConCache_(HOJAS.practica) };
  });
}

/** Comprueba token y posición, y devuelve el caso que corresponde según el orden del codificador. */
function casoPermitido_(token, posicion) {
  const c = codificadorPorToken_(token);
  if (!c) throw errorUsuario_('Enlace no válido.');
  const orden = ordenDe_(c);
  const pos = Number(posicion);
  const res = resumenRespuestas(respuestasDe_(c.codigo), orden.length);
  if (!Number.isInteger(pos) || pos < 1 || pos > orden.length) throw errorUsuario_('Caso no disponible.');
  // Se permite ver hasta el caso siguiente al actual, para precargarlo. Si el navegador va por delante
  // porque aún no han llegado sus últimas respuestas, se le pide que reintente.
  if (pos > res.siguiente + 1) throw errorUsuario_('Guardando tus respuestas anteriores…', true);
  const codigo = orden[pos - 1];
  const caso = leerConCache_(HOJAS.casos).find(function (x) { return String(x.codigo_ciego) === codigo; });
  return { c: c, caso: caso, codigo: codigo, pos: pos, total: orden.length };
}

function getCaso(token, posicion) {
  return seguro_('getCaso', token, function () {
    const p = casoPermitido_(token, posicion);
    const ids = String(p.caso.ids_fotos || '').split('|').filter(String);
    const tipos = String(p.caso.tipos_fotos || '').split('|');
    return {
      ok: true,
      posicion: p.pos,
      total: p.total,
      codigo: p.codigo,
      nombre: String(p.caso.nombre_mostrado || ''),
      precio: String(p.caso.nivel_precio || ''),
      categoria: String(p.caso.categoria_google || ''),
      fotos: ids.map(function (_, i) { return { tipo: tipos[i] || '' }; }),
    };
  });
}

/** Devuelve una foto en base64. El ID de Drive nunca sale del servidor ni se acepta del navegador. */
function getFoto(token, posicion, indice) {
  return seguro_('getFoto', token, function () {
    const p = casoPermitido_(token, posicion);
    const ids = String(p.caso.ids_fotos || '').split('|').filter(String);
    const i = Number(indice);
    if (!Number.isInteger(i) || i < 0 || i >= ids.length) throw errorUsuario_('Foto no disponible.');
    const blob = DriveApp.getFileById(ids[i]).getBlob();
    return { ok: true, mime: blob.getContentType(), data: Utilities.base64Encode(blob.getBytes()) };
  });
}

function guardarRespuesta(token, payload) {
  return seguro_('guardarRespuesta', token, function () {
    const c = codificadorPorToken_(token);
    if (!c) return { ok: false, invalido: true };
    let v;
    try {
      v = validarPayload(payload);
    } catch (err) {
      throw errorUsuario_(err.message);
    }
    const lock = LockService.getScriptLock();
    if (!lock.tryLock(15000)) throw errorUsuario_('El servidor está ocupado. Reintentando…', true);
    try {
      const orden = ordenDe_(c);
      const filas = respuestasDe_(c.codigo);
      const res = resumenRespuestas(filas, orden.length);
      // Reintento de un guardado que ya llegó: se confirma sin escribir otra fila.
      if (v.id && filas.some(function (f) { return String(f.id_respuesta) === v.id; })) {
        return { ok: true, duplicado: true, respondidas: res.respondidas, siguiente: res.siguiente, total: orden.length,
          insignias: insigniasPara(res.respondidas), insigniaNueva: null };
      }
      if (v.posicion > orden.length || !posicionPermitida(v.posicion, res)) {
        throw errorUsuario_('Solo puedes responder la ronda actual o cambiar la anterior.');
      }
      const fila = [new Date(), String(c.codigo), orden[v.posicion - 1], v.posicion, v.n1, v.respuesta, v.motivo,
        v.confianza, v.conoce, v.tiempoMs, v.comentario, VERSION_APP, res.versiones(v.posicion) + 1, v.id];
      const h = hoja_(HOJAS.respuestas);
      h.getRange(h.getLastRow() + 1, 1, 1, fila.length).setValues([fila]);
      SpreadsheetApp.flush();

      const nuevas = res.respondidas + (res.versiones(v.posicion) === 0 ? 1 : 0);
      const antes = insigniasPara(res.respondidas);
      const ahora = insigniasPara(nuevas);
      const cambios = {};
      if (ahora.length > antes.length) cambios.insignias = ahora.join(', ');
      if (nuevas >= orden.length && !c.fin) cambios.fin = new Date();
      if (Object.keys(cambios).length) actualizarCodificador_(String(c.codigo), cambios);

      return {
        ok: true,
        respondidas: nuevas,
        siguiente: Math.max(res.siguiente, v.posicion + 1),
        total: orden.length,
        insignias: ahora,
        insigniaNueva: ahora.length > antes.length ? ahora[ahora.length - 1] : null,
      };
    } finally {
      lock.releaseLock();
    }
  });
}
