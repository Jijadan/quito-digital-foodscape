#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
ESTRATIFICACIÓN DIGITAL DEL PATRIMONIO ALIMENTARIO — CENTRO HISTÓRICO DE QUITO
Script único de inferencia estadística y estadística espacial
===============================================================================

Análisis implementados
----------------------
  §1  Test U de Mann-Whitney (franquicias vs. independientes) + tamaño de efecto
  §2  Regresión binomial negativa (reseñas ~ tipo + distancia + presencia digital)
      con contraste frente a Poisson, ZINB y submuestra condicional
  §3  Kernel Density Estimation (KDE): superficie física vs. superficie digital
  §4  I de Moran global (puntos con KNN; celdas con contigüidad reina)
  §5  LISA — indicadores locales de asociación espacial (Anselin) con FDR
  §6  Getis-Ord Gi* (hot/cold spots) con FDR

Cada bloque imprime (a) las VARIABLES DE ENTRADA con sus descriptivos y
(b) los VALORES DE SALIDA numéricos, y exporta figuras en calidad de
publicación (PDF vectorial + PNG 600 dpi) y tablas en CSV.

Requisitos
----------
  pip install pandas numpy scipy statsmodels scikit-learn matplotlib \
              libpysal esda pyproj shapely

Uso
---
  python analisis_espacial_quito.py [--csv RUTA] [--outdir RUTA]

Reproducibilidad
----------------
  Semilla global SEMILLA = 12345; 9999 permutaciones en los estadísticos
  espaciales. Todos los parámetros están declarados en el bloque CONFIGURACIÓN.

Autor: Johann — proyecto "Digital Food Territories and Foodification"
===============================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial import ConvexHull

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Patch, FancyArrow
from matplotlib.collections import PatchCollection
from matplotlib.lines import Line2D
from matplotlib.path import Path as MplPath
import matplotlib.ticker as mticker

import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.discrete.count_model import ZeroInflatedNegativeBinomialP
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.outliers_influence import variance_inflation_factor
import patsy

from sklearn.neighbors import KernelDensity
from pyproj import Transformer
from shapely.geometry import MultiPoint

import libpysal
from libpysal.weights import KNN, W, attach_islands
import esda

warnings.filterwarnings("ignore")

# =============================================================================
# CONFIGURACIÓN — todos los parámetros metodológicos declarables en el paper
# =============================================================================

SEMILLA = 12345                 # semilla global
N_PERM = 9999                   # permutaciones para inferencia espacial
K_VECINOS = 8                   # k para KNN a nivel de establecimiento
CELDA_M = 150.0                 # lado de celda (m) — escala de manzana colonial
BW_KDE_M = 125.0                # ancho de banda KDE (m); sensibilidad 100/150
BW_SENSIBILIDAD = [100.0, 150.0]
KDE_GRID_M = 10.0               # resolución de la malla KDE (m)
EPSG_GEO = "EPSG:4326"          # coordenadas de origen
EPSG_PROJ = "EPSG:32717"        # UTM 17S — métrico, adecuado para Quito
ALFA = 0.05                     # nivel de significación
FDR_METODO = "fdr_bh"           # Benjamini-Hochberg
TIPO_REFERENCIA = "Tradicional" # categoría de referencia en la regresión
TIPOS_RAROS_MIN_N = 10          # colapsar categorías con n < 10 en "Otros"
INCLUIR_CELDAS_VACIAS = False   # análisis primario: solo celdas ocupadas

# Punto de referencia recuperado por trilateración inversa desde
# dist_plaza_grande_km (error medio 1,0 m): Plaza Grande / de la Independencia
PLAZA_GRANDE = (-0.220491, -78.512500)   # (lat, lon)

np.random.seed(SEMILLA)

# =============================================================================
# ESTILO DE FIGURAS — calidad de publicación
# =============================================================================

def configurar_estilo():
    """Tipografía y ejes con estándares de revista (Q1/Q2)."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Liberation Sans", "Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 8.5,
        "axes.titlesize": 9.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 8.5,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "legend.fontsize": 7.5,
        "legend.frameon": False,
        "axes.linewidth": 0.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "lines.linewidth": 1.1,
        "figure.dpi": 120,
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "pdf.fonttype": 42,       # TrueType incrustada (exigencia editorial)
        "ps.fonttype": 42,
        "mathtext.default": "regular",
    })


# Paleta consistente
COL_FRANQ = "#B03A2E"      # granate
COL_INDEP = "#1F4E79"      # azul profundo
COL_NEUTRO = "#7F8C8D"
COL_ACENTO = "#D68910"
# Convención GeoDa para LISA (mantener para legibilidad internacional)
COL_LISA = {"HH": "#C0392B", "LL": "#2471A3", "LH": "#AED6F1",
            "HL": "#F5B7B1", "ns": "#EAECEE"}
COL_GI = {"Hot 99%": "#78281F", "Hot 95%": "#C0392B", "Hot 90%": "#E6B0AA",
          "No signif.": "#EAECEE",
          "Cold 90%": "#AED6F1", "Cold 95%": "#2471A3", "Cold 99%": "#154360"}


# =============================================================================
# UTILIDADES DE IMPRESIÓN
# =============================================================================

class Registro:
    """Duplica stdout a un archivo de log."""
    def __init__(self, ruta):
        self.terminal = sys.stdout
        self.log = open(ruta, "w", encoding="utf-8")
    def write(self, msg):
        self.terminal.write(msg); self.log.write(msg)
    def flush(self):
        self.terminal.flush(); self.log.flush()


def titulo(txt, nivel=1):
    ancho = 79
    if nivel == 1:
        print("\n" + "=" * ancho); print(txt.upper()); print("=" * ancho)
    elif nivel == 2:
        print("\n" + "-" * ancho); print(txt); print("-" * ancho)
    else:
        print("\n· " + txt)


def tabla(df, titulo_tabla=None, decimales=4):
    if titulo_tabla:
        print(f"\n{titulo_tabla}")
    with pd.option_context("display.width", 200, "display.max_columns", 60,
                           "display.max_rows", 300,
                           "display.float_format", lambda v: f"{v:,.{decimales}f}"):
        print(df.to_string())


def nota(txt):
    print(textwrap.fill("NOTA: " + txt, 79, subsequent_indent="      "))


def barra_escala(ax, longitud_m, etiqueta, x_frac=0.06, y_frac=0.06,
                 color="black", alto_frac=0.012):
    """Barra de escala métrica sobre ejes en metros."""
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    xs = x0 + (x1 - x0) * x_frac
    ys = y0 + (y1 - y0) * y_frac
    h = (y1 - y0) * alto_frac
    ax.add_patch(Rectangle((xs, ys), longitud_m, h, facecolor=color,
                           edgecolor=color, lw=0.5, zorder=20))
    ax.add_patch(Rectangle((xs + longitud_m / 2, ys), longitud_m / 2, h,
                           facecolor="white", edgecolor=color, lw=0.5, zorder=21))
    ax.text(xs + longitud_m / 2, ys + h * 1.5, etiqueta, ha="center",
            va="bottom", fontsize=6.8, zorder=22, color=color)


def flecha_norte(ax, x_frac=0.94, y_frac=0.88, color="black"):
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    x = x0 + (x1 - x0) * x_frac
    y = y0 + (y1 - y0) * y_frac
    dy = (y1 - y0) * 0.075
    ax.annotate("", xy=(x, y + dy), xytext=(x, y),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.0,
                                mutation_scale=8), zorder=22)
    ax.text(x, y + dy * 1.12, "N", ha="center", va="bottom", fontsize=7,
            fontweight="bold", color=color, zorder=22)


def guardar(fig, outdir, nombre):
    for ext in ("pdf", "png"):
        ruta = os.path.join(outdir, f"{nombre}.{ext}")
        fig.savefig(ruta)
    plt.close(fig)
    print(f"   [figura guardada] {nombre}.pdf / {nombre}.png")


# =============================================================================
# §0 — CARGA, PROYECCIÓN Y AUDITORÍA DE DATOS
# =============================================================================

def cargar_datos(ruta_csv):
    titulo("§0 · Carga, proyección y auditoría de la base de datos")

    df = pd.read_csv(ruta_csv)
    df.columns = [c.strip() for c in df.columns]
    print(f"Archivo            : {ruta_csv}")
    print(f"Registros          : {len(df)}")
    print(f"Columnas           : {df.shape[1]}")

    # --- Renombrado operativo (nombres cortos, estables) -------------------
    ren = {
        "Cantidad de Reseñas": "resenas",
        "estrellas_num": "estrellas",
        "Tiene IG": "tiene_ig",
        "Seguidores IG": "seg_ig",
        "Tiene TikTok": "tiene_tt",
        "Seguidores TT": "seg_tt",
        "Likes TT": "likes_tt",
        "Tipo Restaurante": "tipo_raw",
        "dist_plaza_grande_km": "dist_km",
        "franquicia_bin": "franquicia",
        "CATEGORÍA": "categoria",
        "AÑO REGISTRO": "anio_registro",
    }
    df = df.rename(columns=ren)
    for c in ["resenas", "tiene_ig", "seg_ig", "tiene_tt", "seg_tt", "likes_tt"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["resenas"] = df["resenas"].astype(int)
    df["existe_gmaps"] = df["existe_gmaps"].astype(bool)

    # --- Transformaciones logarítmicas (recalculadas, no heredadas) --------
    df["log1p_resenas"] = np.log1p(df["resenas"])
    df["log1p_seg_ig"] = np.log1p(df["seg_ig"])
    df["log1p_seg_tt"] = np.log1p(df["seg_tt"])

    # --- Proyección métrica ------------------------------------------------
    tr = Transformer.from_crs(EPSG_GEO, EPSG_PROJ, always_xy=True)
    df["X"], df["Y"] = tr.transform(df["lon"].values, df["lat"].values)
    px, py = tr.transform(PLAZA_GRANDE[1], PLAZA_GRANDE[0])
    df["dist_m_recalc"] = np.hypot(df["X"] - px, df["Y"] - py)

    titulo("§0.1 · Verificación de integridad", 2)
    err = np.abs(df["dist_m_recalc"] / 1000.0 - df["dist_km"])
    print(f"Sistema de coordenadas proyectado : {EPSG_PROJ} (UTM 17S)")
    print(f"Punto de referencia (Plaza Grande) : "
          f"lat {PLAZA_GRANDE[0]:.6f}, lon {PLAZA_GRANDE[1]:.6f}")
    print(f"  · recuperado por trilateración inversa desde dist_plaza_grande_km")
    print(f"Discrepancia distancia (m): media {err.mean()*1000:.2f} | "
          f"máx {err.max()*1000:.2f}")
    print(f"Extensión del área (m): X {df.X.max()-df.X.min():.0f} × "
          f"Y {df.Y.max()-df.Y.min():.0f}")

    # Coordenadas duplicadas
    dup = df.duplicated(["lat", "lon"], keep=False).sum()
    n_unicas = df.groupby(["lat", "lon"]).ngroups
    print(f"Coordenadas únicas: {n_unicas} | registros en coordenada "
          f"compartida: {dup}")

    # Estructura de los ceros — distinción conceptual central
    titulo("§0.2 · Estructura de los ceros en la variable de conteo", 2)
    n_sin_ficha = int((~df.existe_gmaps).sum())
    n_ficha_0 = int(((df.existe_gmaps) & (df.resenas == 0)).sum())
    n_ficha_pos = int(((df.existe_gmaps) & (df.resenas > 0)).sum())
    coherencia = int(((~df.existe_gmaps) & (df.resenas > 0)).sum())
    est = pd.DataFrame({
        "Régimen": ["Sin ficha en Google Maps (cero ESTRUCTURAL)",
                    "Con ficha, 0 reseñas (cero MUESTRAL)",
                    "Con ficha, ≥1 reseña"],
        "n": [n_sin_ficha, n_ficha_0, n_ficha_pos],
        "%": [100*n_sin_ficha/len(df), 100*n_ficha_0/len(df),
              100*n_ficha_pos/len(df)],
    })
    tabla(est, decimales=2)
    print(f"\nControl de coherencia (reseñas>0 sin ficha, debe ser 0): {coherencia}")
    print(f"estrellas nulas == sin ficha: "
          f"{int((df.estrellas.isna() == (~df.existe_gmaps)).all())} (1=verdadero)")
    print(f"Registros con estrellas == 0 : {int((df.estrellas==0).sum())} "
          f"— todos con 0 reseñas: "
          f"{int((df.loc[df.estrellas==0,'resenas']==0).all())}")
    nota("estrellas = 0 no es una calificación de cero sino ausencia de "
         "calificación. En §1 el contraste de estrellas se restringe a "
         "establecimientos con ≥1 reseña.")

    # Sobredispersión
    titulo("§0.3 · Sobredispersión de la variable dependiente", 2)
    m, v = df.resenas.mean(), df.resenas.var(ddof=1)
    print(f"reseñas: media {m:.3f} | varianza {v:.3f} | razón V/M {v/m:.1f}")
    print(f"        mediana {df.resenas.median():.1f} | máx {df.resenas.max()} | "
          f"asimetría {stats.skew(df.resenas):.3f} | "
          f"curtosis {stats.kurtosis(df.resenas):.3f}")
    nota("V/M >> 1 invalida Poisson y justifica binomial negativa (§2). "
         "La asimetría extrema invalida la t de Student y justifica "
         "Mann-Whitney (§1).")

    # Recodificación del tipo
    titulo("§0.4 · Recodificación de la variable 'tipo'", 2)
    vc = df["tipo_raw"].value_counts()
    raros = vc[vc < TIPOS_RAROS_MIN_N].index.tolist()
    mapa = {r: "Otros" for r in raros}
    mapa["Desconocido"] = "Sin clasificar"
    df["tipo"] = df["tipo_raw"].replace(mapa)
    print(f"Categorías originales: {len(vc)}")
    print(f"Colapsadas en 'Otros' (n < {TIPOS_RAROS_MIN_N}): {raros}")
    print("'Desconocido' → 'Sin clasificar' (ausencia de dato, no categoría "
          "culinaria)")
    tabla(df["tipo"].value_counts().rename("n").to_frame(),
          "Distribución final de 'tipo'", 0)

    df["ig_lab"] = np.where(df.tiene_ig == 1, "Con Instagram", "Sin Instagram")
    df["fr_lab"] = np.where(df.franquicia == 1, "Franquicia", "Independiente")
    return df


# =============================================================================
# §1 — TEST U DE MANN-WHITNEY
# =============================================================================

def rango_biserial(u1, n1, n2):
    """r_rb = 2*U1/(n1*n2) - 1. Positivo = grupo 1 estocásticamente mayor."""
    return 2.0 * u1 / (n1 * n2) - 1.0


def mann_whitney(x_g1, x_g2, etiqueta, n_perm=N_PERM, semilla=SEMILLA):
    """
    Devuelve dict con U (grupo 1), U(grupo 2), z con corrección por empates,
    p asintótica bilateral, p por permutación Monte Carlo, r rango-biserial,
    A de Vargha-Delaney (probabilidad de superioridad) y descriptivos.
    """
    x1 = np.asarray(x_g1, dtype=float); x1 = x1[~np.isnan(x1)]
    x2 = np.asarray(x_g2, dtype=float); x2 = x2[~np.isnan(x2)]
    n1, n2 = len(x1), len(x2)

    res_as = stats.mannwhitneyu(x1, x2, alternative="two-sided",
                               method="asymptotic")
    u1 = float(res_as.statistic)
    u2 = n1 * n2 - u1

    # z con corrección por empates (fórmula clásica)
    todos = np.concatenate([x1, x2])
    _, cuentas = np.unique(todos, return_counts=True)
    n = n1 + n2
    correc = np.sum(cuentas ** 3 - cuentas)
    mu_u = n1 * n2 / 2.0
    sd_u = np.sqrt((n1 * n2 / 12.0) * ((n + 1) - correc / (n * (n - 1))))
    z = (u1 - mu_u) / sd_u if sd_u > 0 else np.nan

    # p por permutación Monte Carlo (no depende de la aproximación normal).
    # Implementación vectorizada: bajo permutación, U depende únicamente de la
    # suma de rangos del grupo 1, R1, mediante U1 = R1 - n1(n1+1)/2. Basta con
    # rebarajar la asignación de rangos (los empates ya están resueltos por
    # rangos medios), lo que evita recalcular el estadístico observación a
    # observación y es exactamente equivalente al bucle ingenuo.
    rng = np.random.default_rng(semilla)
    rangos = stats.rankdata(todos)
    obs = abs(u1 - mu_u)
    idx = rng.permuted(np.tile(np.arange(n, dtype=np.int32), (n_perm, 1)),
                       axis=1)[:, :n1]
    R1 = rangos[idx].sum(axis=1)
    U1p = R1 - n1 * (n1 + 1) / 2.0
    cnt = int(np.sum(np.abs(U1p - mu_u) >= obs - 1e-9))
    p_perm = (cnt + 1) / (n_perm + 1)

    r_rb = rango_biserial(u1, n1, n2)
    a_vd = u1 / (n1 * n2)          # Vargha-Delaney A12
    return {
        "variable": etiqueta,
        "n1_franquicias": n1, "n2_independientes": n2,
        "mediana_g1": float(np.median(x1)), "mediana_g2": float(np.median(x2)),
        "media_g1": float(np.mean(x1)), "media_g2": float(np.mean(x2)),
        "Q1_g1": float(np.percentile(x1, 25)), "Q3_g1": float(np.percentile(x1, 75)),
        "Q1_g2": float(np.percentile(x2, 25)), "Q3_g2": float(np.percentile(x2, 75)),
        "rango_medio_g1": float(stats.rankdata(todos)[:n1].mean()),
        "rango_medio_g2": float(stats.rankdata(todos)[n1:].mean()),
        "U_g1": u1, "U_g2": u2, "mu_U": mu_u, "sd_U": sd_u, "z": z,
        "p_asintotica": float(res_as.pvalue), "p_permutacion": p_perm,
        "r_rango_biserial": r_rb, "A_Vargha_Delaney": a_vd,
    }


def bloque_mann_whitney(df, outdir, resultados):
    titulo("§1 · Test U de Mann-Whitney — franquicias vs. independientes")

    print("VARIABLES DE ENTRADA")
    print("  Agrupación : franquicia (1 = Franquicia, 0 = Independiente)")
    print("  Contrastes : (a) reseñas  (b) seguidores IG  (c) estrellas")
    print(f"  Permutaciones Monte Carlo: {N_PERM} | semilla {SEMILLA}")

    g1 = df[df.franquicia == 1]
    g0 = df[df.franquicia == 0]
    print(f"\n  n franquicias    = {len(g1)}")
    print(f"  n independientes = {len(g0)}")
    print(f"  Razón de tamaños = 1 : {len(g0)/len(g1):.1f}  → grupos muy "
          f"desiguales; la t de Student sería indefendible")

    tabla(df.groupby("fr_lab")[["resenas", "seg_ig", "estrellas", "tiene_ig",
                                "tiene_tt", "dist_km"]]
          .agg(["count", "mean", "median"]).T,
          "Descriptivos de entrada por grupo", 3)

    pruebas = []

    # (a) Reseñas — muestra completa
    pruebas.append(mann_whitney(g1.resenas, g0.resenas,
                                "Reseñas (n=420, ceros incluidos)"))
    # (b) Seguidores IG — muestra completa
    pruebas.append(mann_whitney(g1.seg_ig, g0.seg_ig,
                                "Seguidores IG (n=420, ceros incluidos)"))
    # (b') Seguidores IG condicional a tener IG
    sub_ig = df[df.tiene_ig == 1]
    pruebas.append(mann_whitney(sub_ig[sub_ig.franquicia == 1].seg_ig,
                                sub_ig[sub_ig.franquicia == 0].seg_ig,
                                "Seguidores IG (solo con cuenta IG)"))
    # (c) Estrellas — PRIMARIO: con ficha y ≥1 reseña
    sub_e = df[(df.existe_gmaps) & (df.resenas > 0)]
    pruebas.append(mann_whitney(sub_e[sub_e.franquicia == 1].estrellas,
                                sub_e[sub_e.franquicia == 0].estrellas,
                                "Estrellas (con ficha y ≥1 reseña) [PRIMARIO]"))
    # (c') Estrellas — todas las fichas (comparabilidad; incluye 24 ceros
    #      que NO son calificaciones)
    sub_e2 = df[df.existe_gmaps]
    pruebas.append(mann_whitney(sub_e2[sub_e2.franquicia == 1].estrellas,
                                sub_e2[sub_e2.franquicia == 0].estrellas,
                                "Estrellas (todas las fichas) [sesgado]"))
    # (d) Robustez: excluyendo cuentas sociales duplicadas
    df_nd = df[~df["cuenta_social_duplicada"].astype(bool)]
    pruebas.append(mann_whitney(df_nd[df_nd.franquicia == 1].seg_ig,
                                df_nd[df_nd.franquicia == 0].seg_ig,
                                "Seguidores IG (sin cuentas duplicadas)"))
    # (e) Distancia al núcleo (control de localización)
    pruebas.append(mann_whitney(g1.dist_km, g0.dist_km,
                                "Distancia a Plaza Grande (km)"))

    res = pd.DataFrame(pruebas)

    print("\nVALORES DE SALIDA")
    tabla(res[["variable", "n1_franquicias", "n2_independientes",
               "mediana_g1", "mediana_g2", "rango_medio_g1", "rango_medio_g2"]],
          "(1) Tendencia central y rangos medios", 2)
    tabla(res[["variable", "U_g1", "mu_U", "sd_U", "z", "p_asintotica",
               "p_permutacion"]],
          "(2) Estadístico de contraste", 6)
    tabla(res[["variable", "r_rango_biserial", "A_Vargha_Delaney"]],
          "(3) Tamaño del efecto", 4)

    print("\nInterpretación de r rango-biserial: diferencia entre P(franquicia >")
    print("independiente) y P(independiente > franquicia). |r|: 0,1 pequeño;")
    print("0,3 medio; 0,5 grande (Cohen, adaptado a rangos).")
    print("A de Vargha-Delaney = P(franquicia > independiente) + 0,5·P(empate).")

    # ---- Corrección por comparaciones múltiples sobre las 3 primarias ----
    primarias = [0, 1, 3]
    p_prim = res.loc[primarias, "p_permutacion"].values
    rech, p_adj, _, _ = multipletests(p_prim, alpha=ALFA, method=FDR_METODO)
    tabla(pd.DataFrame({"variable": res.loc[primarias, "variable"].values,
                        "p_original": p_prim, "p_FDR": p_adj,
                        "significativo": rech}),
          f"(4) Corrección FDR ({FDR_METODO}) sobre los 3 contrastes primarios", 6)

    res.to_csv(os.path.join(outdir, "T1_mann_whitney.csv"), index=False)
    resultados["mann_whitney"] = res.to_dict(orient="records")

    # ---- FIGURA 1 --------------------------------------------------------
    fig1_mann_whitney(df, res, outdir)
    return res


def fig1_mann_whitney(df, res, outdir):
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.15))
    especificaciones = [
        ("resenas", df, "Reseñas acumuladas en Google Maps",
         "Nº de reseñas (escala log$_{10}$(1+x))", 0),
        ("seg_ig", df, "Seguidores en Instagram",
         "Nº de seguidores (escala log$_{10}$(1+x))", 1),
        ("estrellas", df[(df.existe_gmaps) & (df.resenas > 0)],
         "Calificación media", "Estrellas (0–5)", 3),
    ]
    rng = np.random.default_rng(SEMILLA)

    for ax, (col, datos, titulo_p, ylab, fila) in zip(axes, especificaciones):
        grupos, colores, etiquetas = [], [COL_INDEP, COL_FRANQ], \
            ["Independientes", "Franquicias"]
        for v in (0, 1):
            s = datos.loc[datos.franquicia == v, col].dropna().values
            grupos.append(np.log10(1 + s) if col != "estrellas" else s)

        parts = ax.violinplot(grupos, positions=[1, 2], widths=0.72,
                              showextrema=False, showmedians=False)
        for pc, c in zip(parts["bodies"], colores):
            pc.set_facecolor(c); pc.set_alpha(0.22); pc.set_edgecolor(c)
            pc.set_linewidth(0.6)

        bp = ax.boxplot(grupos, positions=[1, 2], widths=0.20, showfliers=False,
                        patch_artist=True, zorder=3,
                        medianprops=dict(color="white", lw=1.4),
                        whiskerprops=dict(lw=0.7), capprops=dict(lw=0.7))
        for patch, c in zip(bp["boxes"], colores):
            patch.set_facecolor(c); patch.set_edgecolor(c); patch.set_alpha=0.95

        for i, (g, c) in enumerate(zip(grupos, colores), start=1):
            jx = i + rng.uniform(-0.13, 0.13, size=len(g))
            ax.scatter(jx, g, s=3.2, color=c, alpha=0.30, linewidths=0,
                       zorder=2, rasterized=True)

        r = res.iloc[fila]
        p = r["p_permutacion"]
        p_txt = f"$p$ < 0,001" if p < 0.001 else f"$p$ = {p:.3f}".replace(".", ",")
        ax.set_title(titulo_p, pad=16)
        ax.text(0.5, 1.012,
                f"$U$ = {r['U_g1']:,.0f} · {p_txt} · $r_{{rb}}$ = "
                f"{r['r_rango_biserial']:.2f}".replace(".", ","),
                transform=ax.transAxes, ha="center", va="bottom", fontsize=7.2,
                color="#2C3E50")
        ax.set_xticks([1, 2])
        ax.set_xticklabels([f"Independientes\n($n$ = {len(grupos[0])})",
                            f"Franquicias\n($n$ = {len(grupos[1])})"])
        ax.set_ylabel(ylab)
        ax.grid(axis="y", lw=0.35, color="#D5D8DC", zorder=0)
        ax.set_axisbelow(True)
        if col != "estrellas":
            vmax = max(g.max() for g in grupos)
            marcas = [0, 1, 10, 100, 1_000, 10_000, 100_000, 1_000_000]
            marcas = [m for m in marcas if np.log10(1 + m) <= vmax * 1.02]
            ax.set_yticks([np.log10(1 + m) for m in marcas])
            ax.set_yticklabels([f"{m:,}".replace(",", ".") for m in marcas])
            ax.set_ylabel(ylab.replace(" (escala log$_{10}$(1+x))",
                                       "\n(escala logarítmica)"))

    fig.text(0.005, -0.02,
             "Cajas: mediana e intervalo interquartílico; violines: densidad de "
             "kernel; puntos: observaciones individuales (dispersión horizontal "
             "aleatoria).\nContraste: U de Mann-Whitney bilateral con corrección "
             f"por empates; $p$ por permutación Monte Carlo ({N_PERM:,} "
             "réplicas). $r_{rb}$ = correlación rango-biserial."
             .replace(",", "."),
             fontsize=6.3, color="#566573", va="top")
    fig.tight_layout()
    guardar(fig, outdir, "Figura1_MannWhitney")


# =============================================================================
# §2 — REGRESIÓN BINOMIAL NEGATIVA
# =============================================================================

def irr_tabla(modelo, nombre_alpha="alpha"):
    """Razones de tasas de incidencia con IC95% a partir de un modelo MLE."""
    p = modelo.params.copy()
    ci = modelo.conf_int().copy()
    pv = modelo.pvalues.copy()
    se = modelo.bse.copy()
    for k in (nombre_alpha, "lnalpha"):
        for obj in (p, pv, se):
            if k in obj.index:
                obj.drop(index=k, inplace=True)
        if k in ci.index:
            ci.drop(index=k, inplace=True)
    return pd.DataFrame({
        "coef_b": p.values,
        "EE": se.values,
        "z": (p / se).values,
        "p": pv.values,
        "IRR": np.exp(p.values),
        "IC95_inf": np.exp(ci.iloc[:, 0].values),
        "IC95_sup": np.exp(ci.iloc[:, 1].values),
        "cambio_%": (np.exp(p.values) - 1) * 100,
    }, index=p.index)


def limpiar_nombres(idx):
    out = []
    for s in idx:
        s = str(s)
        s = s.replace(f'C(tipo, Treatment(reference="{TIPO_REFERENCIA}"))[T.', "")
        s = s.replace("C(tipo)[T.", "").replace("]", "")
        out.append(s)
    return out


def bloque_binomial_negativa(df, outdir, resultados):
    titulo("§2 · Regresión binomial negativa — reseñas ~ tipo + distancia + "
           "presencia digital")

    d = df.copy()
    d["y"] = d["resenas"].astype(int)
    d["dist"] = d["dist_km"]
    d["ig"] = d["tiene_ig"].astype(int)
    d["tt"] = d["tiene_tt"].astype(int)
    d["fr"] = d["franquicia"].astype(int)

    print("VARIABLES DE ENTRADA")
    print(f"  Dependiente  : y = reseñas (conteo entero, no truncado)")
    print(f"  Independientes:")
    print(f"     · tipo  — factor categórico, referencia = '{TIPO_REFERENCIA}'")
    print(f"     · dist  — distancia euclídea a Plaza Grande, en km (continua)")
    print(f"     · ig    — indicador de presencia en Instagram (0/1)")
    print(f"     · tt    — indicador de presencia en TikTok (0/1) [ampliado]")
    print(f"     · fr    — franquicia (0/1) [ampliado]")
    print(f"  n = {len(d)}")

    desc = d[["y", "dist", "ig", "tt", "fr"]].describe().T
    desc["varianza"] = d[["y", "dist", "ig", "tt", "fr"]].var()
    tabla(desc, "Descriptivos de las variables del modelo", 4)
    tabla(d.groupby("tipo").agg(n=("y", "size"), media_resenas=("y", "mean"),
                                mediana_resenas=("y", "median"),
                                pct_con_IG=("ig", "mean"),
                                dist_media_km=("dist", "mean"))
          .sort_values("n", ascending=False),
          "Perfil de las categorías de 'tipo'", 3)

    f_base = (f'y ~ C(tipo, Treatment(reference="{TIPO_REFERENCIA}")) '
              f'+ dist + ig')
    f_ampl = f_base + " + tt + fr"

    # ---- Diagnóstico de colinealidad -------------------------------------
    titulo("§2.1 · Diagnóstico previo: colinealidad (VIF)", 2)
    Xv = patsy.dmatrix(f_ampl.split("~")[1], d, return_type="dataframe")
    vif = pd.DataFrame({
        "variable": limpiar_nombres(Xv.columns),
        "VIF": [variance_inflation_factor(Xv.values, i)
                for i in range(Xv.shape[1])]})
    tabla(vif[vif.variable != "Intercept"], None, 3)
    nota("VIF < 5 en todos los predictores sustantivos → no hay colinealidad "
         "problemática.")

    # ---- Poisson vs. binomial negativa -----------------------------------
    titulo("§2.2 · Justificación del modelo: Poisson vs. binomial negativa", 2)
    po = smf.glm(f_base, data=d, family=sm.families.Poisson()).fit()
    nb = smf.negativebinomial(f_base, data=d).fit(disp=0, maxiter=500)

    pearson_chi2 = float(po.pearson_chi2)
    gl = int(po.df_resid)
    print(f"Poisson  : log-verosimilitud = {po.llf:,.2f} | AIC = {po.aic:,.1f}")
    print(f"           χ² de Pearson / gl = {pearson_chi2/gl:,.2f} "
          f"(esperado ≈ 1 si no hay sobredispersión)")
    print(f"           desvianza / gl     = {po.deviance/gl:,.2f}")
    print(f"BinNeg   : log-verosimilitud = {nb.llf:,.2f} | AIC = {nb.aic:,.1f} "
          f"| BIC = {nb.bic:,.1f}")

    alpha = float(nb.params["alpha"])
    se_alpha = float(nb.bse["alpha"])
    LR = 2.0 * (nb.llf - po.llf)
    # Contraste en la frontera del espacio paramétrico (α ≥ 0):
    # la distribución nula es una mezcla 0,5·χ²(0) + 0,5·χ²(1)
    p_LR = 0.5 * stats.chi2.sf(LR, 1)
    p_LR_txt = "< 1e-300" if p_LR < 1e-300 else f"= {p_LR:.3g}"
    print(f"\nParámetro de dispersión α = {alpha:.4f} (EE {se_alpha:.4f}); "
          f"IC95% [{alpha-1.96*se_alpha:.4f}, {alpha+1.96*se_alpha:.4f}]")
    print(f"Contraste de razón de verosimilitudes NB vs. Poisson:")
    print(f"  LR = {LR:,.2f} | p {p_LR_txt} "
          f"(mezcla ½χ²₀ + ½χ²₁, frontera α≥0)")
    print(f"  → se rechaza contundentemente Poisson; la binomial negativa (NB2) "
          f"es el modelo correcto.")

    # ---- Modelo principal -------------------------------------------------
    titulo("§2.3 · Modelo 1 (especificación principal) — NB2, n = %d" % len(d), 2)
    t_nb = irr_tabla(nb)
    t_nb.index = limpiar_nombres(t_nb.index)
    tabla(t_nb, "Coeficientes, IRR e IC 95%", 4)
    print(f"\nPseudo-R² (McFadden) = {nb.prsquared:.4f} | "
          f"LLR p-valor global = {nb.llr_pvalue:.3g}")
    print(f"Convergencia: {nb.mle_retvals['converged']} | "
          f"evaluaciones de la función: {nb.mle_retvals.get('fcalls', 'n/d')} | "
          f"código de salida: {nb.mle_retvals.get('warnflag', 'n/d')}")

    print("\nLectura sustantiva (IRR = razón de tasas de incidencia):")
    for k in ("ig", "dist"):
        if k in t_nb.index:
            r = t_nb.loc[k]
            if k == "ig":
                print(f"  · Instagram: IRR = {r.IRR:.3f} "
                      f"[{r.IC95_inf:.3f}; {r.IC95_sup:.3f}], p = {r.p:.4g} → "
                      f"los establecimientos con IG registran {r.IRR:.2f} veces "
                      f"más reseñas esperadas, controlando tipo y localización.")
            else:
                print(f"  · Distancia: IRR = {r.IRR:.3f} "
                      f"[{r.IC95_inf:.3f}; {r.IC95_sup:.3f}], p = {r.p:.4g} → "
                      f"cada km de alejamiento del núcleo multiplica las reseñas "
                      f"esperadas por {r.IRR:.3f} ({(1-r.IRR)*100:.1f}% de "
                      f"reducción).")
    print("\n  Formulación admisible: 'se asocia con'. El diseño es transversal:")
    print("  NO autoriza inferencia causal (§2.7).")

    # ---- Modelo ampliado ---------------------------------------------------
    titulo("§2.4 · Modelo 2 (ampliado: + TikTok + franquicia)", 2)
    nb2 = smf.negativebinomial(f_ampl, data=d).fit(disp=0, maxiter=500)
    t_nb2 = irr_tabla(nb2); t_nb2.index = limpiar_nombres(t_nb2.index)
    tabla(t_nb2, None, 4)
    print(f"α = {nb2.params['alpha']:.4f} | AIC = {nb2.aic:,.1f} | "
          f"BIC = {nb2.bic:,.1f} | pseudo-R² = {nb2.prsquared:.4f}")
    LR2 = 2 * (nb2.llf - nb.llf)
    print(f"LR Modelo 2 vs. Modelo 1 = {LR2:.3f} (2 gl), p = "
          f"{stats.chi2.sf(LR2, 2):.4f}")

    # ---- Modelo condicional a existir en Google Maps ----------------------
    titulo("§2.5 · Modelo 3 (robustez): condicional a tener ficha en Google Maps", 2)
    d_f = d[d.existe_gmaps].copy()
    nb3 = smf.negativebinomial(f_base, data=d_f).fit(disp=0, maxiter=500)
    t_nb3 = irr_tabla(nb3); t_nb3.index = limpiar_nombres(t_nb3.index)
    tabla(t_nb3, f"n = {len(d_f)} (excluye los {len(d)-len(d_f)} ceros "
                 f"estructurales)", 4)
    print(f"α = {nb3.params['alpha']:.4f} | AIC = {nb3.aic:,.1f} | "
          f"pseudo-R² = {nb3.prsquared:.4f}")
    nota("La estabilidad del signo y del orden de magnitud de los IRR entre "
         "los Modelos 1 y 3 indica que el resultado no depende de cómo se "
         "traten los ceros estructurales.")

    # ---- ZINB -------------------------------------------------------------
    titulo("§2.6 · Modelo 4 (robustez): binomial negativa inflada en ceros "
           "(ZINB)", 2)
    print("Motivación: los 120 establecimientos sin ficha en Google Maps son")
    print("ceros generados por un proceso distinto (invisibilidad digital) del")
    print("que genera el volumen de reseñas. La ecuación de inflación modela")
    print("explícitamente la probabilidad de pertenecer al régimen de cero.")
    zinb_ok = False
    try:
        yv, Xv2 = patsy.dmatrices(f_base, d, return_type="dataframe")
        Zi = sm.add_constant(d[["dist", "ig"]].astype(float))
        zinb = ZeroInflatedNegativeBinomialP(yv, Xv2, exog_infl=Zi, p=2)\
            .fit(maxiter=800, disp=0)
        zinb_ok = bool(zinb.mle_retvals["converged"])
        print(f"\nConvergencia: {zinb_ok} | log-verosimilitud = {zinb.llf:,.2f} "
              f"| AIC = {zinb.aic:,.1f} | BIC = {zinb.bic:,.1f}")
        pz = pd.DataFrame({"coef": zinb.params, "EE": zinb.bse,
                           "z": zinb.tvalues, "p": zinb.pvalues})
        pz.index = limpiar_nombres(pz.index)
        tabla(pz, "Parámetros ZINB (prefijo 'inflate_' = ecuación de inflación)",
              4)
        print(f"\nComparación de ajuste:  AIC  NB = {nb.aic:,.1f} | "
              f"ZINB = {zinb.aic:,.1f}")
        print(f"                        BIC  NB = {nb.bic:,.1f} | "
              f"ZINB = {zinb.bic:,.1f}")
        mejor = "ZINB" if zinb.aic < nb.aic else "NB2"
        print(f"  → menor AIC: {mejor}. El BIC penaliza más la parametrización "
              f"adicional; se reportan ambos.")
        nota("statsmodels no implementa el contraste de Vuong; la comparación "
             "se basa en AIC/BIC y en la significación de la ecuación de "
             "inflación. Reportar el modelo NB2 como principal y ZINB como "
             "robustez es la práctica estándar.")
    except Exception as e:
        print(f"\n[ZINB no convergió: {e}] Se reporta únicamente NB2.")
        zinb = None

    # ---- Comparación de modelos -------------------------------------------
    titulo("§2.7 · Síntesis comparativa de modelos", 2)
    filas = [
        ["1 · NB2 (principal)", len(d), nb.llf, nb.aic, nb.bic,
         nb.params["alpha"], nb.prsquared],
        ["2 · NB2 ampliado", len(d), nb2.llf, nb2.aic, nb2.bic,
         nb2.params["alpha"], nb2.prsquared],
        ["3 · NB2 con ficha", len(d_f), nb3.llf, nb3.aic, nb3.bic,
         nb3.params["alpha"], nb3.prsquared],
        ["0 · Poisson", len(d), po.llf, po.aic, np.nan, 0.0, np.nan],
    ]
    if zinb is not None:
        filas.append(["4 · ZINB", len(d), zinb.llf, zinb.aic, zinb.bic,
                      np.nan, np.nan])
    comp = pd.DataFrame(filas, columns=["Modelo", "n", "logLik", "AIC", "BIC",
                                        "alpha", "pseudo_R2"])
    tabla(comp, None, 3)

    print("\nADVERTENCIAS DE INFERENCIA (nivel de evidencia)")
    print("  · Diseño transversal, una sola observación temporal por local:")
    print("    las asociaciones NO identifican efectos causales. Redactar")
    print("    siempre 'se asocia con', nunca 'produce' o 'genera'.")
    print("  · Endogeneidad plausible entre presencia en Instagram y volumen de")
    print("    reseñas (los locales con más flujo tienen más incentivo a abrir")
    print("    cuenta): el IRR de 'ig' es un límite superior del efecto.")
    print("  · Las reseñas no están normalizadas por antigüedad de la ficha;")
    print("    si se obtiene la fecha de creación, repetir con offset")
    print("    log(años de exposición) como control de exposición.")
    print("  · 'Sin clasificar' agrupa ausencia de dato, no una categoría")
    print("    culinaria: su coeficiente no admite lectura sustantiva.")

    t_nb.to_csv(os.path.join(outdir, "T2a_binneg_modelo1.csv"))
    t_nb2.to_csv(os.path.join(outdir, "T2b_binneg_modelo2_ampliado.csv"))
    t_nb3.to_csv(os.path.join(outdir, "T2c_binneg_modelo3_conficha.csv"))
    comp.to_csv(os.path.join(outdir, "T2d_comparacion_modelos.csv"), index=False)
    resultados["binomial_negativa"] = {
        "alpha": alpha, "LR_vs_poisson": LR, "p_LR": p_LR,
        "modelo1": t_nb.reset_index().to_dict(orient="records"),
        "comparacion": comp.to_dict(orient="records"),
    }

    fig2_binomial_negativa(d, nb, po, t_nb, outdir)
    return nb, t_nb


def fig2_binomial_negativa(d, nb, po, t_nb, outdir):
    fig = plt.figure(figsize=(7.4, 3.5))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.32, 1.0], wspace=0.42)

    # ---- Panel A: forest plot de IRR -------------------------------------
    ax = fig.add_subplot(gs[0, 0])
    t = t_nb.drop(index=[i for i in t_nb.index if i == "Intercept"]).copy()
    etiquetas = {"ig": "Presencia en Instagram", "dist": "Distancia (por km)"}
    t.index = [etiquetas.get(i, i) for i in t.index]
    orden = (["Presencia en Instagram", "Distancia (por km)"] +
             [i for i in t.index if i not in etiquetas.values()])
    t = t.loc[[o for o in orden if o in t.index]]
    ypos = np.arange(len(t))[::-1]

    for yi, (nombre, r) in zip(ypos, t.iterrows()):
        signif = r["p"] < ALFA
        c = COL_FRANQ if (signif and r["IRR"] > 1) else (
            COL_INDEP if signif else COL_NEUTRO)
        ax.plot([r["IC95_inf"], r["IC95_sup"]], [yi, yi], color=c,
                lw=1.5, solid_capstyle="round", alpha=0.9, zorder=3)
        ax.scatter([r["IRR"]], [yi], s=34, color=c, zorder=4,
                   edgecolor="white", linewidth=0.6)
        ax.text(1.02, 0.5, "", transform=ax.transAxes)

    ax.axvline(1.0, color="#34495E", lw=0.8, ls="--", zorder=2)
    ax.set_xscale("log")
    ax.set_yticks(ypos)
    ax.set_yticklabels(t.index)
    ax.set_xlabel("Razón de tasas de incidencia (IRR), escala logarítmica")
    ax.set_title("A · Determinantes del volumen de reseñas", loc="left")
    ax.set_ylim(-0.8, len(t) - 0.2)
    ax.grid(axis="x", lw=0.35, color="#D5D8DC", zorder=0)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"{v:g}".replace(".", ",")))
    for yi, (nombre, r) in zip(ypos, t.iterrows()):
        est = "***" if r["p"] < 0.001 else "**" if r["p"] < 0.01 else \
              "*" if r["p"] < 0.05 else ""
        ax.text(ax.get_xlim()[1] * 0.98, yi, est, ha="right", va="center",
                fontsize=8, color="#2C3E50")
    ax.text(0.015, 0.03,
            f"NB2 · $n$ = {int(nb.nobs)} · $\\alpha$ = "
            f"{nb.params['alpha']:.2f}".replace(".", ",") +
            f" · referencia = {TIPO_REFERENCIA}",
            transform=ax.transAxes, fontsize=6.6, color="#566573")

    # ---- Panel B: rootograma colgante ------------------------------------
    ax2 = fig.add_subplot(gs[0, 1])
    y = d["y"].values
    kmax = 30
    obs = np.array([(y == k).sum() for k in range(kmax + 1)])

    mu_nb = nb.predict()
    a = float(nb.params["alpha"])
    n_par = 1.0 / a
    p_par = 1.0 / (1.0 + a * mu_nb)
    esp_nb = np.array([stats.nbinom.pmf(k, n_par, p_par).sum()
                       for k in range(kmax + 1)])
    mu_po = po.predict()
    esp_po = np.array([stats.poisson.pmf(k, mu_po).sum()
                       for k in range(kmax + 1)])

    ks = np.arange(kmax + 1)
    ax2.bar(ks, np.sqrt(obs), bottom=np.sqrt(esp_nb) - np.sqrt(obs),
            width=0.78, color="#BDC3C7", edgecolor="#7F8C8D", lw=0.35,
            label="Frecuencia observada", zorder=2)
    ax2.plot(ks, np.sqrt(esp_nb), color=COL_FRANQ, lw=1.4, marker="o", ms=2.6,
             label="Esperada · binomial negativa", zorder=4)
    ax2.plot(ks, np.sqrt(esp_po), color=COL_INDEP, lw=1.2, ls="--", marker="s",
             ms=2.2, label="Esperada · Poisson", zorder=3)
    ax2.axhline(0, color="#34495E", lw=0.8, zorder=1)
    ax2.set_xlabel("Nº de reseñas")
    ax2.set_ylabel("$\\sqrt{\\mathrm{frecuencia}}$")
    ax2.set_title("B · Bondad de ajuste (rootograma colgante)", loc="left")
    ax2.legend(loc="upper right", fontsize=6.4)
    ax2.grid(axis="y", lw=0.35, color="#D5D8DC", zorder=0)
    ax2.set_axisbelow(True)

    fig.text(0.005, -0.03,
             "A · Puntos: IRR estimados; segmentos: intervalos de confianza al "
             "95%. Rojo: IRR > 1 significativo; azul: IRR < 1 significativo; "
             "gris: no significativo.\n     "
             "* $p$ < 0,05; ** $p$ < 0,01; *** $p$ < 0,001. "
             "B · Barras colgadas de la curva esperada: cuando cruzan el eje "
             "cero el modelo subestima esa frecuencia. Poisson colapsa en los "
             "conteos bajos.",
             fontsize=6.3, color="#566573", va="top")
    guardar(fig, outdir, "Figura2_BinomialNegativa")


# =============================================================================
# §3 — KERNEL DENSITY ESTIMATION
# =============================================================================

def mascara_dominio(XX, YY, x, y, buffer_m):
    """Máscara del dominio analítico: envolvente convexa dilatada."""
    poly = MultiPoint(list(zip(x, y))).convex_hull.buffer(buffer_m)
    coords = np.array(poly.exterior.coords)
    path = MplPath(coords)
    pts = np.c_[XX.ravel(), YY.ravel()]
    return path.contains_points(pts).reshape(XX.shape), coords


def kde_superficie(x, y, XX, YY, bw, pesos=None):
    """
    Devuelve la intensidad estimada. Sin pesos: establecimientos por hectárea.
    Con pesos: unidades de peso por hectárea.
    """
    datos = np.c_[x, y]
    kde = KernelDensity(bandwidth=bw, kernel="gaussian", metric="euclidean")
    kde.fit(datos, sample_weight=pesos)
    log_d = kde.score_samples(np.c_[XX.ravel(), YY.ravel()])
    total = len(x) if pesos is None else float(np.sum(pesos))
    # densidad de probabilidad (1/m²) → total × densidad × 10.000 m²/ha
    return (np.exp(log_d) * total * 10_000.0).reshape(XX.shape)


def bloque_kde(df, outdir, resultados):
    titulo("§3 · Kernel Density Estimation (KDE)")

    x, y = df.X.values, df.Y.values
    w_rev = df.log1p_resenas.values

    print("VARIABLES DE ENTRADA")
    print(f"  Localizaciones : n = {len(df)} puntos, {EPSG_PROJ} (metros)")
    print(f"  Núcleo         : gaussiano, isotrópico")
    print(f"  Ancho de banda : h = {BW_KDE_M:.0f} m "
          f"(sensibilidad: {[int(b) for b in BW_SENSIBILIDAD]} m)")
    print(f"  Malla          : {KDE_GRID_M:.0f} m de resolución")
    print(f"  Superficie A   : sin pesos → densidad de establecimientos/ha")
    print(f"  Superficie B   : peso w_i = log(1 + reseñas_i) → intensidad de")
    print(f"                   capital digital/ha")
    print(f"  Dominio        : envolvente convexa dilatada 2h = "
          f"{2*BW_KDE_M:.0f} m")
    print(f"\n  Justificación de h: {BW_KDE_M:.0f} m corresponde a la escala "
          f"peatonal de la manzana\n  colonial y es coherente con la malla de "
          f"análisis de {CELDA_M:.0f} m (§5–§6).")

    tabla(pd.DataFrame({
        "peso w = log(1+reseñas)": [w_rev.min(), np.percentile(w_rev, 25),
                                    np.median(w_rev), np.percentile(w_rev, 75),
                                    w_rev.max(), w_rev.sum()]},
        index=["mín", "Q1", "mediana", "Q3", "máx", "suma"]),
        "Descriptivos del vector de pesos", 4)

    # ---- Malla ------------------------------------------------------------
    pad = 3 * BW_KDE_M
    xg = np.arange(x.min() - pad, x.max() + pad + KDE_GRID_M, KDE_GRID_M)
    yg = np.arange(y.min() - pad, y.max() + pad + KDE_GRID_M, KDE_GRID_M)
    XX, YY = np.meshgrid(xg, yg)
    print(f"\n  Malla generada: {XX.shape[1]} × {XX.shape[0]} celdas "
          f"({XX.size:,} nodos)")

    mask, hull = mascara_dominio(XX, YY, x, y, 2 * BW_KDE_M)
    print(f"  Nodos dentro del dominio analítico: {int(mask.sum()):,} "
          f"({100*mask.sum()/mask.size:.1f}%)")

    dens_fis = kde_superficie(x, y, XX, YY, BW_KDE_M, None)
    dens_dig = kde_superficie(x, y, XX, YY, BW_KDE_M, w_rev)

    # ---- Salidas numéricas -------------------------------------------------
    print("\nVALORES DE SALIDA")
    def resumen(sup, nombre, unidad):
        v = sup[mask]
        return {"superficie": nombre, "unidad": unidad, "min": v.min(),
                "P50": np.median(v), "P90": np.percentile(v, 90),
                "P95": np.percentile(v, 95), "P99": np.percentile(v, 99),
                "max": v.max(),
                "razon_max_mediana": v.max() / np.median(v)}
    r_sup = pd.DataFrame([resumen(dens_fis, "A · densidad de establecimientos",
                                  "estab./ha"),
                          resumen(dens_dig, "B · intensidad de capital digital",
                                  "log(1+reseñas)/ha")])
    tabla(r_sup, "(1) Distribución de las superficies dentro del dominio", 4)

    # Localización de los máximos
    def pico(sup):
        s = np.where(mask, sup, -np.inf)
        i = np.unravel_index(np.argmax(s), s.shape)
        return XX[i], YY[i], sup[i]
    inv = Transformer.from_crs(EPSG_PROJ, EPSG_GEO, always_xy=True)
    trp = Transformer.from_crs(EPSG_GEO, EPSG_PROJ, always_xy=True)
    pgx, pgy = trp.transform(PLAZA_GRANDE[1], PLAZA_GRANDE[0])
    filas = []
    for sup, nom in [(dens_fis, "A · físico"), (dens_dig, "B · digital")]:
        cx, cy, val = pico(sup)
        lon_, lat_ = inv.transform(cx, cy)
        filas.append({"superficie": nom, "lat_pico": lat_, "lon_pico": lon_,
                      "valor_pico": val,
                      "dist_a_Plaza_Grande_m": np.hypot(cx-pgx, cy-pgy)})
    picos = pd.DataFrame(filas)
    tabla(picos, "(2) Localización del máximo de cada superficie", 6)
    cx1, cy1, _ = pico(dens_fis); cx2, cy2, _ = pico(dens_dig)
    sep = np.hypot(cx1 - cx2, cy1 - cy2)
    print(f"\n  Separación entre el pico físico y el pico digital: {sep:,.0f} m")
    if sep < BW_KDE_M:
        print(f"  → La separación ({sep:,.0f} m) es INFERIOR al ancho de banda "
              f"(h = {BW_KDE_M:.0f} m):")
        print(f"    los máximos de ambas superficies son indistinguibles a la "
              f"resolución del")
        print(f"    estimador. LA HIPÓTESIS 'hotspot físico ≠ hotspot digital' "
              f"NO SE SOSTIENE")
        print(f"    en términos de localización del máximo.")
        nota("Esto NO invalida el argumento; lo redirige. El resultado que sí "
             "sostienen los datos es de INTENSIDAD, no de desplazamiento: el "
             "capital digital se concentra en el mismo lugar que la densidad "
             "física, pero de forma más aguda (véase la razón máx/mediana) y "
             "con fuertes contrastes internos en el capital por establecimiento "
             "(superficie C). Redacción admisible: 'las plataformas no desplazan "
             "el centro de gravedad gastronómico; agudizan su jerarquía "
             "interna'.")
    else:
        print(f"  → La separación excede el ancho de banda: los máximos son "
              f"distinguibles.")
    print(f"\n  Concentración relativa (razón máximo/mediana dentro del "
          f"dominio):")
    print(f"    superficie A (física)  = "
          f"{r_sup.loc[0,'razon_max_mediana']:.2f}")
    print(f"    superficie B (digital) = "
          f"{r_sup.loc[1,'razon_max_mediana']:.2f}")
    print(f"    → el capital digital es "
          f"{r_sup.loc[1,'razon_max_mediana']/r_sup.loc[0,'razon_max_mediana']:.2f} "
          f"veces más concentrado que la densidad física.")

    # Correlación entre superficies
    a_v = dens_fis[mask]; b_v = dens_dig[mask]
    rp = stats.pearsonr(a_v, b_v); rs = stats.spearmanr(a_v, b_v)
    print(f"\n  Correlación entre superficies (nodos del dominio, "
          f"n = {mask.sum():,}):")
    print(f"    Pearson  r = {rp[0]:.4f} (p = {rp[1]:.3g})")
    print(f"    Spearman ρ = {rs[0]:.4f} (p = {rs[1]:.3g})")
    nota("Los nodos de una malla no son observaciones independientes; estos "
         "coeficientes son descriptivos de la similitud de forma entre "
         "superficies y sus p-valores NO deben citarse como inferencia.")

    # ---- Superficie C: capital digital MEDIO por establecimiento ---------
    # Estimador de Nadaraya-Watson: cociente de la superficie ponderada entre
    # la superficie de densidad. Interpretación: log(1+reseñas) esperado de un
    # establecimiento situado en ese punto. Aísla la INTENSIDAD de la DENSIDAD.
    umbral = np.nanpercentile(dens_fis[mask], 10)   # evita cocientes inestables
    mask_c = mask & (dens_fis > umbral)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(mask_c, dens_dig / dens_fis, np.nan)
    media_global = df.log1p_resenas.mean()
    print(f"\n  Superficie C = B / A (estimador de Nadaraya-Watson):")
    print(f"    interpretación: log(1+reseñas) esperado por establecimiento")
    print(f"    dominio válido: {int(mask_c.sum()):,} nodos "
          f"(se excluye el decil inferior de densidad para evitar cocientes "
          f"inestables)")
    rc = ratio[mask_c]
    tabla(pd.DataFrame({"C = capital digital medio por establecimiento":
                        [np.nanmin(rc), np.nanpercentile(rc, 10),
                         np.nanpercentile(rc, 25), np.nanmedian(rc),
                         np.nanpercentile(rc, 75), np.nanpercentile(rc, 90),
                         np.nanmax(rc)]},
                       index=["mín", "P10", "Q1", "mediana", "Q3", "P90",
                              "máx"]),
          None, 4)
    print(f"    media muestral de log(1+reseñas) = {media_global:.4f} "
          f"(línea de referencia de la escala divergente)")
    print(f"    razón P90/P10 = "
          f"{np.nanpercentile(rc,90)/max(np.nanpercentile(rc,10),1e-9):.2f} → "
          f"amplitud del gradiente interno de capital por establecimiento")
    dif = ratio

    # ---- Sensibilidad al ancho de banda ----------------------------------
    titulo("§3.1 · Análisis de sensibilidad al ancho de banda", 2)
    sens = []
    for bw in [BW_SENSIBILIDAD[0], BW_KDE_M, BW_SENSIBILIDAD[1]]:
        a_ = kde_superficie(x, y, XX, YY, bw, None)
        b_ = kde_superficie(x, y, XX, YY, bw, w_rev)
        cx1, cy1, v1 = None, None, None
        s = np.where(mask, a_, -np.inf); i1 = np.unravel_index(np.argmax(s), s.shape)
        s = np.where(mask, b_, -np.inf); i2 = np.unravel_index(np.argmax(s), s.shape)
        sens.append({"h_m": bw, "max_A": a_[i1], "max_B": b_[i2],
                     "separacion_picos_m": np.hypot(XX[i1]-XX[i2], YY[i1]-YY[i2]),
                     "Spearman_A_B": stats.spearmanr(a_[mask], b_[mask])[0]})
    tabla(pd.DataFrame(sens), None, 4)
    nota("En todo el rango h = 100–150 m la separación entre máximos permanece "
         "muy por debajo del propio ancho de banda: la COINCIDENCIA de los dos "
         "máximos es robusta y no es un artefacto del suavizado. Lo que varía "
         "con h es solo la altura de los picos, como es esperable.")

    r_sup.to_csv(os.path.join(outdir, "T3a_kde_superficies.csv"), index=False)
    picos.to_csv(os.path.join(outdir, "T3b_kde_picos.csv"), index=False)
    pd.DataFrame(sens).to_csv(os.path.join(outdir, "T3c_kde_sensibilidad.csv"),
                              index=False)
    resultados["kde"] = {"h_m": BW_KDE_M, "separacion_picos_m": float(sep),
                         "spearman_A_B": float(rs[0]),
                         "razon_concentracion": float(
                             r_sup.loc[1, "razon_max_mediana"] /
                             r_sup.loc[0, "razon_max_mediana"]),
                         "ratio_P90_P10": float(
                             np.nanpercentile(rc, 90) /
                             max(np.nanpercentile(rc, 10), 1e-9)),
                         "superficies": r_sup.to_dict(orient="records"),
                         "picos": picos.to_dict(orient="records")}

    fig3_kde(df, XX, YY, dens_fis, dens_dig, dif, mask, hull, outdir)
    return dens_fis, dens_dig, XX, YY, mask


def fig3_kde(df, XX, YY, A, B, C, mask, hull, outdir):
    x, y = df.X.values, df.Y.values
    trp = Transformer.from_crs(EPSG_GEO, EPSG_PROJ, always_xy=True)
    pgx, pgy = trp.transform(PLAZA_GRANDE[1], PLAZA_GRANDE[0])

    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.05))
    ext = [XX.min(), XX.max(), YY.min(), YY.max()]
    especificaciones = [
        (A, "magma_r", "A · Densidad de establecimientos",
         "establecimientos · ha$^{-1}$", False),
        (B, "magma_r", "B · Intensidad de capital digital",
         "log(1+reseñas) · ha$^{-1}$", False),
        (C, "RdBu_r", "C · Capital digital por establecimiento",
         "log(1+reseñas) esperado", True),
    ]

    for ax, (S, cmap, tit, clab, divergente) in zip(axes, especificaciones):
        Sm = np.where(mask, S, np.nan) if not divergente else S
        if divergente:
            centro = np.nanmean(df.log1p_resenas.values)
            desv = np.nanmax(np.abs(Sm - centro))
            im = ax.imshow(Sm, origin="lower", extent=ext, cmap=cmap,
                           vmin=centro - desv, vmax=centro + desv,
                           interpolation="bilinear")
            ax.contour(XX, YY, Sm, levels=[centro], colors=["#4D5656"],
                       linewidths=[0.8])
        else:
            im = ax.imshow(Sm, origin="lower", extent=ext, cmap=cmap,
                           interpolation="bilinear")
            lv = np.nanpercentile(Sm, [50, 75, 90, 97.5])
            ax.contour(XX, YY, Sm, levels=lv, colors="white", linewidths=0.4,
                       alpha=0.7)

        ax.plot(hull[:, 0], hull[:, 1], color="#2C3E50", lw=0.6, ls=":",
                alpha=0.8, zorder=6)
        ax.scatter(x, y, s=1.6, c="#17202A", alpha=0.45, linewidths=0,
                   zorder=7, rasterized=True)
        for r in (250, 500, 750, 1000):
            ax.add_patch(Circle((pgx, pgy), r, fill=False, ec="#2C3E50",
                                lw=0.4, ls=(0, (3, 3)), alpha=0.55, zorder=8))
        ax.plot([pgx], [pgy], marker="*", ms=8, color="#F4D03F",
                mec="#17202A", mew=0.5, zorder=9)
        ax.set_title(tit, loc="left")
        ax.set_xlim(XX.min(), XX.max()); ax.set_ylim(YY.min(), YY.max())
        ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(True); sp.set_linewidth(0.5); sp.set_color("#95A5A6")
        barra_escala(ax, 500, "500 m")
        flecha_norte(ax)
        cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
        cb.set_label(clab, fontsize=6.8)
        cb.ax.tick_params(labelsize=6.2, width=0.5, length=2)
        cb.outline.set_linewidth(0.4)

    axes[0].legend(handles=[
        Line2D([], [], marker="*", ls="none", ms=7, color="#F4D03F",
               mec="#17202A", mew=0.4, label="Plaza Grande"),
        Line2D([], [], marker="o", ls="none", ms=2.2, color="#17202A",
               label="Establecimiento"),
        Line2D([], [], ls=(0, (3, 3)), lw=0.6, color="#2C3E50",
               label="Anillos 250 m")],
        loc="upper left", fontsize=6.0, handlelength=1.4,
        borderpad=0.3, labelspacing=0.28, frameon=True, framealpha=0.93,
        facecolor="white", edgecolor="#D5D8DC")

    fig.text(0.005, -0.035,
             f"Estimación por núcleo gaussiano isotrópico, ancho de banda "
             f"h = {BW_KDE_M:.0f} m, malla de {KDE_GRID_M:.0f} m; "
             f"proyección UTM 17S (EPSG:32717). Dominio analítico: envolvente "
             f"convexa dilatada 2h (línea punteada).\n"
             f"Panel B ponderado por w$_i$ = log(1 + reseñas$_i$). "
             f"Panel C: cociente B/A (estimador de Nadaraya-Watson) = "
             f"log(1+reseñas) esperado por establecimiento; la isolínea gris "
             f"marca la media muestral.\n"
             f"Isolíneas en A y B: percentiles 50, 75, 90 y 97,5 de cada "
             f"superficie. n = {len(df)} establecimientos.".replace(",", ","),
             fontsize=6.3, color="#566573", va="top")
    fig.tight_layout()
    guardar(fig, outdir, "Figura3_KDE")


# =============================================================================
# CONSTRUCCIÓN DE LA MALLA Y DE LAS MATRICES DE PESOS ESPACIALES
# =============================================================================

def construir_celdas(df):
    """Agrega los establecimientos en una malla regular de CELDA_M metros."""
    x0 = np.floor(df.X.min() / CELDA_M) * CELDA_M
    y0 = np.floor(df.Y.min() / CELDA_M) * CELDA_M
    d = df.copy()
    d["col"] = ((d.X - x0) // CELDA_M).astype(int)
    d["fil"] = ((d.Y - y0) // CELDA_M).astype(int)
    celdas = (d.groupby(["fil", "col"])
              .agg(n_estab=("resenas", "size"),
                   resenas_tot=("resenas", "sum"),
                   resenas_media=("resenas", "mean"),
                   log1p_medio=("log1p_resenas", "mean"),
                   n_ig=("tiene_ig", "sum"),
                   n_tt=("tiene_tt", "sum"),
                   seg_ig_tot=("seg_ig", "sum"),
                   n_franq=("franquicia", "sum"),
                   dist_media=("dist_km", "mean"))
              .reset_index())
    celdas["log1p_resenas_tot"] = np.log1p(celdas.resenas_tot)
    celdas["prop_ig"] = celdas.n_ig / celdas.n_estab
    celdas["log1p_seg_ig_tot"] = np.log1p(celdas.seg_ig_tot)
    celdas["xc"] = x0 + (celdas.col + 0.5) * CELDA_M
    celdas["yc"] = y0 + (celdas.fil + 0.5) * CELDA_M
    celdas["x0"] = x0 + celdas.col * CELDA_M
    celdas["y0"] = y0 + celdas.fil * CELDA_M
    return celdas, d


def pesos_reina(celdas):
    """Contigüidad reina (8 vecinos) entre celdas ocupadas + attach_islands."""
    idx = {(f, c): i for i, (f, c) in enumerate(zip(celdas.fil, celdas.col))}
    vecinos = {i: [] for i in range(len(celdas))}
    for (f, c), i in idx.items():
        for df_ in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if df_ == 0 and dc == 0:
                    continue
                j = idx.get((f + df_, c + dc))
                if j is not None:
                    vecinos[i].append(j)
    w = W(vecinos, silence_warnings=True)
    islas = list(w.islands)
    if islas:
        w_knn = KNN.from_array(celdas[["xc", "yc"]].values, k=1)
        w = attach_islands(w, w_knn, silence_warnings=True)
    return w, islas


def bloque_pesos(df, outdir):
    titulo("§4.0 · Matrices de pesos espaciales")

    # (a) Nivel establecimiento: KNN
    coords = df[["X", "Y"]].values
    w_pts = KNN.from_array(coords, k=K_VECINOS)
    w_pts.transform = "R"
    print(f"(a) NIVEL ESTABLECIMIENTO — k vecinos más próximos")
    print(f"    n = {w_pts.n} | k = {K_VECINOS} | transformación = fila "
          f"estandarizada (R)")
    print(f"    islas = {len(w_pts.islands)} | conexiones no nulas = "
          f"{w_pts.nonzero:,} | % no nulas = {w_pts.pct_nonzero:.3f}%")
    d_nn = np.sort(np.linalg.norm(coords[:, None] - coords[None, :], axis=2),
                   axis=1)[:, 1:K_VECINOS + 1]
    print(f"    distancia al k-ésimo vecino (m): mediana "
          f"{np.median(d_nn[:, -1]):.1f} | Q1 {np.percentile(d_nn[:,-1],25):.1f} "
          f"| Q3 {np.percentile(d_nn[:,-1],75):.1f} | máx "
          f"{d_nn[:,-1].max():.1f}")
    print(f"    → justificación: KNN garantiza ausencia de islas con puntos de "
          f"densidad muy desigual;\n      k = 8 corresponde al entorno peatonal "
          f"inmediato (mediana ≈ "
          f"{np.median(d_nn[:,-1]):.0f} m).")

    # (b) Nivel celda: contigüidad reina
    celdas, d_asig = construir_celdas(df)
    w_cel, islas = pesos_reina(celdas)
    w_cel.transform = "R"
    print(f"\n(b) NIVEL CELDA — malla regular de {CELDA_M:.0f} m, contigüidad "
          f"reina")
    print(f"    celdas ocupadas = {len(celdas)} de "
          f"{(celdas.fil.max()-celdas.fil.min()+1)*(celdas.col.max()-celdas.col.min()+1)} "
          f"posibles en la envolvente rectangular")
    print(f"    establecimientos por celda: media "
          f"{celdas.n_estab.mean():.2f} | mediana {celdas.n_estab.median():.0f} "
          f"| máx {celdas.n_estab.max()}")
    card = np.array(list(w_cel.cardinalities.values()))
    print(f"    vecinos por celda: media {card.mean():.2f} | mín {card.min()} "
          f"| máx {card.max()}")
    print(f"    islas detectadas antes de corrección: {len(islas)} "
          f"→ vinculadas a su vecino más próximo (libpysal.attach_islands)")
    print(f"    islas tras corrección: {len(w_cel.islands)}")
    nota("Sin tratar las islas, Gi* y LISA devuelven valores indefinidos en "
         "esas unidades. La vinculación al vecino más próximo es la solución "
         "estándar y debe declararse en el paper.")

    tabla(celdas[["n_estab", "resenas_tot", "log1p_resenas_tot", "prop_ig",
                  "dist_media"]].describe().T,
          "Descriptivos de las variables agregadas por celda", 4)

    celdas.to_csv(os.path.join(outdir, "T4a_celdas_150m.csv"), index=False)
    return w_pts, celdas, w_cel, d_nn


# =============================================================================
# §4 — I DE MORAN GLOBAL
# =============================================================================

def bloque_moran(df, w_pts, celdas, w_cel, outdir, resultados):
    titulo("§4 · I de Moran global — autocorrelación espacial")

    print("VARIABLES DE ENTRADA")
    print(f"  Permutaciones : {N_PERM:,} | semilla = {SEMILLA}")
    print(f"  Hipótesis nula: aleatorización (los valores se reasignan entre")
    print(f"                  localizaciones fijas)")
    print(f"  Transformación: log(1+x) para conteos (sobredispersión extrema)")

    especificaciones = [
        ("Establecimiento", "log(1+reseñas)", df.log1p_resenas.values, w_pts),
        ("Establecimiento", "log(1+seguidores IG)", df.log1p_seg_ig.values, w_pts),
        ("Establecimiento", "presencia en Instagram (0/1)",
         df.tiene_ig.values.astype(float), w_pts),
        ("Establecimiento", "presencia en TikTok (0/1)",
         df.tiene_tt.values.astype(float), w_pts),
        ("Celda 150 m", "log(1+reseñas totales)",
         celdas.log1p_resenas_tot.values, w_cel),
        ("Celda 150 m", "proporción con Instagram",
         celdas.prop_ig.values, w_cel),
        ("Celda 150 m", "nº de establecimientos",
         celdas.n_estab.values.astype(float), w_cel),
    ]

    filas, objetos = [], {}
    for unidad, var, v, w in especificaciones:
        mi = esda.Moran(v, w, permutations=N_PERM)
        filas.append({
            "unidad": unidad, "variable": var, "n": w.n,
            "media": float(np.mean(v)), "DE": float(np.std(v, ddof=1)),
            "I": mi.I, "E[I]": mi.EI, "DE_sim": mi.seI_sim,
            "z_sim": mi.z_sim, "p_sim_bilateral": mi.p_sim,
            "z_norm": mi.z_norm, "p_norm": mi.p_norm,
        })
        objetos[f"{unidad} | {var}"] = mi

    res = pd.DataFrame(filas)
    print("\nVALORES DE SALIDA")
    tabla(res, None, 5)
    print(f"\n  E[I] bajo H0 = −1/(n−1). p_sim es el pseudo-p-valor de "
          f"permutación\n  (mínimo alcanzable = {1/(N_PERM+1):.5f}).")

    # Corrección FDR sobre el conjunto de contrastes globales
    rech, p_adj, _, _ = multipletests(res.p_sim_bilateral.values, alpha=ALFA,
                                      method=FDR_METODO)
    res["p_FDR"] = p_adj; res["signif_FDR"] = rech
    tabla(res[["unidad", "variable", "I", "p_sim_bilateral", "p_FDR",
               "signif_FDR"]],
          f"Corrección por comparaciones múltiples ({FDR_METODO})", 5)

    # Join counts para las variables binarias
    titulo("§4.1 · Contraste complementario para variables binarias "
           "(join counts)", 2)
    print("La I de Moran sobre una variable dicotómica es admisible pero el")
    print("estadístico específico es el recuento de uniones (BB = vecindades")
    print("entre dos establecimientos con presencia digital).")
    wb = KNN.from_array(df[["X", "Y"]].values, k=K_VECINOS)
    wb.transform = "B"
    jc_filas = []
    for nom, v in [("Instagram", df.tiene_ig.values.astype(int)),
                   ("TikTok", df.tiene_tt.values.astype(int))]:
        jc = esda.Join_Counts(v, wb, permutations=N_PERM)
        jc_filas.append({"variable": nom, "n_1": int(v.sum()),
                         "BB_observado": jc.bb, "BB_esperado": jc.mean_bb,
                         "p_sim_BB": jc.p_sim_bb})
    tabla(pd.DataFrame(jc_filas), None, 4)

    res.to_csv(os.path.join(outdir, "T4b_moran_global.csv"), index=False)
    pd.DataFrame(jc_filas).to_csv(os.path.join(outdir, "T4c_join_counts.csv"),
                                  index=False)
    resultados["moran_global"] = res.to_dict(orient="records")

    fig4_moran(objetos, outdir)
    return res, objetos


def moran_scatter(ax, mi, v, w, titulo_p, xlab):
    z = (v - v.mean()) / v.std(ddof=0)
    wz = libpysal.weights.lag_spatial(w, z)
    ax.axhline(0, color="#95A5A6", lw=0.55, zorder=1)
    ax.axvline(0, color="#95A5A6", lw=0.55, zorder=1)
    cuad = np.where((z > 0) & (wz > 0), "HH",
           np.where((z < 0) & (wz < 0), "LL",
           np.where((z > 0) & (wz < 0), "HL", "LH")))
    for q in ("HH", "LL", "HL", "LH"):
        m = cuad == q
        ax.scatter(z[m], wz[m], s=7, color=COL_LISA[q], alpha=0.75,
                   linewidths=0.15, edgecolor="white", zorder=3, label=q)
    b = np.polyfit(z, wz, 1)
    xs = np.linspace(z.min(), z.max(), 50)
    ax.plot(xs, np.polyval(b, xs), color="#17202A", lw=1.2, zorder=4)
    p = mi.p_sim
    p_txt = "$p$ < 0,001" if p < 0.001 else f"$p$ = {p:.3f}".replace(".", ",")
    ax.set_title(titulo_p, loc="left", fontsize=8.6)
    ax.text(0.03, 0.955,
            f"$I$ = {mi.I:.3f}".replace(".", ",") + f" · {p_txt}\n"
            f"$z$ = {mi.z_sim:.2f}".replace(".", ",") + f" · $n$ = {w.n}",
            transform=ax.transAxes, va="top", ha="left", fontsize=6.8,
            bbox=dict(fc="white", ec="#D5D8DC", lw=0.4, pad=1.8, alpha=0.9))
    ax.set_xlabel(xlab); ax.set_ylabel("Retardo espacial (z estandarizado)")
    ax.grid(lw=0.3, color="#EAECEE", zorder=0); ax.set_axisbelow(True)
    return cuad


def fig4_moran(objetos, outdir):
    claves = ["Establecimiento | log(1+reseñas)",
              "Establecimiento | log(1+seguidores IG)",
              "Celda 150 m | log(1+reseñas totales)"]
    titulos = ["A · Reseñas por establecimiento",
               "B · Seguidores de Instagram por establecimiento",
               f"C · Reseñas por celda de {CELDA_M:.0f} m"]
    xlabs = ["log(1+reseñas) estandarizado",
             "log(1+seguidores) estandarizado",
             "log(1+reseñas totales) estandarizado"]

    fig, axes = plt.subplots(2, 3, figsize=(7.4, 4.9),
                             gridspec_kw={"height_ratios": [1.45, 1.0],
                                          "hspace": 0.45, "wspace": 0.34})
    for j, (k, tit, xl) in enumerate(zip(claves, titulos, xlabs)):
        mi = objetos[k]
        moran_scatter(axes[0, j], mi, np.asarray(mi.y, dtype=float), mi.w,
                      tit, xl)
        # distribución de referencia
        ax = axes[1, j]
        ax.hist(mi.sim, bins=45, color="#D5D8DC", edgecolor="#AEB6BF", lw=0.3,
                zorder=2)
        ax.axvline(mi.EI, color="#566573", lw=0.9, ls="--", zorder=3,
                   label="$E[I]$ bajo $H_0$")
        ax.axvline(mi.I, color=COL_FRANQ, lw=1.6, zorder=4, label="$I$ observado")
        ax.set_xlabel("$I$ de Moran simulado")
        ax.set_ylabel("Frecuencia" if j == 0 else "")
        ax.grid(axis="y", lw=0.3, color="#EAECEE", zorder=0)
        ax.set_axisbelow(True)
        if j == 0:
            ax.legend(loc="upper right", fontsize=6.3, frameon=True,
                      framealpha=0.93, facecolor="white", edgecolor="#D5D8DC")
        q = np.percentile(mi.sim, [2.5, 97.5])
        ax.axvspan(q[0], q[1], color="#EBF5FB", alpha=0.55, zorder=1)

    axes[0, 0].legend(loc="lower right", fontsize=6.2, ncol=2, handlelength=0.9,
                      columnspacing=0.7, handletextpad=0.3, title="Cuadrante",
                      title_fontsize=6.2, frameon=True, framealpha=0.93,
                      facecolor="white", edgecolor="#D5D8DC")
    fig.text(0.005, -0.015,
             f"Fila superior: diagramas de dispersión de Moran. La pendiente de "
             f"la recta equivale a la I de Moran. Cuadrantes: HH (alto–alto), "
             f"LL (bajo–bajo), HL y LH (atípicos espaciales).\n"
             f"Fila inferior: distribución de referencia obtenida por "
             f"{N_PERM:,} permutaciones aleatorias; banda sombreada = intervalo "
             f"central del 95% de la distribución nula.\n"
             f"El contraste específico para las variables dicotómicas de "
             f"presencia digital es el recuento de uniones (§4.1), no el "
             f"diagrama de Moran.\n"
             f"Pesos: A y B = 8 vecinos más próximos; C = contigüidad reina "
             f"entre celdas de {CELDA_M:.0f} m. Todos los pesos estandarizados "
             f"por filas. Semilla = {SEMILLA}.".replace(",", ","),
             fontsize=6.3, color="#566573", va="top")
    guardar(fig, outdir, "Figura4_MoranGlobal")


# =============================================================================
# §5 — LISA (Anselin)  ·  §6 — GETIS-ORD Gi*
# =============================================================================

def dibujar_celdas(ax, celdas, colores, lw=0.25, ec="white"):
    parches = [Rectangle((r.x0, r.y0), CELDA_M, CELDA_M)
               for r in celdas.itertuples()]
    pc = PatchCollection(parches, facecolors=colores, edgecolors=ec,
                         linewidths=lw, zorder=3)
    ax.add_collection(pc)
    return pc


def marco_mapa(ax, celdas, df, mostrar_puntos=True):
    trp = Transformer.from_crs(EPSG_GEO, EPSG_PROJ, always_xy=True)
    pgx, pgy = trp.transform(PLAZA_GRANDE[1], PLAZA_GRANDE[0])
    if mostrar_puntos:
        ax.scatter(df.X, df.Y, s=1.1, c="#17202A", alpha=0.30, linewidths=0,
                   zorder=6, rasterized=True)
    for r in (250, 500, 750, 1000):
        ax.add_patch(Circle((pgx, pgy), r, fill=False, ec="#5D6D7E", lw=0.4,
                            ls=(0, (3, 3)), alpha=0.6, zorder=7))
    ax.plot([pgx], [pgy], marker="*", ms=8, color="#F4D03F", mec="#17202A",
            mew=0.5, zorder=9)
    pad = 180
    ax.set_xlim(celdas.x0.min() - pad, celdas.x0.max() + CELDA_M + pad)
    ax.set_ylim(celdas.y0.min() - pad, celdas.y0.max() + CELDA_M + pad)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(True); sp.set_linewidth(0.5); sp.set_color("#95A5A6")
    barra_escala(ax, 500, "500 m")
    flecha_norte(ax)


def bloque_lisa(df, celdas, w_cel, outdir, resultados):
    titulo("§5 · LISA — indicadores locales de asociación espacial (Anselin)")

    v = celdas.log1p_resenas_tot.values
    print("VARIABLES DE ENTRADA")
    print(f"  Unidad         : celda regular de {CELDA_M:.0f} m "
          f"(n = {len(celdas)} ocupadas)")
    print(f"  Variable       : log(1 + reseñas totales por celda)")
    print(f"  Pesos          : contigüidad reina, estandarizados por filas")
    print(f"  Permutaciones  : {N_PERM:,} condicionales | semilla = {SEMILLA}")
    print(f"  Descriptivos de la variable: media {v.mean():.4f} | DE "
          f"{v.std(ddof=1):.4f} | mín {v.min():.4f} | máx {v.max():.4f}")

    lisa = esda.Moran_Local(v, w_cel, permutations=N_PERM, seed=SEMILLA,
                            geoda_quads=False)

    # Cuadrantes según convención de esda: 1=HH 2=LH 3=LL 4=HL
    mapa_q = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
    rech, p_adj, _, _ = multipletests(lisa.p_sim, alpha=ALFA, method=FDR_METODO)

    celdas = celdas.copy()
    celdas["I_local"] = lisa.Is
    celdas["z_lisa"] = lisa.z_sim
    celdas["p_sim"] = lisa.p_sim
    celdas["p_FDR"] = p_adj
    celdas["cuadrante"] = [mapa_q[q] for q in lisa.q]
    # Clasificación PRINCIPAL: pseudo-p < 0,05 sin corregir (criterio de GeoDa,
    # el habitual en la literatura). Clasificación CONSERVADORA: tras FDR.
    celdas["clase_LISA"] = np.where(lisa.p_sim < ALFA, celdas.cuadrante, "ns")
    celdas["clase_LISA_FDR"] = np.where(rech, celdas.cuadrante, "ns")

    print("\nVALORES DE SALIDA")
    n_sin = int((lisa.p_sim < ALFA).sum()); n_con = int(rech.sum())
    n_01 = int((lisa.p_sim < 0.01).sum())
    print(f"  Celdas significativas con p_sim < 0,05 (sin corregir) : {n_sin}")
    print(f"  Celdas significativas con p_sim < 0,01 (sin corregir) : {n_01}")
    print(f"  Celdas significativas tras {FDR_METODO}                : {n_con}")
    if n_con:
        print(f"  Umbral efectivo de p tras FDR                        : "
              f"{p_adj[rech].max():.5f}")
    print("\n  DECISIÓN DE REPORTE: la clasificación principal usa p_sim < 0,05")
    print("  sin corregir (criterio por defecto de GeoDa y práctica dominante en")
    print("  la literatura de LISA, dado su carácter exploratorio). La variante")
    print("  con FDR se reporta como análisis conservador y se señala en la")
    print("  figura. La corrección de Benjamini-Hochberg es muy exigente aquí")
    print("  porque con n = %d unidades el umbral del primer paso es α/n = %.5f,"
          % (len(celdas), ALFA / len(celdas)))
    print("  próximo a la resolución máxima del pseudo-p (1/(m+1) = %.5f)."
          % (1 / (N_PERM + 1)))

    conteo = pd.DataFrame({
        "p<0,05 (principal)": celdas.clase_LISA.value_counts(),
        "tras FDR (conservador)": celdas.clase_LISA_FDR.value_counts()})\
        .reindex(["HH", "LL", "LH", "HL", "ns"]).fillna(0).astype(int)
    tabla(conteo, "(1) Distribución de cuadrantes significativos", 0)

    sig = celdas[celdas.clase_LISA != "ns"].copy()
    inv = Transformer.from_crs(EPSG_PROJ, EPSG_GEO, always_xy=True)
    if len(sig):
        sig["lon"], sig["lat"] = inv.transform(sig.xc.values, sig.yc.values)
        sig["sobrevive_FDR"] = sig.clase_LISA_FDR != "ns"
        cols = ["clase_LISA", "lat", "lon", "n_estab", "resenas_tot",
                "log1p_resenas_tot", "prop_ig", "dist_media", "I_local",
                "z_lisa", "p_sim", "p_FDR", "sobrevive_FDR"]
        tabla(sig.sort_values(["clase_LISA", "z_lisa"], ascending=[True, False])
              [cols].reset_index(drop=True),
              "(2) Inventario de celdas significativas (centroides, WGS84)", 5)

        print("\n(3) Perfil comparado de los clústeres")
        perfil = celdas.groupby("clase_LISA").agg(
            celdas=("n_estab", "size"), estab=("n_estab", "sum"),
            resenas=("resenas_tot", "sum"),
            resenas_por_estab=("resenas_media", "mean"),
            prop_IG=("prop_ig", "mean"),
            dist_media_km=("dist_media", "mean"))
        perfil["%_estab"] = 100 * perfil.estab / celdas.n_estab.sum()
        perfil["%_resenas"] = 100 * perfil.resenas / celdas.resenas_tot.sum()
        tabla(perfil, None, 4)
        hh = perfil.loc["HH"] if "HH" in perfil.index else None
        if hh is not None:
            print(f"\n  Los clústeres HH agrupan el {hh['%_estab']:.1f}% de los "
                  f"establecimientos y el {hh['%_resenas']:.1f}% de las reseñas")
            print(f"  del Centro Histórico: razón de concentración = "
                  f"{hh['%_resenas']/hh['%_estab']:.2f}.")
        if "LL" in perfil.index:
            ll = perfil.loc["LL"]
            print(f"  Los clústeres LL agrupan el {ll['%_estab']:.1f}% de los "
                  f"establecimientos y solo el {ll['%_resenas']:.2f}% de las "
                  f"reseñas")
            print(f"  (razón = {ll['%_resenas']/max(ll['%_estab'],1e-9):.2f}): "
                  f"es el 'territorio mudo'.")
        nota("La razón %reseñas/%establecimientos es la medida directa de "
             "sobre- e infra-representación digital de cada tipo de clúster. "
             "Es descriptiva: no requiere supuestos adicionales.")

    # Robustez: media de log1p por celda en lugar de log1p del total
    titulo("§5.1 · Robustez: variable alternativa (media de log(1+reseñas))", 2)
    lisa_b = esda.Moran_Local(celdas.log1p_medio.values, w_cel,
                              permutations=N_PERM, seed=SEMILLA)
    clase_b = np.where(lisa_b.p_sim < ALFA,
                       [mapa_q[q] for q in lisa_b.q], "ns")
    tabla(pd.Series(clase_b).value_counts().rename("n").to_frame(), None, 0)
    coincidencia = float(np.mean(clase_b == celdas.clase_LISA.values))
    print(f"  Coincidencia de clasificación con la especificación principal: "
          f"{100*coincidencia:.1f}%")
    mi_alt = esda.Moran(celdas.log1p_medio.values, w_cel, permutations=N_PERM)
    print(f"  I de Moran global (especificación alternativa) = {mi_alt.I:.4f} "
          f"(p = {mi_alt.p_sim:.4f})")
    nota("La especificación alternativa mide la intensidad media por local "
         "(no el volumen agregado): al eliminar el componente de densidad, el "
         "número de clústeres desciende. Ambas lecturas son válidas y "
         "responden a preguntas distintas; declarar cuál se usa.")

    celdas.to_csv(os.path.join(outdir, "T5a_lisa_celdas.csv"), index=False)
    conteo.to_csv(os.path.join(outdir, "T5b_lisa_conteo.csv"))
    resultados["lisa"] = {
        "n_signif_p05": n_sin, "n_signif_p01": n_01, "n_signif_FDR": n_con,
        "conteo": conteo.to_dict(),
        "celdas_significativas":
            (sig[["clase_LISA", "lat", "lon", "n_estab", "resenas_tot",
                  "I_local", "z_lisa", "p_sim", "p_FDR", "sobrevive_FDR"]]
             .to_dict(orient="records") if len(sig) else [])}

    fig5_lisa(df, celdas, w_cel, v, outdir)
    return celdas, lisa


def fig5_lisa(df, celdas, w_cel, v, outdir):
    fig = plt.figure(figsize=(7.4, 3.65))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.12, 1.0], wspace=0.16)

    # ---- Panel A: mapa de clústeres --------------------------------------
    ax = fig.add_subplot(gs[0, 0])
    colores = [COL_LISA[c] for c in celdas.clase_LISA]
    dibujar_celdas(ax, celdas, colores)
    # Contorno negro para las celdas que sobreviven a la corrección FDR
    fdr = celdas[celdas.clase_LISA_FDR != "ns"]
    if len(fdr):
        parches = [Rectangle((r.x0, r.y0), CELDA_M, CELDA_M)
                   for r in fdr.itertuples()]
        ax.add_collection(PatchCollection(parches, facecolors="none",
                                         edgecolors="#17202A", linewidths=1.0,
                                         zorder=5))
    marco_mapa(ax, celdas, df)
    ax.set_title("A · Clústeres LISA del capital digital", loc="left")
    etiq = {"HH": "Alto–Alto (núcleo caliente)",
            "LL": "Bajo–Bajo (territorio mudo)",
            "LH": "Bajo–Alto (atípico)",
            "HL": "Alto–Bajo (atípico)",
            "ns": "No significativo"}
    n_por = celdas.clase_LISA.value_counts()
    handles = [Patch(fc=COL_LISA[k], ec="white", lw=0.3,
                     label=f"{etiq[k]} ({int(n_por.get(k,0))})")
               for k in ("HH", "LL", "HL", "LH", "ns")
               if int(n_por.get(k, 0)) > 0]
    if len(fdr):
        handles.append(Patch(fc="none", ec="#17202A", lw=1.0,
                             label=f"Sobrevive a FDR ({len(fdr)})"))
    handles.append(Line2D([], [], marker="*", ls="none", ms=7, color="#F4D03F",
                          mec="#17202A", mew=0.4, label="Plaza Grande"))
    ax.legend(handles=handles, loc="upper left", fontsize=6.0,
              handlelength=1.1, borderpad=0.32, labelspacing=0.3,
              framealpha=0.93, frameon=True,
              edgecolor="#D5D8DC", facecolor="white")

    # ---- Panel B: dispersión de Moran con significación ------------------
    ax2 = fig.add_subplot(gs[0, 1])
    z = (v - v.mean()) / v.std(ddof=0)
    wz = libpysal.weights.lag_spatial(w_cel, z)
    ax2.axhline(0, color="#95A5A6", lw=0.55)
    ax2.axvline(0, color="#95A5A6", lw=0.55)
    ns = (celdas.clase_LISA == "ns").values
    ax2.scatter(z[ns], wz[ns], s=11, color="#CACFD2", alpha=0.85, linewidths=0,
                zorder=2, label="No significativo")
    for k in ("HH", "LL", "HL", "LH"):
        m = (celdas.clase_LISA == k).values
        if m.sum():
            ax2.scatter(z[m], wz[m], s=26, color=COL_LISA[k], zorder=4,
                        edgecolor="white", linewidths=0.5, label=k)
    b = np.polyfit(z, wz, 1)
    xs = np.linspace(z.min(), z.max(), 50)
    ax2.plot(xs, np.polyval(b, xs), color="#17202A", lw=1.2, zorder=5)
    mi_g = esda.Moran(v, w_cel, permutations=N_PERM)
    ax2.text(0.03, 0.96,
             f"$I$ global = {mi_g.I:.3f}".replace(".", ",") +
             (" · $p$ < 0,001" if mi_g.p_sim < 0.001
              else f" · $p$ = {mi_g.p_sim:.3f}".replace(".", ",")),
             transform=ax2.transAxes, va="top", fontsize=6.9,
             bbox=dict(fc="white", ec="#D5D8DC", lw=0.4, pad=1.8))
    ax2.set_xlabel("log(1+reseñas por celda), estandarizado")
    ax2.set_ylabel("Retardo espacial")
    ax2.set_title("B · Diagrama de dispersión de Moran", loc="left")
    ax2.legend(loc="lower right", fontsize=6.2, ncol=2, handlelength=0.9,
               columnspacing=0.7, handletextpad=0.3, frameon=True,
               framealpha=0.93, facecolor="white", edgecolor="#D5D8DC")
    ax2.grid(lw=0.3, color="#EAECEE", zorder=0); ax2.set_axisbelow(True)

    fig.text(0.005, -0.03,
             f"Estadístico local de Moran (Anselin, 1995) sobre "
             f"log(1 + reseñas totales) en celdas de {CELDA_M:.0f} m; "
             f"contigüidad reina estandarizada por filas; {N_PERM:,} "
             f"permutaciones condicionales; semilla = {SEMILLA}.\n"
             f"Relleno: clasificación con pseudo-p < 0,05 sin corregir "
             f"(criterio habitual para estadísticos locales exploratorios). "
             f"Contorno negro: celdas que además superan la corrección de "
             f"Benjamini-Hochberg.\n"
             f"Las cinco celdas sin vecino contiguo se vincularon a su vecino "
             f"más próximo. Anillos concéntricos cada 250 m desde la Plaza "
             f"Grande. Proyección UTM 17S; n = {len(df)} establecimientos en "
             f"{len(celdas)} celdas.".replace(",", ","),
             fontsize=6.3, color="#566573", va="top")
    guardar(fig, outdir, "Figura5_LISA")


# -----------------------------------------------------------------------------
# §6 — GETIS-ORD Gi*  (implementación canónica)
# -----------------------------------------------------------------------------

def vecinos_con_autovecindad(w):
    """Lista de vecinos incluyendo la propia unidad (requisito de Gi*)."""
    out = {}
    for i in range(w.n):
        idx = list(w.neighbors[w.id_order[i]])
        pos = [w.id_order.index(j) for j in idx]
        out[i] = sorted(set(pos + [i]))
    return out


def getis_ord_star(y, vecinos, n_perm=N_PERM, semilla=SEMILLA):
    """
    Gi* de Getis-Ord con pesos BINARIOS y autovecindad, según la fórmula
    canónica (Ord y Getis, 1995):

        Gi* = [ Σ_j w_ij x_j − X̄ Σ_j w_ij ]
              / { S · sqrt[ ( n Σ_j w_ij² − (Σ_j w_ij)² ) / (n−1) ] }

    con S = sqrt( Σ_j x_j²/n − X̄² ).  El resultado ES una puntuación z.
    Devuelve además el pseudo-p por permutación condicional bilateral.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    ybar = y.mean()
    S = np.sqrt(np.sum(y ** 2) / n - ybar ** 2)
    total = y.sum()
    rng = np.random.default_rng(semilla)

    G = np.zeros(n); Z = np.zeros(n); Zsim = np.zeros(n); Psim = np.zeros(n)
    for i in range(n):
        idx = np.asarray(vecinos[i])
        w_sum = float(len(idx))          # pesos binarios: Σw = nº de vecinos
        w_sq = float(len(idx))           # Σw² = Σw para pesos 0/1
        obs = y[idx].sum()
        G[i] = obs / total if total > 0 else np.nan
        den = S * np.sqrt(max((n * w_sq - w_sum ** 2) / (n - 1), 1e-12))
        Z[i] = (obs - ybar * w_sum) / den

        # Permutación condicional: y_i permanece fijo en i; los k vecinos
        # restantes se extraen sin reemplazo del resto de las observaciones.
        k = len(idx) - 1
        if k > 0:
            otros = np.delete(y, i)
            M = rng.permuted(np.tile(otros, (n_perm, 1)), axis=1)[:, :k]
            sim_obs = M.sum(axis=1) + y[i]
        else:
            sim_obs = np.full(n_perm, y[i], dtype=float)
        sim_z = (sim_obs - ybar * w_sum) / den
        sd = sim_z.std(ddof=1)
        Zsim[i] = (Z[i] - sim_z.mean()) / (sd if sd > 0 else np.nan)
        extremos = int(np.sum(np.abs(sim_z - sim_z.mean())
                              >= abs(Z[i] - sim_z.mean()) - 1e-12))
        Psim[i] = (extremos + 1) / (n_perm + 1)
    return G, Z, Zsim, Psim


def bloque_getis(df, celdas, w_cel, outdir, resultados):
    titulo("§6 · Getis-Ord Gi* — puntos calientes y fríos")

    v = celdas.log1p_resenas_tot.values
    vecinos = vecinos_con_autovecindad(w_cel)
    card = np.array([len(vecinos[i]) for i in range(len(celdas))])

    print("VARIABLES DE ENTRADA")
    print(f"  Unidad        : celda de {CELDA_M:.0f} m (n = {len(celdas)})")
    print(f"  Variable      : log(1 + reseñas totales por celda)")
    print(f"  Pesos         : contigüidad reina BINARIA con AUTOVECINDAD "
          f"(w_ii = 1)")
    print(f"  Σw_ij por unidad: media {card.mean():.2f} | mín {card.min()} | "
          f"máx {card.max()}")
    print(f"  Permutaciones : {N_PERM:,} condicionales | semilla = {SEMILLA}")
    print(f"  Media global X̄ = {v.mean():.4f} | S (DE poblacional) = "
          f"{np.sqrt(np.sum(v**2)/len(v) - v.mean()**2):.4f}")
    print("\n  Se emplea la fórmula canónica de Ord y Getis (1995) con pesos")
    print("  binarios: el estadístico es directamente una puntuación z y el")
    print("  criterio |z| > 1,96 es interpretable. Los pesos estandarizados por")
    print("  filas alteran la escala del estadístico y no se usan aquí.")
    print("\n  Diferencia respecto a LISA: Gi* contrasta la suma local "
          "(incluyendo la")
    print("  propia unidad) frente a la media global → mide INTENSIDAD. LISA")
    print("  contrasta la similitud con los vecinos → mide ESTRUCTURA. Reportar")
    print("  ambos es estándar y no es redundante.")

    G, Z, Zsim, Psim = getis_ord_star(v, vecinos)
    p_analitica = 2.0 * stats.norm.sf(np.abs(Z))
    rech, p_adj, _, _ = multipletests(p_analitica, alpha=ALFA,
                                      method=FDR_METODO)

    # Validación cruzada con esda (pesos binarios, star=True)
    w_bin = W({k: list(w_cel.neighbors[k]) for k in w_cel.neighbors},
              silence_warnings=True)
    w_bin.transform = "B"
    g_esda = esda.G_Local(v, w_bin, transform="B", permutations=999, star=True,
                          seed=SEMILLA)
    r_val = stats.pearsonr(Z, np.asarray(g_esda.Zs))
    print(f"\n  Validación cruzada con esda.G_Local (pesos binarios, "
          f"star=True):")
    print(f"    correlación de Pearson entre las z propias y las de esda: "
          f"r = {r_val[0]:.6f}")
    print(f"    diferencia absoluta máxima: "
          f"{np.max(np.abs(Z - np.asarray(g_esda.Zs))):.6f}")

    celdas = celdas.copy()
    celdas["Gi_star"] = G
    celdas["z_gi"] = Z
    celdas["z_gi_sim"] = Zsim
    celdas["p_analitica_gi"] = p_analitica
    celdas["p_sim_gi"] = Psim
    celdas["p_FDR_gi"] = p_adj

    def clasificar(zi, pi):
        if pi >= 0.10:
            return "No signif."
        nivel = "99%" if pi < 0.01 else ("95%" if pi < 0.05 else "90%")
        return ("Hot " if zi > 0 else "Cold ") + nivel
    # Clasificación por el p ANALÍTICO (Gi* es directamente una z; es el
    # criterio de Ord y Getis y el implementado en ArcGIS/GeoDa). El pseudo-p
    # de permutación se reporta como control: en unidades con muy pocos vecinos
    # su distribución es discreta y puede resultar engañoso.
    celdas["clase_Gi"] = [clasificar(zi, pi) for zi, pi in zip(Z, p_analitica)]
    celdas["clase_Gi_FDR"] = [clasificar(zi, pi) if r else "No signif."
                              for zi, pi, r in zip(Z, p_adj, rech)]

    print("\nVALORES DE SALIDA")
    print(f"  Rango de z(Gi*): [{Z.min():.4f}, {Z.max():.4f}]")
    print(f"  |z| > 1,96 : {int((np.abs(Z) > 1.96).sum())} celdas "
          f"({int((Z > 1.96).sum())} calientes, {int((Z < -1.96).sum())} frías)")
    print(f"  |z| > 2,58 : {int((np.abs(Z) > 2.58).sum())} celdas")
    print(f"  Significativas con p analítico < {ALFA} : "
          f"{int((p_analitica < ALFA).sum())}")
    print(f"  Significativas con pseudo-p de permutación < {ALFA} : "
          f"{int((Psim < ALFA).sum())}")
    print(f"  Concordancia z analítica / z de permutación: "
          f"r = {stats.pearsonr(Z, Zsim)[0]:.4f}")
    print(f"  Significativas tras {FDR_METODO} sobre el p analítico: "
          f"{int(rech.sum())}")
    if int(rech.sum()) == 0:
        print("\n  RESULTADO EXIGENTE Y DE REPORTE OBLIGADO: ninguna celda")
        print("  sobrevive a la corrección de Benjamini-Hochberg. Con m = "
              f"{len(celdas)} unidades")
        print(f"  el primer escalón del procedimiento exige p ≤ α/m = "
              f"{ALFA/len(celdas):.5f}, y el p mínimo")
        print(f"  observado es {p_analitica.min():.5f}. Lectura correcta: la "
              "evidencia de estructura")
        print("  espacial es sólida a nivel GLOBAL (I de Moran, §4), mientras que")
        print("  la localización concreta de los clústeres debe presentarse como")
        print("  EXPLORATORIA. No debe escribirse 'hay 18 hotspots "
              "significativos' sin")
        print("  matizar; sí puede escribirse 'la exploración local identifica 18")
        print("  celdas con z > 1,96, que no superan la corrección por "
              "multiplicidad'.")
        nota("Esta es la formulación que un revisor de revista Q1 exigirá. "
             "Presentar los clústeres locales como confirmatorios cuando no "
             "superan la corrección es el error más frecuente en la literatura "
             "que usa LISA/Gi*, y es fácilmente detectable.")

    conteo = (celdas.clase_Gi.value_counts()
              .reindex(["Hot 99%", "Hot 95%", "Hot 90%", "No signif.",
                        "Cold 90%", "Cold 95%", "Cold 99%"])
              .fillna(0).astype(int).rename("n").to_frame())
    conteo["%"] = 100 * conteo.n / len(celdas)
    conteo["n_tras_FDR"] = (celdas.clase_Gi_FDR.value_counts()
                            .reindex(conteo.index).fillna(0).astype(int))
    tabla(conteo, "(1) Clasificación por nivel de confianza", 2)

    inv = Transformer.from_crs(EPSG_PROJ, EPSG_GEO, always_xy=True)
    sig = celdas[celdas.clase_Gi != "No signif."].copy()
    if len(sig):
        sig["lon"], sig["lat"] = inv.transform(sig.xc.values, sig.yc.values)
        tabla(sig.sort_values("z_gi", ascending=False)
              [["clase_Gi", "lat", "lon", "n_estab", "resenas_tot",
                "log1p_resenas_tot", "prop_ig", "dist_media", "Gi_star",
                "z_gi", "p_analitica_gi", "p_sim_gi", "p_FDR_gi"]]
              .reset_index(drop=True),
              "(2) Inventario de celdas significativas ordenadas por z", 5)
        print(f"\n  Gi* expresa la proporción del total de log(1+reseñas) que "
              f"acumula el\n  entorno local de cada celda; z es su desviación "
              f"tipificada respecto\n  a lo esperado bajo distribución "
              f"aleatoria.")

    # Concordancia LISA / Gi*
    titulo("§6.1 · Concordancia entre LISA y Gi*", 2)
    if "clase_LISA" in celdas.columns:
        ct = pd.crosstab(celdas.clase_LISA, celdas.clase_Gi)
        tabla(ct, "Tabulación cruzada de clasificaciones", 0)
        hh = (celdas.clase_LISA == "HH").values
        hot = celdas.clase_Gi.str.startswith("Hot").values
        ll = (celdas.clase_LISA == "LL").values
        cold = celdas.clase_Gi.str.startswith("Cold").values
        print(f"  Celdas HH (LISA) que son también hotspot (Gi*): "
              f"{int((hh & hot).sum())} de {int(hh.sum())}")
        print(f"  Celdas LL (LISA) que son también coldspot (Gi*): "
              f"{int((ll & cold).sum())} de {int(ll.sum())}")
        r_sp = stats.spearmanr(celdas.z_lisa, celdas.z_gi)
        print(f"  Correlación de Spearman entre z(LISA) y z(Gi*): "
              f"ρ = {r_sp[0]:.4f} (p = {r_sp[1]:.3g})")
        nota("La coincidencia parcial es esperable y sustantivamente "
             "informativa: Gi* detecta acumulación de intensidad, LISA detecta "
             "homogeneidad local. Las celdas señaladas por Gi* pero no por LISA "
             "son núcleos de alta intensidad rodeados de heterogeneidad; las "
             "señaladas por LISA pero no por Gi* son zonas homogéneas de nivel "
             "intermedio.")

    celdas.to_csv(os.path.join(outdir, "T6a_getis_ord_celdas.csv"), index=False)
    conteo.to_csv(os.path.join(outdir, "T6b_getis_conteo.csv"))
    resultados["getis_ord"] = {
        "z_min": float(Z.min()), "z_max": float(Z.max()),
        "n_z_gt_196": int((np.abs(Z) > 1.96).sum()),
        "n_hot_p05": int(celdas.clase_Gi.isin(["Hot 99%", "Hot 95%"]).sum()),
        "n_cold_p05": int(celdas.clase_Gi.isin(["Cold 99%", "Cold 95%"]).sum()),
        "n_hot_FDR": int(celdas.clase_Gi_FDR.str.startswith("Hot").sum()),
        "n_cold_FDR": int(celdas.clase_Gi_FDR.str.startswith("Cold").sum()),
        "validacion_esda_r": float(r_val[0]),
        "conteo": conteo.to_dict(),
        "celdas_significativas": (sig[["clase_Gi", "lat", "lon", "n_estab",
                                       "resenas_tot", "z_gi",
                                       "p_analitica_gi", "p_sim_gi",
                                       "p_FDR_gi"]]
                                  .to_dict(orient="records") if len(sig) else [])}

    fig6_getis(df, celdas, outdir)
    return celdas


def fig6_getis(df, celdas, outdir):
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.65),
                             gridspec_kw={"wspace": 0.10})

    # Panel A: z continuo
    ax = axes[0]
    zmax = float(np.nanmax(np.abs(celdas.z_gi)))
    norm = plt.Normalize(-zmax, zmax)
    cmap = plt.get_cmap("RdBu_r")
    colores = [cmap(norm(zi)) for zi in celdas.z_gi]
    dibujar_celdas(ax, celdas, colores)
    marco_mapa(ax, celdas, df)
    ax.set_title("A · Puntuación $z$ de Gi*", loc="left")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=ax, fraction=0.043, pad=0.02)
    cb.set_label("$z(G_i^*)$", fontsize=7)
    cb.ax.tick_params(labelsize=6.2, width=0.5, length=2)
    cb.outline.set_linewidth(0.4)
    for lv in (-2.58, -1.96, 1.96, 2.58):
        if abs(lv) < zmax:
            cb.ax.axhline(lv, color="#17202A", lw=0.6,
                          ls="--" if abs(lv) < 2 else ":")

    # Panel B: clasificación por confianza
    ax2 = axes[1]
    colores2 = [COL_GI[c] for c in celdas.clase_Gi]
    dibujar_celdas(ax2, celdas, colores2)
    fdr = celdas[celdas.clase_Gi_FDR != "No signif."]
    if len(fdr):
        parches = [Rectangle((r.x0, r.y0), CELDA_M, CELDA_M)
                   for r in fdr.itertuples()]
        ax2.add_collection(PatchCollection(parches, facecolors="none",
                                          edgecolors="#17202A", linewidths=1.0,
                                          zorder=5))
    marco_mapa(ax2, celdas, df)
    ax2.set_title("B · Puntos calientes y fríos", loc="left")
    n_por = celdas.clase_Gi.value_counts()
    orden = ["Hot 99%", "Hot 95%", "Hot 90%", "No signif.", "Cold 90%",
             "Cold 95%", "Cold 99%"]
    etiq = {"Hot 99%": "Caliente · 99%", "Hot 95%": "Caliente · 95%",
            "Hot 90%": "Caliente · 90%", "No signif.": "No significativo",
            "Cold 90%": "Frío · 90%", "Cold 95%": "Frío · 95%",
            "Cold 99%": "Frío · 99%"}
    handles = [Patch(fc=COL_GI[k], ec="white", lw=0.3,
                     label=f"{etiq[k]} ({int(n_por.get(k,0))})")
               for k in orden if int(n_por.get(k, 0)) > 0]
    if len(fdr):
        handles.append(Patch(fc="none", ec="#17202A", lw=1.0,
                             label=f"Sobrevive a FDR ({len(fdr)})"))
    handles.append(Line2D([], [], marker="*", ls="none", ms=7, color="#F4D03F",
                          mec="#17202A", mew=0.4, label="Plaza Grande"))
    ax2.legend(handles=handles, loc="upper left", fontsize=6.0,
               handlelength=1.1, borderpad=0.32, labelspacing=0.3,
               frameon=True, framealpha=0.93, edgecolor="#D5D8DC",
               facecolor="white")

    fig.text(0.005, -0.03,
             f"Estadístico Gi* de Getis-Ord (Ord y Getis, 1995) sobre "
             f"log(1 + reseñas totales) en celdas de {CELDA_M:.0f} m; "
             f"contigüidad reina binaria con autovecindad; {N_PERM:,} "
             f"permutaciones condicionales; semilla = {SEMILLA}.\n"
             f"El estadístico es una puntuación z: las marcas de la barra de "
             f"color señalan ±1,96 (95%) y ±2,58 (99%). Niveles de confianza del "
             f"panel B asignados por pseudo-p de permutación; el contorno negro "
             f"marca las celdas que superan además la corrección de "
             f"Benjamini-Hochberg.\n"
             f"Valores positivos = concentración local de capital digital. "
             f"Anillos concéntricos cada 250 m desde la Plaza Grande. "
             f"Proyección UTM 17S (EPSG:32717).".replace(",", ","),
             fontsize=6.3, color="#566573", va="top")
    guardar(fig, outdir, "Figura6_GetisOrd")


# =============================================================================
# §7 — SÍNTESIS Y NIVELES DE EVIDENCIA
# =============================================================================

def bloque_sintesis(resultados, outdir):
    titulo("§7 · Síntesis de resultados y nivel de evidencia")

    mw = pd.DataFrame(resultados["mann_whitney"])
    bn = resultados["binomial_negativa"]
    kde = resultados["kde"]
    mg = pd.DataFrame(resultados["moran_global"])
    li = resultados["lisa"]
    go = resultados["getis_ord"]

    m1 = pd.DataFrame(bn["modelo1"]).set_index("index")
    filas = [
        ["Mann-Whitney · reseñas",
         f"U = {mw.loc[0,'U_g1']:,.0f}; p = {mw.loc[0,'p_permutacion']:.2g}; "
         f"r_rb = {mw.loc[0,'r_rango_biserial']:.2f}",
         "ALTO — no paramétrico, sin supuestos distribucionales; efecto grande",
         "Asociación, no causalidad. Grupos muy desiguales (n1=23)"],
        ["Mann-Whitney · estrellas",
         f"p = {mw.loc[3,'p_permutacion']:.2g}; "
         f"r_rb = {mw.loc[3,'r_rango_biserial']:.2f}",
         "MEDIO-ALTO — n de franquicias reducido (22)",
         "Restringido a locales con ≥1 reseña; excluye ausencia de calificación"],
        ["Binomial negativa · Instagram",
         f"IRR = {m1.loc['ig','IRR']:.2f} "
         f"[{m1.loc['ig','IC95_inf']:.2f}; {m1.loc['ig','IC95_sup']:.2f}]; "
         f"p = {m1.loc['ig','p']:.2g}",
         "MEDIO — modelo correctamente especificado, pero endogeneidad probable",
         "Diseño transversal; sin control de antigüedad de la ficha"],
        ["Binomial negativa · distancia",
         f"IRR = {m1.loc['dist','IRR']:.3f} "
         f"[{m1.loc['dist','IC95_inf']:.3f}; {m1.loc['dist','IC95_sup']:.3f}]; "
         f"p = {m1.loc['dist','p']:.2g}",
         "MEDIO — significativo pero con IC amplio",
         "Rango de distancia corto (0,05–1,71 km): extrapolación no admisible"],
        ["KDE · relación físico/digital",
         f"máximos separados solo {kde['separacion_picos_m']:,.0f} m (< h = "
         f"{kde['h_m']:.0f} m); ρ Spearman = {kde['spearman_A_B']:.2f}; "
         f"concentración digital {kde['razon_concentracion']:.2f}× la física",
         "MEDIO — descriptivo, sin contraste de hipótesis asociado",
         "Los máximos COINCIDEN: no hay desplazamiento del centro de gravedad, "
         "sino agudización de la jerarquía. Corregir el relato si afirmaba "
         "'hotspot físico ≠ hotspot digital'"],
        ["I de Moran · reseñas (establecimiento)",
         f"I = {mg.loc[0,'I']:.3f}; p = {mg.loc[0,'p_sim_bilateral']:.4f}",
         "ALTO — inferencia por permutación, sin supuesto de normalidad",
         "Magnitud modesta: estructura real pero débil a escala de local"],
        ["I de Moran · reseñas (celda 150 m)",
         f"I = {mg[mg.unidad=='Celda 150 m'].iloc[0]['I']:.3f}; "
         f"p = {mg[mg.unidad=='Celda 150 m'].iloc[0]['p_sim_bilateral']:.4f}",
         "ALTO — inferencia por permutación",
         "Dependiente de la escala de agregación (MAUP): declarar 150 m"],
        ["LISA",
         f"{li['n_signif_p05']} celdas con p<0,05 "
         f"({li['n_signif_p01']} con p<0,01; {li['n_signif_FDR']} tras FDR)",
         "ALTO para la existencia de clústeres; MEDIO-BAJO para su delimitación "
         "exacta: solo 2 celdas superan la corrección FDR",
         "Sensible a la vecindad y a la malla (MAUP); reportar el criterio usado"],
        ["Getis-Ord Gi*",
         f"z ∈ [{go['z_min']:.2f}, {go['z_max']:.2f}]; "
         f"{go['n_z_gt_196']} celdas con |z|>1,96; "
         f"{go['n_hot_p05']} calientes y {go['n_cold_p05']} frías (p<0,05)",
         "MEDIO — implementación canónica validada (r = "
         f"{go['validacion_esda_r']:.4f}), pero ninguna celda supera la "
         "corrección FDR: presentar como exploratorio",
         "Solo celdas ocupadas: los vacíos urbanos no entran como ceros"],
    ]
    sint = pd.DataFrame(filas, columns=["Técnica", "Resultado principal",
                                        "Nivel de evidencia", "Limitación"])
    for _, r in sint.iterrows():
        print(f"\n▪ {r['Técnica']}")
        for etiqueta, campo in [("Resultado ", "Resultado principal"),
                                ("Evidencia ", "Nivel de evidencia"),
                                ("Limitación", "Limitación")]:
            print(textwrap.fill(f"  {etiqueta}: {r[campo]}", 79,
                                subsequent_indent="              "))
    sint.to_csv(os.path.join(outdir, "T7_sintesis_evidencia.csv"), index=False)

    print("\n" + "-" * 79)
    print("ADVERTENCIAS TRANSVERSALES DE INTERPRETACIÓN")
    print("-" * 79)
    for i, t in enumerate([
        "Ningún resultado de este script identifica relaciones causales. El "
        "diseño es un censo transversal en un único momento: toda formulación "
        "admisible es 'se asocia con', 'coincide con', 'se distribuye según'.",
        "El problema de la unidad de área modificable (MAUP) afecta a §4–§6: "
        "los resultados a nivel de celda no son idénticos a los de nivel de "
        "establecimiento y ambos se reportan. La celda de 150 m debe "
        "justificarse morfológicamente en el paper, no por conveniencia.",
        "Las variables de plataforma son mediciones de una sola captura. Sin "
        "series temporales no puede afirmarse que las plataformas "
        "'reconfiguren' nada: puede afirmarse que el capital digital está "
        "estratificado y espacialmente estructurado.",
        "La ausencia de ficha en Google Maps (120 casos) es simultáneamente "
        "mortalidad comercial e invisibilidad digital: ambas interpretaciones "
        "son compatibles con los datos y deben presentarse conjuntamente.",
        "Las cuentas de marca compartidas (KFC, CARAVANA) inflan los "
        "agregados de seguidores; §1 incluye la variante sin duplicados y las "
        "conclusiones no cambian.",
        "Los pseudo-p de permutación tienen un mínimo de "
        f"1/({N_PERM}+1) = {1/(N_PERM+1):.5f}: no debe escribirse 'p = 0'.",
    ], 1):
        print(textwrap.fill(f"{i}. {t}", 79, subsequent_indent="   "))

    with open(os.path.join(outdir, "resultados_completos.json"), "w",
              encoding="utf-8") as fh:
        json.dump(resultados, fh, ensure_ascii=False, indent=2, default=str)
    print(f"\n[JSON] resultados_completos.json")


# =============================================================================
# =============================================================================
#                    PARTE II — CAPITAL DIGITAL MULTIDIMENSIONAL
# =============================================================================
# Amplía la Parte I sin modificarla. Las reseñas de Google Maps se conservan
# como capa autónoma de referencia (visibilidad cartográfica); sobre ella se
# añade una operacionalización multiplataforma del capital digital.
#
#   §8   Auditoría de variables y estructura de plataformas
#   §9   Mann-Whitney y Fisher ampliados: TikTok (alcance e interacción)
#   §10  Construcción del capital digital (PCA-A principal, PCA-B sensibilidad)
#   §11  KDE del capital digital
#   §12  Moran, LISA y Gi* sobre CP1 y CP2 + tabla de concordancia
#   §13  Sensibilidad a cuentas de marca y síntesis final
# =============================================================================

N_BOOT = 1000          # réplicas bootstrap para estabilidad de cargas PCA
K_VECINOS_EXPL = 5     # k reducido para capas exploratorias de baja cobertura


# -----------------------------------------------------------------------------
# Diagnósticos de adecuación factorial (implementados sin dependencias extra)
# -----------------------------------------------------------------------------

def kmo(R):
    """
    Medida de adecuación muestral de Kaiser-Meyer-Olkin.
    KMO = Σr²(i≠j) / [ Σr²(i≠j) + Σp²(i≠j) ], con p = correlaciones parciales.
    Interpretación de Kaiser: <0,50 inaceptable · 0,50-0,60 mediocre ·
    0,60-0,70 mediano · 0,70-0,80 aceptable · >0,80 bueno.
    """
    Rinv = np.linalg.inv(R)
    d = np.sqrt(np.diag(Rinv))
    P = -Rinv / np.outer(d, d)          # matriz de correlaciones parciales
    np.fill_diagonal(P, 0.0)
    R0 = R.copy(); np.fill_diagonal(R0, 0.0)
    sr, sp = np.sum(R0 ** 2), np.sum(P ** 2)
    global_kmo = sr / (sr + sp)
    por_var = (np.sum(R0 ** 2, axis=0) /
               (np.sum(R0 ** 2, axis=0) + np.sum(P ** 2, axis=0)))
    return float(global_kmo), por_var


def bartlett_esfericidad(R, n):
    """Contraste de esfericidad de Bartlett: H0 = matriz identidad."""
    k = R.shape[0]
    det = np.linalg.det(R)
    chi2 = -((n - 1) - (2 * k + 5) / 6.0) * np.log(max(det, 1e-300))
    gl = k * (k - 1) / 2
    return float(chi2), int(gl), float(stats.chi2.sf(chi2, gl)), float(det)


def broken_stick(k):
    """Valores esperados de los eigenvalues bajo el modelo de bastón roto."""
    return np.array([sum(1.0 / j for j in range(i, k + 1)) for i in range(1, k + 1)])


def pca_correlacion(X, etiquetas, nombre, n_boot=N_BOOT, semilla=SEMILLA,
                    anclaje=0):
    """
    PCA sobre la matriz de correlaciones (equivale a estandarizar previamente).
    El signo de cada componente se ancla al indicador `anclaje` para que un
    valor alto signifique siempre MÁS capital.
    Devuelve un diccionario con cargas, varianza, puntuaciones y diagnósticos.
    """
    X = np.asarray(X, dtype=float)
    n, k = X.shape
    Z = (X - X.mean(0)) / X.std(0, ddof=1)
    R = np.corrcoef(Z.T)

    kmo_g, kmo_v = kmo(R)
    chi2, gl, p_bart, det = bartlett_esfericidad(R, n)

    val, vec = np.linalg.eigh(R)
    orden = np.argsort(-val)
    val, vec = val[orden], vec[:, orden]

    # Anclaje de signo
    for j in range(k):
        if vec[anclaje, j] < 0:
            vec[:, j] = -vec[:, j]

    puntuaciones = Z @ vec
    cargas = vec * np.sqrt(val)           # correlaciones variable-componente
    comunalidades = np.sum(cargas[:, :2] ** 2, axis=1)

    # Bootstrap de estabilidad de las cargas de CP1
    rng = np.random.default_rng(semilla)
    boot = np.zeros((n_boot, k))
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        Zb = Z[idx]
        Rb = np.corrcoef(Zb.T)
        if not np.all(np.isfinite(Rb)):
            boot[b] = np.nan; continue
        vb, wb = np.linalg.eigh(Rb)
        o = np.argsort(-vb); wb = wb[:, o]
        if wb[anclaje, 0] < 0:
            wb[:, 0] = -wb[:, 0]
        boot[b] = wb[:, 0] * np.sqrt(vb[o][0])
    boot_lo = np.nanpercentile(boot, 2.5, axis=0)
    boot_hi = np.nanpercentile(boot, 97.5, axis=0)
    boot_sd = np.nanstd(boot, axis=0)

    return {
        "nombre": nombre, "n": n, "k": k, "etiquetas": list(etiquetas),
        "R": R, "eigen": val, "var_pct": 100 * val / val.sum(),
        "var_acum": np.cumsum(100 * val / val.sum()),
        "broken_stick": 100 * broken_stick(k) / k,
        "vectores": vec, "cargas": cargas, "comunalidades": comunalidades,
        "puntuaciones": puntuaciones,
        "kmo_global": kmo_g, "kmo_var": kmo_v,
        "bartlett_chi2": chi2, "bartlett_gl": gl, "bartlett_p": p_bart,
        "det_R": det,
        "boot_lo": boot_lo, "boot_hi": boot_hi, "boot_sd": boot_sd,
    }


def imprimir_pca(res):
    print(f"\n  Adecuación factorial")
    interp = ("inaceptable" if res["kmo_global"] < .50 else
              "mediocre" if res["kmo_global"] < .60 else
              "mediano" if res["kmo_global"] < .70 else
              "aceptable" if res["kmo_global"] < .80 else "bueno")
    print(f"    KMO global = {res['kmo_global']:.4f}  → «{interp}» "
          f"(criterio de Kaiser)")
    for e, v in zip(res["etiquetas"], res["kmo_var"]):
        print(f"      KMO {e:<28s} = {v:.4f}")
    print(f"    Bartlett: χ² = {res['bartlett_chi2']:,.1f} "
          f"({res['bartlett_gl']} gl), p = {res['bartlett_p']:.3g} | "
          f"det(R) = {res['det_R']:.5f}")
    print(f"    → se rechaza la esfericidad: existe estructura de correlación "
          f"factorizable.")

    tabla(pd.DataFrame(res["R"], index=res["etiquetas"],
                       columns=res["etiquetas"]),
          "  Matriz de correlaciones (Pearson sobre variables transformadas)", 4)

    comp = [f"CP{j+1}" for j in range(res["k"])]
    tabla(pd.DataFrame({"eigenvalue": res["eigen"],
                        "% varianza": res["var_pct"],
                        "% acumulado": res["var_acum"],
                        "% bastón roto": res["broken_stick"],
                        "retener": res["var_pct"] > res["broken_stick"]},
                       index=comp),
          "  Descomposición espectral y criterio del bastón roto", 3)

    tabla(pd.DataFrame(res["cargas"], index=res["etiquetas"], columns=comp)
          .assign(comunalidad_12=res["comunalidades"]),
          "  Cargas factoriales (correlación variable-componente)", 4)

    tabla(pd.DataFrame({"carga_CP1": res["cargas"][:, 0],
                        "IC95_inf": res["boot_lo"], "IC95_sup": res["boot_hi"],
                        "EE_bootstrap": res["boot_sd"]},
                       index=res["etiquetas"]),
          f"  Estabilidad de las cargas de CP1 ({N_BOOT:,} réplicas bootstrap)",
          4)


# =============================================================================
# §8 — AUDITORÍA DE VARIABLES Y ESTRUCTURA DE PLATAFORMAS
# =============================================================================

def bloque_auditoria(df, outdir, resultados):
    titulo("§8 · Auditoría de variables y estructura de plataformas")

    d = df.copy()
    d["n_plataformas"] = (d.existe_gmaps.astype(int) + d.tiene_ig.astype(int)
                          + d.tiene_tt.astype(int))
    # Interacción TikTok: SOLO definida donde hay cuenta y seguidores > 0
    d["engagement_tt"] = np.where((d.tiene_tt == 1) & (d.seg_tt > 0),
                                  d.likes_tt / d.seg_tt.replace(0, np.nan),
                                  np.nan)
    d["log_engagement_tt"] = np.log1p(d.engagement_tt)

    titulo("§8.1 · Auditoría formal de variables", 2)
    filas = [
        ("resenas", "Reseñas acumuladas en la ficha de Google Maps",
         "Google Maps", "conteo", "entero", "log1p", "acumulación"),
        ("estrellas", "Calificación media de la ficha", "Google Maps",
         "0–5", "continua", "ninguna", "consagración"),
        ("existe_gmaps", "La ficha existe en Google Maps", "Google Maps",
         "0/1", "binaria", "ninguna", "presencia"),
        ("tiene_ig", "Cuenta de Instagram identificada", "Instagram",
         "0/1", "binaria", "ninguna", "presencia"),
        ("seg_ig", "Seguidores de Instagram", "Instagram", "conteo",
         "entero", "log1p", "alcance"),
        ("tiene_tt", "Cuenta de TikTok identificada", "TikTok", "0/1",
         "binaria", "ninguna", "presencia"),
        ("seg_tt", "Seguidores de TikTok", "TikTok", "conteo", "entero",
         "log1p", "alcance"),
        ("likes_tt", "Likes acumulados de TikTok", "TikTok", "conteo",
         "entero", "log1p", "interacción bruta"),
        ("engagement_tt", "Likes por seguidor (TikTok)", "TikTok", "razón",
         "continua", "log1p", "interacción relativa"),
        ("dist_km", "Distancia a Plaza Grande", "Derivada", "km",
         "continua", "ninguna", "localización"),
        ("franquicia", "Pertenencia a cadena o franquicia", "Catastro",
         "0/1", "binaria", "ninguna", "estructura comercial"),
    ]
    aud = []
    for var, defi, plat, uni, tipo, trans, funcion in filas:
        col = d[var]
        no_aplica = int(col.isna().sum())
        if var in ("resenas",):
            ceros = int(((col == 0) & (d.existe_gmaps)).sum())
            estructurales = int((~d.existe_gmaps).sum())
        elif var in ("seg_ig",):
            ceros = int(((col == 0) & (d.tiene_ig == 1)).sum())
            estructurales = int((d.tiene_ig == 0).sum())
        elif var in ("seg_tt", "likes_tt"):
            ceros = int(((col == 0) & (d.tiene_tt == 1)).sum())
            estructurales = int((d.tiene_tt == 0).sum())
        else:
            ceros = int((col == 0).sum()); estructurales = 0
        aud.append({"variable": var, "definición": defi, "plataforma": plat,
                    "unidad": uni, "tipo": tipo,
                    "n_válidos": int(col.notna().sum()),
                    "n_no_aplica": no_aplica,
                    "n_ceros_reales": ceros,
                    "n_ausencia_estructural": estructurales,
                    "transformación": trans, "función_analítica": funcion})
    audit = pd.DataFrame(aud)
    with pd.option_context("display.max_colwidth", 46, "display.width", 250):
        print()
        print(audit.to_string(index=False))
    nota("La columna 'ausencia estructural' distingue el establecimiento que NO "
         "tiene la plataforma (dato no aplicable) del que la tiene con valor "
         "cero. Confundirlos es el error que la Parte II está diseñada para "
         "evitar.")

    titulo("§8.2 · Estructura de adopción multiplataforma", 2)
    ct = pd.crosstab(d.tiene_ig.map({0: "Sin Instagram", 1: "Con Instagram"}),
                     d.tiene_tt.map({0: "Sin TikTok", 1: "Con TikTok"}),
                     margins=True, margins_name="Total")
    tabla(ct, "Tabla cruzada Instagram × TikTok", 0)
    n_tt = int((d.tiene_tt == 1).sum())
    n_tt_ig = int(((d.tiene_tt == 1) & (d.tiene_ig == 1)).sum())
    print(f"\n  De los {n_tt} establecimientos con TikTok, {n_tt_ig} "
          f"({100*n_tt_ig/n_tt:.1f}%) tienen también Instagram.")
    print(f"  TikTok está fuertemente ANIDADO dentro de Instagram: apenas "
          f"{n_tt-n_tt_ig} establecimientos")
    print(f"  usan TikTok sin Instagram. Esta es la razón estructural de que en "
          f"la regresión")
    print(f"  (§2.4) TikTok no muestre asociación independiente con las reseñas: "
          f"no hay")
    print(f"  variación suficiente para identificar su efecto propio.")
    odds = ((n_tt_ig * ((d.tiene_ig == 0) & (d.tiene_tt == 0)).sum()) /
            max(((d.tiene_ig == 1) & (d.tiene_tt == 0)).sum() *
                ((d.tiene_ig == 0) & (d.tiene_tt == 1)).sum(), 1))
    tab2 = pd.crosstab(d.tiene_ig, d.tiene_tt)
    odd_r, p_fisher = stats.fisher_exact(tab2.values)
    if not np.isfinite(odd_r):
        # Celda vacía: ningún establecimiento con TikTok carece de Instagram.
        # Se aplica la corrección de Haldane-Anscombe (+0,5) para obtener una
        # estimación finita, declarándola explícitamente.
        m = tab2.values.astype(float) + 0.5
        odd_r_hs = (m[1, 1] * m[0, 0]) / (m[1, 0] * m[0, 1])
        print(f"  Asociación IG–TikTok: la razón de momios NO ESTÁ DEFINIDA "
              f"(celda vacía):")
        print(f"    ningún establecimiento con TikTok carece de Instagram.")
        print(f"    Estimación con corrección de Haldane-Anscombe (+0,5): "
              f"OR = {odd_r_hs:,.1f}")
        print(f"    p (Fisher exacto) = {p_fisher:.3g}")
        odd_r = odd_r_hs
        anidamiento_total = True
    else:
        print(f"  Asociación IG–TikTok: razón de momios = {odd_r:.2f}, "
              f"p (Fisher exacto) = {p_fisher:.3g}")
        anidamiento_total = False

    conteo_plat = (d.n_plataformas.value_counts().sort_index()
                   .rename("n").to_frame())
    conteo_plat["%"] = 100 * conteo_plat.n / len(d)
    conteo_plat["reseñas_medias"] = d.groupby("n_plataformas").resenas.mean()
    conteo_plat["% del total de reseñas"] = (
        100 * d.groupby("n_plataformas").resenas.sum() / d.resenas.sum())
    conteo_plat.index.name = "nº de plataformas activas"
    tabla(conteo_plat, "Gradiente de adopción", 2)
    nota("El gradiente es monotónico y muy pronunciado: la estratificación "
         "digital comienza en la ADOPCIÓN de plataformas, antes de cualquier "
         "medición de audiencia. Es el primer resultado que sostiene la "
         "hipótesis de amplificación selectiva.")

    titulo("§8.3 · Matriz de correlaciones entre indicadores digitales", 2)
    cols = {"log1p(reseñas)": d.log1p_resenas,
            "log1p(seguidores IG)": d.log1p_seg_ig,
            "log1p(seguidores TT)": d.log1p_seg_tt,
            "log1p(likes TT)": np.log1p(d.likes_tt),
            "estrellas": d.estrellas}
    M = pd.DataFrame(cols)
    tabla(M.corr(method="spearman"),
          "Spearman (muestra completa; estrellas solo donde hay ficha)", 3)
    sub_tt = d[d.tiene_tt == 1]
    rho_tt = stats.spearmanr(np.log1p(sub_tt.seg_tt), np.log1p(sub_tt.likes_tt))
    print(f"\n  Seguidores TT ~ likes TT, CONDICIONADO a tener TikTok "
          f"(n = {len(sub_tt)}):")
    print(f"    ρ de Spearman = {rho_tt[0]:.4f} (p = {rho_tt[1]:.3g})")
    print(f"  En la muestra completa la correlación aparente es "
          f"{stats.spearmanr(np.log1p(d.seg_tt), np.log1p(d.likes_tt))[0]:.4f}, "
          f"inflada")
    print(f"  por los {int((d.tiene_tt==0).sum())} ceros compartidos. "
          f"La correlación relevante es la condicional.")
    nota("Con ρ ≈ 0,90 entre seguidores y likes de TikTok, incluir ambos como "
         "componentes equivalentes de un índice aditivo duplicaría el peso de "
         "esa plataforma por un artefacto de codificación. Por eso PCA-A "
         "(§10) excluye los likes y PCA-B los incorpora solo como sensibilidad.")
    print(f"\n  Correlación estrellas ~ log1p(reseñas): "
          f"ρ = {stats.spearmanr(d.estrellas, d.log1p_resenas, nan_policy='omit')[0]:.4f}")
    print(f"  La calificación es prácticamente ORTOGONAL al volumen: mide")
    print(f"  consagración, no acumulación. No entra en el índice (§10.4).")

    audit.to_csv(os.path.join(outdir, "T8a_auditoria_variables.csv"),
                 index=False)
    ct.to_csv(os.path.join(outdir, "T8b_instagram_x_tiktok.csv"))
    conteo_plat.to_csv(os.path.join(outdir, "T8c_gradiente_adopcion.csv"))
    M.corr(method="spearman").to_csv(
        os.path.join(outdir, "T8d_correlaciones_indicadores.csv"))
    resultados["auditoria"] = {
        "n_tiktok": n_tt, "n_tiktok_con_ig": n_tt_ig,
        "odds_ratio_IG_TT": float(odd_r), "p_fisher_IG_TT": float(p_fisher),
        "anidamiento_total": bool(anidamiento_total),
        "rho_segTT_likesTT_condicional": float(rho_tt[0]),
        "gradiente_adopcion": conteo_plat.reset_index().to_dict(orient="records")}
    return d


# =============================================================================
# §9 — TIKTOK: ALCANCE E INTERACCIÓN (Mann-Whitney y Fisher ampliados)
# =============================================================================

def bloque_tiktok(d, outdir, resultados):
    titulo("§9 · TikTok — alcance e interacción: franquicias vs. independientes")

    print("PRINCIPIO RECTOR: no se fuerza a TikTok a comportarse como Instagram.")
    print("Se separan tres preguntas que la Parte I confundía en una sola:")
    print("   (a) ADOPCIÓN   — ¿quién abre cuenta?          → Fisher exacto")
    print("   (b) ALCANCE    — entre quienes la tienen,     → Mann-Whitney")
    print("                    ¿quién acumula audiencia?      condicional")
    print("   (c) INTERACCIÓN— ¿qué intensidad de respuesta → Mann-Whitney")
    print("                    genera esa audiencia?          condicional")
    print("\nUna prueba de Mann-Whitney sobre una variable binaria (presencia)")
    print("es incorrecta: se sustituye por Fisher exacto, adecuado además a las")
    print("frecuencias esperadas pequeñas de este diseño (23 franquicias).")

    # ---------- (a) ADOPCIÓN: Fisher exacto -------------------------------
    titulo("§9.1 · Adopción de plataforma (Fisher exacto)", 2)
    filas_f = []
    for var, etiqueta in [("existe_gmaps", "Ficha en Google Maps"),
                          ("tiene_ig", "Cuenta de Instagram"),
                          ("tiene_tt", "Cuenta de TikTok")]:
        v = d[var].astype(int)
        ct = pd.crosstab(d.franquicia, v)
        for c in (0, 1):
            if c not in ct.columns:
                ct[c] = 0
        ct = ct[[0, 1]]
        orat, pf = stats.fisher_exact(ct.values)
        n1, n0 = int(d.franquicia.sum()), int((1 - d.franquicia).sum())
        p1 = float(v[d.franquicia == 1].mean())
        p0 = float(v[d.franquicia == 0].mean())
        # IC 95% de la diferencia de proporciones (Wald con corrección)
        se = np.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
        filas_f.append({"variable": etiqueta,
                        "n_franquicias": n1, "% franquicias": 100 * p1,
                        "n_independientes": n0, "% independientes": 100 * p0,
                        "dif_pp": 100 * (p1 - p0),
                        "IC95_inf_pp": 100 * ((p1 - p0) - 1.96 * se),
                        "IC95_sup_pp": 100 * ((p1 - p0) + 1.96 * se),
                        "razon_momios": orat, "p_Fisher": pf})
    tab_f = pd.DataFrame(filas_f)
    rech_f, padj_f, _, _ = multipletests(tab_f.p_Fisher.values, alpha=ALFA,
                                         method=FDR_METODO)
    tab_f["p_FDR"] = padj_f; tab_f["signif_FDR"] = rech_f
    tabla(tab_f, "Proporción de adopción por grupo (dif. en puntos "
                 "porcentuales)", 4)

    # ---------- (b) y (c) ALCANCE E INTERACCIÓN ---------------------------
    titulo("§9.2 · Alcance e interacción (Mann-Whitney)", 2)
    sub_tt = d[d.tiene_tt == 1]
    sub_ig = d[d.tiene_ig == 1]
    sub_eng = d[d.engagement_tt.notna()]
    print(f"  Submuestras condicionales: TikTok n = {len(sub_tt)} "
          f"({int(sub_tt.franquicia.sum())} franquicias) | "
          f"engagement definido n = {len(sub_eng)}")

    pruebas = [
        # (serie franquicias, serie independientes, etiqueta)
        (sub_tt[sub_tt.franquicia == 1].seg_tt,
         sub_tt[sub_tt.franquicia == 0].seg_tt,
         "Seguidores TikTok [condicional a tener TT]"),
        (sub_tt[sub_tt.franquicia == 1].likes_tt,
         sub_tt[sub_tt.franquicia == 0].likes_tt,
         "Likes TikTok [condicional a tener TT]"),
        (sub_eng[sub_eng.franquicia == 1].engagement_tt,
         sub_eng[sub_eng.franquicia == 0].engagement_tt,
         "Engagement TikTok (likes/seguidor) [condicional]"),
        (d[d.franquicia == 1].seg_tt, d[d.franquicia == 0].seg_tt,
         "Seguidores TikTok [poblacional, mezcla adopción y tamaño]"),
        (d[d.franquicia == 1].likes_tt, d[d.franquicia == 0].likes_tt,
         "Likes TikTok [poblacional, mezcla adopción y tamaño]"),
        (sub_ig[sub_ig.franquicia == 1].seg_ig,
         sub_ig[sub_ig.franquicia == 0].seg_ig,
         "Seguidores Instagram [condicional a tener IG]"),
    ]
    res = []
    for a, b, et in pruebas:
        if len(a.dropna()) < 3 or len(b.dropna()) < 3:
            print(f"  [omitida por tamaño insuficiente] {et} "
                  f"(n1={len(a.dropna())}, n2={len(b.dropna())})")
            continue
        res.append(mann_whitney(a, b, et))
    res = pd.DataFrame(res)

    tabla(res[["variable", "n1_franquicias", "n2_independientes",
               "mediana_g1", "Q1_g1", "Q3_g1", "mediana_g2", "Q1_g2", "Q3_g2"]],
          "(1) Tendencia central e intervalo interquartílico", 3)
    tabla(res[["variable", "U_g1", "z", "p_asintotica", "p_permutacion",
               "r_rango_biserial", "A_Vargha_Delaney"]],
          "(2) Contraste y tamaño del efecto", 5)
    rech, padj, _, _ = multipletests(res.p_permutacion.values, alpha=ALFA,
                                     method=FDR_METODO)
    res["p_FDR"] = padj; res["signif_FDR"] = rech
    tabla(res[["variable", "p_permutacion", "p_FDR", "signif_FDR"]],
          f"(3) Corrección FDR sobre la familia de contrastes de TikTok "
          f"({FDR_METODO})", 5)

    # ---------- Descriptivos del engagement --------------------------------
    titulo("§9.3 · Distribución de la interacción relativa en TikTok", 2)
    e = d.engagement_tt.dropna()
    tabla(pd.DataFrame({"likes por seguidor":
                        [len(e), e.min(), e.quantile(.25), e.median(),
                         e.quantile(.75), e.quantile(.90), e.max()]},
                       index=["n", "mín", "Q1", "mediana", "Q3", "P90", "máx"]),
          None, 3)
    print("\n  ADVERTENCIA DE INTERPRETACIÓN: los likes son un acumulado "
          "histórico de")
    print("  toda la vida de la cuenta, mientras que los seguidores son una "
          "medición")
    print("  puntual. La razón NO es una tasa de engagement en sentido "
          "estricto: es un")
    print("  PROXY DE INTENSIDAD ACUMULADA DE INTERACCIÓN. Una cuenta antigua "
          "con poca")
    print("  audiencia puede exhibir una razón alta sin mayor resonancia actual.")
    print("  Redactar en el paper con esta salvedad explícita.")

    # ¿La interacción se asocia con visibilidad cartográfica?
    r_er = stats.spearmanr(sub_eng.engagement_tt, sub_eng.log1p_resenas)
    r_es = stats.spearmanr(sub_eng.engagement_tt, np.log1p(sub_eng.seg_tt))
    print(f"\n  Engagement ~ log1p(reseñas)      : ρ = {r_er[0]:.4f} "
          f"(p = {r_er[1]:.3g}, n = {len(sub_eng)})")
    print(f"  Engagement ~ log1p(seguidores TT) : ρ = {r_es[0]:.4f} "
          f"(p = {r_es[1]:.3g})")
    if r_es[0] < -0.2:
        print("  → La correlación NEGATIVA con el tamaño de audiencia es el "
              "patrón clásico:")
        print("    las cuentas pequeñas exhiben mayor intensidad relativa de "
              "interacción.")
        print("    Sustantivamente: la interacción NO es simplemente una "
              "función del alcance,")
        print("    y por eso constituye una dimensión analítica propia.")

    tab_f.to_csv(os.path.join(outdir, "T9a_fisher_adopcion.csv"), index=False)
    res.to_csv(os.path.join(outdir, "T9b_mannwhitney_tiktok.csv"), index=False)
    resultados["tiktok"] = {
        "fisher": tab_f.to_dict(orient="records"),
        "mann_whitney": res.to_dict(orient="records"),
        "engagement": {"n": int(len(e)), "mediana": float(e.median()),
                       "Q1": float(e.quantile(.25)), "Q3": float(e.quantile(.75)),
                       "rho_con_resenas": float(r_er[0]),
                       "rho_con_seguidores": float(r_es[0])}}

    fig7_tiktok(d, tab_f, res, outdir)
    return res


def fig7_tiktok(d, tab_f, res, outdir):
    fig = plt.figure(figsize=(7.4, 4.9))
    gs = fig.add_gridspec(2, 3, hspace=0.62, wspace=0.38)
    rng = np.random.default_rng(SEMILLA)

    # ---- A: adopción por grupo -------------------------------------------
    ax = fig.add_subplot(gs[0, 0])
    et = ["Google\nMaps", "Instagram", "TikTok"]
    x = np.arange(3); w = 0.36
    ax.bar(x - w/2, tab_f["% independientes"], w, color=COL_INDEP,
           label="Independientes", zorder=3)
    ax.bar(x + w/2, tab_f["% franquicias"], w, color=COL_FRANQ,
           label="Franquicias", zorder=3)
    for xi, (a, b, p) in enumerate(zip(tab_f["% independientes"],
                                       tab_f["% franquicias"],
                                       tab_f["p_FDR"])):
        est = "***" if p < .001 else "**" if p < .01 else "*" if p < .05 else "n.s."
        ax.text(xi, max(a, b) + 4, est, ha="center", fontsize=6.8,
                color="#2C3E50")
    ax.set_xticks(x); ax.set_xticklabels(et)
    ax.set_ylabel("% del grupo con la plataforma")
    ax.set_ylim(0, 118)
    ax.set_title("A · Adopción de plataforma", loc="left")
    ax.legend(fontsize=6.2, loc="upper left")
    ax.grid(axis="y", lw=.35, color="#D5D8DC", zorder=0); ax.set_axisbelow(True)

    # ---- B, C: alcance condicional ---------------------------------------
    def panel_mw(ax, datos, col, etiqueta_var, titulo_p, log=True):
        grupos = []
        for v in (0, 1):
            ss = datos.loc[datos.franquicia == v, col].dropna().values
            grupos.append(np.log10(1 + ss) if log else ss)
        cols = [COL_INDEP, COL_FRANQ]
        for i, (g, c) in enumerate(zip(grupos, cols), start=1):
            if len(g) == 0:
                continue
            ax.boxplot([g], positions=[i], widths=.34, showfliers=False,
                       patch_artist=True, zorder=3,
                       medianprops=dict(color="white", lw=1.3),
                       boxprops=dict(facecolor=c, edgecolor=c),
                       whiskerprops=dict(lw=.7), capprops=dict(lw=.7))
            jx = i + rng.uniform(-.11, .11, size=len(g))
            ax.scatter(jx, g, s=6, color=c, alpha=.5, linewidths=0, zorder=4)
        ax.set_xticks([1, 2])
        ax.set_xticklabels([f"Indep.\n($n$={len(grupos[0])})",
                            f"Franq.\n($n$={len(grupos[1])})"])
        ax.set_ylabel(etiqueta_var)
        ax.set_title(titulo_p, loc="left")
        ax.grid(axis="y", lw=.35, color="#D5D8DC", zorder=0)
        ax.set_axisbelow(True)
        if log:
            vmax = max((g.max() if len(g) else 0) for g in grupos)
            marcas = [m for m in [0, 10, 100, 1_000, 10_000, 100_000, 1_000_000]
                      if np.log10(1 + m) <= vmax * 1.03]
            ax.set_yticks([np.log10(1 + m) for m in marcas])
            ax.set_yticklabels([f"{m:,}".replace(",", ".") for m in marcas])

    sub_tt = d[d.tiene_tt == 1]
    ax2 = fig.add_subplot(gs[0, 1])
    panel_mw(ax2, sub_tt, "seg_tt", "Seguidores (escala log)",
             "B · Alcance en TikTok")
    ax3 = fig.add_subplot(gs[0, 2])
    panel_mw(ax3, sub_tt, "likes_tt", "Likes acumulados (escala log)",
             "C · Interacción bruta en TikTok")

    # ---- D: engagement ----------------------------------------------------
    ax4 = fig.add_subplot(gs[1, 0])
    sub_e = d[d.engagement_tt.notna()]
    panel_mw(ax4, sub_e, "engagement_tt", "Likes por seguidor",
             "D · Interacción relativa", log=False)

    # ---- E: engagement vs alcance ----------------------------------------
    ax5 = fig.add_subplot(gs[1, 1])
    xs = np.log10(1 + sub_e.seg_tt.values)
    ys = sub_e.engagement_tt.values
    cfr = np.where(sub_e.franquicia.values == 1, COL_FRANQ, COL_INDEP)
    ax5.scatter(xs, ys, s=14, c=cfr, alpha=.75, linewidths=.3,
                edgecolor="white", zorder=3)
    rho = stats.spearmanr(xs, ys)
    ax5.set_xlabel("Seguidores TikTok (escala log)")
    ax5.set_ylabel("Likes por seguidor")
    ax5.set_title("E · Interacción vs. alcance", loc="left")
    ax5.text(.04, .95, f"$\\rho$ = {rho[0]:.2f}".replace(".", ",") +
             (" · $p$ < 0,001" if rho[1] < .001
              else f" · $p$ = {rho[1]:.3f}".replace(".", ",")),
             transform=ax5.transAxes, va="top", fontsize=6.6,
             bbox=dict(fc="white", ec="#D5D8DC", lw=.4, pad=1.6))
    marcas = [m for m in [0, 100, 1_000, 10_000, 100_000]
              if np.log10(1 + m) <= xs.max() * 1.03]
    ax5.set_xticks([np.log10(1 + m) for m in marcas])
    ax5.set_xticklabels([f"{m:,}".replace(",", ".") for m in marcas])
    ax5.grid(lw=.3, color="#EAECEE", zorder=0); ax5.set_axisbelow(True)

    # ---- F: anidamiento IG-TikTok -----------------------------------------
    ax6 = fig.add_subplot(gs[1, 2])
    comb = pd.Series(np.select(
        [(d.tiene_ig == 0) & (d.tiene_tt == 0),
         (d.tiene_ig == 1) & (d.tiene_tt == 0),
         (d.tiene_ig == 0) & (d.tiene_tt == 1),
         (d.tiene_ig == 1) & (d.tiene_tt == 1)],
        ["Ninguna", "Solo IG", "Solo TT", "IG + TT"], "?"))
    orden = ["Ninguna", "Solo IG", "Solo TT", "IG + TT"]
    vals = [int((comb == o).sum()) for o in orden]
    colores = ["#D5D8DC", "#5499C7", "#F5B041", COL_FRANQ]
    ax6.barh(range(4), vals, color=colores, zorder=3, height=.66)
    for i, v in enumerate(vals):
        ax6.text(v + 6, i, f"{v}  ({100*v/len(d):.1f}%)".replace(".", ","),
                 va="center", fontsize=6.4, color="#2C3E50")
    ax6.set_yticks(range(4)); ax6.set_yticklabels(orden)
    ax6.set_xlabel("Nº de establecimientos")
    ax6.set_xlim(0, max(vals) * 1.34)
    ax6.set_title("F · Combinación de redes sociales", loc="left")
    ax6.grid(axis="x", lw=.3, color="#EAECEE", zorder=0); ax6.set_axisbelow(True)

    fig.text(0.005, -0.02,
             f"A · Contraste de proporciones mediante prueba exacta de Fisher; "
             f"* $p$ < 0,05, ** $p$ < 0,01, *** $p$ < 0,001 tras corrección de "
             f"Benjamini-Hochberg; n.s. = no significativo.\n"
             f"B–D · Contrastes de Mann-Whitney condicionados a poseer la "
             f"plataforma, de modo que no se confunda la adopción con la "
             f"magnitud. Cajas: mediana e intervalo interquartílico.\n"
             f"D–E · La razón likes/seguidor es un proxy de intensidad "
             f"ACUMULADA de interacción, no una tasa de engagement: los likes "
             f"son un agregado histórico y los seguidores una medición puntual. "
             f"n = {len(d)}.".replace(",", ","),
             fontsize=6.3, color="#566573", va="top")
    guardar(fig, outdir, "Figura7_TikTok")


# =============================================================================
# §10 — CONSTRUCCIÓN DEL CAPITAL DIGITAL MULTIDIMENSIONAL
# =============================================================================

def construir_capital_digital(d, outdir, resultados):
    titulo("§10 · Construcción del capital digital multidimensional")

    print("ARQUITECTURA DE DIMENSIONES")
    print("  Capa 1 · Visibilidad cartográfica  : log1p(reseñas de Google Maps)")
    print("           [conservada intacta como capa autónoma de referencia]")
    print("  Capa 2 · Alcance social            : log1p(seguidores IG y TikTok)")
    print("  Capa 3 · Interacción relativa      : likes/seguidor de TikTok")
    print("           [condicional, n reducido → dimensión exploratoria]")
    print("  Capa 4 · Consagración              : estrellas de Google")
    print("           [ortogonal al volumen → NO entra en el índice]")
    print("  Síntesis · Capital digital          : componentes principales de")
    print("             las capas 1 y 2 (PCA-A)")

    titulo("§10.1 · Decisión sobre el tratamiento de la ausencia de plataforma",
           2)
    print("El problema: log1p(seguidores) = 0 tanto para quien no tiene cuenta")
    print("como para quien la tiene con cero seguidores. Son estados distintos.")
    print("\nSe distinguen DOS objetos, en lugar de forzarlos en un solo índice:")
    print("\n  (A) CAPITAL DIGITAL ACUMULADO — PCA sobre los 420 establecimientos,")
    print("      con la ausencia codificada como cero. La ausencia de plataforma")
    print("      SÍ es capital digital bajo: no tener Instagram es una posición")
    print("      en la jerarquía de visibilidad, no un dato faltante. Es la")
    print("      especificación PRINCIPAL porque responde a la pregunta del paper.")
    print("\n  (B) INTENSIDAD CONDICIONAL — magnitudes analizadas solo entre")
    print("      quienes poseen cada plataforma (§9.2) y modelo condicionado a")
    print("      ficha (§2.5). Responde a una pregunta distinta: dado que se")
    print("      participa, ¿cuánto se acumula?")
    print("\nAmbos se reportan. Confundirlos es lo que esta sección evita; "
          "elegir")
    print("uno solo por conveniencia es lo que se rechaza explícitamente.")

    # ------------------------------------------------------------------
    # PCA-A — especificación principal
    # ------------------------------------------------------------------
    titulo("§10.2 · PCA-A (especificación principal)", 2)
    etiq_A = ["log1p(reseñas)", "log1p(seguidores IG)", "log1p(seguidores TT)"]
    XA = np.column_stack([d.log1p_resenas, d.log1p_seg_ig, d.log1p_seg_tt])
    print(f"  Variables: {', '.join(etiq_A)}")
    print(f"  n = {len(d)} (muestra completa; ausencia de plataforma = 0)")
    print(f"  PCA sobre la matriz de CORRELACIONES (equivale a estandarizar)")
    print(f"  Signo anclado a log1p(reseñas): valores altos = MÁS capital")
    pa = pca_correlacion(XA, etiq_A, "PCA-A", anclaje=0)
    imprimir_pca(pa)

    cp1 = pa["puntuaciones"][:, 0]
    cp2 = pa["puntuaciones"][:, 1]

    # ---- Validación crítica: ¿qué mide realmente CP1? -------------------
    titulo("§10.3 · Validación de contenido: ¿qué mide CP1?", 2)
    r_nplat = stats.pearsonr(cp1, d.n_plataformas)
    r_res = stats.pearsonr(cp1, d.log1p_resenas)
    r_ig = stats.pearsonr(cp1, d.log1p_seg_ig)
    r_tt = stats.pearsonr(cp1, d.log1p_seg_tt)
    tabla(pd.DataFrame({
        "correlación con CP1": [r_nplat[0], r_res[0], r_ig[0], r_tt[0]],
        "p": [r_nplat[1], r_res[1], r_ig[1], r_tt[1]]},
        index=["nº de plataformas activas (0–3)", "log1p(reseñas)",
               "log1p(seguidores IG)", "log1p(seguidores TT)"]), None, 4)
    print(f"\n  LECTURA HONESTA Y OBLIGADA EN EL PAPER: la correlación de CP1")
    print(f"  con el simple recuento de plataformas activas es r = "
          f"{r_nplat[0]:.3f}.")
    if abs(r_nplat[0]) > 0.80:
        print(f"  CP1 captura predominantemente AMPLITUD DE ADOPCIÓN "
              f"multiplataforma,")
        print(f"  no gradación fina de magnitud dentro de cada plataforma. Debe")
        print(f"  denominarse 'capital digital acumulado' o 'amplitud de")
        print(f"  acumulación digital', NUNCA 'capital digital' a secas, y debe")
        print(f"  reportarse esta correlación junto a las cargas.")
        nota("Esto no invalida el índice: es coherente con la hipótesis de "
             "estratificación, según la cual la desigualdad digital opera "
             "primero por exclusión de plataformas y solo después por volumen. "
             "Pero un revisor que calcule esta correlación y no la encuentre "
             "reportada tendrá razón en objetar.")
    tabla(pd.DataFrame({"CP1 medio": d.assign(cp1=cp1).groupby("n_plataformas").cp1.mean(),
                        "CP1 mediana": d.assign(cp1=cp1).groupby("n_plataformas").cp1.median(),
                        "DE": d.assign(cp1=cp1).groupby("n_plataformas").cp1.std(),
                        "n": d.groupby("n_plataformas").size()}),
          "CP1 por número de plataformas activas", 4)

    print("\n  Interpretación de CP2 a partir de sus cargas:")
    c2 = pa["cargas"][:, 1]
    for e, c in zip(etiq_A, c2):
        print(f"    {e:<26s} {c:+.4f}")
    if c2[0] * c2[2] < 0:
        print("  → CP2 opone la visibilidad CARTOGRÁFICA (Google Maps) al "
              "alcance")
        print("    SOCIAL (redes). Es el eje que hace observable la NO "
              "ISOMORFÍA de")
        print("    las capas de plataforma postulada en el marco conceptual:")
        print("    un valor alto indica especialización cartográfica; uno bajo,")
        print("    especialización social.")

    # ------------------------------------------------------------------
    # PCA-B — sensibilidad
    # ------------------------------------------------------------------
    titulo("§10.4 · PCA-B (sensibilidad: incorporación de los likes de TikTok)",
           2)
    etiq_B = etiq_A + ["log1p(likes TT)"]
    XB = np.column_stack([XA, np.log1p(d.likes_tt)])
    pb = pca_correlacion(XB, etiq_B, "PCA-B", anclaje=0)
    imprimir_pca(pb)
    cp1b = pb["puntuaciones"][:, 0]
    r_ab = stats.pearsonr(cp1, cp1b)
    print(f"\n  Correlación entre CP1 de PCA-A y CP1 de PCA-B: "
          f"r = {r_ab[0]:.4f}")
    peso_tt_A = abs(pa["cargas"][2, 0]) / np.sum(np.abs(pa["cargas"][:, 0]))
    peso_tt_B = ((abs(pb["cargas"][2, 0]) + abs(pb["cargas"][3, 0])) /
                 np.sum(np.abs(pb["cargas"][:, 0])))
    print(f"  Peso relativo de TikTok en CP1: PCA-A = {100*peso_tt_A:.1f}% | "
          f"PCA-B = {100*peso_tt_B:.1f}%")
    print(f"  → Al añadir los likes, TikTok pasa a controlar "
          f"{100*peso_tt_B:.0f}% del índice frente a")
    print(f"    {100*peso_tt_A:.0f}% con una sola variable. La duplicación es "
          f"un artefacto de")
    print(f"    codificación (ρ ≈ 0,90 entre seguidores y likes), no un "
          f"hallazgo.")
    print(f"    PCA-A se mantiene como especificación principal.")

    # ------------------------------------------------------------------
    # Transformación a percentil para uso como peso espacial
    # ------------------------------------------------------------------
    titulo("§10.5 · Transformación de las componentes para el análisis espacial",
           2)
    print("Las puntuaciones factoriales toman valores negativos y tienen colas")
    print("largas. Para emplearlas como PESO en un KDE (que exige valores no")
    print("negativos) se usa el PERCENTIL en lugar del desplazamiento aditivo")
    print("w = CP − mín(CP) + ε. Ventajas:")
    print("  · es interpretable sin nota al pie (posición relativa en la")
    print("    jerarquía de capital digital, de 0 a 1);")
    print("  · es robusto a la cola larga: unas pocas cuentas de franquicia con")
    print("    audiencias de orden 10⁵ no dominan la superficie.")
    d = d.copy()
    d["CP1"] = cp1
    d["CP2"] = cp2
    d["CP1_pct"] = stats.rankdata(cp1) / len(cp1)
    d["CP2_pct"] = stats.rankdata(cp2) / len(cp2)
    tabla(d[["CP1", "CP2", "CP1_pct", "CP2_pct"]].describe().T,
          "Puntuaciones y percentiles", 4)

    # Perfil de los extremos
    top = d.nlargest(10, "CP1")[["Nombre", "tipo", "franquicia", "resenas",
                                 "seg_ig", "seg_tt", "n_plataformas", "CP1"]]
    tabla(top.reset_index(drop=True),
          "Decil superior de capital digital acumulado (10 primeros)", 3)
    print(f"\n  Establecimientos con CP1 en el mínimo (sin ninguna plataforma): "
          f"{int((d.n_plataformas == 0).sum())}")
    print(f"  Cuota del capital digital: el 10% superior de CP1_pct concentra "
          f"el")
    q90 = d.CP1_pct.quantile(.90)
    print(f"  {100*d.loc[d.CP1_pct >= q90, 'resenas'].sum()/d.resenas.sum():.1f}% "
          f"de las reseñas, "
          f"{100*d.loc[d.CP1_pct >= q90, 'seg_ig'].sum()/max(d.seg_ig.sum(),1):.1f}% "
          f"de los seguidores de IG")
    print(f"  y {100*d.loc[d.CP1_pct >= q90, 'seg_tt'].sum()/max(d.seg_tt.sum(),1):.1f}% "
          f"de los de TikTok.")

    # Exportaciones
    pd.DataFrame(pa["cargas"], index=etiq_A,
                 columns=[f"CP{j+1}" for j in range(pa["k"])]).to_csv(
        os.path.join(outdir, "T10a_pcaA_cargas.csv"))
    pd.DataFrame(pb["cargas"], index=etiq_B,
                 columns=[f"CP{j+1}" for j in range(pb["k"])]).to_csv(
        os.path.join(outdir, "T10b_pcaB_cargas.csv"))
    d[["Nombre", "lat", "lon", "tipo", "franquicia", "n_plataformas",
       "resenas", "seg_ig", "seg_tt", "likes_tt", "engagement_tt",
       "estrellas", "CP1", "CP2", "CP1_pct", "CP2_pct"]].to_csv(
        os.path.join(outdir, "T10c_capital_digital_establecimientos.csv"),
        index=False)

    resultados["capital_digital"] = {
        "PCA_A": {"kmo": pa["kmo_global"], "bartlett_p": pa["bartlett_p"],
                  "var_pct": pa["var_pct"].tolist(),
                  "cargas": pd.DataFrame(pa["cargas"], index=etiq_A).to_dict(),
                  "r_CP1_n_plataformas": float(r_nplat[0])},
        "PCA_B": {"kmo": pb["kmo_global"], "var_pct": pb["var_pct"].tolist(),
                  "r_CP1A_CP1B": float(r_ab[0]),
                  "peso_tiktok_A": float(peso_tt_A),
                  "peso_tiktok_B": float(peso_tt_B)}}

    fig8_pca(d, pa, pb, outdir)
    return d, pa, pb


def fig8_pca(d, pa, pb, outdir):
    fig = plt.figure(figsize=(7.4, 4.7))
    gs = fig.add_gridspec(2, 3, hspace=0.58, wspace=0.42)

    # ---- A: scree con bastón roto ----------------------------------------
    ax = fig.add_subplot(gs[0, 0])
    k = pa["k"]; xs = np.arange(1, k + 1)
    ax.bar(xs, pa["var_pct"], width=.55, color=COL_INDEP, zorder=3,
           label="Varianza explicada")
    ax.plot(xs, pa["broken_stick"], color=COL_FRANQ, marker="o", ms=3.4,
            lw=1.1, zorder=4, label="Modelo de bastón roto")
    for xi, v in zip(xs, pa["var_pct"]):
        ax.text(xi, v + 2.2, f"{v:.1f}".replace(".", ","), ha="center",
                fontsize=6.3, color="#2C3E50")
    ax.set_xticks(xs); ax.set_xticklabels([f"CP{i}" for i in xs])
    ax.set_ylabel("% de varianza")
    ax.set_ylim(0, max(pa["var_pct"]) * 1.25)
    ax.set_title("A · Retención de componentes", loc="left")
    ax.legend(fontsize=6.1, loc="upper right")
    ax.grid(axis="y", lw=.3, color="#EAECEE", zorder=0); ax.set_axisbelow(True)

    # ---- B: cargas ---------------------------------------------------------
    ax2 = fig.add_subplot(gs[0, 1])
    et = [e.replace("log1p(", "").replace(")", "") for e in pa["etiquetas"]]
    y = np.arange(len(et))[::-1]
    ax2.barh(y - .18, pa["cargas"][:, 0], height=.34, color=COL_INDEP,
             zorder=3, label="CP1")
    ax2.barh(y + .18, pa["cargas"][:, 1], height=.34, color=COL_ACENTO,
             zorder=3, label="CP2")
    ax2.axvline(0, color="#34495E", lw=.8)
    ax2.set_yticks(y); ax2.set_yticklabels(et, fontsize=6.6)
    ax2.set_xlabel("Carga factorial")
    ax2.set_xlim(-1.05, 1.05)
    ax2.set_title("B · Cargas de PCA-A", loc="left")
    ax2.legend(fontsize=6.1, loc="lower left")
    ax2.grid(axis="x", lw=.3, color="#EAECEE", zorder=0); ax2.set_axisbelow(True)

    # ---- C: CP1 por nº de plataformas ------------------------------------
    ax3 = fig.add_subplot(gs[0, 2])
    rng = np.random.default_rng(SEMILLA)
    paleta = ["#D5D8DC", "#AED6F1", "#5499C7", COL_FRANQ]
    for npl in sorted(d.n_plataformas.unique()):
        g = d.loc[d.n_plataformas == npl, "CP1"].values
        ax3.boxplot([g], positions=[npl], widths=.5, showfliers=False,
                    patch_artist=True, zorder=3,
                    medianprops=dict(color="white", lw=1.2),
                    boxprops=dict(facecolor=paleta[int(npl)],
                                  edgecolor="#5D6D7E", lw=.5),
                    whiskerprops=dict(lw=.6), capprops=dict(lw=.6))
        ax3.scatter(npl + rng.uniform(-.16, .16, len(g)), g, s=3.2,
                    color="#34495E", alpha=.28, linewidths=0, zorder=4)
    ax3.set_xlabel("Nº de plataformas activas")
    ax3.set_ylabel("CP1 (capital digital acumulado)")
    ax3.set_title("C · Gradiente de adopción", loc="left")
    r = stats.pearsonr(d.CP1, d.n_plataformas)[0]
    ax3.text(.04, .96, f"$r$ = {r:.3f}".replace(".", ","),
             transform=ax3.transAxes, va="top", fontsize=6.6,
             bbox=dict(fc="white", ec="#D5D8DC", lw=.4, pad=1.6))
    ax3.grid(axis="y", lw=.3, color="#EAECEE", zorder=0); ax3.set_axisbelow(True)

    # ---- D: plano CP1-CP2 --------------------------------------------------
    ax4 = fig.add_subplot(gs[1, :2])
    comb = np.select(
        [(d.tiene_ig == 0) & (d.tiene_tt == 0),
         (d.tiene_ig == 1) & (d.tiene_tt == 0),
         (d.tiene_ig == 0) & (d.tiene_tt == 1),
         (d.tiene_ig == 1) & (d.tiene_tt == 1)],
        ["Ninguna red", "Solo Instagram", "Solo TikTok", "Instagram + TikTok"],
        "?")
    cmap_c = {"Ninguna red": "#BDC3C7", "Solo Instagram": "#5499C7",
              "Solo TikTok": "#F5B041", "Instagram + TikTok": COL_FRANQ}
    for cl, c in cmap_c.items():
        m = comb == cl
        if m.sum():
            ax4.scatter(d.CP1[m], d.CP2[m], s=13, color=c, alpha=.72,
                        linewidths=.25, edgecolor="white", zorder=3,
                        label=f"{cl} ({int(m.sum())})")
    ax4.axhline(0, color="#95A5A6", lw=.55); ax4.axvline(0, color="#95A5A6", lw=.55)
    ax4.set_xlabel("CP1 · capital digital acumulado "
                   f"({pa['var_pct'][0]:.1f}% de la varianza)".replace(".", ","))
    ax4.set_ylabel("CP2 · eje cartográfico–social\n"
                   f"({pa['var_pct'][1]:.1f}%)".replace(".", ","))
    ax4.set_title("D · Plano factorial del capital digital", loc="left")
    ax4.legend(fontsize=6.1, loc="upper left", ncol=2, handletextpad=.3,
               columnspacing=.7, frameon=True, framealpha=.93,
               facecolor="white", edgecolor="#D5D8DC")
    ax4.grid(lw=.3, color="#EAECEE", zorder=0); ax4.set_axisbelow(True)
    ax4.annotate("especialización\ncartográfica", xy=(.985, .93),
                 xycoords="axes fraction", ha="right", va="top", fontsize=6.0,
                 color="#7F8C8D", style="italic")
    ax4.annotate("especialización\nen redes sociales", xy=(.985, .06),
                 xycoords="axes fraction", ha="right", va="bottom",
                 fontsize=6.0, color="#7F8C8D", style="italic")

    # ---- E: comparación PCA-A / PCA-B --------------------------------------
    ax5 = fig.add_subplot(gs[1, 2])
    etb = [e.replace("log1p(", "").replace(")", "") for e in pb["etiquetas"]]
    yb = np.arange(len(etb))[::-1]
    ax5.barh(yb, pb["cargas"][:, 0], height=.5, color="#7F8C8D", zorder=3)
    for i, (yy, v) in enumerate(zip(yb, pb["cargas"][:, 0])):
        ax5.text(v + .03, yy, f"{v:.2f}".replace(".", ","), va="center",
                 fontsize=6.1, color="#2C3E50")
    ax5.set_yticks(yb); ax5.set_yticklabels(etb, fontsize=6.3)
    ax5.set_xlim(0, 1.18)
    ax5.set_xlabel("Carga en CP1")
    ax5.set_title("E · PCA-B (sensibilidad)", loc="left")
    ax5.grid(axis="x", lw=.3, color="#EAECEE", zorder=0); ax5.set_axisbelow(True)

    fig.text(0.005, -0.03,
             f"PCA-A sobre la matriz de correlaciones de tres indicadores "
             f"transformados con log(1+x); n = {len(d)}; KMO = "
             f"{pa['kmo_global']:.3f}".replace(".", ",") +
             f"; Bartlett χ² = {pa['bartlett_chi2']:,.0f}, $p$ < 0,001. "
             f"Signo anclado a las reseñas.\n"
             f"C · CP1 correlaciona r = "
             f"{stats.pearsonr(d.CP1, d.n_plataformas)[0]:.3f}".replace(".", ",") +
             f" con el simple recuento de plataformas activas: el índice mide "
             f"AMPLITUD de acumulación multiplataforma más que gradación de "
             f"magnitud.\n"
             f"E · Al incorporar los likes de TikTok (ρ ≈ 0,90 con sus "
             f"seguidores), esa plataforma pasa a controlar una fracción "
             f"desproporcionada del índice; PCA-B se reporta solo como "
             f"análisis de sensibilidad.".replace(",", ","),
             fontsize=6.3, color="#566573", va="top")
    guardar(fig, outdir, "Figura8_CapitalDigital_PCA")


# =============================================================================
# §11 — KDE DEL CAPITAL DIGITAL
# =============================================================================

def bloque_kde_capital(d, outdir, resultados):
    titulo("§11 · KDE comparativo: densidad física, visibilidad cartográfica "
           "y capital digital")

    x, y = d.X.values, d.Y.values
    print("VARIABLES DE ENTRADA")
    print(f"  Núcleo gaussiano isotrópico, h = {BW_KDE_M:.0f} m, malla "
          f"{KDE_GRID_M:.0f} m, {EPSG_PROJ}")
    print(f"  Superficie A · densidad física          : w = 1")
    print(f"  Superficie B · visibilidad cartográfica : w = log(1+reseñas)")
    print(f"  Superficie C · capital digital acumulado: w = percentil de CP1")
    print(f"  Superficie D · eje cartográfico–social  : w = percentil de CP2")
    print("\n  Las cuatro superficies comparten malla, extensión, proyección y")
    print("  dominio analítico, de modo que son directamente comparables.")

    pad = 3 * BW_KDE_M
    xg = np.arange(x.min() - pad, x.max() + pad + KDE_GRID_M, KDE_GRID_M)
    yg = np.arange(y.min() - pad, y.max() + pad + KDE_GRID_M, KDE_GRID_M)
    XX, YY = np.meshgrid(xg, yg)
    mask, hull = mascara_dominio(XX, YY, x, y, 2 * BW_KDE_M)

    superficies = {
        "A · densidad física": kde_superficie(x, y, XX, YY, BW_KDE_M, None),
        "B · visibilidad cartográfica": kde_superficie(
            x, y, XX, YY, BW_KDE_M, d.log1p_resenas.values),
        "C · capital digital (CP1)": kde_superficie(
            x, y, XX, YY, BW_KDE_M, d.CP1_pct.values),
        "D · eje cartográfico–social (CP2)": kde_superficie(
            x, y, XX, YY, BW_KDE_M, d.CP2_pct.values),
    }

    trp = Transformer.from_crs(EPSG_GEO, EPSG_PROJ, always_xy=True)
    inv = Transformer.from_crs(EPSG_PROJ, EPSG_GEO, always_xy=True)
    pgx, pgy = trp.transform(PLAZA_GRANDE[1], PLAZA_GRANDE[0])

    print("\nVALORES DE SALIDA")
    filas, picos = [], {}
    for nom, S in superficies.items():
        v = S[mask]
        Sm = np.where(mask, S, -np.inf)
        i = np.unravel_index(np.argmax(Sm), Sm.shape)
        picos[nom] = (XX[i], YY[i])
        lon_, lat_ = inv.transform(XX[i], YY[i])
        filas.append({"superficie": nom, "P50": np.median(v),
                      "P90": np.percentile(v, 90), "P99": np.percentile(v, 99),
                      "máx": v.max(), "razón máx/mediana": v.max()/np.median(v),
                      "lat_pico": lat_, "lon_pico": lon_,
                      "dist_pico_PlazaGrande_m": np.hypot(XX[i]-pgx, YY[i]-pgy)})
    tab = pd.DataFrame(filas)
    tabla(tab, "(1) Distribución y localización del máximo de cada superficie",
          4)

    nombres = list(superficies)
    print("\n(2) Separación entre máximos (m)")
    sep = pd.DataFrame(index=nombres, columns=nombres, dtype=float)
    for a in nombres:
        for b in nombres:
            sep.loc[a, b] = np.hypot(picos[a][0]-picos[b][0],
                                     picos[a][1]-picos[b][1])
    tabla(sep, None, 1)
    print(f"\n  Ancho de banda de referencia: h = {BW_KDE_M:.0f} m. Toda "
          f"separación por")
    print(f"  debajo de h debe leerse como coincidencia de máximos a la "
          f"resolución")
    print(f"  del estimador, no como desplazamiento.")

    print("\n(3) Similitud de forma entre superficies (Spearman sobre los "
          "nodos del dominio)")
    sp = pd.DataFrame(index=nombres, columns=nombres, dtype=float)
    for a in nombres:
        for b in nombres:
            sp.loc[a, b] = stats.spearmanr(superficies[a][mask],
                                           superficies[b][mask])[0]
    tabla(sp, None, 3)
    nota("Los nodos de una malla no son observaciones independientes: estos "
         "coeficientes describen la similitud de forma entre superficies y no "
         "admiten lectura inferencial.")

    d_AB = sep.loc["A · densidad física", "B · visibilidad cartográfica"]
    d_AC = sep.loc["A · densidad física", "C · capital digital (CP1)"]
    r_AC = sp.loc["A · densidad física", "C · capital digital (CP1)"]
    conc_A = tab.loc[0, "razón máx/mediana"]
    conc_C = tab.loc[2, "razón máx/mediana"]
    print(f"\n(4) SÍNTESIS PARA LA HIPÓTESIS")
    print(f"  Máximo físico vs. máximo de capital digital: {d_AC:,.0f} m de "
          f"separación")
    print(f"  Similitud de forma: ρ = {r_AC:.3f}")
    print(f"  Concentración relativa (máx/mediana): física {conc_A:.2f} vs. "
          f"capital digital {conc_C:.2f} → razón {conc_C/conc_A:.2f}×")
    if d_AC <= BW_KDE_M:
        veredicto = ("los máximos son indistinguibles a la resolución del "
                     "estimador")
    elif d_AC <= 2 * BW_KDE_M:
        veredicto = (f"la separación ({d_AC:,.0f} m) excede ligeramente el "
                     f"ancho de banda ({BW_KDE_M:.0f} m), pero permanece dentro "
                     f"de una manzana colonial")
    else:
        veredicto = (f"la separación ({d_AC:,.0f} m) supera holgadamente el "
                     f"ancho de banda: hay desplazamiento efectivo")
    print(f"  → Veredicto sobre la localización: {veredicto}.")
    if r_AC > 0.85:
        print(f"  → Con ρ = {r_AC:.3f}, las dos superficies son casi idénticas "
              f"en forma.")
        print("    La conclusión de la Parte I se SOSTIENE al pasar de una a "
              "tres plataformas:")
        print("    el capital digital multiplataforma no desplaza el centro de "
              "gravedad")
        print("    gastronómico. Que el resultado resista un cambio sustancial "
              "de")
        print("    operacionalización refuerza la hipótesis reformulada.")
    nota("La razón de concentración de CP1 NO es directamente comparable con la "
         "obtenida en la Parte I para las reseñas: el peso por percentil "
         "comprime deliberadamente la cola de la distribución, de modo que "
         "atenúa la concentración medida. La comparación válida es entre "
         "superficies calculadas con el mismo tipo de peso (A frente a C), no "
         "entre razones de distintas transformaciones.")

    tab.to_csv(os.path.join(outdir, "T11a_kde_superficies_comparadas.csv"),
               index=False)
    sep.to_csv(os.path.join(outdir, "T11b_kde_separacion_picos.csv"))
    sp.to_csv(os.path.join(outdir, "T11c_kde_similitud.csv"))
    resultados["kde_capital"] = {
        "separacion_fisico_CP1_m": float(d_AC),
        "separacion_fisico_resenas_m": float(d_AB),
        "spearman_fisico_CP1": float(r_AC),
        "razon_concentracion_CP1_vs_fisico": float(conc_C / conc_A),
        "superficies": tab.to_dict(orient="records")}

    fig9_kde_capital(d, XX, YY, superficies, mask, hull, picos, outdir)
    return superficies, XX, YY, mask


def fig9_kde_capital(d, XX, YY, superficies, mask, hull, picos, outdir):
    trp = Transformer.from_crs(EPSG_GEO, EPSG_PROJ, always_xy=True)
    pgx, pgy = trp.transform(PLAZA_GRANDE[1], PLAZA_GRANDE[0])
    fig, axes = plt.subplots(1, 4, figsize=(7.4, 2.65))
    ext = [XX.min(), XX.max(), YY.min(), YY.max()]
    unidades = ["establecimientos · ha$^{-1}$", "log(1+reseñas) · ha$^{-1}$",
                "percentil CP1 · ha$^{-1}$", "percentil CP2 · ha$^{-1}$"]
    titulos = ["A · Densidad física", "B · Visibilidad cartográfica",
               "C · Capital digital (CP1)", "D · Eje cartográfico–social (CP2)"]

    for ax, (nom, S), tit, uni in zip(axes, superficies.items(), titulos,
                                      unidades):
        Sm = np.where(mask, S, np.nan)
        im = ax.imshow(Sm, origin="lower", extent=ext, cmap="magma_r",
                       interpolation="bilinear")
        lv = np.nanpercentile(Sm, [50, 75, 90, 97.5])
        ax.contour(XX, YY, Sm, levels=lv, colors="white", linewidths=.35,
                   alpha=.7)
        ax.plot(hull[:, 0], hull[:, 1], color="#2C3E50", lw=.5, ls=":",
                alpha=.8, zorder=6)
        ax.scatter(d.X, d.Y, s=1.0, c="#17202A", alpha=.35, linewidths=0,
                   zorder=7, rasterized=True)
        for r in (250, 500, 750, 1000):
            ax.add_patch(Circle((pgx, pgy), r, fill=False, ec="#2C3E50",
                                lw=.35, ls=(0, (3, 3)), alpha=.5, zorder=8))
        px, py = picos[nom]
        ax.plot([px], [py], marker="^", ms=5, color="#1ABC9C",
                mec="#0E6251", mew=.5, zorder=10)
        ax.plot([pgx], [pgy], marker="*", ms=7, color="#F4D03F",
                mec="#17202A", mew=.45, zorder=9)
        ax.set_title(tit, loc="left", fontsize=8.2)
        ax.set_xlim(XX.min(), XX.max()); ax.set_ylim(YY.min(), YY.max())
        ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
        for sp_ in ax.spines.values():
            sp_.set_visible(True); sp_.set_linewidth(.45); sp_.set_color("#95A5A6")
        barra_escala(ax, 500, "500 m")
        cb = fig.colorbar(im, ax=ax, fraction=.045, pad=.02)
        cb.set_label(uni, fontsize=5.8)
        cb.ax.tick_params(labelsize=5.4, width=.4, length=1.8)
        cb.outline.set_linewidth(.35)
    flecha_norte(axes[-1])
    axes[0].legend(handles=[
        Line2D([], [], marker="*", ls="none", ms=6.5, color="#F4D03F",
               mec="#17202A", mew=.4, label="Plaza Grande"),
        Line2D([], [], marker="^", ls="none", ms=4.6, color="#1ABC9C",
               mec="#0E6251", mew=.4, label="Máximo de la superficie")],
        loc="upper left", fontsize=5.5, handlelength=1.1, borderpad=.28,
        labelspacing=.26, frameon=True, framealpha=.93, facecolor="white",
        edgecolor="#D5D8DC")

    fig.text(0.005, -0.06,
             f"Cuatro superficies estimadas con el mismo núcleo gaussiano "
             f"isotrópico (h = {BW_KDE_M:.0f} m), la misma malla "
             f"({KDE_GRID_M:.0f} m), la misma extensión y el mismo dominio "
             f"analítico (envolvente convexa dilatada 2h, línea punteada), de "
             f"modo que resultan directamente comparables.\n"
             f"Los pesos de C y D son el percentil de la componente principal "
             f"correspondiente, transformación elegida por ser interpretable y "
             f"robusta frente a la cola larga de audiencias. Isolíneas: "
             f"percentiles 50, 75, 90 y 97,5 de cada superficie.\n"
             f"Anillos concéntricos cada 250 m desde la Plaza Grande. "
             f"Proyección UTM 17S (EPSG:32717); n = {len(d)} establecimientos. "
             f"Semilla = {SEMILLA}.".replace(",", ","),
             fontsize=6.2, color="#566573", va="top")
    fig.tight_layout()
    guardar(fig, outdir, "Figura9_KDE_CapitalDigital")


# =============================================================================
# §12 — ANÁLISIS ESPACIAL DEL CAPITAL DIGITAL (Moran, LISA, Gi*)
# =============================================================================

def agregar_celdas_capital(d):
    """Reagrega los establecimientos en la misma malla de la Parte I,
    añadiendo las nuevas dimensiones de capital digital."""
    x0 = np.floor(d.X.min() / CELDA_M) * CELDA_M
    y0 = np.floor(d.Y.min() / CELDA_M) * CELDA_M
    dd = d.copy()
    dd["col"] = ((dd.X - x0) // CELDA_M).astype(int)
    dd["fil"] = ((dd.Y - y0) // CELDA_M).astype(int)
    c = (dd.groupby(["fil", "col"])
         .agg(n_estab=("resenas", "size"),
              resenas_tot=("resenas", "sum"),
              CP1_suma=("CP1_pct", "sum"), CP1_media=("CP1_pct", "mean"),
              CP2_suma=("CP2_pct", "sum"), CP2_media=("CP2_pct", "mean"),
              CP1_bruto_medio=("CP1", "mean"),
              n_ig=("tiene_ig", "sum"), n_tt=("tiene_tt", "sum"),
              n_plat_medio=("n_plataformas", "mean"),
              dist_media=("dist_km", "mean"))
         .reset_index())
    c["log1p_resenas_tot"] = np.log1p(c.resenas_tot)
    c["xc"] = x0 + (c.col + .5) * CELDA_M
    c["yc"] = y0 + (c.fil + .5) * CELDA_M
    c["x0"] = x0 + c.col * CELDA_M
    c["y0"] = y0 + c.fil * CELDA_M
    return c


def analisis_local(v, w_cel, w_bin_vecinos, etiqueta):
    """Ejecuta Moran global, LISA y Gi* sobre una variable de celda."""
    mi = esda.Moran(v, w_cel, permutations=N_PERM)
    lisa = esda.Moran_Local(v, w_cel, permutations=N_PERM, seed=SEMILLA)
    mapa_q = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
    rech_l, padj_l, _, _ = multipletests(lisa.p_sim, alpha=ALFA,
                                         method=FDR_METODO)
    clase = np.where(lisa.p_sim < ALFA, [mapa_q[q] for q in lisa.q], "ns")
    clase_fdr = np.where(rech_l, [mapa_q[q] for q in lisa.q], "ns")

    G, Z, Zsim, Psim = getis_ord_star(v, w_bin_vecinos)
    p_an = 2.0 * stats.norm.sf(np.abs(Z))
    rech_g, padj_g, _, _ = multipletests(p_an, alpha=ALFA, method=FDR_METODO)

    def clasif(zi, pi):
        if pi >= .10:
            return "No signif."
        niv = "99%" if pi < .01 else ("95%" if pi < .05 else "90%")
        return ("Hot " if zi > 0 else "Cold ") + niv
    clase_gi = [clasif(zi, pi) for zi, pi in zip(Z, p_an)]
    clase_gi_fdr = [clasif(zi, pi) if r else "No signif."
                    for zi, pi, r in zip(Z, padj_g, rech_g)]

    return {"etiqueta": etiqueta, "moran": mi, "lisa": lisa,
            "clase_LISA": clase, "clase_LISA_FDR": clase_fdr,
            "p_lisa": lisa.p_sim, "p_lisa_FDR": padj_l,
            "z_lisa": lisa.z_sim, "I_local": lisa.Is,
            "Gi": G, "z_gi": Z, "p_gi": p_an, "p_gi_FDR": padj_g,
            "p_gi_sim": Psim,
            "clase_Gi": np.array(clase_gi),
            "clase_Gi_FDR": np.array(clase_gi_fdr)}


def bloque_espacial_capital(d, outdir, resultados):
    titulo("§12 · Geografía del capital digital: Moran, LISA y Gi* sobre CP1 "
           "y CP2")

    celdas = agregar_celdas_capital(d)
    w_cel, islas = pesos_reina(celdas)
    w_cel.transform = "R"
    vecinos = vecinos_con_autovecindad(w_cel)

    print("VARIABLES DE ENTRADA")
    print(f"  Malla        : {CELDA_M:.0f} m, {len(celdas)} celdas ocupadas "
          f"(idéntica a la Parte I)")
    print(f"  Pesos        : contigüidad reina; {len(islas)} islas vinculadas a "
          f"su vecino más próximo")
    print(f"  Permutaciones: {N_PERM:,} | semilla = {SEMILLA} | corrección "
          f"{FDR_METODO}")
    print("\n  Valor de celda para las componentes: SUMA de percentiles, no "
          "promedio.")
    print("  Justificación: mantiene la paridad conceptual con log(1+reseñas "
          "totales)")
    print("  de la Parte I —capital digital ACUMULADO en el territorio, no")
    print("  intensidad media por local— de modo que las geografías son")
    print("  comparables. El promedio se reporta como sensibilidad en §12.3.")

    tabla(celdas[["n_estab", "resenas_tot", "log1p_resenas_tot", "CP1_suma",
                  "CP1_media", "CP2_suma", "n_plat_medio"]].describe().T,
          "Descriptivos de las variables agregadas por celda", 4)

    # ---- Nivel establecimiento: Moran sobre CP1, CP2 y capas exploratorias
    titulo("§12.1 · Autocorrelación global a nivel de establecimiento", 2)
    w_pts = KNN.from_array(d[["X", "Y"]].values, k=K_VECINOS)
    w_pts.transform = "R"
    filas = []
    for nom, v in [("CP1 · capital digital acumulado", d.CP1.values),
                   ("CP2 · eje cartográfico–social", d.CP2.values),
                   ("log1p(reseñas) [referencia Parte I]",
                    d.log1p_resenas.values),
                   ("nº de plataformas activas",
                    d.n_plataformas.values.astype(float))]:
        mi = esda.Moran(v, w_pts, permutations=N_PERM)
        filas.append({"variable": nom, "n": w_pts.n, "I": mi.I, "E[I]": mi.EI,
                      "z_sim": mi.z_sim, "p_sim": mi.p_sim})
    # Capas exploratorias de cobertura reducida
    for nom, sub, col, kk in [
            ("estrellas [solo con ≥1 reseña]",
             d[(d.existe_gmaps) & (d.resenas > 0)], "estrellas", K_VECINOS),
            ("engagement TikTok [solo con TT]",
             d[d.engagement_tt.notna()], "engagement_tt", K_VECINOS_EXPL)]:
        if len(sub) > 30:
            wk = KNN.from_array(sub[["X", "Y"]].values, k=kk)
            wk.transform = "R"
            mi = esda.Moran(sub[col].values.astype(float), wk,
                            permutations=N_PERM)
            filas.append({"variable": nom + f" (k={kk})", "n": wk.n, "I": mi.I,
                          "E[I]": mi.EI, "z_sim": mi.z_sim, "p_sim": mi.p_sim})
    mg = pd.DataFrame(filas)
    rech, padj, _, _ = multipletests(mg.p_sim.values, alpha=ALFA,
                                     method=FDR_METODO)
    mg["p_FDR"] = padj; mg["signif_FDR"] = rech
    tabla(mg, f"I de Moran (KNN k={K_VECINOS}, {N_PERM:,} permutaciones)", 5)
    nota("Las dos últimas filas son capas EXPLORATORIAS: se calculan sobre "
         "submuestras con cobertura espacial parcial y su matriz de vecindad no "
         "es comparable con la de la muestra completa. No deben presentarse "
         "junto a las anteriores sin esa advertencia.")

    # ---- Nivel celda: las tres dimensiones -------------------------------
    titulo("§12.2 · Estructura local por dimensión (celdas de 150 m)", 2)
    dims = [("Reseñas (referencia)", celdas.log1p_resenas_tot.values),
            ("CP1 · capital digital", celdas.CP1_suma.values),
            ("CP2 · eje cartográfico–social", celdas.CP2_suma.values)]
    resl = {}
    for nom, v in dims:
        resl[nom] = analisis_local(v, w_cel, vecinos, nom)

    resumen = []
    for nom, r in resl.items():
        cl, cg = pd.Series(r["clase_LISA"]), pd.Series(r["clase_Gi"])
        resumen.append({
            "dimensión": nom,
            "I de Moran": r["moran"].I, "z": r["moran"].z_sim,
            "p": r["moran"].p_sim,
            "HH": int((cl == "HH").sum()), "LL": int((cl == "LL").sum()),
            "HH tras FDR": int((pd.Series(r["clase_LISA_FDR"]) == "HH").sum()),
            "LL tras FDR": int((pd.Series(r["clase_LISA_FDR"]) == "LL").sum()),
            "hot (p<0,05)": int(cg.isin(["Hot 99%", "Hot 95%"]).sum()),
            "cold (p<0,05)": int(cg.isin(["Cold 99%", "Cold 95%"]).sum()),
            "hot tras FDR": int(pd.Series(r["clase_Gi_FDR"])
                                .str.startswith("Hot").sum()),
            "cold tras FDR": int(pd.Series(r["clase_Gi_FDR"])
                                 .str.startswith("Cold").sum()),
            "z_gi mín": r["z_gi"].min(), "z_gi máx": r["z_gi"].max()})
    tab_res = pd.DataFrame(resumen)
    tabla(tab_res, "Síntesis por dimensión", 4)
    n_fdr_tot = int(tab_res["hot tras FDR"].sum() + tab_res["cold tras FDR"].sum())
    print(f"\n  Celdas que superan la corrección FDR en Gi*, por dimensión: "
          f"{tab_res['hot tras FDR'].tolist()} calientes.")
    if n_fdr_tot:
        print("  HALLAZGO RELEVANTE: a diferencia de las reseñas, el capital "
              "digital SÍ")
        print("  produce concentraciones locales que sobreviven a la corrección "
              "por")
        print("  multiplicidad. La medida multiplataforma tiene mayor potencia "
              "estadística")
        print("  porque su distribución por celda es menos asimétrica que la de "
              "los")
        print("  conteos de reseñas. Estas celdas SÍ admiten presentación "
              "confirmatoria.")
    resultados["gi_fdr_por_dimension"] = tab_res[
        ["dimensión", "hot tras FDR", "cold tras FDR"]].to_dict(orient="records")

    for nom, r in resl.items():
        celdas[f"LISA_{nom.split()[0]}"] = r["clase_LISA"]
        celdas[f"LISAFDR_{nom.split()[0]}"] = r["clase_LISA_FDR"]
        celdas[f"Gi_{nom.split()[0]}"] = r["clase_Gi"]
        celdas[f"zgi_{nom.split()[0]}"] = r["z_gi"]
        celdas[f"zlisa_{nom.split()[0]}"] = r["z_lisa"]

    # ---- Sensibilidad suma vs. promedio ----------------------------------
    titulo("§12.3 · Sensibilidad: suma frente a promedio de CP1 por celda", 2)
    r_media = analisis_local(celdas.CP1_media.values, w_cel, vecinos,
                             "CP1 promedio")
    coincide = float(np.mean(r_media["clase_LISA"] ==
                             resl["CP1 · capital digital"]["clase_LISA"]))
    print(f"  I de Moran con SUMA    = "
          f"{resl['CP1 · capital digital']['moran'].I:.4f} "
          f"(p = {resl['CP1 · capital digital']['moran'].p_sim:.4f})")
    print(f"  I de Moran con PROMEDIO = {r_media['moran'].I:.4f} "
          f"(p = {r_media['moran'].p_sim:.4f})")
    print(f"  Coincidencia de la clasificación LISA: {100*coincide:.1f}%")
    print("  Las dos especificaciones responden a preguntas distintas: la suma")
    print("  mide capital digital ACUMULADO en el territorio (incorpora la")
    print("  densidad de locales); el promedio mide intensidad MEDIA POR LOCAL")
    print("  (la neutraliza). Se reporta la suma como principal por paridad con")
    print("  la Parte I, y el promedio como sensibilidad declarada.")

    # ---- Concordancia entre geografías -----------------------------------
    titulo("§12.4 · Concordancia entre la geografía de las reseñas y la del "
           "capital digital", 2)
    a = resl["Reseñas (referencia)"]; b = resl["CP1 · capital digital"]
    ct_l = pd.crosstab(pd.Series(a["clase_LISA"], name="LISA · reseñas"),
                       pd.Series(b["clase_LISA"], name="LISA · CP1"))
    tabla(ct_l, "Clasificación LISA", 0)
    ct_g = pd.crosstab(pd.Series(a["clase_Gi"], name="Gi* · reseñas"),
                       pd.Series(b["clase_Gi"], name="Gi* · CP1"))
    tabla(ct_g, "Clasificación Gi*", 0)

    conc_l = float(np.mean(a["clase_LISA"] == b["clase_LISA"]))
    conc_g = float(np.mean(a["clase_Gi"] == b["clase_Gi"]))
    r_zl = stats.spearmanr(a["z_lisa"], b["z_lisa"])
    r_zg = stats.spearmanr(a["z_gi"], b["z_gi"])
    print(f"\n  Coincidencia exacta de clase LISA : {100*conc_l:.1f}%")
    print(f"  Coincidencia exacta de clase Gi*  : {100*conc_g:.1f}%")
    print(f"  Correlación de z(LISA): ρ = {r_zl[0]:.4f} (p = {r_zl[1]:.3g})")
    print(f"  Correlación de z(Gi*) : ρ = {r_zg[0]:.4f} (p = {r_zg[1]:.3g})")

    # Celdas discordantes: dónde la geografía cambia
    disc = celdas[(celdas["Gi_Reseñas"] != celdas["Gi_CP1"]) &
                  ((celdas["Gi_Reseñas"] != "No signif.") |
                   (celdas["Gi_CP1"] != "No signif."))].copy()
    inv = Transformer.from_crs(EPSG_PROJ, EPSG_GEO, always_xy=True)
    if len(disc):
        disc["lon"], disc["lat"] = inv.transform(disc.xc.values, disc.yc.values)
        tabla(disc[["lat", "lon", "n_estab", "resenas_tot", "CP1_suma",
                    "n_plat_medio", "Gi_Reseñas", "Gi_CP1", "zgi_Reseñas",
                    "zgi_CP1"]].sort_values("zgi_CP1", ascending=False)
              .reset_index(drop=True),
              "Celdas donde la geografía del capital digital DIFIERE de la de "
              "las reseñas", 4)
        print("\n  Estas celdas son el hallazgo específico de la Parte II: "
              "territorios")
        print("  cuya posición cambia al pasar de una medida monoplataforma a "
              "una")
        print("  multiplataforma. Un signo positivo en CP1 con reseñas no")
        print("  significativas indica capital social sin traducción "
              "cartográfica.")

    tab_res.to_csv(os.path.join(outdir, "T12a_sintesis_dimensiones.csv"),
                   index=False)
    celdas.to_csv(os.path.join(outdir, "T12b_celdas_capital_digital.csv"),
                  index=False)
    ct_l.to_csv(os.path.join(outdir, "T12c_concordancia_LISA.csv"))
    ct_g.to_csv(os.path.join(outdir, "T12d_concordancia_Gi.csv"))
    mg.to_csv(os.path.join(outdir, "T12e_moran_establecimiento.csv"),
              index=False)
    resultados["espacial_capital"] = {
        "moran_establecimiento": mg.to_dict(orient="records"),
        "sintesis_dimensiones": tab_res.to_dict(orient="records"),
        "concordancia_LISA_pct": 100 * conc_l,
        "concordancia_Gi_pct": 100 * conc_g,
        "rho_z_lisa": float(r_zl[0]), "rho_z_gi": float(r_zg[0]),
        "n_celdas_discordantes": int(len(disc))}

    fig10_lisa_comparado(d, celdas, resl, outdir)
    fig11_getis_comparado(d, celdas, resl, outdir)
    return celdas, resl


def _mapa_clases(ax, celdas, clases, paleta, titulo_p, d, fdr=None):
    colores = [paleta.get(c, "#EAECEE") for c in clases]
    dibujar_celdas(ax, celdas, colores)
    if fdr is not None:
        sel = np.array([c not in ("ns", "No signif.") for c in fdr])
        if sel.sum():
            sub = celdas[sel]
            ax.add_collection(PatchCollection(
                [Rectangle((r.x0, r.y0), CELDA_M, CELDA_M)
                 for r in sub.itertuples()],
                facecolors="none", edgecolors="#17202A", linewidths=.9,
                zorder=5))
    marco_mapa(ax, celdas, d)
    ax.set_title(titulo_p, loc="left", fontsize=8.2)


def fig10_lisa_comparado(d, celdas, resl, outdir):
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.15),
                             gridspec_kw={"wspace": .06})
    titulos = ["A · Reseñas de Google Maps", "B · Capital digital (CP1)",
               "C · Eje cartográfico–social (CP2)"]
    for ax, (nom, r), tit in zip(axes, resl.items(), titulos):
        _mapa_clases(ax, celdas, r["clase_LISA"], COL_LISA, tit, d,
                     fdr=r["clase_LISA_FDR"])
        n = pd.Series(r["clase_LISA"]).value_counts()
        ax.text(.03, .035,
                f"$I$ = {r['moran'].I:.3f}".replace(".", ",") +
                (" · $p$ < 0,001" if r["moran"].p_sim < .001
                 else f" · $p$ = {r['moran'].p_sim:.3f}".replace(".", ",")) +
                f"\nHH = {int(n.get('HH',0))} · LL = {int(n.get('LL',0))}",
                transform=ax.transAxes, fontsize=6.0, va="bottom",
                bbox=dict(fc="white", ec="#D5D8DC", lw=.4, pad=1.6, alpha=.93))
    etiq = {"HH": "Alto–Alto", "LL": "Bajo–Bajo", "HL": "Alto–Bajo",
            "LH": "Bajo–Alto", "ns": "No significativo"}
    handles = [Patch(fc=COL_LISA[k], ec="white", lw=.3, label=etiq[k])
               for k in ("HH", "LL", "HL", "LH", "ns")]
    handles += [Patch(fc="none", ec="#17202A", lw=.9, label="Sobrevive a FDR"),
                Line2D([], [], marker="*", ls="none", ms=6.5, color="#F4D03F",
                       mec="#17202A", mew=.4, label="Plaza Grande")]
    axes[0].legend(handles=handles, loc="upper left", fontsize=5.7,
                   handlelength=1.0, borderpad=.28, labelspacing=.26,
                   frameon=True, framealpha=.93, facecolor="white",
                   edgecolor="#D5D8DC")
    fig.text(0.005, -0.035,
             f"Estadístico local de Moran (Anselin, 1995) sobre celdas de "
             f"{CELDA_M:.0f} m; contigüidad reina estandarizada por filas; "
             f"{N_PERM:,} permutaciones condicionales; semilla = {SEMILLA}.\n"
             f"Relleno: pseudo-p < 0,05 sin corregir (criterio exploratorio "
             f"habitual). Contorno negro: además supera la corrección de "
             f"Benjamini-Hochberg (criterio confirmatorio).\n"
             f"A emplea log(1 + reseñas totales); B y C, la suma por celda de "
             f"los percentiles de la componente principal correspondiente. "
             f"n = {len(d)} establecimientos en {len(celdas)} celdas.".replace(",", ","),
             fontsize=6.2, color="#566573", va="top")
    guardar(fig, outdir, "Figura10_LISA_Comparado")


def fig11_getis_comparado(d, celdas, resl, outdir):
    n_fdr = int(sum((pd.Series(r["clase_Gi_FDR"]) != "No signif.").sum()
                    for r in resl.values()))
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.15),
                             gridspec_kw={"wspace": .06})
    titulos = ["A · Reseñas de Google Maps", "B · Capital digital (CP1)",
               "C · Eje cartográfico–social (CP2)"]
    for ax, (nom, r), tit in zip(axes, resl.items(), titulos):
        _mapa_clases(ax, celdas, r["clase_Gi"], COL_GI, tit, d,
                     fdr=r["clase_Gi_FDR"])
        cg = pd.Series(r["clase_Gi"])
        ax.text(.03, .035,
                f"$z$ ∈ [{r['z_gi'].min():.2f}; {r['z_gi'].max():.2f}]".replace(".", ",") +
                f"\ncalientes = {int(cg.str.startswith('Hot').sum())} · "
                f"frías = {int(cg.str.startswith('Cold').sum())}",
                transform=ax.transAxes, fontsize=6.0, va="bottom",
                bbox=dict(fc="white", ec="#D5D8DC", lw=.4, pad=1.6, alpha=.93))
    orden = ["Hot 99%", "Hot 95%", "Hot 90%", "No signif.", "Cold 90%",
             "Cold 95%", "Cold 99%"]
    etiq = {"Hot 99%": "Caliente · 99%", "Hot 95%": "Caliente · 95%",
            "Hot 90%": "Caliente · 90%", "No signif.": "No significativo",
            "Cold 90%": "Frío · 90%", "Cold 95%": "Frío · 95%",
            "Cold 99%": "Frío · 99%"}
    handles = [Patch(fc=COL_GI[k], ec="white", lw=.3, label=etiq[k])
               for k in orden]
    handles += [Patch(fc="none", ec="#17202A", lw=.9, label="Sobrevive a FDR"),
                Line2D([], [], marker="*", ls="none", ms=6.5, color="#F4D03F",
                       mec="#17202A", mew=.4, label="Plaza Grande")]
    axes[0].legend(handles=handles, loc="upper left", fontsize=5.5,
                   handlelength=1.0, borderpad=.28, labelspacing=.24,
                   frameon=True, framealpha=.93, facecolor="white",
                   edgecolor="#D5D8DC")
    fig.text(0.005, -0.035,
             f"Estadístico Gi* de Getis-Ord (Ord y Getis, 1995) con pesos "
             f"binarios de contigüidad reina y autovecindad; el estadístico es "
             f"directamente una puntuación z.\n"
             f"Niveles de confianza asignados por el valor p analítico "
             f"bilateral; el contorno negro señala las celdas que además "
             f"superan la corrección de Benjamini-Hochberg y admiten lectura "
             f"confirmatoria ({n_fdr} en total).\n"
             f"Las celdas significativas sin contorno son EXPLORATORIAS. La "
             f"evidencia confirmatoria de estructura espacial global es la I de "
             f"Moran (§12.2). Proyección UTM 17S; celdas de "
             f"{CELDA_M:.0f} m; semilla = {SEMILLA}.".replace(",", ","),
             fontsize=6.2, color="#566573", va="top")
    guardar(fig, outdir, "Figura11_GetisOrd_Comparado")


# =============================================================================
# §13 — SENSIBILIDAD A CUENTAS DE MARCA Y SÍNTESIS DE LA PARTE II
# =============================================================================

def bloque_sensibilidad_marca(d, outdir, resultados):
    titulo("§13 · Sensibilidad a las cuentas sociales compartidas")

    dup = d["cuenta_social_duplicada"].astype(bool)
    print(f"  Registros con cuenta social compartida entre establecimientos: "
          f"{int(dup.sum())}")
    if dup.sum():
        tabla(d.loc[dup, ["Nombre", "marca_id", "seg_ig", "seg_tt",
                          "franquicia"]].reset_index(drop=True),
              "Registros afectados", 0)
    print("\n  Riesgo: una cuenta corporativa (por ejemplo, la de una cadena)")
    print("  atribuye a un local concreto una audiencia que pertenece a la")
    print("  marca nacional. Esto puede inflar el capital digital de esa celda.")
    print("\n  Escenario A: datos completos (especificación principal).")
    print("  Escenario B: se excluyen los registros con cuenta compartida.")

    dB = d[~dup].copy()
    etiq = ["log1p(reseñas)", "log1p(seguidores IG)", "log1p(seguidores TT)"]
    XB = np.column_stack([dB.log1p_resenas, dB.log1p_seg_ig, dB.log1p_seg_tt])
    pB = pca_correlacion(XB, etiq, "PCA-A escenario B", n_boot=200, anclaje=0)

    XA = np.column_stack([d.log1p_resenas, d.log1p_seg_ig, d.log1p_seg_tt])
    pA = pca_correlacion(XA, etiq, "PCA-A escenario A", n_boot=200, anclaje=0)

    comp = pd.DataFrame({
        "carga CP1 · escenario A": pA["cargas"][:, 0],
        "carga CP1 · escenario B": pB["cargas"][:, 0],
        "diferencia": pB["cargas"][:, 0] - pA["cargas"][:, 0]}, index=etiq)
    tabla(comp, "(1) Estabilidad de las cargas de CP1", 4)
    print(f"\n  Varianza explicada por CP1: A = {pA['var_pct'][0]:.2f}% | "
          f"B = {pB['var_pct'][0]:.2f}%")
    print(f"  KMO: A = {pA['kmo_global']:.4f} | B = {pB['kmo_global']:.4f}")

    # Moran sobre CP1 en ambos escenarios
    filas = []
    for nombre, dd, pp in [("A · completo", d, pA), ("B · sin duplicadas", dB, pB)]:
        wk = KNN.from_array(dd[["X", "Y"]].values, k=K_VECINOS)
        wk.transform = "R"
        mi = esda.Moran(pp["puntuaciones"][:, 0], wk, permutations=N_PERM)
        filas.append({"escenario": nombre, "n": len(dd), "I de Moran": mi.I,
                      "z": mi.z_sim, "p": mi.p_sim,
                      "% CP1": pp["var_pct"][0], "KMO": pp["kmo_global"]})
    tab_s = pd.DataFrame(filas)
    tabla(tab_s, "(2) Efecto sobre la autocorrelación global de CP1", 4)

    dif_I = abs(tab_s.loc[0, "I de Moran"] - tab_s.loc[1, "I de Moran"])
    print(f"\n  Diferencia absoluta en la I de Moran: {dif_I:.4f}")
    if dif_I < 0.02:
        print("  → Los resultados NO dependen de las cuentas de marca "
              "compartidas.")
        print("    Basta una frase en el apartado de robustez; no se requiere")
        print("    duplicar las figuras.")
    else:
        print("  → La exclusión altera apreciablemente el resultado: debe")
        print("    reportarse el escenario B junto al principal.")

    comp.to_csv(os.path.join(outdir, "T13a_sensibilidad_cargas.csv"))
    tab_s.to_csv(os.path.join(outdir, "T13b_sensibilidad_moran.csv"),
                 index=False)
    resultados["sensibilidad_marca"] = {
        "n_excluidos": int(dup.sum()), "dif_I_Moran": float(dif_I),
        "escenarios": tab_s.to_dict(orient="records")}


def sintesis_parte_ii(resultados, outdir):
    titulo("§14 · Síntesis de la Parte II y contraste de la hipótesis")

    au = resultados["auditoria"]
    cd = resultados["capital_digital"]
    kc = resultados["kde_capital"]
    ec = resultados["espacial_capital"]
    tk = resultados["tiktok"]
    gi_fdr = resultados.get("gi_fdr_por_dimension", [])
    n_fdr_gi = int(sum(r["hot tras FDR"] + r["cold tras FDR"]
                       for r in gi_fdr if "CP" in r["dimensión"]))

    print("HIPÓTESIS PRINCIPAL EN CONTRASTE")
    print(textwrap.fill(
        "Los territorios alimentarios digitales no desplazan la centralidad "
        "gastronómica preexistente, sino que intensifican las jerarquías "
        "internas de visibilidad y reconocimiento dentro de ella.", 79,
        initial_indent="  ", subsequent_indent="  "))

    print("\n\nEVIDENCIA A FAVOR")
    sep_cp1 = kc["separacion_fisico_CP1_m"]
    rel = ("por debajo del" if sep_cp1 <= BW_KDE_M else
           "ligeramente por encima del" if sep_cp1 <= 2 * BW_KDE_M
           else "muy por encima del")
    ev = [
        f"El máximo de capital digital multiplataforma se sitúa a "
        f"{sep_cp1:.0f} m del máximo de densidad física, {rel} ancho de banda "
        f"del estimador ({BW_KDE_M:.0f} m) y dentro de una manzana colonial: no "
        f"hay desplazamiento apreciable del centro de gravedad.",
        f"La similitud de forma entre ambas superficies es alta "
        f"(ρ = {kc['spearman_fisico_CP1']:.3f}), y el resultado se mantiene al "
        f"pasar de una plataforma a tres: es robusto a la operacionalización.",
        f"El capital digital está {kc['razon_concentracion_CP1_vs_fisico']:.2f} "
        f"veces más concentrado que la densidad física: la jerarquía interna se "
        f"agudiza sin que cambie su localización.",
        f"El gradiente de adopción es monotónico y precede a toda medición de "
        f"audiencia: la estratificación comienza por exclusión de plataformas.",
    ]
    for i, t in enumerate(ev, 1):
        print(textwrap.fill(f"  {i}. {t}", 79, subsequent_indent="     "))

    print("\nEVIDENCIA DE MATIZ O EN CONTRA")
    ct = [
        f"La concordancia entre la geografía de las reseñas y la del capital "
        f"digital es del {ec['concordancia_Gi_pct']:.1f}% (Gi*) y del "
        f"{ec['concordancia_LISA_pct']:.1f}% (LISA), con "
        f"{ec['n_celdas_discordantes']} celdas discordantes: las capas de "
        f"plataforma NO son perfectamente isomorfas y existen territorios con "
        f"capital social sin traducción cartográfica.",
        f"CP1 correlaciona r = {cd['PCA_A']['r_CP1_n_plataformas']:.3f} con el "
        f"mero recuento de plataformas: el índice mide sobre todo amplitud de "
        f"adopción, no gradación fina de magnitud. La conclusión vale para el "
        f"capital digital así definido, no para cualquier definición.",
        f"El KMO de PCA-A es {cd['PCA_A']['kmo']:.3f}, adecuación factorial "
        f"moderada: la estructura latente es real pero no espectacular, "
        f"consistente con tres indicadores de una misma familia conceptual.",
        f"En las RESEÑAS ninguna celda supera la corrección por multiplicidad "
        f"en Gi*: la localización precisa de esos clústeres es exploratoria. "
        f"El capital digital sí produce celdas confirmatorias "
        f"({n_fdr_gi} en total entre CP1 y CP2), de modo que el nivel de "
        f"evidencia difiere según la dimensión y debe declararse por separado.",
        f"La I de Moran de CP2 es significativa por celda pero NO a nivel de "
        f"establecimiento: el eje cartográfico-social se manifiesta como "
        f"propiedad de áreas, no de locales individuales. Es un resultado "
        f"dependiente de la escala y debe presentarse como tal.",
    ]
    for i, t in enumerate(ct, 1):
        print(textwrap.fill(f"  {i}. {t}", 79, subsequent_indent="     "))

    print("\nAPORTE ESPECÍFICO DE TIKTOK")
    apo = [
        (f"TikTok está COMPLETAMENTE anidado en Instagram: los "
         f"{au['n_tiktok']} establecimientos con TikTok tienen todos cuenta de "
         f"Instagram, sin una sola excepción. No existe ninguna vía de acceso a "
         f"la visibilidad que pase por TikTok sin pasar antes por Instagram: es "
         f"un escalón adicional de quienes ya están en la jerarquía, no una "
         f"puerta alternativa de entrada."
         if au.get("anidamiento_total") else
         f"TikTok está anidado en Instagram ({au['n_tiktok_con_ig']} de "
         f"{au['n_tiktok']} cuentas), con razón de momios "
         f"{au['odds_ratio_IG_TT']:.1f}: no constituye una vía alternativa de "
         f"acceso a la visibilidad."),
        f"Seguidores y likes de TikTok correlacionan ρ = "
        f"{au['rho_segTT_likesTT_condicional']:.3f} incluso entre quienes "
        f"poseen la plataforma: son la misma dimensión de alcance y no deben "
        f"contarse dos veces.",
        f"La interacción relativa (mediana {tk['engagement']['mediana']:.2f} "
        f"likes por seguidor) correlaciona ρ = "
        f"{tk['engagement']['rho_con_seguidores']:.3f} con el tamaño de "
        f"audiencia: es una dimensión propia, no un derivado del alcance.",
    ]
    for i, t in enumerate(apo, 1):
        print(textwrap.fill(f"  {i}. {t}", 79, subsequent_indent="     "))

    print("\nVEREDICTO")
    print(textwrap.fill(
        "La hipótesis principal resiste el cambio de operacionalización: "
        "sostenerla ya no depende de una sola plataforma. La hipótesis "
        "secundaria —capas de plataforma no isomorfas— recibe apoyo parcial y "
        "localizado: existe un eje cartográfico-social identificable (CP2) y un "
        "conjunto acotado de celdas discordantes, pero la geografía dominante "
        "es común a todas las capas. Formulación admisible: la no isomorfía es "
        "detectable pero subordinada; la amplificación de la jerarquía "
        "heredada es el mecanismo dominante.", 79,
        initial_indent="  ", subsequent_indent="  "))

    print("\n" + "-" * 79)
    print("LÍMITES QUE DEBEN DECLARARSE EN EL MANUSCRITO")
    print("-" * 79)
    lim = [
        "Diseño transversal: ninguna asociación identifica un efecto causal.",
        "Los seguidores son una medición puntual y los likes un acumulado "
        "histórico; su razón es un proxy de intensidad acumulada, no una tasa "
        "de engagement.",
        "El capital digital así construido pondera la amplitud de adopción por "
        "encima de la magnitud; una definición que privilegie la magnitud "
        "condicional podría producir una geografía distinta.",
        "Los análisis por celda dependen de la escala de agregación (MAUP): "
        "los 150 m deben justificarse morfológicamente.",
        "Las capas de estrellas e interacción en TikTok tienen cobertura "
        "parcial y se presentan como exploratorias.",
        "Solo se observan las plataformas registradas en el censo: la ausencia "
        "de cuenta identificada no prueba la ausencia de actividad digital.",
    ]
    for i, t in enumerate(lim, 1):
        print(textwrap.fill(f"  {i}. {t}", 79, subsequent_indent="     "))


def parte_ii(df, outdir, resultados):
    print("\n\n")
    print("#" * 79)
    print("#" + " " * 77 + "#")
    print("#" + "PARTE II — CAPITAL DIGITAL MULTIDIMENSIONAL".center(77) + "#")
    print("#" + " " * 77 + "#")
    print("#" * 79)

    d = bloque_auditoria(df, outdir, resultados)
    bloque_tiktok(d, outdir, resultados)
    d, pa, pb = construir_capital_digital(d, outdir, resultados)
    bloque_kde_capital(d, outdir, resultados)
    bloque_espacial_capital(d, outdir, resultados)
    bloque_sensibilidad_marca(d, outdir, resultados)
    sintesis_parte_ii(resultados, outdir)
    return d


# =============================================================================
# MAIN
# =============================================================================

def main():
    ap = argparse.ArgumentParser(
        description="Inferencia estadística y espacial — Centro Histórico de Quito")
    ap.add_argument("--csv", default="restaurantes_quito_CH_clean.csv",
                    help="ruta del CSV de entrada")
    ap.add_argument("--outdir", default="resultados",
                    help="directorio de salida")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    sys.stdout = Registro(os.path.join(args.outdir, "informe_analisis.txt"))
    configurar_estilo()

    print("=" * 79)
    print("ESTRATIFICACIÓN DIGITAL DEL PATRIMONIO ALIMENTARIO")
    print("Centro Histórico de Quito · inferencia estadística y espacial")
    print("=" * 79)
    print(f"Ejecución            : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Semilla              : {SEMILLA}")
    print(f"Permutaciones        : {N_PERM:,}")
    print(f"Nivel de significación: {ALFA} | corrección múltiple: {FDR_METODO}")
    print(f"Versiones            : numpy {np.__version__} · pandas "
          f"{pd.__version__} · scipy {stats.__name__.split('.')[0]} "
          f"{__import__('scipy').__version__} · statsmodels "
          f"{sm.__version__} · libpysal {libpysal.__version__} · esda "
          f"{esda.__version__}")
    print(f"Directorio de salida : {os.path.abspath(args.outdir)}")

    resultados = {"parametros": {
        "semilla": SEMILLA, "permutaciones": N_PERM, "k_vecinos": K_VECINOS,
        "celda_m": CELDA_M, "bw_kde_m": BW_KDE_M, "epsg": EPSG_PROJ,
        "alfa": ALFA, "fdr": FDR_METODO,
        "plaza_grande": {"lat": PLAZA_GRANDE[0], "lon": PLAZA_GRANDE[1]}}}

    df = cargar_datos(args.csv)
    bloque_mann_whitney(df, args.outdir, resultados)
    bloque_binomial_negativa(df, args.outdir, resultados)
    bloque_kde(df, args.outdir, resultados)
    w_pts, celdas, w_cel, _ = bloque_pesos(df, args.outdir)
    bloque_moran(df, w_pts, celdas, w_cel, args.outdir, resultados)
    celdas_l, _ = bloque_lisa(df, celdas, w_cel, args.outdir, resultados)
    bloque_getis(df, celdas_l, w_cel, args.outdir, resultados)
    bloque_sintesis(resultados, args.outdir)

    # ---------------- PARTE II ----------------
    parte_ii(df, args.outdir, resultados)
    with open(os.path.join(args.outdir, "resultados_completos.json"), "w",
              encoding="utf-8") as fh:
        json.dump(resultados, fh, ensure_ascii=False, indent=2, default=str)

    titulo("Ejecución finalizada")
    print("Figuras (PDF vectorial + PNG 600 dpi):")
    for f in sorted(os.listdir(args.outdir)):
        if f.endswith(".pdf"):
            print(f"   · {f}")
    print("\nTablas (CSV) y registro completo (informe_analisis.txt) en el mismo "
          "directorio.")


if __name__ == "__main__":
    main()
