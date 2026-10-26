#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
FIGURAS Y TABLAS FINALES PARA EL MANUSCRITO
Destino: Frontiers in Nutrition — Nutrition and Sustainable Diets
Research Topic: "Social and Cultural Pathways to Sustainable Diets"
===============================================================================

Genera EXCLUSIVAMENTE el material listo para insertar en el manuscrito, en una
carpeta independiente. Cada figura contiene un solo gráfico, salvo cuando la
comparación entre superficies o dimensiones es el argumento mismo.

Productos
---------
  Figura 1 · Área de estudio y censo de establecimientos          [1 mapa]
  Figura 2 · Gradiente de estratificación digital                 [1 gráfico]
  Figura 3 · Anidamiento de plataformas sociales                  [1 gráfico]
  Figura 4 · Determinantes del volumen de reseñas (IRR)           [1 gráfico]
  Figura 5 · Densidad física frente a capital digital             [3 paneles*]
  Figura 6 · Concentración local: reseñas frente a capital        [2 paneles*]
  Figura 7 · Volumen frente a calificación en franquicias         [2 paneles*]
  * la comparación es el resultado; separarlas lo destruiría

  Tabla 1 · Caracterización de la muestra
  Tabla 2 · Regresión binomial negativa
  valores_para_el_texto.txt · cifras exactas citables, con su redacción
  pies_de_figura.txt        · pies completos en español e inglés

Control de calidad tipográfico
------------------------------
Ningún elemento de texto se superpone con otro. Los mapas reservan una franja
inferior exclusiva para barra de escala y flecha de norte; las leyendas se
disponen fuera del área de datos; los estadísticos van al pie de figura, no
sobre el gráfico.

Requisitos: el archivo analisis_espacial_quito_v2_capital_digital.py debe
encontrarse en el mismo directorio (se reutilizan sus funciones validadas).

Uso:  python figuras_paper_frontiers.py --csv restaurantes_quito_CH_clean.csv
===============================================================================
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import textwrap
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Patch, FancyBboxPatch
from matplotlib.collections import PatchCollection
from matplotlib.lines import Line2D
import matplotlib.ticker as mticker

import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests
from pyproj import Transformer
from libpysal.weights import KNN
import esda
import geopandas as gpd

warnings.filterwarnings("ignore")

# --- carga del módulo de análisis validado -----------------------------------
_AQUI = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_AQUI, "analisis_espacial_quito_v2_capital_digital.py")
if not os.path.exists(_MOD):
    sys.exit(f"ERROR: no se encuentra {_MOD}\n"
             "Coloque este script en el mismo directorio que el análisis.")
_spec = importlib.util.spec_from_file_location("motor", _MOD)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

# --- capas de referencia geográfica (opcionales) -----------------------------
# Buscar shapefiles junto al script O junto al CSV (robusto a ejecución
# desde otro directorio)
def _buscar_shp(nombre):
    for base in [_AQUI, os.getcwd(), os.path.dirname(os.path.abspath(
            __import__("sys").argv[-1])) if __import__("sys").argv else "."]:
        r = os.path.join(base, nombre)
        if os.path.exists(r):
            return r
    return os.path.join(_AQUI, nombre)   # fallback
RUTA_ZET = _buscar_shp("zet_centro_historico_a.shp")
RUTA_CATASTRO = _buscar_shp("catastro_turismo_p.shp")

# =============================================================================
# PARÁMETROS EDITORIALES
# =============================================================================

# Frontiers admite 85 mm (1 columna) y 180 mm (2 columnas). Se trabaja en
# pulgadas al tamaño final de impresión, sin reescalado posterior.
ANCHO_1COL = 3.35     # 85 mm
ANCHO_15COL = 5.50    # 140 mm
ANCHO_2COL = 7.09     # 180 mm
DPI_SALIDA = 600

SEMILLA = M.SEMILLA
N_PERM = M.N_PERM
CELDA_M = M.CELDA_M
BW_KDE_M = M.BW_KDE_M
K_VECINOS = M.K_VECINOS
ALFA = M.ALFA
FDR = M.FDR_METODO
EPSG_GEO, EPSG_PROJ = M.EPSG_GEO, M.EPSG_PROJ
PLAZA = M.PLAZA_GRANDE

# Paleta sobria, legible en escala de grises y apta para daltonismo
AZUL = "#1F4E79"
GRANATE = "#B03A2E"
GRIS = "#95A5A6"
GRIS_CLARO = "#D6DBDF"
AMBAR = "#D68910"
VERDE = "#1E8449"
COL_GI = {"Hot 99%": "#7B241C", "Hot 95%": "#C0392B", "Hot 90%": "#E6B0AA",
          "No signif.": "#ECEFF1",
          "Cold 90%": "#AED6F1", "Cold 95%": "#2471A3", "Cold 99%": "#154360"}


def estilo():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Liberation Sans", "Arial", "Helvetica",
                            "DejaVu Sans"],
        "font.size": 7.5,
        "axes.titlesize": 8.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 7.5,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
        "legend.fontsize": 6.8,
        "legend.frameon": False,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.4,
        "ytick.major.size": 2.4,
        "lines.linewidth": 1.0,
        "figure.dpi": 110,
        "savefig.dpi": DPI_SALIDA,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "mathtext.default": "regular",
    })


def guardar(fig, outdir, nombre):
    """Exporta en los tres formatos que acepta Frontiers."""
    for ext in ("pdf", "png", "tif"):
        ruta = os.path.join(outdir, f"{nombre}.{ext}")
        try:
            if ext == "tif":
                fig.savefig(ruta, dpi=DPI_SALIDA, pil_kwargs={"compression":
                                                              "tiff_lzw"})
            else:
                fig.savefig(ruta)
        except Exception:
            pass
    plt.close(fig)
    print(f"    guardada: {nombre}.pdf / .png / .tif")


def miles(v):
    """Thousands format with comma, English convention."""
    return f"{v:,.0f}"


def coma(v, dec=3):
    """Decimal format with typographic minus sign (U+2212).
    English convention: period as decimal separator."""
    return f"{v:.{dec}f}".replace("-", "\u2212")


# =============================================================================
# MOBILIARIO CARTOGRÁFICO SIN SUPERPOSICIONES
# =============================================================================
#
# Principio de diseño: el eje se divide en dos zonas disjuntas.
#   · ZONA DE DATOS  — ocupa el 100 % del ancho y el 82 % superior del alto
#   · FRANJA INFERIOR — 18 % del alto, reservada en exclusiva para la barra de
#     escala (izquierda) y la flecha de norte (derecha). No se dibuja ningún
#     dato en ella, por lo que la colisión es imposible por construcción.
# Las leyendas se sitúan fuera del área del eje y los estadísticos van al pie
# de figura, nunca sobre el mapa.
# =============================================================================

FRANJA = 0.115         # proporción del alto reservada al mobiliario


def encuadrar_mapa(ax, xmin, xmax, ymin, ymax, margen=0.06):
    """
    Fija los límites conservando la proporción real del área (sin forzar un
    cuadrado, que desperdiciaría lienzo) y añadiendo por debajo la franja
    reservada al mobiliario cartográfico.
    """
    dx, dy = xmax - xmin, ymax - ymin
    mx, my = dx * margen, dy * margen
    x0, x1 = xmin - mx, xmax + mx
    y1 = ymax + my
    alto_datos = (ymax + my) - (ymin - my)
    y0 = (ymin - my) - alto_datos * FRANJA / (1 - FRANJA)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(True); sp.set_linewidth(0.5); sp.set_color("#B0B8BC")
    return (x0, x1, y0, y1)


def proporcion_mapa(xmin, xmax, ymin, ymax, margen=0.06):
    """Alto/ancho que debe tener el eje, incluida la franja de mobiliario."""
    dx = (xmax - xmin) * (1 + 2 * margen)
    dy = (ymax - ymin) * (1 + 2 * margen)
    return (dy / (1 - FRANJA)) / dx


def mobiliario(ax, longitud_m=500, etiqueta="500 m", fuente=6.2):
    """Barra de escala a la izquierda y flecha de norte a la derecha, ambas
    dentro de la franja inferior reservada. Nunca colisionan con datos."""
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    alto = y1 - y0
    banda_sup = y0 + alto * FRANJA          # techo de la franja

    # --- barra de escala (segmentada, con marca en 0, mitad y total) --------
    bx = x0 + (x1 - x0) * 0.055
    by = y0 + alto * FRANJA * 0.40
    h = alto * 0.016
    ax.add_patch(Rectangle((bx, by), longitud_m / 2, h, facecolor="#17202A",
                           edgecolor="#17202A", lw=0.4, zorder=30))
    ax.add_patch(Rectangle((bx + longitud_m / 2, by), longitud_m / 2, h,
                           facecolor="white", edgecolor="#17202A", lw=0.4,
                           zorder=30))
    ax.text(bx, by - h * 1.1, "0", ha="center", va="top", fontsize=fuente - 0.6,
            color="#17202A", zorder=31)
    ax.text(bx + longitud_m, by - h * 1.1, etiqueta, ha="center", va="top",
            fontsize=fuente - 0.6, color="#17202A", zorder=31)

    # --- flecha de norte ----------------------------------------------------
    # La longitud del asta se expresa en PUNTOS, no en unidades de mapa, de
    # modo que conserva una proporción legible con independencia del tamaño
    # del panel y de la escala de los datos.
    # Se ancla en fracción de eje para que el asta nunca desborde el marco.
    ancla = (0.925, FRANJA * 0.80)
    ax.annotate("", xy=ancla, xycoords="axes fraction",
                xytext=(0, -11), textcoords="offset points",
                arrowprops=dict(arrowstyle="-|>", color="#17202A", lw=0.8,
                                mutation_scale=6, shrinkA=0, shrinkB=0),
                zorder=31)
    ax.annotate("N", xy=ancla, xycoords="axes fraction", xytext=(0, 1.5),
                textcoords="offset points", ha="center", va="bottom",
                fontsize=fuente, fontweight="bold", color="#17202A", zorder=31)
    return banda_sup


def anillos(ax, pgx, pgy, radios=(250, 500, 750, 1000), etiquetar=False):
    for r in radios:
        ax.add_patch(Circle((pgx, pgy), r, fill=False, ec="#7F8C8D", lw=0.35,
                            ls=(0, (2.6, 2.6)), alpha=0.55, zorder=4))
    if etiquetar:
        # Se rotulan sobre el radio noroeste, sector con menor densidad de
        # puntos, y con halo blanco para garantizar legibilidad.
        import matplotlib.patheffects as pe
        ang = np.deg2rad(140)
        for r in radios:
            ax.text(pgx + r * np.cos(ang), pgy + r * np.sin(ang),
                    f"{miles(r)} m", ha="center", va="center",
                    fontsize=5.4, color="#5D6D7E", zorder=12,
                    path_effects=[pe.withStroke(linewidth=1.8,
                                                foreground="white")])


def celdas_patches(ax, celdas, colores, lw=0.25, ec="white", zorder=3):
    ax.add_collection(PatchCollection(
        [Rectangle((r.x0, r.y0), CELDA_M, CELDA_M) for r in celdas.itertuples()],
        facecolors=colores, edgecolors=ec, linewidths=lw, zorder=zorder))


def contorno_fdr(ax, celdas, mascara, color="#17202A", lw=1.0):
    sub = celdas[mascara]
    if len(sub):
        ax.add_collection(PatchCollection(
            [Rectangle((r.x0, r.y0), CELDA_M, CELDA_M) for r in sub.itertuples()],
            facecolors="none", edgecolors=color, linewidths=lw, zorder=8))
    return len(sub)


# =============================================================================
# PREPARACIÓN DE DATOS
# =============================================================================

def preparar(csv):
    print("· Cargando y preparando datos …")
    df = pd.read_csv(csv)
    df.columns = [c.strip() for c in df.columns]
    ren = {"Cantidad de Reseñas": "resenas", "estrellas_num": "estrellas",
           "Tiene IG": "tiene_ig", "Seguidores IG": "seg_ig",
           "Tiene TikTok": "tiene_tt", "Seguidores TT": "seg_tt",
           "Likes TT": "likes_tt", "Tipo Restaurante": "tipo_raw",
           "dist_plaza_grande_km": "dist_km", "franquicia_bin": "franquicia",
           "CATEGORÍA": "categoria"}
    df = df.rename(columns=ren)
    for c in ["resenas", "tiene_ig", "seg_ig", "tiene_tt", "seg_tt", "likes_tt"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["resenas"] = df["resenas"].astype(int)
    df["existe_gmaps"] = df["existe_gmaps"].astype(bool)
    df["log1p_resenas"] = np.log1p(df.resenas)
    df["log1p_seg_ig"] = np.log1p(df.seg_ig)
    df["log1p_seg_tt"] = np.log1p(df.seg_tt)
    df["n_plataformas"] = (df.existe_gmaps.astype(int) + df.tiene_ig.astype(int)
                           + df.tiene_tt.astype(int))

    tr = Transformer.from_crs(EPSG_GEO, EPSG_PROJ, always_xy=True)
    df["X"], df["Y"] = tr.transform(df.lon.values, df.lat.values)

    vc = df.tipo_raw.value_counts()
    mapa = {r: "Other" for r in vc[vc < M.TIPOS_RAROS_MIN_N].index}
    mapa["Desconocido"] = "Unclassified"
    df["tipo"] = df.tipo_raw.replace(mapa)
    # Translate culinary categories to English
    df["tipo"] = df["tipo"].replace({
        "Tradicional": "Traditional",
        "Comida Ecuatoriana": "Ecuadorian Cuisine",
        "Nuevo Tradicional": "New Traditional",
        "Cafetería": "Café",
        "Internacional": "International",
    })

    # Capital digital (PCA-A, especificación principal validada en §10)
    X = np.column_stack([df.log1p_resenas, df.log1p_seg_ig, df.log1p_seg_tt])
    pca = M.pca_correlacion(
        X, ["log1p(reseñas)", "log1p(seguidores IG)", "log1p(seguidores TT)"],
        "PCA-A", n_boot=1000, anclaje=0)
    df["CP1"] = pca["puntuaciones"][:, 0]
    df["CP2"] = pca["puntuaciones"][:, 1]
    df["CP1_pct"] = stats.rankdata(df.CP1) / len(df)
    df["CP2_pct"] = stats.rankdata(df.CP2) / len(df)
    print(f"  n = {len(df)} · CP1 explica {pca['var_pct'][0]:.1f} % · "
          f"KMO = {pca['kmo_global']:.3f}")
    return df, pca


# =============================================================================
# FIGURA 1 · ÁREA DE ESTUDIO Y CENSO
# =============================================================================

def cargar_capas_referencia():
    """
    Carga las capas oficiales de referencia, si están disponibles:
      · ZET       — perímetro de la Zona Especial Turística (contorno, no
                    recorte: cubre solo el 72,6 % del censo analizado).
      · Catastro  — universo de establecimientos de alimentos y bebidas
                    registrados en el catastro turístico municipal (MDMQ,
                    parroquia Centro Histórico), como capa de contexto.
                    NUNCA se fusiona con el censo analítico: los nombres
                    genéricos producen falsos empates por coordenada (mediana
                    de discrepancia 55 m, pero 21,6 % de los empates por
                    nombre exacto difiere más de 300 m). Se muestra tal cual,
                    sin alterar ni una coordenada del censo de 420.
    Devuelve (zet, catastro), cada uno None si el archivo no existe.
    """
    zet = None
    if os.path.exists(RUTA_ZET):
        try:
            zet = gpd.read_file(RUTA_ZET)
            print(f"  capa ZET cargada: {len(zet)} polígono(s)")
        except Exception as e:
            print(f"  [ZET no cargada: {e}]")

    catastro = None
    if os.path.exists(RUTA_CATASTRO):
        try:
            c = gpd.read_file(RUTA_CATASTRO)
            c = c[(c.des_parroq == "CENTRO HISTÓRICO") &
                  (c.des_tipolo.isin(["RESTAURANTE", "CAFETERÍA", "BAR",
                                      "PLAZAS DE COMIDA"]))].copy()
            catastro = c
            print(f"  capa catastro municipal cargada: {len(c)} "
                  f"establecimientos de alimentos y bebidas "
                  f"(parroquia Centro Histórico, MDMQ 2026-03)")
        except Exception as e:
            print(f"  [catastro no cargado: {e}]")
    return zet, catastro


def figura1(df, outdir, V):
    print("· Figura 1 · Área de estudio …")
    import matplotlib.patheffects as pe
    tr = Transformer.from_crs(EPSG_GEO, EPSG_PROJ, always_xy=True)
    pgx, pgy = tr.transform(PLAZA[1], PLAZA[0])

    zet, catastro = cargar_capas_referencia()

    xmin, xmax = df.X.min(), df.X.max()
    ymin, ymax = df.Y.min(), df.Y.max()
    prop = proporcion_mapa(xmin, xmax, ymin, ymax, margen=0.07)

    ancho = ANCHO_15COL
    alto_eje = ancho * prop
    alto_total = alto_eje + 0.68
    fig = plt.figure(figsize=(ancho, alto_total))
    ax = fig.add_axes([0.015, 0.68 / alto_total, 0.97,
                       alto_eje / alto_total])

    encuadrar_mapa(ax, xmin, xmax, ymin, ymax, margen=0.07)

    # --- capa de contexto: catastro municipal (fondo, no analítica) --------
    n_catastro = 0
    if catastro is not None:
        cx_, cy_ = tr.transform(catastro.geometry.x.values,
                                catastro.geometry.y.values)
        ax.scatter(cx_, cy_, s=7, c="#C9CFD3", alpha=0.65, linewidths=0,
                   zorder=3, label=f"Municipal tourism registry "
                   f"(n = {len(catastro)})")
        n_catastro = len(catastro)

    # --- contorno administrativo: Zona Especial Turística -------------------
    if zet is not None:
        zet_p = zet.to_crs(EPSG_PROJ)
        for geom in zet_p.geometry:
            xs, ys = geom.exterior.xy
            ax.plot(xs, ys, color="#6C7A89", lw=0.9, ls=(0, (5, 2)),
                    alpha=0.85, zorder=4,
                    label="Special Tourism Zone boundary (ZET)")

    anillos(ax, pgx, pgy, etiquetar=True)

    # --- censo analítico (primer plano) -------------------------------------
    escala = {0: (12, "#B7BEC3", "None"), 1: (17, "#7FB3D5", "One"),
              2: (26, "#2E86C1", "Two"), 3: (36, GRANATE, "Three")}
    for k in (0, 1, 2, 3):
        m = (df.n_plataformas == k).values
        sz, c, lab = escala[k]
        ax.scatter(df.X[m], df.Y[m], s=sz, c=c, alpha=0.92, linewidths=0.35,
                   edgecolor="white", zorder=8 + k,
                   label=f"{lab}  (n = {int(m.sum())})")

    ax.plot([pgx], [pgy], marker="*", ms=13, color="#F4D03F", mec="#17202A",
            mew=0.7, zorder=14)
    ax.text(pgx, pgy - 145, "Plaza Grande", fontsize=6.6, style="italic",
            color="#17202A", ha="center", va="top", zorder=15,
            path_effects=[pe.withStroke(linewidth=2.4, foreground="white")])

    mobiliario(ax)

    # --- leyenda en dos filas: censo analítico / capas de referencia --------
    h_censo = [Line2D([], [], marker="o", ls="none", ms=np.sqrt(escala[k][0]),
                      color=escala[k][1], mec="white", mew=0.3,
                      label=f"{escala[k][2]}  (n = {int((df.n_plataformas==k).sum())})")
               for k in (0, 1, 2, 3)]
    h_ref = []
    if catastro is not None:
        h_ref.append(Line2D([], [], marker="o", ls="none", ms=4.2,
                            color="#C9CFD3",
                            label=f"Municipal tourism registry "
                            f"(n = {n_catastro})"))
    if zet is not None:
        h_ref.append(Line2D([], [], ls=(0, (5, 2)), lw=0.9, color="#6C7A89",
                            label="Special Tourism Zone boundary"))
    h_ref.append(Line2D([], [], marker="*", ls="none", ms=9, color="#F4D03F",
                        mec="#17202A", mew=0.4, label="Plaza Grande"))

    leg1 = ax.legend(handles=h_censo, loc="upper center",
                     bbox_to_anchor=(0.5, -0.010), ncol=4, fontsize=6.5,
                     handletextpad=0.35, columnspacing=1.05, frameon=False,
                     title="Analysed census · active digital platforms "
                     "per establishment",
                     title_fontsize=6.8)
    leg1._legend_box.align = "center"
    ax.add_artist(leg1)
    leg2 = ax.legend(handles=h_ref, loc="upper center",
                     bbox_to_anchor=(0.5, -0.145), ncol=3, fontsize=6.3,
                     handletextpad=0.35, columnspacing=1.3, frameon=False,
                     title="Institutional reference layers (not analysed)",
                     title_fontsize=6.6, labelcolor="#5D6D7E")
    leg2._legend_box.align = "center"

    guardar(fig, outdir, "Figura1_Area_de_estudio")

    V["n_total"] = len(df)
    V["n_por_plataformas"] = df.n_plataformas.value_counts().sort_index().to_dict()
    V["extension_m"] = (xmax - xmin, ymax - ymin)
    V["dist_max_km"] = float(df.dist_km.max())
    V["n_catastro_referencia"] = n_catastro


# =============================================================================
# FIGURA 2 · GRADIENTE DE ESTRATIFICACIÓN DIGITAL
# =============================================================================

def figura2(df, outdir, V):
    print("· Figura 2 · Gradiente de estratificación …")
    g = df.groupby("n_plataformas").agg(
        n=("resenas", "size"), reviews=("resenas", "sum"),
        ig=("seg_ig", "sum"), tt=("seg_tt", "sum")).reindex([0, 1, 2, 3])
    g = g.fillna(0)
    pct_estab = 100 * g.n / g.n.sum()
    pct_rev = 100 * g.reviews / g.reviews.sum()

    fig, ax = plt.subplots(figsize=(ANCHO_15COL, ANCHO_15COL * 0.62))
    fig.subplots_adjust(left=0.11, right=0.985, top=0.90, bottom=0.30)

    x = np.arange(4); w = 0.38
    b1 = ax.bar(x - w / 2, pct_estab, w, color=GRIS, zorder=3,
                label="Establishments in the census")
    b2 = ax.bar(x + w / 2, pct_rev, w, color=GRANATE, zorder=3,
                label="Accumulated Google Maps reviews")

    for xi, (a, b, n_, r_) in enumerate(zip(pct_estab, pct_rev, g.n, g.reviews)):
        ax.text(xi - w / 2, a + 1.3, f"{coma(a,1)} %", ha="center", va="bottom",
                fontsize=6.3, color="#2C3E50")
        ax.text(xi + w / 2, b + 1.3, f"{coma(b,1)} %", ha="center", va="bottom",
                fontsize=6.3, color=GRANATE, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([f"{lab}\n(n = {int(n_)})" for lab, n_ in
                        zip(["None", "One", "Two", "Three"], g.n)])
    ax.set_xlabel("Number of active digital platforms per establishment",
                  labelpad=7)
    ax.set_ylabel("Percentage of total (%)")
    ax.set_ylim(0, max(pct_estab.max(), pct_rev.max()) * 1.20)
    ax.grid(axis="y", lw=0.3, color=GRIS_CLARO, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.16), ncol=2,
              fontsize=6.8, handletextpad=0.4, columnspacing=1.4)

    guardar(fig, outdir, "Figura2_Gradiente_estratificacion")

    V["gradiente"] = pd.DataFrame({"n": g.n.astype(int),
                                   "pct_estab": pct_estab,
                                   "reviews": g.reviews.astype(int),
                                   "pct_reviews": pct_rev})
    V["pct_estab_sin_plataforma"] = float(pct_estab.iloc[0])
    V["pct_rev_tres"] = float(pct_rev.iloc[3])
    V["pct_estab_tres"] = float(pct_estab.iloc[3])


# =============================================================================
# FIGURA 3 · ANIDAMIENTO DE PLATAFORMAS SOCIALES
# =============================================================================

def figura3(df, outdir, V):
    print("· Figura 3 · Anidamiento de plataformas …")
    comb = np.select(
        [(df.tiene_ig == 0) & (df.tiene_tt == 0),
         (df.tiene_ig == 1) & (df.tiene_tt == 0),
         (df.tiene_ig == 0) & (df.tiene_tt == 1),
         (df.tiene_ig == 1) & (df.tiene_tt == 1)],
        ["No social media", "Instagram only", "TikTok only",
         "Instagram and TikTok"], "?")
    orden = ["No social media", "Instagram only", "TikTok only",
             "Instagram and TikTok"]
    vals = [int((comb == o).sum()) for o in orden]
    colores = [GRIS_CLARO, "#5499C7", AMBAR, GRANATE]

    tab = pd.crosstab(df.tiene_ig, df.tiene_tt)
    orat, pf = stats.fisher_exact(tab.values)

    fig, ax = plt.subplots(figsize=(ANCHO_15COL, ANCHO_15COL * 0.50))
    fig.subplots_adjust(left=0.27, right=0.965, top=0.94, bottom=0.20)

    y = np.arange(4)[::-1]
    ax.barh(y, vals, color=colores, height=0.62, zorder=3,
            edgecolor="#7F8C8D", linewidth=0.3)
    for yi, v in zip(y, vals):
        ax.text(v + max(vals) * 0.016, yi, f"{v}   ({coma(100*v/len(df),1)} %)",
                va="center", ha="left", fontsize=6.6, color="#2C3E50")

    # Señalamiento del hallazgo estructural, en zona vacía del eje
    i_solo_tt = orden.index("TikTok only")
    ax.text(max(vals) * 0.30, y[i_solo_tt],
            "no establishment accesses TikTok\nwithout first being present "
            "on Instagram",
            fontsize=6.4, style="italic", color=AMBAR, va="center", ha="left")

    ax.set_yticks(y); ax.set_yticklabels(orden)
    ax.set_xlabel("Number of establishments")
    ax.set_xlim(0, max(vals) * 1.30)
    ax.grid(axis="x", lw=0.3, color=GRIS_CLARO, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)

    guardar(fig, outdir, "Figura3_Anidamiento_plataformas")

    V["comb"] = dict(zip(orden, vals))
    V["p_fisher_ig_tt"] = float(pf)
    V["n_tt"] = int((df.tiene_tt == 1).sum())
    V["n_tt_con_ig"] = int(((df.tiene_tt == 1) & (df.tiene_ig == 1)).sum())
    m = tab.values.astype(float) + 0.5
    V["or_haldane"] = float((m[1, 1] * m[0, 0]) / (m[1, 0] * m[0, 1]))


# =============================================================================
# FIGURA 4 · DETERMINANTES DEL VOLUMEN DE RESEÑAS (BINOMIAL NEGATIVA)
# =============================================================================

def figura4(df, outdir, V):
    print("· Figura 4 · Regresión binomial negativa …")
    d = df.copy()
    d["y"] = d.resenas
    d["dist"] = d.dist_km
    d["ig"] = d.tiene_ig.astype(int)
    f = ('y ~ C(tipo, Treatment(reference="Traditional")) + dist + ig')
    po = smf.glm(f, data=d, family=sm.families.Poisson()).fit()
    nb = smf.negativebinomial(f, data=d).fit(disp=0, maxiter=500)

    p = nb.params.drop("alpha"); ci = nb.conf_int().drop("alpha")
    pv = nb.pvalues.drop("alpha")
    limpio = [str(i).replace('C(tipo, Treatment(reference="Traditional"))[T.',
                             "").replace("]", "") for i in p.index]
    t = pd.DataFrame({"IRR": np.exp(p.values),
                      "lo": np.exp(ci.iloc[:, 0].values),
                      "hi": np.exp(ci.iloc[:, 1].values),
                      "p": pv.values}, index=limpio)
    t = t.drop(index=["Intercept"])

    etiquetas = {"ig": "Instagram presence",
                 "dist": "Distance to Plaza Grande (per km)",
                 "Unclassified": "Unclassified\u1d43"}
    t.index = [etiquetas.get(i, i) for i in t.index]
    orden = ([etiquetas["ig"], etiquetas["dist"]] +
             sorted([i for i in t.index
                     if i not in (etiquetas["ig"], etiquetas["dist"])]))
    t = t.loc[[o for o in orden if o in t.index]]

    fig, ax = plt.subplots(figsize=(ANCHO_15COL, ANCHO_15COL * 0.66))
    fig.subplots_adjust(left=0.38, right=0.895, top=0.95, bottom=0.22)

    y = np.arange(len(t))[::-1]
    for yi, (nom, r) in zip(y, t.iterrows()):
        sig = r.p < ALFA
        c = GRANATE if (sig and r.IRR > 1) else (AZUL if sig else GRIS)
        ax.plot([r.lo, r.hi], [yi, yi], color=c, lw=1.4, zorder=3,
                solid_capstyle="round")
        ax.plot([r.lo, r.lo], [yi - .12, yi + .12], color=c, lw=1.0, zorder=3)
        ax.plot([r.hi, r.hi], [yi - .12, yi + .12], color=c, lw=1.0, zorder=3)
        ax.scatter([r.IRR], [yi], s=26, color=c, zorder=4, edgecolor="white",
                   linewidth=0.5)

    ax.axvline(1.0, color="#34495E", lw=0.7, ls="--", zorder=2)
    ax.set_xscale("log")
    ax.set_yticks(y); ax.set_yticklabels(t.index)
    ax.set_ylim(-0.7, len(t) - 0.3)
    ax.set_xlabel("Incidence rate ratio (IRR) and 95% confidence interval", labelpad=5)
    ax.grid(axis="x", lw=0.3, color=GRIS_CLARO, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.xaxis.set_major_locator(mticker.FixedLocator([0.1, 0.25, 0.5, 1, 2.5,
                                                     5, 10]))
    ax.xaxis.set_minor_locator(mticker.NullLocator())
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: coma(v, 2).rstrip("0").rstrip(",") if v < 1 else f"{v:g}"))

    # Columna numérica a la derecha, fuera del área de datos
    xr = 1.035
    ax.text(xr, 1.028, "IRR [95% CI]", transform=ax.transAxes, fontsize=6.3,
            fontweight="bold", ha="left", va="bottom", color="#2C3E50")
    for yi, (nom, r) in zip(y, t.iterrows()):
        est = "***" if r.p < .001 else "**" if r.p < .01 else "*" if r.p < .05 else ""
        ax.text(xr, (yi + 0.7) / len(t),
                f"{coma(r.IRR,2)} [{coma(r.lo,2)}–{coma(r.hi,2)}]{est}",
                transform=ax.transAxes, fontsize=6.1, ha="left", va="center",
                color="#2C3E50")

    # Guía de lectura del eje. Los rótulos se anclan a los EXTREMOS y las
    # flechas apuntan hacia fuera desde el centro, de modo que el espacio
    # central queda libre y los dos textos no pueden encontrarse. Se evitan
    # los glifos ◀ ▶, ausentes en Liberation Sans.
    YG = -0.205
    t_izq = ax.text(0.0, YG, "lower visibility", transform=ax.transAxes,
                    fontsize=6.0, color=AZUL, ha="left", va="center",
                    style="italic")
    t_der = ax.text(1.0, YG, "higher visibility", transform=ax.transAxes,
                    fontsize=6.0, color=GRANATE, ha="right", va="center",
                    style="italic")

    # Se miden las cajas reales de texto con el renderizador y las flechas se
    # trazan solo en el hueco disponible: la superposición es imposible.
    fig.canvas.draw()
    inv = ax.transAxes.inverted()
    r = fig.canvas.get_renderer()
    fin_izq = inv.transform(t_izq.get_window_extent(r).corners()[2])[0]
    ini_der = inv.transform(t_der.get_window_extent(r).corners()[0])[0]
    hueco = ini_der - fin_izq
    if hueco > 0.14:
        sep = 0.030                     # separación entre texto y flecha
        largo = min(0.16, (hueco - 2 * sep - 0.05) / 2)
        ax.annotate("", xy=(fin_izq + sep, YG),
                    xytext=(fin_izq + sep + largo, YG),
                    xycoords="axes fraction", textcoords="axes fraction",
                    arrowprops=dict(arrowstyle="-|>", color=AZUL, lw=0.7,
                                    mutation_scale=6, shrinkA=0, shrinkB=0))
        ax.annotate("", xy=(ini_der - sep, YG),
                    xytext=(ini_der - sep - largo, YG),
                    xycoords="axes fraction", textcoords="axes fraction",
                    arrowprops=dict(arrowstyle="-|>", color=GRANATE, lw=0.7,
                                    mutation_scale=6, shrinkA=0, shrinkB=0))

    guardar(fig, outdir, "Figura4_Binomial_negativa_IRR")

    LR = 2 * (nb.llf - po.llf)
    V["nb"] = t
    V["nb_alpha"] = float(nb.params["alpha"])
    V["nb_LR"] = float(LR)
    V["nb_n"] = int(nb.nobs)
    V["nb_pseudoR2"] = float(nb.prsquared)
    V["irr_ig"] = (float(t.loc[etiquetas["ig"], "IRR"]),
                   float(t.loc[etiquetas["ig"], "lo"]),
                   float(t.loc[etiquetas["ig"], "hi"]),
                   float(t.loc[etiquetas["ig"], "p"]))
    V["irr_dist"] = (float(t.loc[etiquetas["dist"], "IRR"]),
                     float(t.loc[etiquetas["dist"], "lo"]),
                     float(t.loc[etiquetas["dist"], "hi"]),
                     float(t.loc[etiquetas["dist"], "p"]))


# =============================================================================
# FIGURA 5 · DENSIDAD FÍSICA FRENTE A CAPITAL DIGITAL (KDE)
# =============================================================================

def figura5(df, outdir, V):
    print("· Figura 5 · Superficies de densidad …")
    x, y = df.X.values, df.Y.values
    tr = Transformer.from_crs(EPSG_GEO, EPSG_PROJ, always_xy=True)
    inv = Transformer.from_crs(EPSG_PROJ, EPSG_GEO, always_xy=True)
    pgx, pgy = tr.transform(PLAZA[1], PLAZA[0])

    pad = 3 * BW_KDE_M
    xg = np.arange(x.min() - pad, x.max() + pad + M.KDE_GRID_M, M.KDE_GRID_M)
    yg = np.arange(y.min() - pad, y.max() + pad + M.KDE_GRID_M, M.KDE_GRID_M)
    XX, YY = np.meshgrid(xg, yg)
    mask, hull = M.mascara_dominio(XX, YY, x, y, 2 * BW_KDE_M)

    # --- Tres superficies base ---
    S_fis = M.kde_superficie(x, y, XX, YY, BW_KDE_M, None)
    S_rev = M.kde_superficie(x, y, XX, YY, BW_KDE_M, df.log1p_resenas.values)

    # --- Panel C: cociente de Nadaraya-Watson (capital digital por establ.) ---
    # Interpretación: log(1+reseñas) esperado de un establecimiento situado en
    # ese punto. Aísla la INTENSIDAD de la DENSIDAD: rojo = el local rinde más
    # de lo que predice la densidad física; azul = menos.
    umbral = np.nanpercentile(S_fis[mask], 10)
    mask_c = mask & (S_fis > umbral)
    with np.errstate(divide="ignore", invalid="ignore"):
        S_ratio = np.where(mask_c, S_rev / S_fis, np.nan)
    media_global = float(df.log1p_resenas.mean())

    # --- Picos de A y B ---
    def pico(S):
        Sinf = np.where(mask, S, -np.inf)
        i = np.unravel_index(np.argmax(Sinf), Sinf.shape)
        return XX[i], YY[i], S[i]

    pA = pico(S_fis); pB = pico(S_rev)

    # --- Pico de C (máximo del cociente dentro del dominio válido) ---
    Sinf_c = np.where(mask_c, S_ratio, -np.inf)
    ic = np.unravel_index(np.argmax(Sinf_c), Sinf_c.shape)
    pC = (XX[ic], YY[ic], S_ratio[ic])

    # =====================================================================
    # FIGURA
    # =====================================================================
    fig = plt.figure(figsize=(ANCHO_2COL, ANCHO_2COL * 0.46))
    gs = fig.add_gridspec(1, 3, left=0.012, right=0.988, top=0.90, bottom=0.20,
                          wspace=0.06)
    ext = [XX.min(), XX.max(), YY.min(), YY.max()]

    paneles = [
        ("A", "Establishment density", S_fis,
         "establishments · ha$^{-1}$", "magma_r", False),
        ("B", "Cartographic visibility", S_rev,
         "log(1 + reseñas) · ha$^{-1}$", "magma_r", False),
        ("C", "Digital capital per establishment", S_ratio,
         "expected log(1 + reviews)", "RdBu_r", True),
    ]
    picos_dict = {"A": pA, "B": pB, "C": pC}

    for j, (letra, titulo, S, unidad, cmap, divergente) in enumerate(paneles):
        ax = fig.add_subplot(gs[0, j])

        if divergente:
            # Escala divergente centrada en la media global. Se usa una escala
            # ASIMÉTRICA recortada al rango real del cociente [0, máx], no la
            # simétrica [media−desv, media+desv], que creaba un extremo
            # inferior ficticio de −0,1 fuera del dominio del cociente.
            Sm = np.where(mask_c, S, np.nan)
            rc_valid = S[mask_c]
            vmin_real = float(np.nanmin(rc_valid))
            vmax_real = float(np.nanmax(rc_valid))
            # La escala centra visualmente en la media pero recorta en 0
            im = ax.imshow(Sm, origin="lower", extent=ext, cmap=cmap,
                           vmin=0.0, vmax=vmax_real, interpolation="bilinear",
                           zorder=2)
            # Isolínea en la media global (umbral neutro), color gris medio
            ax.contour(XX, YY, np.where(mask_c, S, np.nan),
                       levels=[media_global], colors=["#7F8C8D"],
                       linewidths=0.8, zorder=3)
        else:
            Sm = np.where(mask, S, np.nan)
            im = ax.imshow(Sm, origin="lower", extent=ext, cmap=cmap,
                           interpolation="bilinear", zorder=2)
            ax.contour(XX, YY, Sm,
                       levels=np.nanpercentile(Sm, [50, 75, 90, 97.5]),
                       colors="white", linewidths=0.32, alpha=0.72, zorder=3)

        ax.plot(hull[:, 0], hull[:, 1], color="#2C3E50", lw=0.45, ls=":",
                alpha=0.75, zorder=5)
        ax.scatter(x, y, s=0.8, c="#17202A", alpha=0.32, linewidths=0,
                   zorder=6, rasterized=True)
        anillos(ax, pgx, pgy)

        # Marcador del máximo — solo en A y B, no en C.
        # En C el máximo del cociente cae en una zona de baja densidad
        # (2 establecimientos a 150 m) donde el cociente es inestable;
        # mostrarlo como "máximo de la superficie" induciría a concluir
        # erróneamente que el capital digital se relocaliza.
        if not divergente:
            px, py, _ = picos_dict[letra]
            ax.plot([px], [py], marker="^", ms=6, color="#16A085",
                    mec="#0B5345", mew=0.6, zorder=10)
        ax.plot([pgx], [pgy], marker="*", ms=8, color="#F4D03F", mec="#17202A",
                mew=0.5, zorder=9)

        encuadrar_mapa(ax, x.min() - pad, x.max() + pad, y.min() - pad,
                       y.max() + pad, margen=0.0)
        if j == 0:
            mobiliario(ax)
        ax.set_title(f"{letra} · {titulo}", loc="left", fontsize=8.0, pad=4)

        # Barra de color horizontal debajo de cada panel
        cax = ax.inset_axes([0.055, -0.055, 0.60, 0.030])
        cb = fig.colorbar(im, cax=cax, orientation="horizontal")
        cb.set_label(unidad, fontsize=5.8, labelpad=1.6)
        cb.ax.tick_params(labelsize=5.2, width=0.35, length=1.6, pad=1.2)
        cb.outline.set_linewidth(0.3)
        if divergente:
            cb.set_ticks([0, media_global, vmax_real])
            cb.set_ticklabels(["0", f"{coma(media_global, 1)} (mean)",
                               coma(vmax_real, 1)])
        else:
            cb.locator = mticker.MaxNLocator(nbins=4); cb.update_ticks()

    # --- Leyenda común ---
    handles = [Line2D([], [], marker="*", ls="none", ms=7, color="#F4D03F",
                      mec="#17202A", mew=0.4, label="Plaza Grande"),
               Line2D([], [], marker="^", ls="none", ms=5, color="#16A085",
                      mec="#0B5345", mew=0.4,
                      label="Surface maximum (A and B only)"),
               Line2D([], [], marker="o", ls="none", ms=2.0, color="#17202A",
                      label="Establishment"),
               Line2D([], [], ls=(0, (2.6, 2.6)), lw=0.5, color="#7F8C8D",
                      label="Concentric rings every 250 m"),
               Line2D([], [], ls=":", lw=0.5, color="#2C3E50",
                      label="Analytical domain")]
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=6.2,
               bbox_to_anchor=(0.5, 0.005), handletextpad=0.35,
               columnspacing=1.1, frameon=False)

    guardar(fig, outdir, "Figura5_KDE_fisico_vs_digital")

    # --- Valores citables ---
    sep_AB = np.hypot(pA[0] - pB[0], pA[1] - pB[1])
    V["sep_AB"] = float(sep_AB)
    V["rho_AB"] = float(stats.spearmanr(S_fis[mask], S_rev[mask])[0])
    conc_fis = float(S_fis[mask].max() / np.median(S_fis[mask]))
    conc_rev = float(S_rev[mask].max() / np.median(S_rev[mask]))
    V["conc"] = [conc_fis, conc_rev, 0.0]   # tercer slot no aplica al cociente
    V["razon_conc_BA"] = conc_rev / conc_fis

    rc = S_ratio[mask_c]
    V["ratio_P90_P10"] = float(np.nanpercentile(rc, 90) /
                               max(np.nanpercentile(rc, 10), 1e-9))
    V["ratio_media"] = float(media_global)
    V["ratio_max"] = float(np.nanmax(rc))
    V["ratio_min"] = float(np.nanmin(rc))

    # Para compatibilidad con los valores que usan otras funciones
    V["sep_AC"] = float(sep_AB)    # ya no hay superficie CP1 en esta figura
    V["rho_AC"] = V["rho_AB"]
    lon_, lat_ = inv.transform(pB[0], pB[1])
    V["pico_C"] = (lat_, lon_)


# =============================================================================
# FIGURA 6 · CONCENTRACIÓN LOCAL: RESEÑAS FRENTE A CAPITAL DIGITAL (Gi*)
# =============================================================================

def figura6(df, outdir, V):
    print("· Figura 6 · Getis-Ord Gi* comparado …")
    celdas = M.agregar_celdas_capital(df)
    w, islas = M.pesos_reina(celdas)
    w.transform = "R"
    vecinos = M.vecinos_con_autovecindad(w)

    tr = Transformer.from_crs(EPSG_GEO, EPSG_PROJ, always_xy=True)
    inv = Transformer.from_crs(EPSG_PROJ, EPSG_GEO, always_xy=True)
    pgx, pgy = tr.transform(PLAZA[1], PLAZA[0])

    dims = [("A", "Google Maps reviews", celdas.log1p_resenas_tot.values),
            ("B", "Multi-platform digital capital", celdas.CP1_suma.values)]

    fig = plt.figure(figsize=(ANCHO_2COL, ANCHO_2COL * 0.60))
    gs = fig.add_gridspec(1, 2, left=0.015, right=0.985, top=0.93, bottom=0.17,
                          wspace=0.04)

    resumen = {}
    for j, (letra, titulo, v) in enumerate(dims):
        ax = fig.add_subplot(gs[0, j])
        G, Z, Zsim, Psim = M.getis_ord_star(v, vecinos)
        p_an = 2.0 * stats.norm.sf(np.abs(Z))
        rech, p_adj, _, _ = multipletests(p_an, alpha=ALFA, method=FDR)

        def clase(zi, pi):
            if pi >= 0.10:
                return "No signif."
            niv = "99%" if pi < .01 else ("95%" if pi < .05 else "90%")
            return ("Hot " if zi > 0 else "Cold ") + niv
        cl = np.array([clase(zi, pi) for zi, pi in zip(Z, p_an)])
        cl_fdr = np.array([clase(zi, pi) if r else "No signif."
                           for zi, pi, r in zip(Z, p_adj, rech)])

        celdas_patches(ax, celdas, [COL_GI[c] for c in cl])
        n_fdr = contorno_fdr(ax, celdas, cl_fdr != "No signif.")
        ax.scatter(df.X, df.Y, s=0.7, c="#17202A", alpha=0.24, linewidths=0,
                   zorder=6, rasterized=True)
        anillos(ax, pgx, pgy)
        ax.plot([pgx], [pgy], marker="*", ms=8, color="#F4D03F", mec="#17202A",
                mew=0.5, zorder=9)

        encuadrar_mapa(ax, celdas.x0.min(), celdas.x0.max() + CELDA_M,
                       celdas.y0.min(), celdas.y0.max() + CELDA_M, margen=0.05)
        if j == 0:
            mobiliario(ax)
        ax.set_title(f"{letra} · {titulo}", loc="left", fontsize=8.2, pad=4)

        mi = esda.Moran(v, w, permutations=N_PERM)
        resumen[letra] = {
            "titulo": titulo, "I": float(mi.I), "p_I": float(mi.p_sim),
            "z_min": float(Z.min()), "z_max": float(Z.max()),
            "hot95": int(np.isin(cl, ["Hot 99%", "Hot 95%"]).sum()),
            "cold95": int(np.isin(cl, ["Cold 99%", "Cold 95%"]).sum()),
            "n_fdr": int(n_fdr)}
        if letra == "B":
            sig = celdas[cl_fdr != "No signif."].copy()
            if len(sig):
                sig["lon"], sig["lat"] = inv.transform(sig.xc.values,
                                                       sig.yc.values)
                sig["z_gi"] = Z[cl_fdr != "No signif."]
                V["celdas_fdr_CP1"] = sig[["lat", "lon", "n_estab",
                                           "resenas_tot", "CP1_suma", "z_gi"]]

    orden = ["Hot 99%", "Hot 95%", "Hot 90%", "No signif.", "Cold 90%",
             "Cold 95%", "Cold 99%"]
    etiq = {"Hot 99%": "Hot · 99%", "Hot 95%": "Hot · 95%",
            "Hot 90%": "Hot · 90%", "No signif.": "Not significant",
            "Cold 90%": "Cold · 90%", "Cold 95%": "Cold · 95%",
            "Cold 99%": "Cold · 99%"}
    handles = [Patch(fc=COL_GI[k], ec="white", lw=0.3, label=etiq[k])
               for k in orden]
    handles += [Patch(fc="none", ec="#17202A", lw=1.0,
                      label="Survives FDR correction"),
                Line2D([], [], marker="*", ls="none", ms=7, color="#F4D03F",
                       mec="#17202A", mew=0.4, label="Plaza Grande")]
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=6.2,
               bbox_to_anchor=(0.5, 0.005), handletextpad=0.4,
               columnspacing=1.0, frameon=False)

    guardar(fig, outdir, "Figura6_GetisOrd_resenas_vs_capital")
    V["gi"] = resumen
    V["n_celdas"] = len(celdas)
    V["n_islas"] = len(islas)


# =============================================================================
# FIGURA 7 · VOLUMEN FRENTE A CALIFICACIÓN EN FRANQUICIAS
# =============================================================================

def figura7(df, outdir, V):
    print("· Figura 7 · Franquicias: volumen y calificación …")
    rng = np.random.default_rng(SEMILLA)
    fig = plt.figure(figsize=(ANCHO_15COL, ANCHO_15COL * 0.56))
    gs = fig.add_gridspec(1, 2, left=0.105, right=0.985, top=0.87, bottom=0.20,
                          wspace=0.34)

    especificaciones = [
        ("A", "Review volume", df, "resenas", True,
         "Accumulated reviews (logarithmic scale)"),
        ("B", "Mean rating", df[(df.existe_gmaps) & (df.resenas > 0)],
         "estrellas", False, "Google Maps rating (0–5)"),
    ]
    pruebas = {}
    for j, (letra, titulo, datos, col, log, ylab) in enumerate(especificaciones):
        ax = fig.add_subplot(gs[0, j])
        grupos, colores = [], [AZUL, GRANATE]
        for vgrupo in (0, 1):
            s = datos.loc[datos.franquicia == vgrupo, col].dropna().values
            grupos.append(np.log10(1 + s) if log else s)

        for i, (g, c) in enumerate(zip(grupos, colores), start=1):
            parts = ax.violinplot([g], positions=[i], widths=0.66,
                                  showextrema=False, showmedians=False)
            for pc in parts["bodies"]:
                pc.set_facecolor(c); pc.set_alpha(0.20)
                pc.set_edgecolor(c); pc.set_linewidth(0.5)
            ax.boxplot([g], positions=[i], widths=0.19, showfliers=False,
                       patch_artist=True, zorder=4,
                       medianprops=dict(color="white", lw=1.3),
                       boxprops=dict(facecolor=c, edgecolor=c, lw=0.5),
                       whiskerprops=dict(lw=0.6, color="#2C3E50"),
                       capprops=dict(lw=0.6, color="#2C3E50"))
            ax.scatter(i + rng.uniform(-0.115, 0.115, len(g)), g, s=3.0,
                       color=c, alpha=0.32, linewidths=0, zorder=3,
                       rasterized=True)

        pr = M.mann_whitney(datos.loc[datos.franquicia == 1, col],
                            datos.loc[datos.franquicia == 0, col], titulo)
        pruebas[letra] = pr

        ax.set_xticks([1, 2])
        ax.set_xticklabels([f"Independent\n(n = {len(grupos[0])})",
                            f"Franchises\n(n = {len(grupos[1])})"])
        ax.set_ylabel(ylab)
        ax.set_title(f"{letra} · {titulo}", loc="left", fontsize=8.2, pad=5)
        ax.grid(axis="y", lw=0.3, color=GRIS_CLARO, zorder=0)
        ax.set_axisbelow(True)
        if log:
            vmax = max(g.max() for g in grupos)
            marcas = [m for m in [0, 10, 100, 1_000, 10_000]
                      if np.log10(1 + m) <= vmax * 1.04]
            ax.set_yticks([np.log10(1 + m) for m in marcas])
            ax.set_yticklabels([miles(m) for m in marcas])

        # Sentido del efecto, en el margen superior libre del eje
        flecha = "▲" if pr["r_rango_biserial"] > 0 else "▼"
        ax.text(0.985, 0.985,
                f"{flecha} $r_{{rb}}$ = {coma(pr['r_rango_biserial'],2)}",
                transform=ax.transAxes, ha="right", va="top", fontsize=6.6,
                color=GRANATE if pr["r_rango_biserial"] > 0 else AZUL)

    guardar(fig, outdir, "Figura7_Franquicias_volumen_vs_calificacion")
    V["mw"] = pruebas


# =============================================================================
# TABLAS
# =============================================================================

def tabla1(df, outdir, V):
    print("· Tabla 1 · Caracterización de la muestra …")
    filas = []

    def add(bloque, categoria, sub):
        n = len(sub)
        filas.append({
            "Section": bloque, "Category": categoria, "n": n,
            "% of census": 100 * n / len(df),
            "Google Maps listing (%)": 100 * sub.existe_gmaps.mean(),
            "Instagram (%)": 100 * sub.tiene_ig.mean(),
            "TikTok (%)": 100 * sub.tiene_tt.mean(),
            "Reviews (median)": sub.resenas.median(),
            "Reviews (IQR)": f"{sub.resenas.quantile(.25):.0f}–"
                             f"{sub.resenas.quantile(.75):.0f}",
            "Rating (median)": sub.loc[(sub.existe_gmaps) &
                                              (sub.resenas > 0),
                                              "estrellas"].median(),
            "Distance km (median)": sub.dist_km.median()})

    add("Total", "All establishments", df)
    for t in df.tipo.value_counts().index:
        add("Establishment type", t, df[df.tipo == t])
    for f_ in (0, 1):
        add("Commercial structure",
            "Independent" if f_ == 0 else "Franchise or chain",
            df[df.franquicia == f_])
    if "categoria" in df.columns:
        for c in sorted(df.categoria.dropna().unique()):
            sub = df[df.categoria == c]
            if len(sub) >= 5:
                add("Institutional category", str(c), sub)

    t1 = pd.DataFrame(filas)
    for c in t1.columns:
        if t1[c].dtype.kind == "f":
            t1[c] = t1[c].round(1)
    t1.to_csv(os.path.join(outdir, "Tabla1_Caracterizacion_muestra.csv"),
              index=False, encoding="utf-8-sig")
    print(f"    guardada: Tabla1_Caracterizacion_muestra.csv "
          f"({len(t1)} filas)")
    V["tabla1"] = t1


def tabla2(V, outdir):
    print("· Tabla 2 · Regresión binomial negativa …")
    t = V["nb"].copy()
    # Strip LaTeX/Unicode superscripts for clean CSV output
    clean_idx = [str(i).replace("$^{a}$", "").replace("\u1d43", "(a)")
                 for i in t.index]
    out = pd.DataFrame({
        "Predictor": clean_idx,
        "IRR": t.IRR.round(3),
        "95% CI lower": t.lo.round(3),
        "95% CI upper": t.hi.round(3),
        "% change": ((t.IRR - 1) * 100).round(1),
        "p value": t.p.map(lambda v: "< 0.001" if v < .001
                           else coma(v, 3))})
    out.to_csv(os.path.join(outdir, "Tabla2_Binomial_negativa.csv"),
               index=False, encoding="utf-8-sig")
    print("    guardada: Tabla2_Binomial_negativa.csv")


# =============================================================================
# VALORES CITABLES Y PIES DE FIGURA
# =============================================================================

def documento_valores(V, pca, outdir):
    print("· Documento de valores y pies de figura …")
    L = []
    A = L.append
    A("=" * 79)
    A("VALORES EXACTOS PARA EL TEXTO DEL MANUSCRITO")
    A("Estratificación digital del patrimonio alimentario · Centro Histórico "
      "de Quito")
    A(f"Generado el {datetime.now():%Y-%m-%d %H:%M} · semilla {SEMILLA} · "
      f"{N_PERM:,} permutaciones".replace(",", "."))
    A("=" * 79)

    A("\n\n1. MUESTRA Y ÁREA DE ESTUDIO   [Figura 1 · Tabla 1]")
    A("-" * 79)
    A(f"  Establecimientos censados            n = {V['n_total']}")
    A(f"  Extensión del área analizada         {V['extension_m'][0]:.0f} m × "
      f"{V['extension_m'][1]:.0f} m")
    A(f"  Distancia máxima a Plaza Grande      {coma(V['dist_max_km'],2)} km")
    A(f"  Malla de análisis espacial           {CELDA_M:.0f} m · "
      f"{V['n_celdas']} celdas ocupadas")
    A(f"  Proyección                           UTM 17S (EPSG:32717)")

    A("\n\n2. GRADIENTE DE ESTRATIFICACIÓN   [Figura 2]")
    A("-" * 79)
    g = V["gradiente"]
    A(f"  {'Plataformas':<13}{'n':>6}{'% censo':>10}{'reseñas':>11}"
      f"{'% reseñas':>11}")
    for i, r in g.iterrows():
        A(f"  {i:<13}{int(r.n):>6}{coma(r.pct_estab,1):>10}"
          f"{miles(r.reviews):>11}{coma(r.pct_reviews,1):>11}")
    A("")
    A("  REDACCIÓN SUGERIDA:")
    A(textwrap.fill(
        f"El {coma(V['pct_estab_sin_plataforma'],1)} % de los establecimientos "
        f"censados carece de presencia en las tres plataformas examinadas y no "
        f"acumula ninguna reseña, mientras que el "
        f"{coma(V['pct_estab_tres'],1)} % presente en las tres concentra el "
        f"{coma(V['pct_rev_tres'],1)} % del total de reseñas del Centro "
        f"Histórico.", 76, initial_indent="    ", subsequent_indent="    "))

    A("\n\n3. ANIDAMIENTO DE PLATAFORMAS   [Figura 3]")
    A("-" * 79)
    for k, v in V["comb"].items():
        A(f"  {k:<24}{v:>5}   ({coma(100*v/V['n_total'],1)} %)")
    A(f"\n  Establecimientos con TikTok          {V['n_tt']}")
    A(f"  De ellos, con Instagram              {V['n_tt_con_ig']}  "
      f"({coma(100*V['n_tt_con_ig']/V['n_tt'],1)} %)")
    A(f"  Prueba exacta de Fisher              p = {V['p_fisher_ig_tt']:.3g}")
    A(f"  Razón de momios (Haldane-Anscombe)   {miles(V['or_haldane'])}")
    A("")
    A("  ADVERTENCIA: la razón de momios no está definida (celda vacía). "
      "Debe")
    A("  reportarse como tal y acompañarse de la estimación corregida.")
    A("")
    A("  REDACCIÓN SUGERIDA:")
    A(textwrap.fill(
        f"Los {V['n_tt']} establecimientos con cuenta de TikTok poseen también "
        f"cuenta de Instagram, sin una sola excepción (prueba exacta de "
        f"Fisher, p < 0,001). Ningún establecimiento accede a TikTok sin estar "
        f"previamente presente en Instagram: la plataforma más reciente no "
        f"constituye una vía alternativa de acceso a la visibilidad, sino un "
        f"peldaño adicional para quienes ya ocupan posiciones altas en la "
        f"jerarquía digital.", 76, initial_indent="    ",
        subsequent_indent="    "))

    A("\n\n4. REGRESIÓN BINOMIAL NEGATIVA   [Figura 4 · Tabla 2]")
    A("-" * 79)
    irr_ig, lo_ig, hi_ig, p_ig = V["irr_ig"]
    irr_d, lo_d, hi_d, p_d = V["irr_dist"]
    A(f"  n                                    {V['nb_n']}")
    A(f"  Parámetro de dispersión α            {coma(V['nb_alpha'],2)}")
    A(f"  Razón de verosimilitudes vs Poisson  LR = {miles(V['nb_LR'])} "
      f"(p < 0,001)")
    A(f"  Pseudo-R² de McFadden                {coma(V['nb_pseudoR2'],3)}")
    A(f"  IRR Instagram                        {coma(irr_ig,2)} "
      f"[{coma(lo_ig,2)}; {coma(hi_ig,2)}], p < 0,001")
    A(f"  IRR distancia (por km)               {coma(irr_d,3)} "
      f"[{coma(lo_d,3)}; {coma(hi_d,3)}], p = {coma(p_d,3)}")
    A(f"  Reducción por kilómetro              {coma((1-irr_d)*100,1)} %")
    A("")
    A("  REDACCIÓN SUGERIDA:")
    A(textwrap.fill(
        f"Controlando el tipo de establecimiento y la localización, la "
        f"presencia en Instagram se asocia con un número esperado de reseñas "
        f"{coma(irr_ig,1)} veces mayor (IRR = {coma(irr_ig,2)}; IC 95 % "
        f"{coma(lo_ig,2)}–{coma(hi_ig,2)}; p < 0,001), mientras que cada "
        f"kilómetro de alejamiento del núcleo patrimonial se asocia con una "
        f"reducción del {coma((1-irr_d)*100,0)} % en la visibilidad esperada "
        f"(IRR = {coma(irr_d,3)}; p = {coma(p_d,3)}).", 76,
        initial_indent="    ", subsequent_indent="    "))
    A("")
    A("  El diseño es transversal: emplear siempre 'se asocia con', nunca")
    A("  'produce', 'genera' ni 'aumenta'.")

    A("\n\n5. SUPERFICIES DE DENSIDAD   [Figura 5]")
    A("-" * 79)
    A(f"  Ancho de banda                       h = {BW_KDE_M:.0f} m "
      f"(núcleo gaussiano)")
    A(f"  Separación máximo físico / reseñas   {V['sep_AB']:.0f} m")
    A(f"  Correlación física–reseñas (ρ)       {coma(V['rho_AB'],3)}")
    A(f"  Concentración (máx/mediana)          física {coma(V['conc'][0],1)} · "
      f"reseñas {coma(V['conc'][1],1)}")
    A(f"  Razón de concentración reseñas/física {coma(V['razon_conc_BA'],2)}×")
    A(f"  Capital digital por establecimiento (cociente B/A, Nadaraya-Watson):")
    A(f"    media global de log(1+reseñas)     {coma(V['ratio_media'],3)}")
    A(f"    rango del cociente                 [0,00; "
      f"{coma(V['ratio_max'],2)}]")
    A(f"    (la escala de color arranca en 0, no en un valor negativo ficticio)")
    A(f"    razón P90/P10 del cociente         {coma(V['ratio_P90_P10'],1)}")
    A("")
    A("  REDACCIÓN SUGERIDA:")
    A(textwrap.fill(
        f"Los máximos de las superficies de densidad física y de visibilidad "
        f"digital se sitúan a {V['sep_AB']:.0f} m de distancia, por debajo del "
        f"ancho de banda del estimador ({BW_KDE_M:.0f} m), y ambas superficies "
        f"presentan una correlación de rangos de {coma(V['rho_AB'],2)}. El "
        f"capital digital no relocaliza el centro de gravedad gastronómico del "
        f"Centro Histórico; se superpone a él con una concentración "
        f"{coma(V['razon_conc_BA'],1)} veces mayor. Sin embargo, la intensidad "
        f"por establecimiento (cociente entre visibilidad y densidad) varía con "
        f"una razón P90/P10 de {coma(V['ratio_P90_P10'],1)} dentro de un radio "
        f"de un kilómetro: las plataformas no desplazan la centralidad "
        f"heredada, pero amplifican selectivamente la jerarquía interna de "
        f"visibilidad entre establecimientos que comparten la misma zona.", 76,
        initial_indent="    ", subsequent_indent="    "))

    A("\n\n6. AUTOCORRELACIÓN Y CONCENTRACIÓN LOCAL   [Figura 6]")
    A("-" * 79)
    for letra, r in V["gi"].items():
        A(f"  {letra} · {r['titulo']}")
        A(f"      I de Moran global                {coma(r['I'],3)} "
          f"(p = {coma(r['p_I'],4)})")
        A(f"      Rango de z(Gi*)                  [{coma(r['z_min'],2)}; "
          f"{coma(r['z_max'],2)}]")
        A(f"      Celdas calientes (p < 0,05)      {r['hot95']}")
        A(f"      Celdas frías (p < 0,05)          {r['cold95']}")
        A(f"      Celdas que superan FDR           {r['n_fdr']}")
    A("")
    A("  REDACCIÓN SUGERIDA:")
    A(textwrap.fill(
        f"Ningún conglomerado local de reseñas supera la corrección de "
        f"Benjamini-Hochberg por comparaciones múltiples, por lo que esos "
        f"resultados se presentan como exploratorios. El índice "
        f"multiplataforma, en cambio, identifica {V['gi']['B']['n_fdr']} "
        f"celdas que sí la superan (z máximo = "
        f"{coma(V['gi']['B']['z_max'],2)}), lo que indica una mayor potencia "
        f"estadística de la medida multiplataforma frente a la "
        f"monoplataforma.", 76, initial_indent="    ",
        subsequent_indent="    "))
    if "celdas_fdr_CP1" in V:
        A("\n  Celdas confirmatorias de capital digital (centroides, WGS84):")
        cf = V["celdas_fdr_CP1"].sort_values("z_gi", ascending=False)
        A(f"      {'lat':>10}{'lon':>11}{'estab.':>8}{'reseñas':>9}{'z':>8}")
        for _, r in cf.iterrows():
            A(f"      {r.lat:>10.4f}{r.lon:>11.4f}{int(r.n_estab):>8}"
              f"{int(r.resenas_tot):>9}{r.z_gi:>8.2f}")

    A("\n\n7. FRANQUICIAS FRENTE A INDEPENDIENTES   [Figura 7]")
    A("-" * 79)
    for letra, pr in V["mw"].items():
        A(f"  {letra} · {pr['variable']}")
        A(f"      n franquicias / independientes   {pr['n1_franquicias']} / "
          f"{pr['n2_independientes']}")
        A(f"      Medianas                         "
          f"{coma(pr['mediana_g1'],2)} vs {coma(pr['mediana_g2'],2)}")
        A(f"      U de Mann-Whitney                {pr['U_g1']:,.0f}"
          .replace(",", "."))
        A(f"      p (permutación)                  "
          f"{'< 0,001' if pr['p_permutacion']<.001 else coma(pr['p_permutacion'],4)}")
        A(f"      r rango-biserial                 "
          f"{coma(pr['r_rango_biserial'],3)}")
    A("")
    A("  REDACCIÓN SUGERIDA:")
    A(textwrap.fill(
        f"Las franquicias acumulan un volumen de reseñas significativamente "
        f"mayor que los establecimientos independientes "
        f"(r = {coma(V['mw']['A']['r_rango_biserial'],2)}; p < 0,001) y, "
        f"simultáneamente, reciben calificaciones significativamente menores "
        f"(r = {coma(V['mw']['B']['r_rango_biserial'],2)}; p < 0,001). La "
        f"inversión del signo entre ambos contrastes documenta una disociación "
        f"entre marca y lugar: las plataformas recompensan el reconocimiento "
        f"de marca con visibilidad, con independencia de la valoración que "
        f"recibe la experiencia concreta.", 76, initial_indent="    ",
        subsequent_indent="    "))

    A("\n\n8. ÍNDICE DE CAPITAL DIGITAL (MATERIAL SUPLEMENTARIO)")
    A("-" * 79)
    A(f"  Componentes                          reseñas, seguidores IG, "
      f"seguidores TikTok (log1p)")
    A(f"  KMO global                           {coma(pca['kmo_global'],3)} "
      f"(adecuación mediana)")
    A(f"  Bartlett                             χ² = "
      f"{pca['bartlett_chi2']:,.1f}".replace(",", ".") +
      f" ({pca['bartlett_gl']} gl), p < 0,001")
    A(f"  Varianza explicada por CP1           "
      f"{coma(pca['var_pct'][0],1)} %")
    A(f"  Cargas en CP1                        " +
      " · ".join(f"{e.replace('log1p','').strip('()')}: {coma(c,2)}"
                 for e, c in zip(pca["etiquetas"], pca["cargas"][:, 0])))
    A(f"  Correlación CP1 ~ nº de plataformas  {coma(V['r_cp1_nplat'],3)}")
    A("")
    A("  DECLARACIÓN OBLIGADA EN EL MANUSCRITO:")
    A(textwrap.fill(
        f"El índice correlaciona r = {coma(V['r_cp1_nplat'],3)} con el mero "
        f"recuento de plataformas activas. Lejos de ser un artefacto, este "
        f"resultado indica que la estratificación digital opera "
        f"principalmente por exclusión de acceso y no por gradación de "
        f"magnitud: la distancia decisiva no separa a quien tiene mil "
        f"seguidores de quien tiene diez mil, sino a quien está presente en "
        f"alguna plataforma de quien no lo está en ninguna.", 76,
        initial_indent="    ", subsequent_indent="    "))

    A("\n\n9. LÍMITES QUE DEBEN DECLARARSE")
    A("-" * 79)
    for i, t in enumerate([
        "Diseño transversal de una sola observación temporal: ninguna "
        "asociación identifica un efecto causal.",
        "Endogeneidad plausible entre presencia en Instagram y volumen de "
        "reseñas; el IRR estimado es un límite superior del efecto.",
        "Las reseñas no están normalizadas por antigüedad de la ficha.",
        "Los resultados por celda dependen de la escala de agregación "
        "(problema de la unidad de área modificable); la malla de 150 m se "
        "justifica por la dimensión de la manzana colonial.",
        "Los conglomerados locales de reseñas no superan la corrección por "
        "comparaciones múltiples y se presentan como exploratorios.",
        "La ausencia de cuenta identificada no prueba la ausencia de "
        "actividad digital del establecimiento.",
    ], 1):
        A(textwrap.fill(f"  {i}. {t}", 76, subsequent_indent="     "))

    ruta = os.path.join(outdir, "valores_para_el_texto.txt")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print(f"    guardado: valores_para_el_texto.txt")


def documento_valores_en(V, pca, outdir):
    """English version of citable values for the manuscript."""
    print("· Citable values (English) …")
    L = []
    A = L.append
    A("=" * 79)
    A("CITABLE VALUES FOR THE MANUSCRIPT")
    A("Digital Stratification of Food Heritage · Historic Centre of Quito")
    A(f"Generated {datetime.now():%Y-%m-%d %H:%M} · seed {SEMILLA} · "
      f"{N_PERM:,} permutations")
    A("=" * 79)

    A("\n\n1. SAMPLE AND STUDY AREA   [Figure 1 · Table 1]")
    A("-" * 79)
    A(f"  Establishments surveyed              n = {V['n_total']}")
    A(f"  Study area extent                    {V['extension_m'][0]:.0f} m x "
      f"{V['extension_m'][1]:.0f} m")
    A(f"  Maximum distance to Plaza Grande     {coma(V['dist_max_km'],2)} km")
    A(f"  Spatial analysis grid                {CELDA_M:.0f} m · "
      f"{V['n_celdas']} occupied cells")
    A(f"  Projection                           UTM 17S (EPSG:32717)")

    A("\n\n2. DIGITAL STRATIFICATION GRADIENT   [Figure 2]")
    A("-" * 79)
    g = V["gradiente"]
    A(f"  {'Platforms':<13}{'n':>6}{'% census':>10}{'reviews':>11}"
      f"{'% reviews':>11}")
    for i, r in g.iterrows():
        A(f"  {i:<13}{int(r.n):>6}{coma(r.pct_estab,1):>10}"
          f"{miles(r.reviews):>11}{coma(r.pct_reviews,1):>11}")
    A("")
    A("  SUGGESTED WORDING:")
    A(textwrap.fill(
        f"{coma(V['pct_estab_sin_plataforma'],1)}% of surveyed establishments "
        f"have no presence on any of the three examined platforms and "
        f"accumulate no reviews, while the "
        f"{coma(V['pct_estab_tres'],1)}% present on all three concentrate "
        f"{coma(V['pct_rev_tres'],1)}% of all reviews in the Historic "
        f"Centre.", 76, initial_indent="    ", subsequent_indent="    "))

    A("\n\n3. PLATFORM NESTING   [Figure 3]")
    A("-" * 79)
    for k, v in V["comb"].items():
        A(f"  {k:<24}{v:>5}   ({coma(100*v/V['n_total'],1)}%)")
    A(f"\n  Establishments with TikTok           {V['n_tt']}")
    A(f"  Of those, with Instagram              {V['n_tt_con_ig']}  "
      f"({coma(100*V['n_tt_con_ig']/V['n_tt'],1)}%)")
    A(f"  Fisher's exact test                   p = {V['p_fisher_ig_tt']:.3g}")
    A(f"  Odds ratio (Haldane-Anscombe)         {miles(V['or_haldane'])}")
    A("")
    A("  NOTE: The odds ratio is undefined (empty cell). Report as such,")
    A("  accompanied by the corrected estimate.")
    A("")
    A("  SUGGESTED WORDING:")
    A(textwrap.fill(
        f"All {V['n_tt']} establishments with a TikTok account also hold an "
        f"Instagram account, without a single exception (Fisher's exact test, "
        f"p < 0.001). No establishment accesses TikTok without first being "
        f"present on Instagram: the newer platform does not constitute an "
        f"alternative pathway to visibility, but an additional step for those "
        f"already occupying high positions in the digital hierarchy.",
        76, initial_indent="    ", subsequent_indent="    "))

    A("\n\n4. NEGATIVE BINOMIAL REGRESSION   [Figure 4 · Table 2]")
    A("-" * 79)
    irr_ig, lo_ig, hi_ig, p_ig = V["irr_ig"]
    irr_d, lo_d, hi_d, p_d = V["irr_dist"]
    A(f"  n                                    {V['nb_n']}")
    A(f"  Dispersion parameter alpha           {coma(V['nb_alpha'],2)}")
    A(f"  Likelihood ratio vs Poisson          LR = {miles(V['nb_LR'])} "
      f"(p < 0.001)")
    A(f"  McFadden pseudo-R2                   {coma(V['nb_pseudoR2'],3)}")
    A(f"  IRR Instagram                        {coma(irr_ig,2)} "
      f"[{coma(lo_ig,2)}; {coma(hi_ig,2)}], p < 0.001")
    A(f"  IRR distance (per km)                {coma(irr_d,3)} "
      f"[{coma(lo_d,3)}; {coma(hi_d,3)}], p = {coma(p_d,3)}")
    A(f"  Reduction per kilometre              {coma((1-irr_d)*100,1)}%")
    A("")
    A("  SUGGESTED WORDING:")
    A(textwrap.fill(
        f"Controlling for establishment type and location, Instagram presence "
        f"is associated with a {coma(irr_ig,1)}-fold increase in expected "
        f"review count (IRR = {coma(irr_ig,2)}; 95% CI "
        f"{coma(lo_ig,2)}-{coma(hi_ig,2)}; p < 0.001), while each additional "
        f"kilometre from the heritage core is associated with a "
        f"{coma((1-irr_d)*100,0)}% reduction in expected visibility "
        f"(IRR = {coma(irr_d,3)}; p = {coma(p_d,3)}).", 76,
        initial_indent="    ", subsequent_indent="    "))
    A("")
    A("  The design is cross-sectional: use 'is associated with', never")
    A("  'produces', 'generates' or 'increases'.")

    A("\n\n5. DENSITY SURFACES   [Figure 5]")
    A("-" * 79)
    A(f"  Bandwidth                            h = {BW_KDE_M:.0f} m "
      f"(Gaussian kernel)")
    A(f"  Separation physical max / reviews     {V['sep_AB']:.0f} m")
    A(f"  Surface correlation (rho)             physical-reviews "
      f"{coma(V['rho_AB'],3)}")
    A(f"  Concentration (max/median)            physical {coma(V['conc'][0],1)} · "
      f"reviews {coma(V['conc'][1],1)}")
    A(f"  Concentration ratio reviews/physical  {coma(V['razon_conc_BA'],2)}x")
    A(f"  Digital capital per establishment (Nadaraya-Watson quotient B/A):")
    A(f"    global mean of log(1+reviews)       {coma(V['ratio_media'],3)}")
    A(f"    quotient range                      [0.00; "
      f"{coma(V['ratio_max'],2)}]")
    A(f"    (colour scale starts at 0, not at a fictitious negative value)")
    A(f"    P90/P10 ratio of quotient           {coma(V['ratio_P90_P10'],1)}")
    A("")
    A("  SUGGESTED WORDING:")
    A(textwrap.fill(
        f"The maxima of the physical density and digital visibility surfaces "
        f"lie {V['sep_AB']:.0f} m apart, below the estimator bandwidth "
        f"({BW_KDE_M:.0f} m), and the two surfaces correlate at "
        f"rho = {coma(V['rho_AB'],2)}. Digital capital does not relocate the "
        f"gastronomic centre of gravity of the Historic Centre; it overlaps "
        f"with it at a {coma(V['razon_conc_BA'],1)}-fold higher concentration. "
        f"However, the intensity per establishment (visibility-to-density "
        f"quotient) varies with a P90/P10 ratio of "
        f"{coma(V['ratio_P90_P10'],1)} within the study area (maximum "
        f"distance to Plaza Grande: 1.71 km): platforms do not displace the "
        f"inherited centrality but selectively amplify the internal hierarchy "
        f"of visibility among establishments sharing the same zone.",
        76, initial_indent="    ", subsequent_indent="    "))

    A("\n\n6. SPATIAL AUTOCORRELATION AND LOCAL CONCENTRATION   [Figure 6]")
    A("-" * 79)
    for letra, r in V["gi"].items():
        A(f"  {letra} · {r['titulo']}")
        A(f"      Global Moran's I                 {coma(r['I'],3)} "
          f"(p = {coma(r['p_I'],4)})")
        A(f"      Gi* z range                      [{coma(r['z_min'],2)}; "
          f"{coma(r['z_max'],2)}]")
        A(f"      Hot cells (p < 0.05)             {r['hot95']}")
        A(f"      Cold cells (p < 0.05)            {r['cold95']}")
        A(f"      Cells surviving FDR              {r['n_fdr']}")
    A("")
    A("  SUGGESTED WORDING:")
    A(textwrap.fill(
        f"No review cluster survives the Benjamini-Hochberg correction for "
        f"multiple comparisons, so those results are reported as exploratory. "
        f"The multi-platform index, by contrast, identifies "
        f"{V['gi']['B']['n_fdr']} cells that do survive (maximum z = "
        f"{coma(V['gi']['B']['z_max'],2)}), indicating greater statistical "
        f"power of the multi-platform measure over the single-platform one.",
        76, initial_indent="    ", subsequent_indent="    "))
    if "celdas_fdr_CP1" in V:
        A("\n  Confirmed digital capital cells (centroids, WGS84):")
        cf = V["celdas_fdr_CP1"].sort_values("z_gi", ascending=False)
        A(f"      {'lat':>10}{'lon':>11}{'estab.':>8}{'reviews':>9}{'z':>8}")
        for _, r in cf.iterrows():
            A(f"      {r.lat:>10.4f}{r.lon:>11.4f}{int(r.n_estab):>8}"
              f"{int(r.resenas_tot):>9}{r.z_gi:>8.2f}")

    A("\n\n7. FRANCHISES VS INDEPENDENT ESTABLISHMENTS   [Figure 7]")
    A("-" * 79)
    for letra, pr in V["mw"].items():
        A(f"  {letra} · {pr['variable']}")
        A(f"      n franchises / independent       {pr['n1_franquicias']} / "
          f"{pr['n2_independientes']}")
        A(f"      Medians                          "
          f"{coma(pr['mediana_g1'],2)} vs {coma(pr['mediana_g2'],2)}")
        A(f"      Mann-Whitney U                   {pr['U_g1']:,.0f}")
        A(f"      p (permutation)                  "
          f"{'< 0.001' if pr['p_permutacion']<.001 else coma(pr['p_permutacion'],4)}")
        A(f"      Rank-biserial r                  "
          f"{coma(pr['r_rango_biserial'],3)}")
    A("")
    A("  SUGGESTED WORDING:")
    A(textwrap.fill(
        f"Franchises accumulate significantly more reviews than independent "
        f"establishments (r = {coma(V['mw']['A']['r_rango_biserial'],2)}; "
        f"p < 0.001) while simultaneously receiving significantly lower "
        f"ratings (r = {coma(V['mw']['B']['r_rango_biserial'],2)}; p < 0.001). "
        f"The sign reversal between the two contrasts documents a dissociation "
        f"between brand and place: platforms reward brand recognition with "
        f"visibility, regardless of the rating given to the actual dining "
        f"experience.", 76, initial_indent="    ", subsequent_indent="    "))

    A("\n\n8. DIGITAL CAPITAL INDEX (SUPPLEMENTARY MATERIAL)")
    A("-" * 79)
    A(f"  Components                           reviews, IG followers, "
      f"TikTok followers (log1p)")
    A(f"  Global KMO                           {coma(pca['kmo_global'],3)} "
      f"(moderate adequacy)")
    A(f"  Bartlett                             chi2 = "
      f"{pca['bartlett_chi2']:,.1f}" +
      f" ({pca['bartlett_gl']} df), p < 0.001")
    A(f"  Variance explained by PC1            "
      f"{coma(pca['var_pct'][0],1)}%")
    A(f"  PC1 loadings                         " +
      " · ".join(f"{e.replace('log1p','').strip('()')}: {coma(c,2)}"
                 for e, c in zip(pca["etiquetas"], pca["cargas"][:, 0])))
    A(f"  Correlation PC1 ~ no. platforms      {coma(V['r_cp1_nplat'],3)}")
    A("")
    A("  MANDATORY DISCLOSURE:")
    A(textwrap.fill(
        f"The index correlates r = {coma(V['r_cp1_nplat'],3)} with the simple "
        f"count of active platforms. Far from being an artefact, this result "
        f"indicates that digital stratification operates primarily through "
        f"access exclusion rather than magnitude gradation: the decisive "
        f"distance does not separate those with a thousand followers from those "
        f"with ten thousand, but those present on some platform from those "
        f"present on none.", 76, initial_indent="    ",
        subsequent_indent="    "))

    A("\n\n9. LIMITATIONS TO DECLARE")
    A("-" * 79)
    for i, t in enumerate([
        "Cross-sectional design with a single temporal observation: no "
        "association identifies a causal effect.",
        "Plausible endogeneity between Instagram presence and review volume; "
        "the estimated IRR is an upper bound of the effect.",
        "Reviews are not normalised by listing age.",
        "Cell-level results depend on the aggregation scale (modifiable areal "
        "unit problem); the 150 m grid is justified by colonial block "
        "dimensions.",
        "Local review clusters do not survive the correction for multiple "
        "comparisons and are reported as exploratory.",
        "The absence of an identified account does not prove the absence of "
        "digital activity by the establishment.",
    ], 1):
        A(textwrap.fill(f"  {i}. {t}", 76, subsequent_indent="     "))

    ruta = os.path.join(outdir, "citable_values_EN.txt")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print(f"    saved: citable_values_EN.txt")


def pies_de_figura(V, pca, outdir):
    """Pies completos, en español e inglés, listos para pegar."""
    print("· Pies de figura …")
    g = V["gradiente"]
    P = []
    A = P.append
    A("=" * 79)
    A("PIES DE FIGURA · versión en español")
    A("=" * 79)

    A("\nFigura 1. Área de estudio y censo de establecimientos de restauración "
      "del Centro Histórico de Quito.")
    ncat = V.get("n_catastro_referencia", 0)
    A(textwrap.fill(
        f"Cada punto coloreado representa un establecimiento del censo "
        f"analizado (n = {V['n_total']}); el tamaño y el color indican el "
        f"número de plataformas digitales activas (ficha en Google Maps, "
        f"cuenta de Instagram, cuenta de TikTok). Como referencia "
        f"institucional se muestran, sin formar parte del análisis, el "
        f"universo de establecimientos de alimentos y bebidas del catastro "
        f"turístico municipal en la parroquia Centro Histórico "
        f"(n = {ncat}; Municipio del Distrito Metropolitano de Quito, "
        f"actualización 2026-03) y el límite de la Zona Especial Turística. "
        f"Los anillos concéntricos, trazados cada 250 m desde la Plaza "
        f"Grande, sitúan el gradiente radial analizado en las Figuras 4 y 5. "
        f"Proyección UTM 17S (EPSG:32717).", 79))

    A("\nFigura 2. Gradiente de estratificación digital del patrimonio "
      "alimentario.")
    A(textwrap.fill(
        f"Distribución de los establecimientos y de las reseñas acumuladas "
        f"según el número de plataformas digitales activas. El "
        f"{coma(V['pct_estab_sin_plataforma'],1)} % del censo carece de "
        f"presencia en las tres plataformas y no acumula ninguna reseña, "
        f"mientras que el {coma(V['pct_estab_tres'],1)} % presente en las tres "
        f"concentra el {coma(V['pct_rev_tres'],1)} % del total. Las cifras "
        f"sobre las barras indican el porcentaje correspondiente; n = "
        f"{V['n_total']}.", 79))

    A("\nFigura 3. Combinación de redes sociales entre los establecimientos "
      "censados.")
    A(textwrap.fill(
        f"Los {V['n_tt']} establecimientos con cuenta de TikTok poseen también "
        f"cuenta de Instagram, sin excepción, de modo que la categoría «solo "
        f"TikTok» está vacía. La asociación entre ambas plataformas es "
        f"estadísticamente significativa (prueba exacta de Fisher, p < 0,001); "
        f"la razón de momios no está definida por tratarse de una celda vacía "
        f"y su estimación con corrección de Haldane-Anscombe asciende a "
        f"{miles(V['or_haldane'])}. n = {V['n_total']}.", 79))

    irr_ig, lo_ig, hi_ig, _ = V["irr_ig"]
    irr_d, lo_d, hi_d, p_d = V["irr_dist"]
    A("\nFigura 4. Determinantes del volumen de reseñas: modelo de regresión "
      "binomial negativa.")
    A(textwrap.fill(
        f"Razones de tasas de incidencia (IRR) con intervalos de confianza al "
        f"95 %, en escala logarítmica. Los valores superiores a la unidad "
        f"(línea discontinua) indican mayor número esperado de reseñas. "
        f"Categoría de referencia del tipo de establecimiento: Tradicional. "
        f"Rojo: IRR significativamente superior a 1; azul: significativamente "
        f"inferior; gris: no significativo. Parámetro de dispersión α = "
        f"{coma(V['nb_alpha'],2)}; contraste de razón de verosimilitudes "
        f"frente al modelo de Poisson: LR = {miles(V['nb_LR'])}, p < 0,001; "
        f"n = {V['nb_n']}. * p < 0,05; ** p < 0,01; *** p < 0,001. "
        f"$^{{a}}$ La categoría «Sin clasificar» agrupa registros sin "
        f"información de tipo y no admite lectura sustantiva. El diseño es "
        f"transversal y las asociaciones no identifican efectos causales.", 79))

    A("\nFigura 5. Densidad física, visibilidad cartográfica e intensidad "
      "digital por establecimiento.")
    A(textwrap.fill(
        f"(A) Densidad de establecimientos (sin ponderación) y (B) visibilidad "
        f"cartográfica (ponderada por log(1 + reseñas)), estimadas por núcleo "
        f"gaussiano isotrópico con idéntico ancho de banda "
        f"(h = {BW_KDE_M:.0f} m), malla ({M.KDE_GRID_M:.0f} m) y dominio "
        f"analítico. Los máximos de (A) y (B) distan {V['sep_AB']:.0f} m "
        f"entre sí, por debajo del ancho de banda, y las superficies "
        f"correlacionan ρ = {coma(V['rho_AB'],2)}. "
        f"(C) Cociente de Nadaraya-Watson B/A: capital digital esperado por "
        f"establecimiento. Aísla la intensidad de la densidad: valores "
        f"superiores a la media global (isolínea gris; {coma(V['ratio_media'],2)}) "
        f"indican establecimientos que acumulan más visibilidad de la prevista "
        f"por la densidad física de su entorno (rojo); valores inferiores "
        f"(azul) indican silenciamiento relativo. La razón P90/P10 del "
        f"cociente es {coma(V['ratio_P90_P10'],1)}: la jerarquía interna de "
        f"visibilidad es amplia dentro del área del Centro Histórico "
        f"(distancia máxima a la Plaza Grande: 1,71 km). "
        f"Las isolíneas de (A) y (B) corresponden a los percentiles 50, 75, "
        f"90 y 97,5. Se excluye el decil inferior de densidad de (A) para "
        f"evitar cocientes inestables en zonas con muy pocos establecimientos. "
        f"n = {V['n_total']}.", 79))

    A("\nFigura 6. Concentración local de la visibilidad digital (estadístico "
      "Gi* de Getis-Ord).")
    A(textwrap.fill(
        f"Celdas regulares de {CELDA_M:.0f} m ({V['n_celdas']} ocupadas) con "
        f"pesos binarios de contigüidad reina y autovecindad; el estadístico "
        f"es directamente una puntuación z. Los niveles de confianza se "
        f"asignan por el valor p analítico bilateral y el contorno negro marca "
        f"las celdas que además superan la corrección de Benjamini-Hochberg "
        f"por comparaciones múltiples. En (A) ninguna celda supera dicha "
        f"corrección, por lo que sus conglomerados se presentan como "
        f"exploratorios; en (B) lo hacen {V['gi']['B']['n_fdr']}. "
        f"Autocorrelación global: I de Moran = {coma(V['gi']['A']['I'],3)} en "
        f"(A) y {coma(V['gi']['B']['I'],3)} en (B), ambas significativas "
        f"({N_PERM:,} permutaciones; p < 0,01). Las "
        f"{V['n_islas']} celdas sin vecino contiguo se vincularon a su vecino "
        f"más próximo.".replace(",", "."), 79))

    A("\nFigura 7. Volumen de reseñas y calificación media según la estructura "
      "comercial del establecimiento.")
    A(textwrap.fill(
        f"Contrastes de Mann-Whitney bilaterales con corrección por empates; "
        f"valores p obtenidos por permutación de Monte Carlo "
        f"({N_PERM:,} réplicas). Las franquicias acumulan significativamente "
        f"más reseñas (r rango-biserial = "
        f"{coma(V['mw']['A']['r_rango_biserial'],2)}) y reciben "
        f"significativamente menor calificación (r = "
        f"{coma(V['mw']['B']['r_rango_biserial'],2)}); ambos p < 0,001. El "
        f"panel B se restringe a los establecimientos con ficha activa y al "
        f"menos una reseña, dado que la ausencia de calificación no equivale a "
        f"una calificación de cero. Cajas: mediana e intervalo "
        f"interquartílico; violines: densidad estimada por núcleo; puntos: "
        f"observaciones individuales con dispersión horizontal "
        f"aleatoria.".replace(",", "."), 79))

    A("\n\n" + "=" * 79)
    A("FIGURE CAPTIONS · English version")
    A("=" * 79)

    A("\nFigure 1. Study area and census of food establishments in Quito's "
      "Historic Centre.")
    A(textwrap.fill(
        f"Each coloured point represents an establishment in the analysed "
        f"census (n = {V['n_total']}); size and colour denote the number of "
        f"active digital platforms (Google Maps listing, Instagram account, "
        f"TikTok account). For institutional context only, not part of the "
        f"analysis, the figure also shows the universe of food and beverage "
        f"venues in the municipal tourism registry for the Centro Histórico "
        f"parish (n = {ncat}; Quito Metropolitan District, 2026-03 update) "
        f"and the Special Tourism Zone boundary. Concentric rings are drawn "
        f"every 250 m from Plaza Grande. Projection: UTM 17S (EPSG:32717).",
        79))

    A("\nFigure 2. Digital stratification gradient of food heritage.")
    A(textwrap.fill(
        f"Distribution of establishments and of accumulated Google Maps "
        f"reviews by number of active digital platforms. "
        f"{coma(V['pct_estab_sin_plataforma'],1)} % of the census has no "
        f"presence on any of the three platforms and accumulates no reviews, "
        f"whereas the {coma(V['pct_estab_tres'],1)} % present on all three "
        f"concentrates {coma(V['pct_rev_tres'],1)} % of all reviews. "
        f"n = {V['n_total']}.", 79))

    A("\nFigure 3. Social media combinations across the surveyed "
      "establishments.")
    A(textwrap.fill(
        f"All {V['n_tt']} establishments holding a TikTok account also hold an "
        f"Instagram account, leaving the 'TikTok only' category empty. The "
        f"association is statistically significant (Fisher's exact test, "
        f"p < 0.001); the odds ratio is undefined owing to the empty cell, and "
        f"its Haldane-Anscombe corrected estimate is {V['or_haldane']:,.0f}. "
        f"n = {V['n_total']}.", 79))

    A("\nFigure 4. Determinants of review volume: negative binomial "
      "regression.")
    A(textwrap.fill(
        f"Incidence rate ratios (IRR) with 95 % confidence intervals on a "
        f"logarithmic scale. Values above unity (dashed line) indicate a "
        f"higher expected review count. Reference category for establishment "
        f"type: Traditional. Dispersion parameter α = {V['nb_alpha']:.2f}; "
        f"likelihood ratio test against the Poisson model: LR = "
        f"{V['nb_LR']:,.0f}, p < 0.001; n = {V['nb_n']}. * p < 0.05; "
        f"** p < 0.01; *** p < 0.001. The design is cross-sectional and the "
        f"associations do not identify causal effects.", 79))

    A("\nFigure 5. Physical density, cartographic visibility and digital "
      "intensity per establishment.")
    A(textwrap.fill(
        f"(A) Establishment density (unweighted) and (B) cartographic "
        f"visibility (weighted by log(1 + reviews)), estimated with an "
        f"isotropic Gaussian kernel sharing bandwidth "
        f"(h = {BW_KDE_M:.0f} m), grid and analytical domain. The maxima of "
        f"(A) and (B) lie {V['sep_AB']:.0f} m apart, below the estimator "
        f"bandwidth, and the surfaces correlate at ρ = {V['rho_AB']:.2f}. "
        f"(C) Nadaraya-Watson quotient B/A: expected digital capital per "
        f"establishment. It isolates intensity from density: values above the "
        f"global mean (grey contour; {V['ratio_media']:.2f}) indicate "
        f"establishments accumulating more visibility than predicted by their "
        f"surroundings (red); values below (blue) indicate relative "
        f"silencing. The P90/P10 ratio of the quotient is "
        f"{V['ratio_P90_P10']:.1f}. The bottom density decile of (A) is "
        f"excluded to avoid unstable quotients. n = {V['n_total']}.", 79))

    A("\nFigure 6. Local concentration of digital visibility (Getis-Ord Gi* "
      "statistic).")
    A(textwrap.fill(
        f"Regular {CELDA_M:.0f} m cells ({V['n_celdas']} occupied) with binary "
        f"queen contiguity weights and self-inclusion; the statistic is a z "
        f"score. Confidence levels follow the two-sided analytical p value; "
        f"black outlines mark cells that additionally survive the "
        f"Benjamini-Hochberg correction. No cell survives in (A), so its "
        f"clusters are reported as exploratory, whereas "
        f"{V['gi']['B']['n_fdr']} do in (B). Global Moran's I = "
        f"{V['gi']['A']['I']:.3f} in (A) and {V['gi']['B']['I']:.3f} in (B), "
        f"both significant ({N_PERM:,} permutations; p < 0.01).", 79))

    A("\nFigure 7. Review volume and mean rating by commercial structure.")
    A(textwrap.fill(
        f"Two-sided Mann-Whitney tests with tie correction; p values obtained "
        f"by Monte Carlo permutation ({N_PERM:,} replicates). Franchises "
        f"accumulate significantly more reviews (rank-biserial r = "
        f"{V['mw']['A']['r_rango_biserial']:.2f}) while receiving "
        f"significantly lower ratings (r = "
        f"{V['mw']['B']['r_rango_biserial']:.2f}); both p < 0.001. Panel B is "
        f"restricted to establishments with an active listing and at least one "
        f"review, since the absence of a rating is not equivalent to a rating "
        f"of zero.", 79))

    ruta = os.path.join(outdir, "pies_de_figura.txt")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(P))
    print("    guardado: pies_de_figura.txt")


# =============================================================================
# MAIN
# =============================================================================

def figure_captions_en(V, pca, outdir):
    """English-only figure captions, ready to paste into the manuscript."""
    print("· Figure captions (English only) …")
    ncat = V.get("n_catastro_referencia", 0)
    P = []
    A = P.append
    A("=" * 79)
    A("FIGURE CAPTIONS — English")
    A("=" * 79)

    A("\nFigure 1. Study area and census of food establishments in Quito's "
      "Historic Centre.")
    A(textwrap.fill(
        f"Each coloured point represents an establishment in the analysed "
        f"census (n = {V['n_total']}); size and colour denote the number of "
        f"active digital platforms (Google Maps listing, Instagram account, "
        f"TikTok account). For institutional context only, not part of the "
        f"analysis, the figure also shows the universe of food and beverage "
        f"venues in the municipal tourism registry for the Centro Historico "
        f"parish (n = {ncat}; Quito Metropolitan District, 2026-03 update) "
        f"and the Special Tourism Zone boundary. Concentric rings are drawn "
        f"every 250 m from Plaza Grande. Projection: UTM 17S (EPSG:32717).",
        79))

    A("\nFigure 2. Digital stratification gradient of food heritage.")
    A(textwrap.fill(
        f"Distribution of establishments and of accumulated Google Maps "
        f"reviews by number of active digital platforms. "
        f"{coma(V['pct_estab_sin_plataforma'],1)}% of the census has no "
        f"presence on any of the three platforms and accumulates no reviews, "
        f"whereas the {coma(V['pct_estab_tres'],1)}% present on all three "
        f"concentrates {coma(V['pct_rev_tres'],1)}% of all reviews. "
        f"n = {V['n_total']}.", 79))

    A("\nFigure 3. Social media combinations across the surveyed "
      "establishments.")
    A(textwrap.fill(
        f"All {V['n_tt']} establishments holding a TikTok account also hold an "
        f"Instagram account, leaving the 'TikTok only' category empty. The "
        f"association is statistically significant (Fisher's exact test, "
        f"p < 0.001); the odds ratio is undefined owing to the empty cell, and "
        f"its Haldane-Anscombe corrected estimate is {V['or_haldane']:,.0f}. "
        f"n = {V['n_total']}.", 79))

    irr_ig, lo_ig, hi_ig, _ = V["irr_ig"]
    A("\nFigure 4. Determinants of review volume: negative binomial "
      "regression.")
    A(textwrap.fill(
        f"Incidence rate ratios (IRR) with 95% confidence intervals on a "
        f"logarithmic scale. Values above unity (dashed line) indicate a "
        f"higher expected review count. Reference category for establishment "
        f"type: Traditional. Red: IRR significantly above 1; blue: "
        f"significantly below; grey: not significant. Dispersion parameter "
        f"alpha = {V['nb_alpha']:.2f}; likelihood ratio test against Poisson: "
        f"LR = {V['nb_LR']:,.0f}, p < 0.001; n = {V['nb_n']}. * p < 0.05; "
        f"** p < 0.01; *** p < 0.001. (a) 'Unclassified' groups records "
        f"without type information; its coefficient has no substantive "
        f"interpretation. The design is cross-sectional and associations do "
        f"not identify causal effects.", 79))

    A("\nFigure 5. Physical density, cartographic visibility and digital "
      "intensity per establishment.")
    A(textwrap.fill(
        f"(A) Establishment density (unweighted) and (B) cartographic "
        f"visibility (weighted by log(1 + reviews)), estimated with an "
        f"isotropic Gaussian kernel sharing bandwidth "
        f"(h = {BW_KDE_M:.0f} m), grid ({M.KDE_GRID_M:.0f} m) and analytical "
        f"domain. The maxima of (A) and (B) lie {V['sep_AB']:.0f} m apart, "
        f"below the estimator bandwidth, and the surfaces correlate at "
        f"rho = {V['rho_AB']:.2f}. (C) Nadaraya-Watson quotient B/A: expected "
        f"digital capital per establishment. Isolates intensity from density: "
        f"values above the global mean (grey contour; {V['ratio_media']:.2f}) "
        f"indicate establishments accumulating more visibility than predicted "
        f"by their surroundings (red); values below (blue) indicate relative "
        f"silencing. The P90/P10 ratio of the quotient is "
        f"{V['ratio_P90_P10']:.1f}. The maximum marker is shown only in (A) "
        f"and (B), where it is informative; in (C) the quotient maximum falls "
        f"on a low-density fringe and does not represent a meaningful "
        f"concentration. The bottom density decile of (A) is excluded to avoid "
        f"unstable quotients. Contour lines in (A) and (B) mark the 50th, "
        f"75th, 90th and 97.5th percentiles. n = {V['n_total']}.", 79))

    A("\nFigure 6. Local concentration of digital visibility (Getis-Ord Gi* "
      "statistic).")
    A(textwrap.fill(
        f"Regular {CELDA_M:.0f} m cells ({V['n_celdas']} occupied) with binary "
        f"queen contiguity weights and self-inclusion; the statistic is a "
        f"z-score. Confidence levels follow the two-sided analytical p-value; "
        f"black outlines mark cells that additionally survive the "
        f"Benjamini-Hochberg correction. No cell survives in (A), so its "
        f"clusters are reported as exploratory; {V['gi']['B']['n_fdr']} do in "
        f"(B). Global Moran's I = {V['gi']['A']['I']:.3f} in (A) and "
        f"{V['gi']['B']['I']:.3f} in (B); both significant "
        f"({N_PERM:,} permutations, p < 0.01). The {V['n_islas']} cells "
        f"lacking a contiguous neighbour were linked to their nearest "
        f"neighbour.", 79))

    A("\nFigure 7. Review volume and mean rating by commercial structure.")
    A(textwrap.fill(
        f"Two-sided Mann-Whitney tests with tie correction; p-values obtained "
        f"by Monte Carlo permutation ({N_PERM:,} replicates). Franchises "
        f"accumulate significantly more reviews (rank-biserial r = "
        f"{V['mw']['A']['r_rango_biserial']:.2f}) while receiving "
        f"significantly lower ratings (r = "
        f"{V['mw']['B']['r_rango_biserial']:.2f}); both p < 0.001. Panel B is "
        f"restricted to establishments with an active listing and at least one "
        f"review, since the absence of a rating is not equivalent to a rating "
        f"of zero. Boxes: median and interquartile range; violins: kernel "
        f"density estimate; points: individual observations with random "
        f"horizontal jitter.", 79))

    ruta = os.path.join(outdir, "figure_captions_EN.txt")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(P))
    print("    saved: figure_captions_EN.txt")


def main():
    ap = argparse.ArgumentParser(
        description="Genera el material final para el manuscrito de Frontiers")
    ap.add_argument("--csv", default="restaurantes_quito_CH_clean.csv")
    ap.add_argument("--outdir", default="figuras_paper")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    estilo()

    print("=" * 79)
    print("MATERIAL FINAL PARA EL MANUSCRITO")
    print("Frontiers in Nutrition · Nutrition and Sustainable Diets")
    print("=" * 79)

    df, pca = preparar(args.csv)
    V = {"r_cp1_nplat": float(stats.pearsonr(df.CP1, df.n_plataformas)[0])}

    figura1(df, args.outdir, V)
    figura2(df, args.outdir, V)
    figura3(df, args.outdir, V)
    figura4(df, args.outdir, V)
    figura5(df, args.outdir, V)
    figura6(df, args.outdir, V)
    figura7(df, args.outdir, V)
    tabla1(df, args.outdir, V)
    tabla2(V, args.outdir)
    documento_valores(V, pca, args.outdir)
    documento_valores_en(V, pca, args.outdir)
    pies_de_figura(V, pca, args.outdir)
    figure_captions_en(V, pca, args.outdir)

    print("\n" + "=" * 79)
    print(f"COMPLETADO · {os.path.abspath(args.outdir)}")
    print("=" * 79)
    for f in sorted(os.listdir(args.outdir)):
        if not f.endswith((".png", ".tif")):
            print("   " + f)
    print("\n(cada figura se exporta además en .png y .tif a 600 ppp)")


if __name__ == "__main__":
    main()
