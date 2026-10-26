/**
 * Logica.gs — constantes y funciones puras (sin servicios de Google).
 * Se prueban en local con Node: `node --test webapp/tests`.
 * Las categorías, motivos y confianza siguen el libro de códigos S6 (S6.4, S6.9, S6.12.3).
 */

const VERSION_APP = '1.0.0';

const HOJAS = {
  casos: 'casos',
  codificadores: 'codificadores',
  respuestas: 'respuestas',
  practica: 'practica',
  errores: 'errores',
};

const ENCABEZADOS = {
  casos: ['codigo_ciego', 'nombre_mostrado', 'nivel_precio', 'categoria_google', 'ids_fotos', 'tipos_fotos'],
  codificadores: ['codigo', 'token', 'nombre', 'semilla_orden', 'prueba', 'activo', 'inicio', 'practica_ok', 'insignias', 'fin'],
  respuestas: ['timestamp', 'codificador', 'codigo_ciego', 'posicion', 'respuesta_n1', 'respuesta', 'motivo_nd',
    'confianza', 'conoce_local', 'tiempo_ms', 'comentario', 'version_app', 'version_respuesta', 'id_respuesta'],
  practica: ['id', 'titulo', 'descripcion', 'respuesta_n1', 'respuesta', 'explicacion'],
  errores: ['timestamp', 'funcion', 'codificador', 'mensaje', 'detalle'],
};

/** Codificadores previstos: 4 chefs (S6.12.1 amplía a cuatro) y el investigador (S6.12.7). T1 y T2 son tokens de prueba que borra limpiarPruebas(). */
const CODIFICADORES_PREVISTOS = [
  { codigo: 'C1', nombre: 'Chef 1', prueba: false },
  { codigo: 'C2', nombre: 'Chef 2', prueba: false },
  { codigo: 'C3', nombre: 'Chef 3', prueba: false },
  { codigo: 'C4', nombre: 'Chef 4', prueba: false },
  { codigo: 'J', nombre: 'Johann', prueba: false },
  { codigo: 'T1', nombre: 'Prueba investigador', prueba: true },
  { codigo: 'T2', nombre: 'Piloto chef', prueba: true },
];

/** Primer nivel de respuesta (S6.12.3). */
const NIVEL1 = {
  tradicional: 'Tradicional',
  nuevo_tradicional: 'Nuevo Tradicional',
  regional: 'Cocina ecuatoriana regional',
  otra: 'Otra categoría',
  no_determinable: 'No puedo determinarlo',
};

/** Segundo nivel de «Otra categoría»: las nueve categorías restantes de la Tabla S6.4. */
const OTRAS = {
  internacional: 'Internacional',
  fast_food: 'Fast Food',
  bar: 'Bar',
  cafeteria: 'Cafetería',
  parrilla: 'Parrilla',
  saludable: 'Saludable',
  casa_cultural: 'Casa Cultural',
  hostal: 'Hostal',
  catering: 'Catering',
};

/** Motivos de No determinable (S6.9). */
const MOTIVOS_ND = {
  fotos_insuficientes: 'Fotografías insuficientes',
  fotos_no_corresponden: 'Las fotografías no corresponden al local',
  oferta_mixta: 'Oferta mixta sin eje',
  repertorio_no_reconocible: 'Repertorio no reconocible',
  evidencia_contradictoria: 'Evidencia insuficiente o contradictoria',
  otro: 'Otro (explícalo en el comentario)',
};

const CONFIANZAS = { baja: 'Baja', media: 'Media', alta: 'Alta' };

/** Insignias decorativas: una por cada bloque de 10 rondas. */
const INSIGNIAS = ['Hornado', 'Fanesca', 'Encebollado', 'Locro', 'Fritada', 'Colada morada'];
const RONDAS_POR_INSIGNIA = 10;

const MAX_COMENTARIO = 300;
const MAX_TIEMPO_MS = 24 * 60 * 60 * 1000;

/** PRNG determinista (mulberry32): mismo orden al reanudar. */
function mulberry32(semilla) {
  let a = semilla >>> 0;
  return function () {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Orden propio de cada codificador. Ordena antes de barajar para no depender del orden de la hoja. */
function ordenParaSemilla(codigos, semilla) {
  const orden = codigos.slice().sort();
  const azar = mulberry32(Number(semilla) || 1);
  for (let i = orden.length - 1; i > 0; i--) {
    const j = Math.floor(azar() * (i + 1));
    const tmp = orden[i];
    orden[i] = orden[j];
    orden[j] = tmp;
  }
  return orden;
}

/** Evita que un comentario se interprete como fórmula en la hoja y quita caracteres de control. */
function textoSeguro(valor, max) {
  let s = String(valor == null ? '' : valor).replace(/[\u0000-\u001F\u007F]/g, ' ').trim().slice(0, max);
  if (/^[=+\-@]/.test(s)) s = "'" + s;
  return s;
}

function tieneClave(obj, clave) {
  return typeof clave === 'string' && Object.prototype.hasOwnProperty.call(obj, clave);
}

/**
 * Valida y normaliza la respuesta enviada por el navegador. Lanza Error con un mensaje legible.
 * Devuelve { posicion, n1, respuesta, motivo, confianza, conoce, tiempoMs, comentario }.
 */
function validarPayload(p) {
  if (!p || typeof p !== 'object') throw new Error('Respuesta vacía.');
  const posicion = Number(p.posicion);
  if (!Number.isInteger(posicion) || posicion < 1) throw new Error('Posición no válida.');
  if (!tieneClave(NIVEL1, p.n1)) throw new Error('Categoría no válida.');

  let respuesta = p.n1;
  if (p.n1 === 'otra') {
    if (!tieneClave(OTRAS, p.sub)) throw new Error('Elige cuál de las otras categorías.');
    respuesta = p.sub;
  }

  const comentario = textoSeguro(p.comentario, MAX_COMENTARIO);
  let motivo = '';
  let confianza = '';
  if (p.n1 === 'no_determinable') {
    if (!tieneClave(MOTIVOS_ND, p.motivo)) throw new Error('Indica el motivo.');
    if (p.motivo === 'otro' && !comentario) throw new Error('Explica el motivo en el comentario.');
    motivo = p.motivo;
  } else {
    if (!tieneClave(CONFIANZAS, p.confianza)) throw new Error('Indica tu confianza.');
    confianza = p.confianza;
  }

  let tiempoMs = Math.round(Number(p.tiempoMs));
  if (!Number.isFinite(tiempoMs) || tiempoMs < 0) tiempoMs = 0;
  tiempoMs = Math.min(tiempoMs, MAX_TIEMPO_MS);

  // Identificador generado en el navegador: evita filas duplicadas si se reintenta un guardado que sí llegó.
  const id = /^[A-Za-z0-9-]{8,40}$/.test(String(p.id || '')) ? String(p.id) : '';

  return { posicion, n1: p.n1, respuesta, motivo, confianza, conoce: p.conoce === true, tiempoMs, comentario, id };
}

/** Insignias ganadas con n rondas respondidas. */
function insigniasPara(n) {
  return INSIGNIAS.slice(0, Math.min(INSIGNIAS.length, Math.floor(n / RONDAS_POR_INSIGNIA)));
}

/**
 * Resume las respuestas de un codificador: posiciones respondidas, siguiente y última.
 * `filas` son objetos { posicion, ... } en orden de escritura.
 */
function resumenRespuestas(filas, total) {
  const ultimaPorPos = {};
  filas.forEach(function (f) { ultimaPorPos[Number(f.posicion)] = f; });
  let siguiente = 1;
  while (siguiente <= total && ultimaPorPos[siguiente]) siguiente++;
  const respondidas = Object.keys(ultimaPorPos).length;
  const ultimaPos = siguiente - 1;
  return {
    respondidas: respondidas,
    siguiente: siguiente,
    ultima: ultimaPos >= 1 ? ultimaPorPos[ultimaPos] : null,
    versiones: function (pos) { return filas.filter(function (f) { return Number(f.posicion) === pos; }).length; },
  };
}

/** Solo se puede responder la siguiente posición o corregir la última (S6.12.3). */
function posicionPermitida(posicion, resumen) {
  return posicion === resumen.siguiente || (resumen.ultima !== null && posicion === resumen.siguiente - 1);
}

/** Última respuesta por (codificador, codigo_ciego): es la que usa el análisis. */
function ultimaPorCaso(filas) {
  const mapa = {};
  filas.forEach(function (f) { mapa[f.codificador + '|' + f.codigo_ciego] = f; });
  return Object.keys(mapa).map(function (k) { return mapa[k]; });
}

function aCsv(encabezados, filas) {
  const esc = function (v) {
    let s = v instanceof Date ? v.toISOString() : String(v == null ? '' : v);
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; // que Excel no lo ejecute como fórmula
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  return [encabezados.map(esc).join(',')]
    .concat(filas.map(function (f) { return encabezados.map(function (h) { return esc(f[h]); }).join(','); }))
    .join('\r\n');
}

/** Convierte filas de getValues() (con encabezado) en objetos. */
function filasAObjetos(valores) {
  if (!valores || valores.length < 2) return [];
  const enc = valores[0].map(String);
  return valores.slice(1)
    .filter(function (r) { return r.some(function (c) { return c !== '' && c !== null; }); })
    .map(function (r) {
      const o = {};
      enc.forEach(function (h, i) { o[h] = r[i]; });
      return o;
    });
}

/** Tipo de foto a partir del nombre de archivo: '01_plato.jpg' -> 'plato'. */
function tipoDeArchivo(nombre) {
  return String(nombre).replace(/\.[^.]+$/, '').replace(/^.*__/, '').replace(/^\d+_/, '').toLowerCase();
}

/** Fotos subidas sin subcarpetas: 'C103__01_plato.jpg' -> { codigo: 'C103', archivo: '01_plato.jpg' }. */
function separarNombrePlano(nombre) {
  const m = /^([A-Za-z0-9]+)__(.+)$/.exec(String(nombre));
  return m ? { codigo: m[1], archivo: m[2] } : null;
}

/** Casos de práctica del libro de códigos (S6.14): hipotéticos, no pertenecen al censo. */
const PRACTICA_INICIAL = [
  ['P1', 'Las Fritadas de Doña Clemencia',
    'Fotografías: fritada con mote y maduro en plato de loza blanco; paila grande junto a la puerta; pizarra con tres opciones entre US$ 3,50 y 5; mesas con mantel de hule.',
    'tradicional', 'tradicional',
    'Vajilla de uso, servicio a la ración y oferta breve (A, B y C: seis puntos), más precio e interior.'],
  ['P2', 'Los Ceviches de la Guayaquil',
    'Fotografías: ceviche de camarón con chifles y canguil en plato hondo de plástico; lona con «encebollado · ceviche · bolón».',
    'regional', 'regional',
    '«De la Guayaquil» es una calle, no un origen, pero el repertorio es costeño; el registro sencillo no la convierte en Tradicional.'],
];

if (typeof module !== 'undefined') {
  module.exports = {
    VERSION_APP, HOJAS, ENCABEZADOS, CODIFICADORES_PREVISTOS, NIVEL1, OTRAS, MOTIVOS_ND, CONFIANZAS, INSIGNIAS,
    mulberry32, ordenParaSemilla, textoSeguro, validarPayload, insigniasPara, resumenRespuestas,
    posicionPermitida, ultimaPorCaso, aCsv, filasAObjetos, tipoDeArchivo, separarNombrePlano, PRACTICA_INICIAL,
  };
}
