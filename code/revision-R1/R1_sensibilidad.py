# -*- coding: utf-8 -*-
"""
R1 · Análisis de sensibilidad y verificación pedidos por los revisores
======================================================================

Script NUEVO de la revisión R1 (Frontiers 1983275). NO modifica el script
original ni los resultados enviados: importa en modo lectura las funciones de
final_figures_CODE/analisis_espacial_quito_v2_capital_digital.py (mismo KDE,
mismo Gi*, misma PCA) y escribe todo en R1_v2_borrador/resultados/sensibilidad/.

Bloques
  A  Reproducción de la línea base (comprueba que las cifras enviadas salen igual)
  B  KDE: sensibilidad al ancho de banda (75–250 m), estabilidad cuantificada
  C  Malla: sensibilidad al tamaño de celda (100–250 m) y al origen (MAUP)
  D  Nivel de punto: Gi* sobre CP1 (banda de distancia y KNN), recuento local
     de uniones (local join counts) sobre la ausencia binaria y superficie de
     proporción (riesgo relativo) de encontrabilidad
  E  Efecto de borde: exclusión de locales a ≤ h y ≤ 2h del límite
  F  Índice: sin franquicias, sin cuentas compartidas, solo con ≥1 plataforma
  G  Los 116: escenarios de cierre con la verificación de octubre de 2026
  H  Reseñas frente al año de registro del catastro (comprobación pedida por R1)
  I  Street View, TripAdvisor y presencia alternativa (resumen de la verificación)
  J  Caracterización de los 116 (tipo, categoría, distancia)

Uso (desde la raíz del proyecto):
    python R1_v2_borrador/codigo/R1_sensibilidad.py
    python R1_v2_borrador/codigo/R1_sensibilidad.py --limite ruta/parroquia.gpkg
"""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests
from shapely.geometry import MultiPoint, Point
import esda
from libpysal.weights import KNN, DistanceBand, W

SEMILLA = 12345
N_PERM = 9999


# ── utilidades ───────────────────────────────────────────────────────────────
def cargar_motor(raiz: Path):
    ruta = raiz / "final_figures_CODE" / "analisis_espacial_quito_v2_capital_digital.py"
    spec = importlib.util.spec_from_file_location("motor_original", ruta)
    M = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(M)
    return M


def silencio(f, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return f(*a, **k)


def preparar(M, csv):
    d = silencio(M.cargar_datos, str(csv))
    d["id_censo"] = np.arange(1, len(d) + 1)
    d["n_plataformas"] = d.existe_gmaps.astype(int) + d.tiene_ig.astype(int) + d.tiene_tt.astype(int)
    d["ausente"] = (d.n_plataformas == 0).astype(int)
    return d


def pca_cp1(M, d):
    X = np.column_stack([d.log1p_resenas, d.log1p_seg_ig, d.log1p_seg_tt])
    pa = M.pca_correlacion(X, ["res", "ig", "tt"], "PCA", n_boot=10, anclaje=0)
    cp1 = pa["puntuaciones"][:, 0]
    return cp1, pa


def celdas(d, lado, offset=(0.0, 0.0), x0=None, y0=None):
    """Igual que construir_celdas/agregar_celdas_capital del original, con lado y
    origen variables. offset en fracción de celda (0.5 = media celda)."""
    if x0 is None:
        x0 = np.floor(d.X.min() / lado) * lado - offset[0] * lado
    if y0 is None:
        y0 = np.floor(d.Y.min() / lado) * lado - offset[1] * lado
    dd = d.copy()
    dd["col"] = ((dd.X - x0) // lado).astype(int)
    dd["fil"] = ((dd.Y - y0) // lado).astype(int)
    c = (dd.groupby(["fil", "col"])
         .agg(n_estab=("resenas", "size"), resenas_tot=("resenas", "sum"),
              CP1_suma=("CP1_pct", "sum"))
         .reset_index())
    c["log1p_resenas_tot"] = np.log1p(c.resenas_tot)
    c["xc"] = x0 + (c.col + .5) * lado
    c["yc"] = y0 + (c.fil + .5) * lado
    dd = dd.merge(c[["fil", "col"]].reset_index().rename(columns={"index": "celda"}),
                  on=["fil", "col"], how="left")
    return c, dd, (x0, y0)


def gi_celdas(M, c, perm=99):
    """Gi* canónico del original (pesos reina binarios + autovecindad); p analítico + BH."""
    w, islas = M.pesos_reina(c)
    vec = M.vecinos_con_autovecindad(w)
    out = {}
    for var in ["log1p_resenas_tot", "CP1_suma"]:
        _, Z, _, _ = M.getis_ord_star(c[var].values, vec, n_perm=perm)
        p = 2 * stats.norm.sf(np.abs(Z))
        rech, padj, _, _ = multipletests(p, alpha=0.05, method="fdr_bh")
        w.transform = "R"
        mi = esda.Moran(c[var].values, w, permutations=N_PERM)
        out[var] = {"Z": Z, "p": p, "fdr": rech,
                    "hot_nominal": int(((Z > 0) & (p < .05)).sum()),
                    "cold_nominal": int(((Z < 0) & (p < .05)).sum()),
                    "hot_FDR": int(((Z > 0) & rech).sum()),
                    "cold_FDR": int(((Z < 0) & rech).sum()),
                    "moran_I": float(mi.I), "moran_p": float(mi.p_sim),
                    "z_max": float(Z.max())}
    return out, len(islas)


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else np.nan


def gi_puntos(y, vecinos):
    """Gi* canónico (Ord y Getis 1995) con pesos binarios + autovecindad, a nivel de punto."""
    y = np.asarray(y, float); n = len(y); ybar = y.mean()
    S = np.sqrt(np.sum(y ** 2) / n - ybar ** 2)
    Z = np.zeros(n)
    for i in range(n):
        idx = np.asarray(vecinos[i]); w = float(len(idx))
        Z[i] = (y[idx].sum() - ybar * w) / (S * np.sqrt(max((n * w - w ** 2) / (n - 1), 1e-12)))
    return Z


def nb_irr_ig(M, d):
    dd = d.copy()
    dd["y"] = dd.resenas.astype(int); dd["dist"] = dd.dist_km; dd["ig"] = dd.tiene_ig.astype(int)
    f = f'y ~ C(tipo, Treatment(reference="{M.TIPO_REFERENCIA}")) + dist + ig'
    nb = smf.negativebinomial(f, data=dd).fit(disp=0, maxiter=500)
    ci = np.exp(nb.conf_int().loc["ig"])
    return {"IRR_ig": float(np.exp(nb.params["ig"])), "IC95": [float(ci[0]), float(ci[1])],
            "p": float(nb.pvalues["ig"]), "IRR_dist": float(np.exp(nb.params["dist"])),
            "p_dist": float(nb.pvalues["dist"]), "n": int(nb.nobs)}


def metricas_basicas(M, d):
    cp1, pa = pca_cp1(M, d)
    tot = d.resenas.sum()
    tr = d[d.tipo_raw == "Tradicional"]; nt = d[d.tipo_raw == "Nuevo Tradicional"]
    return {"n": len(d), "n_cero": int((d.n_plataformas == 0).sum()),
            "pct_cero": 100 * float((d.n_plataformas == 0).mean()),
            "pct_tres": 100 * float((d.n_plataformas == 3).mean()),
            "pct_resenas_tres": 100 * float(d.loc[d.n_plataformas == 3, "resenas"].sum() / tot),
            "r_CP1_nplat": float(stats.pearsonr(cp1, d.n_plataformas)[0]),
            "var_CP1": float(pa["var_pct"][0]), "KMO": float(pa["kmo_global"]),
            "IG_T": 100 * float(tr.tiene_ig.mean()), "n_T": len(tr),
            "IG_NT": 100 * float(nt.tiene_ig.mean()), "n_NT": len(nt)}


# ── principal ────────────────────────────────────────────────────────────────
def main(raiz: Path, salida: Path, limite):
    salida.mkdir(parents=True, exist_ok=True)
    M = cargar_motor(raiz)
    csv = raiz / "final_figures_CODE" / "restaurantes_quito_CH_clean.csv"
    d = preparar(M, csv)
    cp1, pa = pca_cp1(M, d)
    d["CP1"] = cp1
    d["CP1_pct"] = stats.rankdata(cp1) / len(cp1)
    R = {}

    # ── A · línea base ──────────────────────────────────────────────────────
    x, y = d.X.values, d.Y.values
    w_rev = d.log1p_resenas.values
    h0 = M.BW_KDE_M
    pad = 3 * h0
    xg = np.arange(x.min() - pad, x.max() + pad + M.KDE_GRID_M, M.KDE_GRID_M)
    yg = np.arange(y.min() - pad, y.max() + pad + M.KDE_GRID_M, M.KDE_GRID_M)
    XX, YY = np.meshgrid(xg, yg)
    mask, hull = M.mascara_dominio(XX, YY, x, y, 2 * h0)

    def superficies(h, xs=x, ys=y, ws=w_rev):
        A = M.kde_superficie(xs, ys, XX, YY, h, None)
        B = M.kde_superficie(xs, ys, XX, YY, h, ws)
        return A, B

    def resumen_kde(A, B, mk=mask, media=None):
        sA = np.where(mk, A, -np.inf); i1 = np.unravel_index(np.argmax(sA), sA.shape)
        sB = np.where(mk, B, -np.inf); i2 = np.unravel_index(np.argmax(sB), sB.shape)
        sep = float(np.hypot(XX[i1] - XX[i2], YY[i1] - YY[i2]))
        rho = float(stats.spearmanr(A[mk], B[mk])[0])
        conc = float((B[mk].max() / np.median(B[mk])) / (A[mk].max() / np.median(A[mk])))
        um = np.nanpercentile(A[mk], 10); mc = mk & (A > um)
        C = np.where(mc, B / A, np.nan); rc = C[mc]
        return {"sep_m": sep, "rho_AB": rho, "conc_ratio": conc,
                "P90_P10_C": float(np.nanpercentile(rc, 90) / max(np.nanpercentile(rc, 10), 1e-9))}, C

    A0, B0 = superficies(h0)
    base_kde, C0 = resumen_kde(A0, B0)
    c150, d150, org150 = celdas(d, 150.0)
    gi150, n_islas = gi_celdas(M, c150)
    R["A_linea_base"] = {
        "kde": base_kde, "celdas_150": int(len(c150)), "islas": n_islas,
        "moran_resenas": gi150["log1p_resenas_tot"]["moran_I"],
        "moran_CP1": gi150["CP1_suma"]["moran_I"],
        "FDR_hot_CP1": gi150["CP1_suma"]["hot_FDR"], "FDR_resenas": gi150["log1p_resenas_tot"]["hot_FDR"]
        + gi150["log1p_resenas_tot"]["cold_FDR"],
        "z_max_CP1": gi150["CP1_suma"]["z_max"],
        "r_CP1_nplat": float(stats.pearsonr(cp1, d.n_plataformas)[0]),
        "esperado_manuscrito": {"sep_m": 28, "rho_AB": 0.960, "conc_ratio": 1.55, "P90_P10_C": 6.3,
                                "celdas": 89, "moran_resenas": 0.304, "moran_CP1": 0.269,
                                "FDR_hot_CP1": 11, "FDR_resenas": 0, "z_max": 5.36, "r": 0.898}}
    base_ok = (round(base_kde["sep_m"]) == 28 and round(base_kde["rho_AB"], 2) == 0.96
               and len(c150) == 89 and gi150["CP1_suma"]["hot_FDR"] == 11
               and gi150["log1p_resenas_tot"]["hot_FDR"] == 0
               and round(R["A_linea_base"]["r_CP1_nplat"], 3) == 0.898)
    R["A_linea_base"]["reproduce_manuscrito"] = bool(base_ok)
    hot_base = set(np.where((gi150["CP1_suma"]["Z"] > 0) & gi150["CP1_suma"]["fdr"])[0])
    est_hot_base = set(d150.loc[d150.celda.isin(hot_base), "id_censo"])

    # ── B · ancho de banda ──────────────────────────────────────────────────
    filas = []
    top = lambda S: set(np.where(mask.ravel() & (S.ravel() >= np.percentile(S[mask], 90)))[0])
    tB0, tA0 = top(B0), top(A0)
    for h in [75.0, 100.0, 125.0, 150.0, 200.0, 250.0]:
        A, B = superficies(h)
        r, C = resumen_kde(A, B)
        ok = ~np.isnan(C) & ~np.isnan(C0)
        r.update({"h_m": h,
                  "rho_B_vs_B125": float(stats.spearmanr(B[mask], B0[mask])[0]),
                  "rho_C_vs_C125": float(stats.spearmanr(C[ok], C0[ok])[0]),
                  "jaccard_top10_B_vs_B125": jaccard(top(B), tB0),
                  "jaccard_top10_A_vs_B_mismo_h": jaccard(top(A), top(B))})
        filas.append(r)
    tb = pd.DataFrame(filas)[["h_m", "sep_m", "rho_AB", "conc_ratio", "P90_P10_C", "rho_B_vs_B125",
                              "rho_C_vs_C125", "jaccard_top10_B_vs_B125", "jaccard_top10_A_vs_B_mismo_h"]]
    tb.to_csv(salida / "B_kde_ancho_banda.csv", index=False)
    R["B_kde"] = tb.round(4).to_dict(orient="records")

    # ── C · tamaño y origen de celda ────────────────────────────────────────
    filas = []
    for lado in [100.0, 125.0, 150.0, 200.0, 250.0]:
        for off in [(0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.5, 0.5)]:
            c, dd, _ = celdas(d, lado, off)
            g, ni = gi_celdas(M, c)
            hot = set(np.where((g["CP1_suma"]["Z"] > 0) & g["CP1_suma"]["fdr"])[0])
            est_hot = set(dd.loc[dd.celda.isin(hot), "id_censo"])
            filas.append({"lado_m": lado, "origen_desplazado": f"{off[0]},{off[1]}", "celdas": len(c),
                          "islas": ni,
                          "moran_I_resenas": g["log1p_resenas_tot"]["moran_I"],
                          "moran_p_resenas": g["log1p_resenas_tot"]["moran_p"],
                          "moran_I_CP1": g["CP1_suma"]["moran_I"], "moran_p_CP1": g["CP1_suma"]["moran_p"],
                          "resenas_hot_nom": g["log1p_resenas_tot"]["hot_nominal"],
                          "resenas_hot_FDR": g["log1p_resenas_tot"]["hot_FDR"],
                          "resenas_cold_FDR": g["log1p_resenas_tot"]["cold_FDR"],
                          "CP1_hot_nom": g["CP1_suma"]["hot_nominal"], "CP1_hot_FDR": g["CP1_suma"]["hot_FDR"],
                          "CP1_cold_FDR": g["CP1_suma"]["cold_FDR"],
                          "estab_en_hot_FDR": len(est_hot),
                          "jaccard_estab_vs_base": jaccard(est_hot, est_hot_base),
                          "pct_base_conservado": 100 * len(est_hot & est_hot_base) / len(est_hot_base)})
    tc = pd.DataFrame(filas)
    tc.to_csv(salida / "C_malla_MAUP.csv", index=False)
    R["C_malla"] = tc.round(4).to_dict(orient="records")

    # ── D · nivel de punto ──────────────────────────────────────────────────
    coords = d[["X", "Y"]].values
    D = {}
    # D1 Gi* puntual sobre CP1_pct
    pesos = {"banda_150m": DistanceBand(coords, threshold=150, binary=True, silence_warnings=True),
             "banda_250m": DistanceBand(coords, threshold=250, binary=True, silence_warnings=True),
             "KNN_8": KNN.from_array(coords, k=8)}
    filas = []
    for nom, w in pesos.items():
        vec = {i: sorted(set([w.id_order.index(j) for j in w.neighbors[w.id_order[i]]] + [i]))
               for i in range(w.n)}
        Z = gi_puntos(d.CP1_pct.values, vec)
        p = 2 * stats.norm.sf(np.abs(Z))
        rech, _, _, _ = multipletests(p, alpha=0.05, method="fdr_bh")
        hot = set(d.id_censo[(Z > 0) & rech]); cold = set(d.id_censo[(Z < 0) & rech])
        d[f"giP_{nom}"] = np.where((Z > 0) & rech, "hot", np.where((Z < 0) & rech, "cold", "ns"))
        filas.append({"pesos": nom, "vecinos_medios": float(np.mean([len(v) - 1 for v in vec.values()])),
                      "islas": int(sum(len(v) == 1 for v in vec.values())),
                      "z_max": float(Z.max()), "z_min": float(Z.min()),
                      "hot_nominal": int(((Z > 0) & (p < .05)).sum()), "cold_nominal": int(((Z < 0) & (p < .05)).sum()),
                      "hot_FDR": len(hot), "cold_FDR": len(cold),
                      "pct_hot_dentro_celdas_hot_base": 100 * len(hot & est_hot_base) / max(len(hot), 1),
                      "pct_base_cubierto_por_hot": 100 * len(hot & est_hot_base) / len(est_hot_base)})
    td1 = pd.DataFrame(filas); td1.to_csv(salida / "D1_gi_puntos_CP1.csv", index=False)
    # D0 Autocorrelación global a nivel de punto (I de Moran, pesos estandarizados por fila)
    filas = []
    for nom, w in pesos.items():
        w.transform = "R"
        for var, v in [("CP1", d.CP1.values), ("log1p_resenas", d.log1p_resenas.values),
                       ("n_plataformas", d.n_plataformas.values.astype(float)),
                       ("ausente_0plat", d.ausente.values.astype(float))]:
            mi = esda.Moran(v, w, permutations=N_PERM)
            filas.append({"pesos": nom, "variable": var, "I": float(mi.I), "p_sim": float(mi.p_sim)})
        w.transform = "O"
    td0 = pd.DataFrame(filas); td0.to_csv(salida / "D0_moran_puntos.csv", index=False)
    D["moran_puntos"] = td0.round(4).to_dict(orient="records")
    D["gi_puntos_CP1"] = td1.round(3).to_dict(orient="records")

    # D2 Recuento local de uniones (ausencia binaria) — Anselin y Li (2019)
    filas = []
    for nom, w in [("KNN_8", KNN.from_array(coords, k=8)),
                   ("banda_150m", DistanceBand(coords, threshold=150, binary=True, silence_warnings=True))]:
        w.transform = "B"
        for etiqueta, yb in [("ausente_0plat", d.ausente.values), ("presente_1plus", 1 - d.ausente.values)]:
            jc = esda.Join_Counts_Local(connectivity=w, permutations=N_PERM, seed=SEMILLA,
                                        drop_islands=False, island_weight=0).fit(yb)
            p = np.where(np.isnan(jc.p_sim), 1.0, jc.p_sim)
            focal = yb == 1
            rech = np.zeros(len(p), bool)
            r_, _, _, _ = multipletests(p[focal], alpha=0.05, method="fdr_bh")
            rech[focal] = r_
            gj = esda.Join_Counts(yb, w, permutations=N_PERM)
            filas.append({"pesos": nom, "variable": etiqueta, "n_focal": int(focal.sum()),
                          "global_BB": float(gj.bb), "global_BB_p_sim": float(gj.p_sim_bb),
                          "local_sig_nominal": int(((p < .05) & focal).sum()),
                          "local_sig_FDR": int(rech.sum())})
            d[f"ljc_{etiqueta}_{nom}"] = np.where(rech, "cluster_FDR", np.where((p < .05) & focal, "nominal", "ns"))
    td2 = pd.DataFrame(filas); td2.to_csv(salida / "D2_local_join_counts.csv", index=False)
    D["local_join_counts"] = td2.round(4).to_dict(orient="records")

    # D3 Superficie de proporción (riesgo relativo) de encontrabilidad
    filas = []; P0 = None
    pres = d.ausente.values == 0
    for h in [75.0, 100.0, 125.0, 150.0, 200.0, 250.0]:
        A = M.kde_superficie(x, y, XX, YY, h, None)
        Bp = M.kde_superficie(x[pres], y[pres], XX, YY, h, None)
        um = np.nanpercentile(A[mask], 10); mc = mask & (A > um)
        P = np.where(mc, Bp / A, np.nan)
        if h == 125.0:
            P0 = P
        filas.append({"h_m": h, "P_min": float(np.nanmin(P)), "P_mediana": float(np.nanmedian(P)),
                      "P_max": float(np.nanmax(P)), "pct_area_P_menor_0.6": 100 * float(np.nanmean(P[mc] < 0.6))})
    for f in filas:
        A = M.kde_superficie(x, y, XX, YY, f["h_m"], None)
        Bp = M.kde_superficie(x[pres], y[pres], XX, YY, f["h_m"], None)
        um = np.nanpercentile(A[mask], 10); mc = mask & (A > um)
        P = np.where(mc, Bp / A, np.nan); ok = ~np.isnan(P) & ~np.isnan(P0)
        f["rho_vs_h125"] = float(stats.spearmanr(P[ok], P0[ok])[0])
    td3 = pd.DataFrame(filas); td3.to_csv(salida / "D3_superficie_proporcion_encontrable.csv", index=False)
    D["superficie_proporcion"] = td3.round(4).to_dict(orient="records")
    D["proporcion_global_encontrable"] = float(pres.mean())
    R["D_puntos"] = D

    # ── E · efecto de borde ─────────────────────────────────────────────────
    if limite:
        import geopandas as gpd
        g = gpd.read_file(limite).to_crs(M.EPSG_PROJ)
        poligono = g.unary_union
        fuente_limite = f"polígono {Path(limite).name}"
    else:
        poligono = MultiPoint(list(zip(x, y))).convex_hull
        fuente_limite = "envolvente convexa del censo (PROVISIONAL)"
    borde = poligono.boundary
    # distancia con signo: negativa si el local queda FUERA del límite (siempre se excluye con búfer)
    d["dist_borde_m"] = [borde.distance(Point(a, b)) * (1 if poligono.covers(Point(a, b)) else -1)
                         for a, b in zip(x, y)]
    d_nn8 = np.sort(np.linalg.norm(coords[:, None] - coords[None, :], axis=2), axis=1)[:, 8]
    E = {"limite": fuente_limite, "mediana_dist_8vecino_m": float(np.median(d_nn8)), "escenarios": [],
         "locales_dentro_del_limite": int((d.dist_borde_m >= 0).sum()),
         "locales_fuera": d.loc[d.dist_borde_m < 0, ["id_censo", "Nombre", "n_plataformas", "dist_borde_m"]]
                           .round(0).to_dict(orient="records")}
    hot_cells_xy = c150.loc[list(hot_base), ["xc", "yc"]].values
    cerca_borde = [i for i, (cx, cy) in zip(hot_base, hot_cells_xy) if borde.distance(Point(cx, cy)) <= 250]
    base_hot_fc = set(zip(c150.loc[list(hot_base), "fil"], c150.loc[list(hot_base), "col"]))
    # Dos variantes: (i) índice FIJO (el CP1 de cada local no cambia; solo se retiran
    # locales del cálculo local) y (ii) índice RE-ESTIMADO con la submuestra.
    for variante in ["indice_fijo", "indice_reestimado"]:
        for buf in [None, 125.0, 250.0]:            # None = muestra completa
            dd = d.copy() if buf is None else d[d.dist_borde_m > buf].copy()
            if variante == "indice_reestimado":
                cpb, _ = pca_cp1(M, dd); dd["CP1_pct"] = stats.rankdata(cpb) / len(cpb)
            else:
                cpb = dd.CP1.values
            c, dd2, _ = celdas(dd, 150.0, x0=org150[0], y0=org150[1])   # misma malla que la base
            g, _ = gi_celdas(M, c)
            hot = c.loc[(g["CP1_suma"]["Z"] > 0) & g["CP1_suma"]["fdr"], ["fil", "col"]]
            A_, B_ = superficies(h0, dd.X.values, dd.Y.values, dd.log1p_resenas.values)
            rk, _ = resumen_kde(A_, B_)
            E["escenarios"].append({
                "variante": variante, "buffer_m": 0.0 if buf is None else buf, "n": len(dd),
                "excluidos": int(len(d) - len(dd)),
                "excluidos_ausentes": 0 if buf is None else int(((d.dist_borde_m <= buf) & (d.ausente == 1)).sum()),
                "celdas": len(c), "moran_I_CP1": g["CP1_suma"]["moran_I"], "moran_p_CP1": g["CP1_suma"]["moran_p"],
                "moran_I_resenas": g["log1p_resenas_tot"]["moran_I"], "moran_p_resenas": g["log1p_resenas_tot"]["moran_p"],
                "CP1_hot_FDR": g["CP1_suma"]["hot_FDR"], "CP1_cold_FDR": g["CP1_suma"]["cold_FDR"],
                "resenas_FDR": g["log1p_resenas_tot"]["hot_FDR"] + g["log1p_resenas_tot"]["cold_FDR"],
                "celdas_hot_base_que_persisten": len(set(zip(hot.fil, hot.col)) & base_hot_fc),
                "celdas_hot_base_total": len(base_hot_fc),
                "kde_sep_m": rk["sep_m"], "kde_rho_AB": rk["rho_AB"],
                "r_CP1_nplat": float(stats.pearsonr(cpb, dd.n_plataformas)[0])})
    E["celdas_hot_base_a_250m_del_borde"] = len(cerca_borde)
    pd.DataFrame(E["escenarios"]).to_csv(salida / "E_efecto_borde.csv", index=False)
    R["E_borde"] = E

    # ── F · sensibilidad del índice ─────────────────────────────────────────
    F = []
    for nom, mk in [("completo", np.ones(len(d), bool)),
                    ("sin_franquicias", d.franquicia.values == 0),
                    ("sin_cuentas_compartidas", ~d.cuenta_social_duplicada.astype(bool).values),
                    ("solo_con_1plus_plataforma", d.n_plataformas.values >= 1)]:
        dd = d[mk].copy()
        cpf, pf = pca_cp1(M, dd)
        dd["CP1_pct"] = stats.rankdata(cpf) / len(cpf)
        fila = {"escenario": nom, "n": len(dd), "KMO": float(pf["kmo_global"]),
                "var_CP1": float(pf["var_pct"][0]),
                "carga_res": float(pf["cargas"][0, 0]), "carga_ig": float(pf["cargas"][1, 0]),
                "carga_tt": float(pf["cargas"][2, 0]),
                "r_CP1_nplat": float(stats.pearsonr(cpf, dd.n_plataformas)[0]),
                "rho_CP1_nplat": float(stats.spearmanr(cpf, dd.n_plataformas)[0])}
        if nom != "solo_con_1plus_plataforma":
            c, _, _ = celdas(dd, 150.0, x0=org150[0], y0=org150[1])
            g, _ = gi_celdas(M, c)
            fila.update({"moran_I_CP1": g["CP1_suma"]["moran_I"], "CP1_hot_FDR": g["CP1_suma"]["hot_FDR"]})
        F.append(fila)
    # correlación parcial dentro de los presentes: CP1 vs n plataformas controlando nada; y dentro de cada nivel
    tf = pd.DataFrame(F); tf.to_csv(salida / "F_indice_sensibilidad.csv", index=False)
    R["F_indice"] = tf.round(4).to_dict(orient="records")

    # ── G · escenarios de cierre de los 116 ─────────────────────────────────
    ver = pd.read_excel(raiz / "revision_R1" / "datos" / "verificacion_116_TRABAJO.xlsx", "verificacion_116")
    assert set(ver.id_censo) == set(d.id_censo[d.n_plataformas == 0])
    estado = ver.set_index("id_censo")["FINAL_estado"]
    cerrados = set(estado[estado == "Cerrado/trasladado"].index)
    sin_ev = np.array(sorted(estado[estado == "Sin evidencia"].index))
    rng = np.random.default_rng(SEMILLA)
    G = []
    G.append({"escenario": "S0 · censo original", **metricas_basicas(M, d), **nb_irr_ig(M, d)})
    d1 = d[~d.id_censo.isin(cerrados)]
    G.append({"escenario": f"S1 · sin {len(cerrados)} cerrados/trasladados", **metricas_basicas(M, d1), **nb_irr_ig(M, d1)})
    for q in [0.25, 0.50, 0.75]:
        sims = []
        for _ in range(200):
            fuera = set(rng.choice(sin_ev, int(round(q * len(sin_ev))), replace=False)) | cerrados
            sims.append(metricas_basicas(M, d[~d.id_censo.isin(fuera)]))
        s = pd.DataFrame(sims)
        G.append({"escenario": f"S2 · S1 + {int(q*100)} % de los {len(sin_ev)} 'sin evidencia' cerrados (200 sorteos)",
                  **{k: float(s[k].mean()) for k in s.columns},
                  **{f"{k}_P2.5": float(s[k].quantile(.025)) for k in ["pct_cero", "r_CP1_nplat"]},
                  **{f"{k}_P97.5": float(s[k].quantile(.975)) for k in ["pct_cero", "r_CP1_nplat"]}})
    d4 = d[~d.id_censo.isin(cerrados | set(sin_ev))]
    G.append({"escenario": "S3 · S1 + 100 % de 'sin evidencia' (solo quedan los 6 operativos)",
              **metricas_basicas(M, d4), **nb_irr_ig(M, d4)})
    d5 = d[d.n_plataformas > 0]
    G.append({"escenario": "S4 · sin los 116", **metricas_basicas(M, d5)})
    tg = pd.DataFrame(G); tg.to_csv(salida / "G_escenarios_cierre.csv", index=False)
    R["G_cierre"] = tg.round(4).to_dict(orient="records")

    # ── H · reseñas frente al año de registro ───────────────────────────────
    g = d[d.existe_gmaps & d.anio_registro.notna()]
    g2 = g[g.resenas > 0]
    R["H_resenas_vs_anio_registro"] = {
        "n_con_ficha": len(g), "rho": float(stats.spearmanr(g.anio_registro, g.resenas)[0]),
        "p": float(stats.spearmanr(g.anio_registro, g.resenas)[1]),
        "n_con_resenas": len(g2), "rho_con_resenas": float(stats.spearmanr(g2.anio_registro, g2.resenas)[0]),
        "p_con_resenas": float(stats.spearmanr(g2.anio_registro, g2.resenas)[1]),
        "anio_min": float(d.anio_registro.min()), "anio_max": float(d.anio_registro.max()),
        "n_sin_anio": int(d.anio_registro.isna().sum())}

    # ── I · verificación: Street View, TripAdvisor, presencia alternativa ───
    sv = pd.to_datetime(ver.SV_fecha_imagen.astype(str).str[:7], format="%Y-%m", errors="coerce")
    t4 = pd.read_excel(raiz / "revision_R1" / "datos" / "verificacion_116_TRABAJO.xlsx", "tripadvisor_4")
    R["I_verificacion"] = {
        "estado": ver.FINAL_estado.value_counts().to_dict(),
        "SV_con_fecha": int(sv.notna().sum()), "SV_min": str(sv.min())[:7], "SV_mediana": str(sv.sort_values().iloc[int(sv.notna().sum()) // 2])[:7],
        "SV_max": str(sv.max())[:7], "SV_por_anio": sv.dt.year.value_counts().sort_index().to_dict(),
        "TA_116_si": int((ver.TA_presente == "Sí").sum()), "TA_4_si": int((t4.TA_presente == "Sí").sum()),
        "GM_ficha_oct2026": int((ver.GM_ficha_oct2026 == "Sí").sum()),
        "FB_presente": int((ver.FB_presente == "Sí").sum()), "WA": int((ver.WA_evidencia == "Sí").sum()),
        "IGTT_hallazgo": ver.IGTT_hallazgo.value_counts().to_dict(),
        "presencia_alternativa": ver.FINAL_presencia_digital_alternativa.value_counts().to_dict(),
        "cruce_estado_presencia": pd.crosstab(ver.FINAL_estado, ver.FINAL_presencia_digital_alternativa).to_dict()}

    # ── J · caracterización de los 116 ──────────────────────────────────────
    mapa_val = ver.set_index("id_censo")["OFERTA_tipo_validado_Johann"]
    z = d[d.n_plataformas == 0].copy()
    z["tipo_original"] = z.tipo_raw.replace({"Desconocido": "Sin clasificar"})
    z["oferta_validada"] = z.id_censo.map(mapa_val).fillna("No determinable")
    z["fuente_oferta"] = z.id_censo.map(ver.set_index("id_censo")["OFERTA_fuente"])
    # categoría combinada: original si existe; si no, la oferta validada
    z["categoria_combinada"] = np.where(z.tipo_original != "Sin clasificar", z.tipo_original,
                                        "Sin clasificar → " + z.oferta_validada)
    porc_tipo = (d.assign(cero=d.n_plataformas == 0).groupby("tipo_raw")
                 .agg(n=("cero", "size"), sin_plataforma=("cero", "sum")))
    porc_tipo["pct_sin_plataforma"] = 100 * porc_tipo.sin_plataforma / porc_tipo.n
    porc_tipo.to_csv(salida / "J_sin_plataforma_por_tipo_censo.csv")
    pd.crosstab(z.categoria_combinada, z.id_censo.map(estado), margins=True).to_csv(salida / "J_116_categoria_x_estado.csv")
    pd.crosstab(z.tipo_original, z.oferta_validada, margins=True).to_csv(salida / "J_116_original_x_oferta.csv")
    cat = d.assign(cero=d.n_plataformas == 0).groupby(d.categoria.fillna("(vacío)")).agg(
        n=("cero", "size"), sin_plataforma=("cero", "sum"))
    cat["pct"] = 100 * cat.sin_plataforma / cat.n
    cat.to_csv(salida / "J_sin_plataforma_por_categoria_tenedores.csv")
    mw = stats.mannwhitneyu(d.loc[d.n_plataformas == 0, "dist_km"], d.loc[d.n_plataformas > 0, "dist_km"])
    R["J_caracterizacion"] = {
        "por_tipo_censo": porc_tipo.round(1).to_dict(orient="index"),
        "por_categoria": cat.round(1).to_dict(orient="index"),
        "116_categoria_combinada": z.categoria_combinada.value_counts().to_dict(),
        "116_fuente_oferta": z.fuente_oferta.value_counts().to_dict(),
        "dist_mediana_km_ausentes": float(d.loc[d.n_plataformas == 0, "dist_km"].median()),
        "dist_mediana_km_presentes": float(d.loc[d.n_plataformas > 0, "dist_km"].median()),
        "mannwhitney_p": float(mw.pvalue)}
    z[["id_censo", "Nombre", "tipo_original", "oferta_validada", "fuente_oferta", "categoria_combinada",
       "categoria", "dist_km"]].assign(estado=z.id_censo.map(estado)).to_csv(
        salida / "J_116_detalle.csv", index=False)

    d.drop(columns=[c for c in d.columns if c.startswith("log_engagement")], errors="ignore")\
     [["id_censo", "Nombre", "X", "Y", "n_plataformas", "ausente", "CP1_pct", "dist_borde_m"]
      + [c for c in d.columns if c.startswith(("giP_", "ljc_"))]].to_csv(salida / "puntos_clasificados.csv", index=False)

    with open(salida / "R1_sensibilidad_resultados.json", "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(json.dumps({k: R[k] for k in ["A_linea_base"]}, ensure_ascii=False, indent=1, default=str))
    print("Listo:", salida)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--raiz", default=".")
    p.add_argument("--salida", default="R1_v2_borrador/resultados/sensibilidad")
    p.add_argument("--limite", default=None, help="polígono del límite del área de estudio (gpkg/shp)")
    a = p.parse_args()
    raiz = Path(a.raiz)
    main(raiz, raiz / a.salida, a.limite)
