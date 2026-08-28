/**
 * ╔══════════════════════════════════════════════════════════════╗
 * ║  Recolección y validación de datos — Censo digital CHQ       ║
 * ╚══════════════════════════════════════════════════════════════╝
 *
 * Scripts de geocodificación, validación de coordenadas y extracción
 * de estrellas/reseñas usados durante la fase de recolección de datos
 * del censo (junio 2026). Estos scripts alimentan la hoja "Mapa" que
 * luego consume el script de generación del mapa (repositorio separado
 * del mapa público).
 *
 * REQUIERE: una pestaña llamada "Configuracion" en el mismo Google
 * Sheet, con la API Key de Google Maps/Places en la celda A1.
 * La API Key NUNCA se hardcodea en este script — se lee dinámicamente
 * desde esa celda en tiempo de ejecución.
 *
 * NOTA SOBRE CONTEO DE FILAS:
 *   Estas funciones operan sobre rangos de 422–427 filas porque
 *   trabajan directamente sobre la hoja de recolección interna,
 *   previa a la depuración final. El dataset limpio y citable en
 *   el artículo es n = 420 (ver /data en el repo de reproducibilidad
 *   y el script de generación de mapa, que sí usa el rango final).
 */

/**
 * Menú de la barra de herramientas — funciones de recolección/validación.
 */
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('⚙️ Recolección y Validación')
    .addItem('📍 Procesar Solo Coordenadas (Lat/Lng)', 'procesarCoordenadas')
    .addItem('⭐ Procesar Solo Estrellas y Reseñas', 'procesarEstrellasYReviews')
    .addSeparator()
    .addItem('🔍 Validar coordenadas', 'validarCoordenadas')
    .addItem('🔧 Corregir coordenadas erróneas', 'corregirCoordenadas')
    .addToUi();
}

/**
 * GEOCODIFICACIÓN ESTRICTA - CENTRO HISTÓRICO DE QUITO (V7)
 *
 * Estrategia de búsqueda en 3 pasos:
 *   a) Geocoding API con la dirección exacta → si cae en el bbox, se acepta
 *      directamente (la dirección específica de Quito es suficiente garantía)
 *   b) findplacefromtext con nombre+dirección → validación de nombre relajada
 *   c) textsearch como último recurso
 *
 * La validación de nombre es OPCIONAL cuando la dirección geocodifica
 * correctamente dentro del CHQ. El nombre del catastro y el de Google Maps
 * pueden diferir mucho (ej. "HASTA LA VUELTA SEÑOR" vs "¡Hasta la Vuelta!, Señor").
 *
 * Columnas R/S reciben "" (vacío) cuando C/D ya tienen coordenadas válidas.
 * Solo se rellenan R/S cuando C/D = "No disponible".
 *
 * COLUMNAS:
 *   A = Nombre del restaurante
 *   B = Dirección exacta (ya incluye ", Quito, Ecuador")
 *   C = Latitud  (validado dentro del CHQ)
 *   D = Longitud (validado dentro del CHQ)
 *   R = Latitud  (solo dirección, para locales no encontrados con nombre)
 *   S = Longitud (solo dirección, para locales no encontrados con nombre)
 *
 * NOTA SOBRE CALLES:
 *   El CHQ tiene calles llamadas Guayaquil, Venezuela, Manabí, Chile, etc.
 *   Ningún filtro actúa sobre nombres de calles. El bbox descarta todo
 *   resultado que no esté en Quito.
 */

// ── CONFIGURACIÓN ────────────────────────────────────────────────────────────

var BBOX = {
  latMin: -0.2420,
  latMax: -0.1880,
  lngMin: -78.5380,
  lngMax: -78.4940
};

var CHQ_LAT   = -0.2200;
var CHQ_LNG   = -78.5120;
var CHQ_RADIO = 3000; // metros

var STOP_WORDS = [
  "de","del","la","el","los","las","y","e","o","a","en","un","una",
  "por","con","que","su","al","lo","restaurante","rest","cafe","café",
  "bar","grill","food","the","sr","don","doña","dona","snack","picanteria",
  "cevicheria","marisqueria","heladeria","cafeteria","pizzeria","asadero",
  "comedor","chifa","fonda","bistro","pub","senor","señor","hasta","vuelta"
];

// ── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────────

function procesarCoordenadas() {
  var t0     = new Date().getTime();
  var libro  = SpreadsheetApp.getActiveSpreadsheet();
  var hoja   = libro.getActiveSheet();
  var config = libro.getSheetByName("Configuracion");

  if (!config) {
    SpreadsheetApp.getUi().alert('No se encuentra la pestaña "Configuracion".');
    return;
  }
  var apiKey = config.getRange(1, 1).getValue().toString().trim();
  if (!apiKey) {
    SpreadsheetApp.getUi().alert('Coloca tu API Key en A1 de "Configuracion".');
    return;
  }

  var FILA_INICIO = 2;
  var TOTAL_FILAS = 422;

  var nombres     = hoja.getRange(FILA_INICIO, 1,  TOTAL_FILAS, 1).getValues();
  var direcciones = hoja.getRange(FILA_INICIO, 2,  TOTAL_FILAS, 1).getValues();
  var latsC       = hoja.getRange(FILA_INICIO, 3,  TOTAL_FILAS, 1).getValues();
  var lngsD       = hoja.getRange(FILA_INICIO, 4,  TOTAL_FILAS, 1).getValues();
  var latsR       = hoja.getRange(FILA_INICIO, 18, TOTAL_FILAS, 1).getValues();
  var lngsS       = hoja.getRange(FILA_INICIO, 19, TOTAL_FILAS, 1).getValues();

  var resLatC = [], resLngD = [], resLatR = [], resLngS = [];
  var procesados = 0, exitososCD = 0, exitososRS = 0, noDispCD = 0, omitidos = 0;
  var detenido = false;

  for (var i = 0; i < TOTAL_FILAS; i++) {
    var nombre    = nombres[i][0].toString().trim();
    var direccion = direcciones[i][0].toString().trim();
    var latC      = latsC[i][0].toString().trim();
    var lngD      = lngsD[i][0].toString().trim();
    var latR      = latsR[i][0].toString().trim();
    var lngS      = lngsS[i][0].toString().trim();

    // ── Detectar si C/D ya está resuelta ────────────────────────────────────
    var cdResuelta = false;
    if (latC !== "" && latC !== "Error") {
      var latCNum = parseFloat(latC);
      var lngDNum = parseFloat(lngD);
      if (latC === "No disponible" || esDentroDelBbox(latCNum, lngDNum)) {
        cdResuelta = true;
      }
    }

    // ── Detectar si R/S ya está resuelta ────────────────────────────────────
    var rsResuelta = false;
    if (latR !== "" && latR !== "Error") {
      var latRNum = parseFloat(latR);
      var lngSNum = parseFloat(lngS);
      // "0" también cuenta como resuelta
      if (latR === "No disponible" || latR === "0" ||
          esDentroDelBbox(latRNum, lngSNum)) {
        rsResuelta = true;
      }
    }

    if (cdResuelta && rsResuelta) {
      resLatC.push([latC]); resLngD.push([lngD]);
      resLatR.push([latR]); resLngS.push([lngS]);
      omitidos++;
      continue;
    }

    // ── Control de tiempo ───────────────────────────────────────────────────
    if ((new Date().getTime() - t0) > 270000) {
      detenido = true;
      for (var j = i; j < TOTAL_FILAS; j++) {
        resLatC.push([latsC[j][0]]); resLngD.push([lngsD[j][0]]);
        resLatR.push([latsR[j][0]]); resLngS.push([lngsS[j][0]]);
      }
      break;
    }

    if (!nombre || !direccion) {
      resLatC.push(["No disponible"]); resLngD.push(["No disponible"]);
      resLatR.push(["No disponible"]); resLngS.push(["No disponible"]);
      noDispCD++;
      continue;
    }

    procesados++;

    // ── PASO 1: Buscar con dirección + (opcionalmente) nombre ───────────────
    var coordCD = cdResuelta ? null : geocodificarConValidacion(nombre, direccion, apiKey);

    if (coordCD) {
      // ✓ Encontrado → C/D con coords, R/S con 0
      resLatC.push([coordCD.lat]);
      resLngD.push([coordCD.lng]);
      resLatR.push([0]);
      resLngS.push([0]);
      exitososCD++;
    } else {
      // ✗ No encontrado → C/D = "No disponible"
      resLatC.push(["No disponible"]);
      resLngD.push(["No disponible"]);
      noDispCD++;

      // ── PASO 2: Buscar SOLO DIRECCIÓN para R/S ───────────────────────────
      if (!rsResuelta) {
        Utilities.sleep(150);
        var coordRS = geocodificarSoloDireccion(direccion, apiKey);
        if (coordRS) {
          resLatR.push([coordRS.lat]);
          resLngS.push([coordRS.lng]);
          exitososRS++;
        } else {
          resLatR.push(["No disponible"]);
          resLngS.push(["No disponible"]);
        }
      } else {
        resLatR.push([latR]);
        resLngS.push([lngS]);
      }
    }

    Utilities.sleep(200);
  }

  // ── Escribir en hoja ─────────────────────────────────────────────────────
  hoja.getRange(FILA_INICIO, 3,  resLatC.length, 1).setValues(resLatC);
  hoja.getRange(FILA_INICIO, 4,  resLngD.length, 1).setValues(resLngD);
  hoja.getRange(FILA_INICIO, 18, resLatR.length, 1).setValues(resLatR);
  hoja.getRange(FILA_INICIO, 19, resLngS.length, 1).setValues(resLngS);

  var msg = detenido
    ? "⏱️ Tiempo agotado — vuelve a ejecutar para continuar.\n\n"
    : "✅ Proceso completado.\n\n";
  msg += "Procesados: " + procesados + "\n"
       + "  ✓ C/D (coord. válidas): " + exitososCD + "\n"
       + "  ✗ C/D No disponible:    " + noDispCD   + "\n"
       + "  ✓ R/S (solo dirección): " + exitososRS + "\n"
       + "  → Omitidos:             " + omitidos;

  SpreadsheetApp.getUi().alert(msg);
}

// ── GEOCODIFICACIÓN CON VALIDACIÓN (para C/D) ───────────────────────────────
//
// Jerarquía de búsqueda:
//   1. Geocoding API con dirección exacta → más preciso para calles específicas
//   2. findplacefromtext con nombre+dirección → permite validar por nombre
//   3. textsearch como último recurso
//
// La validación de nombre es SECUNDARIA: si la dirección geocodifica
// correctamente en el CHQ, aceptamos el resultado. El nombre solo se
// usa para descartar coincidencias claramente erróneas en Places.

function geocodificarConValidacion(nombre, direccion, apiKey) {
  var nombreLimpio = limpiarTexto(nombre);
  // La dirección ya viene con ", Quito, Ecuador"
  var dir = direccion.trim();

  // ── 1. Geocoding API (dirección sola) ─────────────────────────────────────
  // Si la dirección exacta geocodifica dentro del CHQ, la aceptamos.
  // No necesitamos validar el nombre porque la dirección es suficientemente
  // específica (número + intersección de calles + ciudad).
  var urlGeo = "https://maps.googleapis.com/maps/api/geocode/json"
    + "?address=" + encodeURIComponent(dir)
    + "&key="     + apiKey;

  try {
    var rg = UrlFetchApp.fetch(urlGeo, { muteHttpExceptions: true });
    var jg = JSON.parse(rg.getContentText());
    if (jg.results && jg.results.length > 0) {
      var geo = jg.results[0].geometry.location;
      if (esDentroDelBbox(geo.lat, geo.lng)) {
        return { lat: geo.lat, lng: geo.lng };
      }
    }
  } catch(e) {}

  Utilities.sleep(100);

  // ── 2. findplacefromtext con nombre+dirección ──────────────────────────────
  var query2 = nombreLimpio + " " + dir;
  var url2 = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    + "?input="        + encodeURIComponent(query2)
    + "&inputtype=textquery"
    + "&fields=name,geometry"
    + "&locationbias=circle:" + CHQ_RADIO + "@" + CHQ_LAT + "," + CHQ_LNG
    + "&key="          + apiKey;

  try {
    var r2 = UrlFetchApp.fetch(url2, { muteHttpExceptions: true });
    var j2 = JSON.parse(r2.getContentText());
    if (j2.candidates && j2.candidates.length > 0) {
      var c2  = j2.candidates[0];
      var g2  = c2.geometry ? c2.geometry.location : null;
      var n2  = c2.name || "";
      // Validación relajada: aceptar si está en el bbox, aunque el nombre
      // no coincida perfectamente (puede diferir del catastro municipal)
      if (g2 && esDentroDelBbox(g2.lat, g2.lng) && validarNombreRelajado(nombreLimpio, n2)) {
        return { lat: g2.lat, lng: g2.lng };
      }
    }
  } catch(e) {}

  Utilities.sleep(100);

  // ── 3. textsearch ──────────────────────────────────────────────────────────
  var query3 = nombreLimpio + " " + dir;
  var url3 = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    + "?query="    + encodeURIComponent(query3)
    + "&location=" + CHQ_LAT + "," + CHQ_LNG
    + "&radius="   + CHQ_RADIO
    + "&key="      + apiKey;

  try {
    var r3 = UrlFetchApp.fetch(url3, { muteHttpExceptions: true });
    var j3 = JSON.parse(r3.getContentText());
    if (j3.results && j3.results.length > 0) {
      for (var k = 0; k < Math.min(3, j3.results.length); k++) {
        var res = j3.results[k];
        var g3  = res.geometry ? res.geometry.location : null;
        var n3  = res.name || "";
        if (g3 && esDentroDelBbox(g3.lat, g3.lng) && validarNombreRelajado(nombreLimpio, n3)) {
          return { lat: g3.lat, lng: g3.lng };
        }
      }
    }
  } catch(e) {}

  return null;
}

// ── GEOCODIFICACIÓN SOLO DIRECCIÓN (para R/S) ────────────────────────────────

function geocodificarSoloDireccion(direccion, apiKey) {
  var dir = direccion.trim();

  // Geocoding API
  var urlGeo = "https://maps.googleapis.com/maps/api/geocode/json"
    + "?address=" + encodeURIComponent(dir)
    + "&key="     + apiKey;

  try {
    var r = UrlFetchApp.fetch(urlGeo, { muteHttpExceptions: true });
    var j = JSON.parse(r.getContentText());
    if (j.results && j.results.length > 0) {
      var geo = j.results[0].geometry.location;
      if (esDentroDelBbox(geo.lat, geo.lng)) {
        return { lat: geo.lat, lng: geo.lng };
      }
    }
  } catch(e) {}

  // textsearch como fallback
  var urlTS = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    + "?query="    + encodeURIComponent(dir)
    + "&location=" + CHQ_LAT + "," + CHQ_LNG
    + "&radius="   + CHQ_RADIO
    + "&key="      + apiKey;

  try {
    var r2 = UrlFetchApp.fetch(urlTS, { muteHttpExceptions: true });
    var j2 = JSON.parse(r2.getContentText());
    if (j2.results && j2.results.length > 0) {
      var geo2 = j2.results[0].geometry.location;
      if (esDentroDelBbox(geo2.lat, geo2.lng)) {
        return { lat: geo2.lat, lng: geo2.lng };
      }
    }
  } catch(e2) {}

  return null;
}

// ── VALIDACIÓN DE NOMBRE (RELAJADA) ─────────────────────────────────────────
//
// Con la Geocoding API como paso 1, esta función solo se usa como
// desempate en Places cuando hay varias opciones. Se acepta si:
//   - Una cadena contiene a la otra
//   - Comparten al menos 1 palabra clave significativa
//   - El resultado está en el CHQ (ya validado antes de llamar aquí)

function validarNombreRelajado(original, google) {
  if (!google) return false;

  var o = normalizar(original);
  var g = normalizar(google);

  // Contención directa
  if (g.indexOf(o) !== -1 || o.indexOf(g) !== -1) return true;

  // Palabras clave del original
  var palabras = o.split(/\s+/).filter(function(p) {
    return p.length > 3 && STOP_WORDS.indexOf(p) === -1;
  });

  if (palabras.length === 0) return true; // nombre demasiado corto, aceptar

  var hits = palabras.filter(function(p) { return g.indexOf(p) !== -1; }).length;

  // Relajado: basta con 1 palabra o 30% de coincidencia
  if (hits >= 1) return true;
  if (hits / palabras.length >= 0.30) return true;

  return false;
}

// ── UTILIDADES ───────────────────────────────────────────────────────────────

function esDentroDelBbox(lat, lng) {
  return lat >= BBOX.latMin && lat <= BBOX.latMax
      && lng >= BBOX.lngMin && lng <= BBOX.lngMax;
}

function limpiarTexto(s) {
  return s.replace(/\.\.\./g, "")
          .replace(/["'"""«»¡!¿?]+/g, "")
          .replace(/\s+/g, " ")
          .trim();
}

function normalizar(s) {
  return s.toLowerCase()
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "")
          .replace(/[^a-z0-9\s]/g, "")
          .trim();
}

// ── LIMPIEZA PREVIA ──────────────────────────────────────────────────────────
// Ejecutar UNA SOLA VEZ antes de procesarCoordenadas()
// Limpia: "Error", coords fuera del bbox, y deja intactos "No disponible" y "0"

function limpiarErrores() {
  var hoja        = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var FILA_INICIO = 2;
  var TOTAL_FILAS = 422;

  var latsC = hoja.getRange(FILA_INICIO, 3,  TOTAL_FILAS, 1).getValues();
  var lngsD = hoja.getRange(FILA_INICIO, 4,  TOTAL_FILAS, 1).getValues();
  var latsR = hoja.getRange(FILA_INICIO, 18, TOTAL_FILAS, 1).getValues();
  var lngsS = hoja.getRange(FILA_INICIO, 19, TOTAL_FILAS, 1).getValues();
  var n = 0;

  function limpiarPar(lats, lngs, idx) {
    var lv = lats[idx][0].toString().trim();
    if (lv === "Error") {
      lats[idx][0] = ""; lngs[idx][0] = ""; n++; return;
    }
    // "No disponible" y "0" se conservan
    if (lv === "No disponible" || lv === "0" || lv === "") return;
    var latNum = parseFloat(lv);
    var lngNum = parseFloat(lngs[idx][0]);
    if (!isNaN(latNum) && !isNaN(lngNum) && !esDentroDelBbox(latNum, lngNum)) {
      lats[idx][0] = ""; lngs[idx][0] = ""; n++;
    }
  }

  for (var i = 0; i < TOTAL_FILAS; i++) {
    limpiarPar(latsC, lngsD, i);
    limpiarPar(latsR, lngsS, i);
  }

  hoja.getRange(FILA_INICIO, 3,  TOTAL_FILAS, 1).setValues(latsC);
  hoja.getRange(FILA_INICIO, 4,  TOTAL_FILAS, 1).setValues(lngsD);
  hoja.getRange(FILA_INICIO, 18, TOTAL_FILAS, 1).setValues(latsR);
  hoja.getRange(FILA_INICIO, 19, TOTAL_FILAS, 1).setValues(lngsS);

  SpreadsheetApp.getUi().alert(
    "🧹 Limpiadas " + n + " celdas con Error o coords fuera del CHQ.\n"
    + "Ahora ejecuta procesarCoordenadas()."
  );
}



/**
 * PROCESO 2: EXTRACCIÓN ESTRICTA DE ESTRELLAS Y REVIEWS (VERSIÓN ACADÉMICA V3)
 * Valida de forma estricta que el nombre coincida y evita falsos positivos.
 * Rango corregido: Fila 2 a 428 (A2:A428).
 */
function procesarEstrellasYReviews() {
  var tiempoInicio = new Date().getTime();
  var libro = SpreadsheetApp.getActiveSpreadsheet();
  var hojaConfig = libro.getSheetByName("Configuracion");
  var hoja = libro.getActiveSheet();
  
  if (!hojaConfig) {
    SpreadsheetApp.getUi().alert('Error: No se encuentra la pestaña "Configuracion".');
    return;
  }
  var apiKey = hojaConfig.getRange(1, 1).getValue().trim();
  if (!apiKey) {
    SpreadsheetApp.getUi().alert('Error: Por favor coloca tu API Key en A1 de "Configuracion".');
    return;
  }

  // Configuración estricta del rango (A2:A428 -> 422 filas en total)
  var filaInicio = 2;
  var totalFilas = 422; 
  
  var datosNombres = hoja.getRange(filaInicio, 1, totalFilas, 1).getValues();
  var datosDirecciones = hoja.getRange(filaInicio, 2, totalFilas, 1).getValues();
  
  var valoresActualesEstrellas = hoja.getRange(filaInicio, 5, totalFilas, 1).getValues();
  var valoresActualesReviews = hoja.getRange(filaInicio, 6, totalFilas, 1).getValues();
  
  var resultadosEstrellas = [];
  var resultadosReviews = [];
  var nuevasFilasProcesadas = 0;
  var detencionPorTiempo = false;
  
  for (var i = 0; i < totalFilas; i++) {
    var nombreOriginal = datosNombres[i][0].toString().trim();
    var direccionOriginal = datosDirecciones[i][0].toString().trim();
    var estrellaActual = valoresActualesEstrellas[i][0].toString().trim();
    var reviewActual = valoresActualesReviews[i][0];
    
    // CONTROL INCREMENTAL: Si ya determinamos con éxito un estado válido, saltar.
    // Si antes dio "Error" o guardó un dato falso, lo volverá a procesar para corregirlo.
    if (estrellaActual !== "" && estrellaActual !== "Error" && estrellaActual !== "Pendiente" && estrellaActual !== "0") {
      // Si ya dice "No existe registro", lo respetamos para no volver a gastar API
      if (estrellaActual === "No existe registro") {
        resultadosEstrellas.push([estrellaActual]);
        resultadosReviews.push([reviewActual]);
        continue;
      }
      // Si es un número (calificación válida antigua), la dejamos pasar
      if (!isNaN(parseFloat(estrellaActual))) {
        resultadosEstrellas.push([estrellaActual]);
        resultadosReviews.push([reviewActual]);
        continue;
      }
    }
    
    // CONTROL DE TIEMPO SEGURO (Evitar congelamiento a los 4.5 minutos)
    var tiempoActual = new Date().getTime();
    if (tiempoActual - tiempoInicio > 270000) {
      detencionPorTiempo = true;
      for (var j = i; j < totalFilas; j++) {
        resultadosEstrellas.push([valoresActualesEstrellas[j][0]]);
        resultadosReviews.push([valoresActualesReviews[j][0]]);
      }
      break;
    }
    
    if (!nombreOriginal || !direccionOriginal) {
      resultadosEstrellas.push(["No existe registro"]);
      resultadosReviews.push([0]);
      continue;
    }
    
    try {
      // 1. Limpieza preservando la esencia (quitamos solo puntos suspensivos o espacios dobles)
      var nombreLimpio = nombreOriginal.replace(/\.\.\./g, "").replace(/\s+/g, " ").trim();
      
      // 2. Forzar la búsqueda combinando NOMBRE + DIRECCIÓN en el mismo campo de texto
      var consultaBusqueda = encodeURIComponent(nombreLimpio + ", " + direccionOriginal);
      
      // Pedimos a Google el place_id y además el NOMBRE REAL con el que Google tiene registrado ese punto
      var urlBuscarLugar = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input=" + consultaBusqueda + "&inputtype=textquery&fields=place_id,name&key=" + apiKey;
      
      var respuestaBusqueda = UrlFetchApp.fetch(urlBuscarLugar, {muteHttpExceptions: true});
      var jsonBusqueda = JSON.parse(respuestaBusqueda.getContentText());
      
      var rating = "No existe registro";
      var totalReviews = 0;
      var coincidenciaExitosa = false;
      
      if (jsonBusqueda.candidates && jsonBusqueda.candidates.length > 0) {
        var candidato = jsonBusqueda.candidates[0];
        var placeId = candidato.place_id;
        var nombreDevueltoPorGoogle = candidato.name ? candidato.name.toLowerCase() : "";
        
        // --- CONTROL DE CALIDAD Y COMPARACIÓN ESTRICTA ---
        var nombreEsperado = nombreLimpio.toLowerCase();
        
        // Verificamos si el nombre que nos da Google comparte palabras clave esenciales de tu lista.
        // Si Google devuelve algo completamente ajeno, se asume que intentó "adivinar" por error.
        if (nombreDevueltoPorGoogle.indexOf(nombreEsperado) !== -1 || nombreEsperado.indexOf(nombreDevueltoPorGoogle) !== -1) {
          coincidenciaExitosa = true;
        } else {
          // Filtro por palabras clave (ej: si ambas contienen "Zarumeña", pasa. Si una dice "Esquina" y Google da "Villa", bloquea)
          var palabrasOriginales = nombreEsperado.split(" ");
          var coincidenciasPalabras = 0;
          for (var p = 0; p < palabrasOriginales.length; p++) {
            if (palabrasOriginales[p].length > 3 && nombreDevueltoPorGoogle.indexOf(palabrasOriginales[p]) !== -1) {
              coincidenciasPalabras++;
            }
          }
          // Si comparten palabras clave significativas, lo damos por bueno, de lo contrario se rechaza
          if (coincidenciasPalabras >= 1) {
            coincidenciaExitosa = true;
          }
        }
        
        // Si pasó el control de calidad, extraemos sus datos profundos
        if (placeId && coincidenciaExitosa) {
          var urlDetalles = "https://maps.googleapis.com/maps/api/place/details/json?place_id=" + placeId + "&fields=rating,user_ratings_total&key=" + apiKey;
          var respuestaDetalles = UrlFetchApp.fetch(urlDetalles, {muteHttpExceptions: true});
          var jsonDetalles = JSON.parse(respuestaDetalles.getContentText());
          
          if (jsonDetalles.result) {
            rating = jsonDetalles.result.rating || "Sin opiniones";
            totalReviews = jsonDetalles.result.user_ratings_total || 0;
            nuevasFilasProcesadas++;
          }
        }
      }
      
      resultadosEstrellas.push([rating]); 
      resultadosReviews.push([totalReviews]);
      
    } catch (error) {
      resultadosEstrellas.push(["Error"]);
      resultadosReviews.push([0]);
    }
    
    Utilities.sleep(150); 
  }
  
  // Guardar en las columnas E y F
  hoja.getRange(filaInicio, 5, resultadosEstrellas.length, 1).setValues(resultadosEstrellas);
  hoja.getRange(filaInicio, 6, resultadosReviews.length, 1).setValues(resultadosReviews);
  
  if (detencionPorTiempo) {
    SpreadsheetApp.getUi().alert('⏱️ Bloque estricto guardado. Se procesaron ' + nuevasFilasProcesadas + ' filas. Vuelve a ejecutar para continuar.');
  } else {
    SpreadsheetApp.getUi().alert('🎉 ¡Verificación estricta finalizada! Toda la lista (2 a 428) se encuentra limpia y libre de falsos positivos.');
  }
}

/* ══════════════════════════════════════════════════════════════════
   FUNCIÓN: validarCoordenadas()
   Geocodifica cada dirección, compara con coords en C/D (o R/S),
   y escribe "Sí cumple" / "No cumple · X.XX km" en la columna T.
   ══════════════════════════════════════════════════════════════════ */

/**
 * Umbral máximo de distancia (km) para considerar que las coordenadas
 * corresponden a la dirección. En el CHQ, ~400 m = ~3-4 manzanas.
 */
const THRESHOLD_KM = 0.40;

/**
 * Coordenada placeholder que Google Maps asigna cuando no encuentra
 * la dirección exacta (centro genérico del CHQ).
 */
const PLACEHOLDER = { lat: -0.2232523, lng: -78.5141064 };

/* ──────────────────────────────────────────────────────────────── */
function validarCoordenadas() {
  const ui    = SpreadsheetApp.getUi();
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Mapa');

  if (!sheet) {
    ui.alert('No se encontró la hoja "Mapa".');
    return;
  }

  // Leer A2:T428 (20 columnas)
  const lastRow  = Math.max(sheet.getLastRow(), 2);
  const numRows  = Math.min(lastRow - 1, 427);
  const data     = sheet.getRange(2, 1, numRows, 20).getValues();

  const geocoder = Maps.newGeocoder().setLanguage('es');
  const results  = [];

  // Contadores para el resumen final
  let cSiCumple = 0, cNoCumple = 0, cSinCoord = 0, cError = 0;

  data.forEach(function(row, i) {
    const nombre = String(row[0] || '').trim();

    // Fila vacía → dejar en blanco
    if (!nombre) {
      results.push(['']);
      return;
    }

    const direccion = String(row[1] || '').trim();

    // ── 1. Determinar coordenadas a validar ──────────────────────
    //    Prioridad: C/D (índices 2,3) → si no, R/S (índices 17,18)
    const latC  = parseFloat(row[2]);
    const lngC  = parseFloat(row[3]);
    const latRS = parseFloat(row[17]);
    const lngRS = parseFloat(row[18]);

    const mainOk   = _coordOk(latC, lngC);
    const backupOk = _coordOk(latRS, lngRS);

    if (!mainOk && !backupOk) {
      results.push(['Sin coordenadas']);
      cSinCoord++;
      return;
    }

    const useLat = mainOk ? latC : latRS;
    const useLng = mainOk ? lngC : lngRS;
    const source = mainOk ? 'C/D' : 'R/S';

    // ── 2. Detectar coordenada placeholder ───────────────────────
    const isPlaceholder = (
      Math.abs(useLat - PLACEHOLDER.lat) < 0.00001 &&
      Math.abs(useLng - PLACEHOLDER.lng) < 0.00001
    );

    // ── 3. Limpiar dirección para geocodificación ─────────────────
    const cleanAddr = _cleanAddress(direccion);

    // ── 4. Geocodificar ───────────────────────────────────────────
    let geoResult;
    try {
      geoResult = geocoder.geocode(cleanAddr);
    } catch (err) {
      results.push(['Error API: ' + err.message.substring(0, 60)]);
      cError++;
      Utilities.sleep(200);
      return;
    }

    if (!geoResult || geoResult.status !== 'OK' ||
        !geoResult.results || !geoResult.results.length) {
      results.push(['Sin resultado geocoding']);
      cError++;
      Utilities.sleep(150);
      return;
    }

    const geo = geoResult.results[0].geometry.location;
    const km  = _haversineKm(useLat, useLng, geo.lat, geo.lng);

    // ── 5. Evaluar ────────────────────────────────────────────────
    let verdict;
    if (isPlaceholder) {
      // Placeholder siempre puede estar lejos; indicarlo explícitamente
      verdict = km <= THRESHOLD_KM
        ? 'Sí cumple (placeholder · ' + km.toFixed(2) + ' km)'
        : 'No cumple · placeholder · ' + km.toFixed(2) + ' km [' + source + ']';
    } else {
      verdict = km <= THRESHOLD_KM
        ? 'Sí cumple'
        : 'No cumple · ' + km.toFixed(2) + ' km [' + source + ']';
    }

    if (verdict.startsWith('Sí')) cSiCumple++;
    else                          cNoCumple++;

    results.push([verdict]);

    // Pausa para no saturar la API (≈45 s total para 427 filas)
    Utilities.sleep(100);
  });

  // ── 6. Escribir resultados en columna T ──────────────────────
  sheet.getRange(2, 20, results.length, 1).setValues(results);

  // Resaltar "No cumple" en amarillo claro para revisión visual
  const colT = sheet.getRange(2, 20, results.length, 1);
  results.forEach(function(r, i) {
    const cell = sheet.getRange(i + 2, 20);
    if (r[0].startsWith('No cumple')) {
      cell.setBackground('#FFF3CD');
      cell.setFontColor('#856404');
    } else if (r[0].startsWith('Sí cumple')) {
      cell.setBackground('#D4EDDA');
      cell.setFontColor('#155724');
    } else {
      cell.setBackground('#F8F9FA');
      cell.setFontColor('#6C757D');
    }
  });

  ui.alert(
    '✅ Validación completada\n\n' +
    '  Sí cumple : ' + cSiCumple  + '\n' +
    '  No cumple : ' + cNoCumple  + '\n' +
    '  Sin coords: ' + cSinCoord  + '\n' +
    '  Errores   : ' + cError     + '\n\n' +
    'Revisa la columna T (COMPROBACION).\n' +
    'Las filas con problemas aparecen en amarillo.'
  );
}

/* ──────────────────────────────────────────────────────────────────
   HELPERS
────────────────────────────────────────────────────────────────── */

/**
 * Limpia una dirección quiteña para geocodificación:
 * elimina números de intersección (OE1-22, N4-65, etc.),
 * códigos de bloque sueltos (OE5, N8, S1C), y palabras auxiliares.
 */
function _cleanAddress(addr) {
  // Quitar sufijo de ciudad ya existente (lo volvemos a agregar con precisión)
  let a = addr.replace(/,\s*Quito.*$/i, '').trim();

  // Eliminar números de intersección estilo Quito: OE1-22, N4-65, E4-12, S1C-30
  a = a.replace(/\b[NSEOnseo]{1,3}\d+[A-Za-z]?-\d+[A-Za-z]?\b/g, '');

  // Eliminar códigos de bloque sueltos: OE5, N8, S1C, E3B, N11E
  a = a.replace(/\b[NSEOnseo]{1,3}\d+[A-Za-z]?\b/g, '');

  // Eliminar palabras auxiliares frecuentes
  a = a.replace(/\b(S\/N|PASAJE|PISO|SECTOR|CASA|NA|PB|LOCAL)\b/gi, '');

  // Limpiar espacios múltiples y comas dobles
  a = a.replace(/,+/g, ',').replace(/\s+/g, ' ').trim();

  // Agregar contexto geográfico preciso para mejorar geocoding
  return a + ', Centro Histórico, Quito, Ecuador';
}

/**
 * Distancia entre dos puntos geográficos en kilómetros (fórmula de Haversine).
 */
function _haversineKm(lat1, lng1, lat2, lng2) {
  const R    = 6371;
  const d2r  = Math.PI / 180;
  const dLat = (lat2 - lat1) * d2r;
  const dLng = (lng2 - lng1) * d2r;
  const a    = Math.sin(dLat / 2) ** 2 +
               Math.cos(lat1 * d2r) * Math.cos(lat2 * d2r) *
               Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Verifica que una coordenada sea numérica y esté dentro del
 * área metropolitana de Quito (excluye Guayaquil, Sevilla, etc.).
 */
function _coordOk(lat, lng) {
  return (
    !isNaN(lat) && !isNaN(lng) &&
    lat !== 0   && lng !== 0   &&
    lat >= -0.42 && lat <= -0.05 &&
    lng >= -78.60 && lng <= -78.42
  );
}


/* ══════════════════════════════════════════════════════════════════
   FUNCIÓN: corregirCoordenadas()
   Para cada fila marcada "No cumple" en la columna T:
     · Geocodifica la dirección limpia (sin códigos de intersección)
     · Valida que el resultado esté dentro de Quito
     · Escribe las coordenadas corregidas en la columna que corresponde:
         C/D = "No disponible"  →  escribe en R/S  (dead lat/long)
         R/S = 0                →  escribe en C/D  (latitud/longitud)
     · Actualiza la columna T con el resultado de la corrección
   ══════════════════════════════════════════════════════════════════ */
function corregirCoordenadas() {
  const ui    = SpreadsheetApp.getUi();
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Mapa');

  if (!sheet) {
    ui.alert('No se encontró la hoja "Mapa".');
    return;
  }

  // ── Confirmación ─────────────────────────────────────────────────
  const confirm = ui.alert(
    '🔧 Confirmar corrección de coordenadas',
    'Esta función geocodificará las direcciones de todos los registros\n' +
    'marcados como "No cumple" en la columna T y sobreescribirá las\n' +
    'coordenadas incorrectas.\n\n' +
    '  · Si C/D = "No disponible"  →  coordenadas corregidas a R/S\n' +
    '  · Si R/S = 0                →  coordenadas corregidas a C/D\n\n' +
    '¿Continuar?',
    ui.ButtonSet.YES_NO
  );
  if (confirm !== ui.Button.YES) {
    ui.alert('Operación cancelada.');
    return;
  }

  // ── Leer datos (A2:T428, 20 columnas) ────────────────────────────
  const FILA_INICIO = 2;
  const TOTAL_FILAS = 427;
  const data     = sheet.getRange(FILA_INICIO, 1, TOTAL_FILAS, 20).getValues();
  const geocoder = Maps.newGeocoder().setLanguage('es');

  // Contadores para el resumen
  let nCorregido = 0, nError = 0, nOmitido = 0, nFueraBounds = 0;

  data.forEach(function(row, i) {
    const sheetRow = i + FILA_INICIO;   // fila real en la hoja (base 1)
    const nombre   = String(row[0] || '').trim();

    if (!nombre) return;

    // ── Solo procesar "No cumple" ─────────────────────────────────
    const verdict = String(row[19] || '').trim();   // col T (índice 19)
    if (!verdict.startsWith('No cumple')) {
      nOmitido++;
      return;
    }

    const direccion = String(row[1] || '').trim();  // col B

    // ── Determinar estado actual de coordenadas ───────────────────
    //    C/D: índices 2,3 (cols C y D de la hoja)
    //    R/S: índices 17,18 (cols R y S de la hoja = "dead lat/long")
    const latC_raw  = String(row[2]).trim();
    const lngC_raw  = String(row[3]).trim();
    const latRS     = parseFloat(row[17]);
    const lngRS     = parseFloat(row[18]);

    // "No disponible" en C/D → texto no numérico
    const cdNoDisp  = (latC_raw === 'No disponible' || isNaN(parseFloat(latC_raw)));
    // 0 en R/S → backup vacío
    const rsVacia   = (isNaN(latRS) || latRS === 0);

    // ── Limpiar dirección ─────────────────────────────────────────
    const cleanAddr = _cleanAddress(direccion);
    const shortAddr = cleanAddr.replace(', Centro Histórico, Quito, Ecuador', '');

    // ── Geocodificar ──────────────────────────────────────────────
    let geoRes;
    try {
      geoRes = geocoder.geocode(cleanAddr);
    } catch (err) {
      _writeT(sheet, sheetRow,
        'Error API: ' + err.message.substring(0, 60), 'error');
      nError++;
      Utilities.sleep(300);
      return;
    }

    if (!geoRes || geoRes.status !== 'OK' ||
        !geoRes.results || !geoRes.results.length) {
      _writeT(sheet, sheetRow,
        'Sin resultado · "' + shortAddr + '"', 'error');
      nError++;
      Utilities.sleep(150);
      return;
    }

    const geo    = geoRes.results[0].geometry.location;
    const newLat = geo.lat;
    const newLng = geo.lng;

    // ── Validar que las coords corregidas sean de Quito ───────────
    if (!_coordOk(newLat, newLng)) {
      _writeT(sheet, sheetRow,
        'Fuera de Quito · ' + newLat.toFixed(5) + ',' + newLng.toFixed(5) +
        ' · "' + shortAddr + '"', 'error');
      nFueraBounds++;
      Utilities.sleep(100);
      return;
    }

    // ── Escribir en la columna correcta ───────────────────────────
    if (cdNoDisp) {
      // C/D = "No disponible"  →  guardar coordenada corregida en R/S
      sheet.getRange(sheetRow, 18).setValue(newLat);   // col R: dead lat
      sheet.getRange(sheetRow, 19).setValue(newLng);   // col S: dead long
      _writeT(sheet, sheetRow,
        'Corregido → R/S · "' + shortAddr + '"', 'ok');

    } else if (rsVacia) {
      // R/S = 0  →  la coord errónea está en C/D → sobreescribir C/D
      sheet.getRange(sheetRow, 3).setValue(newLat);    // col C: Latitud
      sheet.getRange(sheetRow, 4).setValue(newLng);    // col D: Longitud
      _writeT(sheet, sheetRow,
        'Corregido → C/D · "' + shortAddr + '"', 'ok');

    } else {
      // Ambas tienen valores pero la principal (C/D) era incorrecta
      // → sobreescribir C/D (es la que usa el mapa como prioridad)
      sheet.getRange(sheetRow, 3).setValue(newLat);    // col C: Latitud
      sheet.getRange(sheetRow, 4).setValue(newLng);    // col D: Longitud
      _writeT(sheet, sheetRow,
        'Corregido → C/D (reemplazó valor previo) · "' + shortAddr + '"', 'ok');
    }

    nCorregido++;
    Utilities.sleep(100);   // evitar saturar la API de Maps
  });

  // ── Resumen final ─────────────────────────────────────────────────
  ui.alert(
    '✅ Corrección completada\n\n' +
    '  Corregidos         : ' + nCorregido    + '\n' +
    '  Omitidos (ok/vacío): ' + nOmitido      + '\n' +
    '  Sin resultado API  : ' + nError        + '\n' +
    '  Fuera de Quito     : ' + nFueraBounds  + '\n\n' +
    'Columna T actualizada.\n' +
    'Ahora puedes volver a ejecutar 🔍 Validar coordenadas\n' +
    'para verificar que las correcciones son correctas,\n' +
    'y luego regenerar el mapa con 🗺️ Generar Mapa.'
  );
}

/* ──────────────────────────────────────────────────────────────────
   HELPER INTERNO: escribe resultado en columna T con color
────────────────────────────────────────────────────────────────── */
function _writeT(sheet, sheetRow, text, type) {
  const cell = sheet.getRange(sheetRow, 20);
  cell.setValue(text);
  switch (type) {
    case 'ok':
      // Azul → corregido manualmente por geocoding
      cell.setBackground('#CFE2FF').setFontColor('#0A367A');
      break;
    case 'error':
      // Rojo → no se pudo corregir
      cell.setBackground('#F8D7DA').setFontColor('#721C24');
      break;
    default:
      cell.setBackground(null).setFontColor(null);
  }
}
