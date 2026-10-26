# -*- coding: utf-8 -*-
"""
R1 · Figuras del manuscrito revisadas (Sesión 2)
================================================

Qué hace
  Reutiliza SIN MODIFICARLO final_figures_CODE/figuras_paper_frontiers.py (y,
  a través de él, el motor de análisis). Solo le añade, en tiempo de ejecución:
    1. Mapa base de OpenStreetMap en las Figuras 1, 5 y 6. Por defecto (auto) prueba primero
       las teselas estándar de OSM del mapa interactivo de GitHub, en gris; si el servidor las
       rechaza, dibuja las calles de OSM descargadas una vez por Overpass (vector)
       y en la figura suplementaria del núcleo robusto.
    2. Retícula de coordenadas geográficas (grados) rotulada dentro del marco.
    3. El límite del área de estudio, si se pasa --limite (gpkg, shp o geojson).
    4. La etiqueta "Regional Ecuadorian cuisine" en lugar de "Ecuadorian Cuisine"
       (Figura 4 y Tabla 1).
  Las cifras NO cambian: el cálculo es el del script original.

Salida (carpeta nueva; nada se sobrescribe en final_figures_CODE)
  R1_v2_borrador/figuras_R1/
     Figura1_Area_de_estudio.{pdf,png,tif}
     Figura4_Binomial_negativa_IRR.{pdf,png,tif}
     Figura5_KDE_fisico_vs_digital.{pdf,png,tif}
     Figura6_GetisOrd_resenas_vs_capital.{pdf,png,tif}
     FiguraS8_1_Nucleo_robusto.{pdf,png,tif}
     Tabla1_Caracterizacion_muestra.csv
     registro_figuras_R1.txt

Requiere internet (descarga de teselas). Uso, desde la carpeta raíz del proyecto:
    python R1_v2_borrador/codigo/R1_figuras.py
    python R1_v2_borrador/codigo/R1_figuras.py --limite R1_v2_borrador/datos/limite_CHQ.gpkg \
           --etiqueta-limite "Historic Centre limit (IMP, 2019)"
    python R1_v2_borrador/codigo/R1_figuras.py --sin-mapa-base     # prueba sin internet
"""
import argparse
import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.legend  # noqa: F401  (estilo del límite en la leyenda de la Figura 1)
import matplotlib.patheffects as pe
from matplotlib.collections import PatchCollection
from matplotlib.lines import Line2D
from pyproj import Transformer

ETIQUETA_REGIONAL = "Regional Ecuadorian cuisine"
ATRIBUCION = "© OpenStreetMap contributors"


def cargar_figuras(raiz: Path):
    cod = raiz / "final_figures_CODE"
    sys.path.insert(0, str(cod))
    ruta = cod / "figuras_paper_frontiers.py"
    spec = importlib.util.spec_from_file_location("figuras_originales", ruta)
    F = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(F)
    return F


COLOR_LIMITE, ESTILO_LIMITE = "#17202A", (0, (4, 2))   # límite del CHQ, igual en todos los mapas

# Política de uso de OpenStreetMap: toda petición debe identificar la aplicación.
# (contextily usa por defecto "contextily-<código aleatorio>", que OSM bloquea con 403.)
USER_AGENT = "R1-figuras-CHQ/1.1 (academic figure; +https://github.com/jijadan/quito-digital-foodscape)"
SERVIDORES_OVERPASS = ["https://overpass-api.de/api/interpreter",
                       "https://overpass.kumi.systems/api/interpreter",
                       "https://overpass.private.coffee/api/interpreter"]


def probar_teselas(zoom):
    """Pide una sola tesela del CHQ antes de dibujar. Devuelve (ok, detalle)."""
    import urllib.request, urllib.error
    import math
    lat, lon = -0.2205, -78.5125
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=20) as r:
            tipo = r.headers.get("Content-Type", "")
            return (r.status == 200 and tipo.startswith("image")), f"HTTP {r.status} {tipo}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} (servidor de teselas de OSM rechaza la petición)"
    except Exception as e:
        return False, f"sin conexión: {e}"


# Vías de OSM: clase → (grosor en puntos, color). Grises para no competir con los datos.
ANCHOS_VIAS = {"menor": (0.25, "#D5D9DC"), "peatonal": (0.30, "#CDD3D7"),
               "secundaria": (0.45, "#C3CACF"), "principal": (0.70, "#B5BDC3")}
CLASE_VIA = {"motorway": "principal", "trunk": "principal", "primary": "principal",
             "secondary": "secundaria", "tertiary": "secundaria",
             "pedestrian": "peatonal", "footway": "peatonal", "steps": "peatonal", "living_street": "peatonal"}


def osm_vector(raiz, F, tr):
    """Descarga UNA vez las calles, parques y plazas de OSM (Overpass API) para el área
    del censo ± 700 m y las guarda en R1_v2_borrador/datos/osm_CHQ_vias.geojson (con la
    fecha de descarga). Las ejecuciones siguientes usan esa copia: reproducible y sin red."""
    import geopandas as gpd
    from shapely.geometry import LineString, Polygon
    cache = raiz / "R1_v2_borrador" / "datos" / "osm_CHQ_vias.geojson"
    if not cache.exists():
        import json, urllib.request, urllib.parse
        d = pd.read_csv(raiz / "final_figures_CODE" / "restaurantes_quito_CH_clean.csv")
        s_, n_ = d.lat.min() - 0.0065, d.lat.max() + 0.0065
        w_, e_ = d.lon.min() - 0.0065, d.lon.max() + 0.0065
        bb = f"{s_:.5f},{w_:.5f},{n_:.5f},{e_:.5f}"
        q = (f'[out:json][timeout:90];(way["highway"]({bb});way["leisure"="park"]({bb});'
             f'way["place"="square"]({bb});way["highway"="pedestrian"]["area"="yes"]({bb}););out geom;')
        js, errores = None, []
        for url in SERVIDORES_OVERPASS:
            try:
                req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(),
                                             headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=150) as r:
                    js = json.load(r)
                if js.get("elements"):
                    servidor = url
                    break
                errores.append(f"{url}: respuesta vacía")
            except Exception as e:
                errores.append(f"{url}: {e}")
        if js is None or not js.get("elements"):
            raise SystemExit("No se pudieron descargar las calles de OSM por Overpass:\n  "
                             + "\n  ".join(errores) + "\nRevisa la conexión y vuelve a intentarlo.")
        filas = []
        for el in js.get("elements", []):
            pts = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
            if len(pts) < 2:
                continue
            tags = el.get("tags", {})
            area = tags.get("leisure") == "park" or tags.get("place") == "square" or tags.get("area") == "yes"
            if area and len(pts) >= 4 and pts[0] == pts[-1]:
                geom, tipo = Polygon(pts), "area"
            else:
                geom, tipo = LineString(pts), "via"
            filas.append({"tipo": tipo, "highway": tags.get("highway", ""), "geometry": geom})
        g = gpd.GeoDataFrame(filas, geometry="geometry", crs="EPSG:4326")
        g["descargado"] = datetime.now().strftime("%Y-%m-%d")
        cache.parent.mkdir(parents=True, exist_ok=True)
        g.to_file(cache, driver="GeoJSON")
        msg = f"OSM descargado ({servidor}) y guardado en {cache.name}: {len(g)} elementos"
    else:
        g = gpd.read_file(cache)
        msg = f"OSM leído de la copia local {cache.name} (descargado {g.descargado.iloc[0]}): {len(g)} elementos"
    g = g.to_crs(F.EPSG_PROJ)
    calles = g[g.tipo == "via"].copy()
    calles["clase"] = calles.highway.map(CLASE_VIA).fillna("menor")
    parques = g[g.tipo == "area"].copy()
    return calles, parques, msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--salida", default="R1_v2_borrador/figuras_R1")
    ap.add_argument("--limite", default=None)
    ap.add_argument("--etiqueta-limite", default="Study area limit")
    ap.add_argument("--sin-mapa-base", action="store_true")
    ap.add_argument("--mapa-base", choices=["auto", "teselas", "vector", "ninguno"], default="auto",
                    help="teselas = mismas teselas estándar de OpenStreetMap del mapa interactivo de GitHub "
                         "(tile.openstreetmap.org), en gris; vector = calles de OSM descargadas una vez "
                         "(Overpass) y dibujadas como líneas; auto (por defecto) = prueba las teselas y, si OSM "
                         "las rechaza, pasa solo a vector")
    ap.add_argument("--zoom", type=int, default=17)
    ap.add_argument("--aclarado", type=float, default=0.70,
                    help="0 = gris sin aclarar; 1 = blanco. Aclara el mapa base para que no compita con los datos")
    a = ap.parse_args()

    raiz = Path(a.raiz).resolve()
    salida = raiz / a.salida
    salida.mkdir(parents=True, exist_ok=True)
    F = cargar_figuras(raiz)
    tr = Transformer.from_crs(F.EPSG_GEO, F.EPSG_PROJ, always_xy=True)
    inv = Transformer.from_crs(F.EPSG_PROJ, F.EPSG_GEO, always_xy=True)
    if a.sin_mapa_base:
        a.mapa_base = "ninguno"
    log = [f"R1_figuras.py · {datetime.now():%Y-%m-%d %H:%M}", f"mapa base: {a.mapa_base}"]

    # --- límite del área de estudio (opcional) ---------------------------------
    limite = None
    if a.limite:
        import geopandas as gpd
        g = gpd.read_file(raiz / a.limite).to_crs(F.EPSG_PROJ)
        limite = g.explode(index_parts=False).reset_index(drop=True)
        log.append(f"límite: {a.limite} ({len(limite)} polígono/s) · etiqueta: {a.etiqueta_limite}")
    else:
        log.append("límite: no se dibujó (falta --limite)")

    if a.mapa_base in ("auto", "teselas"):
        ok, detalle = probar_teselas(a.zoom)
        print(f"prueba de teselas OSM: {detalle}")
        log.append(f"prueba de teselas OSM: {detalle}")
        if not ok:
            if a.mapa_base == "teselas":
                raise SystemExit("OSM rechazó las teselas (" + detalle + "). Usa --mapa-base vector.")
            a.mapa_base = "vector"
            log.append("teselas rechazadas → se usa el modo vector")
            print("Las teselas no están disponibles; se dibujan las calles de OSM en vector.")
        elif a.mapa_base == "auto":
            a.mapa_base = "teselas"
        log.append(f"mapa base usado: {a.mapa_base}")
    ctx = {"mapa_base": a.mapa_base != "ninguno", "dibujar_limite": True, "ejes_mapa": set(), "avisos": []}
    if a.mapa_base == "teselas":
        import contextily as cx
        import contextily.tile as cx_tile
        cx_tile.USER_AGENT = USER_AGENT   # identifica la aplicación (política de uso de OSM)
    calles = parques = None
    if a.mapa_base == "vector":
        calles, parques, msg = osm_vector(raiz, F, tr)
        log.append(msg)

    # --- 1. Etiqueta de la categoría regional ------------------------------------
    preparar_original = F.preparar

    def preparar_R1(csv):
        df, pca = preparar_original(csv)
        df["tipo"] = df["tipo"].replace({"Ecuadorian Cuisine": ETIQUETA_REGIONAL})
        return df, pca
    F.preparar = preparar_R1

    # --- 2. Mapa base, retícula y límite en cada mapa ----------------------------
    encuadrar_original = F.encuadrar_mapa

    def reticula(ax):
        x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
        y_franja = y0 + (y1 - y0) * F.FRANJA
        (lon0, lon1), (lat0, lat1) = inv.transform([x0, x1], [y_franja, y1])
        ancho_pulg = ax.get_window_extent().width / ax.figure.dpi
        paso = 0.005 if ancho_pulg >= 3.0 else 0.010   # paneles estrechos: menos rótulos
        efecto = [pe.withStroke(linewidth=1.6, foreground="white")]
        for lon in np.arange(np.ceil(lon0 / paso) * paso, lon1, paso):
            xs, ys = tr.transform([lon, lon], [lat0, lat1])
            ax.plot(xs, ys, color="#7B8A94", lw=0.25, alpha=0.55, zorder=1.5)
            if xs[1] < x0 + (x1 - x0) * 0.12 or xs[1] > x1 - (x1 - x0) * 0.05:
                continue            # sin rótulo junto a las esquinas (choca con el de latitud)
            ax.text(xs[1], y1 - (y1 - y0) * 0.012, f"{abs(lon):.3f}°W", fontsize=4.6, color="#4D5B63",
                    ha="center", va="top", zorder=25, path_effects=efecto)
        for lat in np.arange(np.ceil(lat0 / paso) * paso, lat1, paso):
            xs, ys = tr.transform([lon0, lon1], [lat, lat])
            if ys[0] <= y_franja:
                continue
            ax.plot(xs, ys, color="#7B8A94", lw=0.25, alpha=0.55, zorder=1.5)
            if ys[0] > y1 - (y1 - y0) * 0.05:
                continue            # sin rótulo pegado al borde superior
            ax.text(x0 + (x1 - x0) * 0.008, ys[0], f"{abs(lat):.3f}°S", fontsize=4.6, color="#4D5B63",
                    ha="left", va="center", zorder=25, path_effects=efecto)

    def dibujar_limite(ax):
        for geom in limite.geometry:
            xs, ys = geom.exterior.xy
            ax.plot(xs, ys, color=COLOR_LIMITE, lw=0.8, ls=ESTILO_LIMITE, zorder=7.5)

    def encuadrar_R1(ax, xmin, xmax, ymin, ymax, margen=0.06):
        lim = encuadrar_original(ax, xmin, xmax, ymin, ymax, margen)
        if a.mapa_base == "vector" and calles is not None:
            for geom in parques.geometry:
                xs, ys = geom.exterior.xy
                ax.fill(xs, ys, color="#E4E9E4", lw=0, zorder=0.4)
            from matplotlib.collections import LineCollection
            for clase, (ancho, color) in ANCHOS_VIAS.items():
                segs = [np.asarray(geom.coords) for geom in calles.loc[calles.clase == clase].geometry]
                if segs:
                    lc = LineCollection(segs, colors=color, linewidths=ancho, capstyle="round", zorder=0.5)
                    lc.set_gid("osm_vias")
                    ax.add_collection(lc, autolim=False)
        if a.mapa_base == "teselas":
            try:
                # CARTO exige ahora una clave de API; se usan las teselas estándar de OSM
                # (sin clave; licencia ODbL, atribución obligatoria) convertidas a gris claro.
                cx.add_basemap(ax, crs=F.EPSG_PROJ, source=cx.providers.OpenStreetMap.Mapnik,
                               zoom=a.zoom, attribution=False, zorder=0)
                tesela = ax.images[-1]
                arr = np.asarray(tesela.get_array(), dtype=float)
                if arr.max() > 1.0:
                    arr = arr / 255.0
                gris = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
                gris = a.aclarado + (1.0 - a.aclarado) * gris
                tesela.set_data(np.dstack([gris, gris, gris]))
                ctx.setdefault("teselas", set()).add(id(tesela))
            except Exception as e:  # sin conexión o servidor caído
                ctx["avisos"].append(f"mapa base no descargado: {e}")
        if ctx["mapa_base"]:
            x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
            ax.text(x1 - (x1 - x0) * 0.01, y0 + (y1 - y0) * F.FRANJA * 1.05, ATRIBUCION, fontsize=3.9,
                    color="#4D5B63", ha="right", va="bottom", zorder=25,
                    path_effects=[pe.withStroke(linewidth=1.4, foreground="white")])
        reticula(ax)
        if limite is not None and ctx["dibujar_limite"]:
            dibujar_limite(ax)
        ctx["ejes_mapa"].add(ax)
        return lim
    F.encuadrar_mapa = encuadrar_R1

    # Figura 1: el límite entra por la ranura de capas de referencia (para que tenga
    # su entrada en la leyenda) y se renombra al guardar.
    def capas_R1():
        return (limite if limite is not None else None), None
    F.cargar_capas_referencia = capas_R1

    # --- 3. Transparencia sobre el mapa base y etiquetas al guardar ----------------
    guardar_original = F.guardar

    def guardar_R1(fig, outdir, nombre):
        if ctx["mapa_base"]:
            for ax in fig.axes:
                if ax not in ctx["ejes_mapa"]:
                    continue
                for im in ax.images:
                    if id(im) not in ctx.get("teselas", set()):
                        im.set_alpha(0.80)
                for col in ax.collections:
                    if isinstance(col, PatchCollection):
                        col.set_alpha(0.80)
        # Figura 1: el límite entra por la ranura de la ZET con su estilo gris; se iguala al
        # trazo negro discontinuo de las Figuras 5, 6 y S8.1 (mapa y leyenda)
        for ax in fig.axes:
            lineas = [ln for ln in ax.get_lines() if ln.get_label().startswith("Special Tourism Zone boundary")]
            leyendas = [art for art in ax.artists + [ax.get_legend()] if isinstance(art, matplotlib.legend.Legend)]
            for leg in leyendas:
                manijas = getattr(leg, "legend_handles", None) or getattr(leg, "legendHandles", [])
                for h, txt in zip(manijas, leg.get_texts()):
                    if txt.get_text().startswith("Special Tourism Zone boundary"):
                        lineas.append(h)
            for ln in lineas:
                ln.set_color(COLOR_LIMITE); ln.set_linewidth(0.8); ln.set_linestyle(ESTILO_LIMITE); ln.set_alpha(1)
        for t in fig.findobj(matplotlib.text.Text):
            s = t.get_text()
            if s.startswith("Special Tourism Zone boundary"):
                t.set_text(a.etiqueta_limite)
            elif s == "Institutional reference layers (not analysed)":
                t.set_text("Reference layers (not analysed)")
            elif "reseñas" in s:            # rótulo en español que quedó en la Figura 5B original
                t.set_text(s.replace("reseñas", "reviews"))
        guardar_original(fig, str(salida), nombre)
        log.append(f"guardada: {nombre}")
    F.guardar = guardar_R1

    # --- 4. Ejecutar las figuras que cambian --------------------------------------
    F.estilo()
    df, pca = F.preparar(str(raiz / "final_figures_CODE" / "restaurantes_quito_CH_clean.csv"))
    V = {}
    ctx["dibujar_limite"] = False          # en la Figura 1 lo dibuja la ranura ZET
    F.figura1(df, str(salida), V)
    ctx["dibujar_limite"] = True
    F.figura4(df, str(salida), V)
    F.figura5(df, str(salida), V)
    F.figura6(df, str(salida), V)
    F.tabla1(df, str(salida), V)

    # --- 5. Figura suplementaria S8.1 · núcleo robusto ------------------------------
    frec = raiz / "R1_v2_borrador" / "resultados" / "sensibilidad" / "C2_frecuencia_hot_por_local.csv"
    if frec.exists():
        fr = pd.read_csv(frec)
        d = df.assign(id_censo=np.arange(1, len(df) + 1)).merge(fr, on="id_censo")
        fig, ax = plt.subplots(figsize=(F.ANCHO_15COL, F.ANCHO_15COL * 1.25))
        orden = d.sort_values("frecuencia_hot")
        sc = ax.scatter(orden.X, orden.Y, c=orden.frecuencia_hot, cmap="YlOrRd", vmin=0, vmax=1,
                        s=14, edgecolor="#17202A", linewidths=0.25, zorder=8)
        nucleo = d[d.frecuencia_hot >= 0.75]
        ax.scatter(nucleo.X, nucleo.Y, s=34, facecolor="none", edgecolor="#17202A", linewidths=0.7,
                   zorder=9)
        pgx, pgy = tr.transform(F.PLAZA[1], F.PLAZA[0])
        ax.plot([pgx], [pgy], marker="*", ms=10, color="#F4D03F", mec="#17202A", mew=0.5, zorder=10)
        F.encuadrar_mapa(ax, d.X.min(), d.X.max(), d.Y.min(), d.Y.max(), margen=0.06)
        F.mobiliario(ax)
        cax = ax.inset_axes([0.30, -0.06, 0.40, 0.022])
        cb = fig.colorbar(sc, cax=cax, orientation="horizontal")
        cb.set_label("Share of the 20 grid configurations in which the establishment lies in an "
                     "FDR-significant Gi* hot cell", fontsize=5.6)
        cb.ax.tick_params(labelsize=5.2)
        h = [Line2D([], [], marker="o", ls="none", ms=6, mfc="none", mec="#17202A",
                    label=f"Robust core (≥ 0.75; n = {len(nucleo)})"),
             Line2D([], [], marker="*", ls="none", ms=8, color="#F4D03F", mec="#17202A",
                    label="Plaza Grande")]
        if limite is not None:
            h.append(Line2D([], [], ls=(0, (4, 2)), lw=0.8, color="#17202A", label=a.etiqueta_limite))
        ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, fontsize=6,
                  frameon=False)
        F.guardar(fig, str(salida), "FiguraS8_1_Nucleo_robusto")
    else:
        log.append("FiguraS8_1 omitida: falta C2_frecuencia_hot_por_local.csv")

    log += ctx["avisos"]
    (salida / "registro_figuras_R1.txt").write_text("\n".join(log), encoding="utf-8")
    print("\n".join(log))
    print(f"\nListo: {salida}")


if __name__ == "__main__":
    main()
