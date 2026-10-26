# -*- coding: utf-8 -*-
"""
R1 · Tablas del Material Suplementario (S1, S6.9.7, S7 y S8) generadas desde los resultados
==========================================================================================

Script NUEVO de la revisión R1. Solo LEE los CSV y JSON de R1_v2_borrador/resultados/
(producidos por R1_sensibilidad.py, R1_nucleo_robusto.py, R1_tipologia_fiabilidad.py y
R1_tipologia_sensibilidad_IG.py) y la exportación de la verificación de los 116
(revision_R1/datos/exportaciones/verificacion_116_final.csv). Escribe un archivo .tex por
tabla en R1_v2_borrador/suplementario/tablas/, que el suplementario incluye con \\input.
Así ninguna cifra de las tablas se copia a mano.

Además imprime las cifras sueltas que el texto cita (para cotejarlas con la prosa).

Uso (desde la carpeta raíz del proyecto):
    python R1_v2_borrador/codigo/R1_tablas_suplementario.py
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# Criterio de cada cierre (validación manual del 21-oct-2026; registro_cambios_1B.csv)
CIERRES = {
    "explicit closure on the listing or page": [108, 157, 241],
    "relocation outside the Historic Centre confirmed": [167, 392],
    "directory entry and closed listing": [230],
    "another business occupies the census address": [109, 110, 163, 225, 256, 337, 340],
}
TIPO_EN = {"Tradicional": "Traditional", "Nuevo Tradicional": "New Traditional",
           "Comida Ecuatoriana": "Regional Ecuadorian cuisine", "Internacional": "International",
           "Fast Food": "Fast Food", "Bar": "Bar", "Cafetería": "Café", "Desconocido": "Unclassified"}


def f(x, d=3):
    return f"{x:.{d}f}"


def p_txt(p):
    return "$< 0.001$" if p < 0.001 else f"{p:.3f}"


def rango(a, b, d=None):
    """'a--b', o un solo valor si coinciden."""
    fa, fb = (f"{a:.{d}f}", f"{b:.{d}f}") if d is not None else (str(a), str(b))
    return fa if fa == fb else f"{fa}--{fb}"


def escribir(carpeta, nombre, cuerpo):
    (carpeta / f"{nombre}.tex").write_text(cuerpo.strip() + "\n", encoding="utf-8")
    print(f"  tabla: {nombre}.tex")


def main(raiz: Path):
    res = raiz / "R1_v2_borrador" / "resultados"
    sen, tip = res / "sensibilidad", res / "tipologia"
    out = raiz / "R1_v2_borrador" / "suplementario" / "tablas"
    out.mkdir(parents=True, exist_ok=True)
    js = json.loads((sen / "R1_sensibilidad_resultados.json").read_text(encoding="utf-8"))
    jt = json.loads((tip / "S6_fiabilidad_resultados.json").read_text(encoding="utf-8"))
    assert js["A_linea_base"]["reproduce_manuscrito"], "la línea base no reproduce el manuscrito"

    # ── S1 · sensibilidad del índice ─────────────────────────────────────────
    F = pd.read_csv(sen / "F_indice_sensibilidad.csv").set_index("escenario")
    etiquetas = {"completo": "Full census", "sin_franquicias": "Excluding franchise/chain records",
                 "sin_cuentas_compartidas": "Excluding the three records sharing a brand account",
                 "solo_con_1plus_plataforma": "Only establishments on $\\geq$1 platform"}
    filas = []
    for k, lab in etiquetas.items():
        r = F.loc[k]
        filas.append(f"{lab} & {int(r.n)} & {f(r.KMO)} & {r.var_CP1:.1f}\\% & {f(r.carga_res, 2)} / "
                     f"{f(r.carga_ig, 2)} / {f(r.carga_tt, 2)} & {f(r.r_CP1_nplat)} & {f(r.rho_CP1_nplat)} \\\\")
    escribir(out, "S1_indice", r"""
\begin{table}[h!]
\caption{Sensitivity of the digital capital index (PCA-A) to the composition of the sample. Loadings are given for reviews / Instagram followers / TikTok followers (log-transformed); $r$ and $\rho$ are the Pearson and Spearman correlations between PC1 and the number of active platforms.}\label{tab:S1_index}
\footnotesize\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}>{\raggedright\arraybackslash}p{0.3\textwidth}>{\centering\arraybackslash}p{0.045\textwidth}>{\centering\arraybackslash}p{0.06\textwidth}>{\centering\arraybackslash}p{0.08\textwidth}>{\centering\arraybackslash}p{0.17\textwidth}>{\centering\arraybackslash}p{0.06\textwidth}>{\centering\arraybackslash}p{0.06\textwidth}@{}}
\toprule
\textbf{Sample} & \textbf{n} & \textbf{KMO} & \textbf{PC1 variance} & \textbf{Loadings} & \textbf{$r$} & \textbf{$\rho$} \\
\midrule
""" + "\n".join(filas) + r"""
\bottomrule
\end{tabular}
\end{table}""")

    # ── S6.9.7 · α ───────────────────────────────────────────────────────────
    niv = [("a_categorias_articulo", "(a) Categories used in the article (Other grouped)"),
           ("b_13_categorias", "(b) The thirteen categories of the typology"),
           ("c_T_vs_NT_51_con_Otra", "(c) Traditional vs.\\ New Traditional, 51 establishments; any other answer kept as ``Other''"),
           ("c2_T_vs_NT_51_solo_TyNT", "(c$'$) As (c), counting only Traditional or New Traditional answers\\textsuperscript{a}")]
    filas = []
    for k, lab in niv:
        r = jt[k]
        filas.append(f"{lab} & {r['unidades_usadas']} & {f(r['alfa'])} & {f(r['IC95'][0])}--{f(r['IC95'][1])} & "
                     f"{100 * r['acuerdo_porcentual_pares']:.1f}\\% \\\\")
    escribir(out, "S6_alfa", r"""
\begin{table}[h!]
\caption{Agreement among the four chefs (Krippendorff's $\alpha$, nominal). ``I cannot determine it'' is treated as missing. The 95\% confidence interval resamples establishments with replacement (10,000 replicates, seed 12345). Pairwise agreement is the share of coinciding pairs of answers.}\label{tab:S6_alpha}
\footnotesize\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}>{\raggedright\arraybackslash}p{0.46\textwidth}>{\centering\arraybackslash}p{0.07\textwidth}>{\centering\arraybackslash}p{0.07\textwidth}>{\centering\arraybackslash}p{0.13\textwidth}>{\centering\arraybackslash}p{0.13\textwidth}@{}}
\toprule
\textbf{Level} & \textbf{Units} & \textbf{$\alpha$} & \textbf{95\% CI} & \textbf{Pairwise agreement} \\
\midrule
""" + "\n".join(filas) + r"""
\bottomrule
\end{tabular}

{\footnotesize\textsuperscript{a}Not announced in \ref{sec:S6.9.6}; added after seeing the data, to separate disagreement about the register from disagreement about whether the cuisine is from Quito at all.\par}
\end{table}""")

    # ── S6.9.7 · sensibilidad Instagram ──────────────────────────────────────
    S = pd.read_csv(tip / "S6_sensibilidad_instagram.csv").set_index("escenario")
    lab = {"original": "Original labels (June 2026, as in the article)",
           "consenso": "Consensus label ($\\geq$3 of 4 chefs) where reached",
           "pluralidad": "Most frequent chef label, if not tied",
           "confirmadas": "Only labels confirmed by the chefs' consensus\\textsuperscript{a}"}
    # p en formato legible: 3.2 × 10^-10
    filas = []
    for k, l in lab.items():
        r = S.loc[k]
        m, e = f"{r.p_fisher:.1e}".split("e")
        filas.append(f"{l} & {int(r.T_con_IG)}/{int(r.T_n)} ({r.T_pct:.1f}\\%) & {int(r.NT_con_IG)}/{int(r.NT_n)} ({r.NT_pct:.1f}\\%) & "
                     f"{r.OR_fisher:.1f} & ${m} \\times 10^{{{int(e)}}}$ \\\\")
    chefs = S.loc[["C1", "C2", "C3", "C4"]]
    pmax = chefs.p_fisher.max()
    m, e = f"{pmax:.1e}".split("e")
    filas.append(f"Each chef's labels separately (four codings) & {chefs.T_pct.min():.1f}--{chefs.T_pct.max():.1f}\\% & "
                 f"{chefs.NT_pct.min():.1f}--{chefs.NT_pct.max():.1f}\\% & {chefs.OR_fisher.min():.1f}--{chefs.OR_fisher.max():.1f} & "
                 f"$\\leq {m} \\times 10^{{{int(e)}}}$ \\\\")
    escribir(out, "S6_sensibilidad", r"""
\begin{table}[h!]
\caption{Sensitivity of the article's central contrast to the coder. In each row the original label is replaced, only for the 67 sampled establishments, by the label indicated; the rest of the census keeps its original label. Odds ratio and $p$ from Fisher's exact test (New Traditional vs.\ Traditional).}\label{tab:S6_sens}
\footnotesize\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}>{\raggedright\arraybackslash}p{0.34\textwidth}>{\centering\arraybackslash}p{0.17\textwidth}>{\centering\arraybackslash}p{0.17\textwidth}>{\centering\arraybackslash}p{0.08\textwidth}>{\centering\arraybackslash}p{0.12\textwidth}@{}}
\toprule
\textbf{Labels used} & \textbf{Traditional with Instagram} & \textbf{New Traditional with Instagram} & \textbf{OR} & \textbf{$p$} \\
\midrule
""" + "\n".join(filas) + r"""
\bottomrule
\end{tabular}

{\footnotesize\textsuperscript{a}Sampled establishments whose consensus label differs from the original, or that reached no consensus, are dropped.\par}
\end{table}""")

    # ── S7 · escenarios de cierre ────────────────────────────────────────────
    G = pd.read_csv(sen / "G_escenarios_cierre.csv")
    nombres = ["June 2026 census (upper bound)", "Excluding the 13 verified closures",
               "+ 25\\% of the 97 without evidence closed", "+ 50\\% of the 97 without evidence closed",
               "+ 75\\% of the 97 without evidence closed",
               "Extreme: all 97 without evidence closed\\textsuperscript{a}"]
    filas = []
    for i, nom in enumerate(nombres):
        r = G.iloc[i]
        irr = f"{r.IRR_ig:.2f} [{json.loads(r.IC95)[0]:.2f}--{json.loads(r.IC95)[1]:.2f}]" if pd.notna(r.IRR_ig) else "---"
        dist = f"{r.IRR_dist:.2f} ({r.p_dist:.3f})" if pd.notna(r.IRR_dist) else "---"
        filas.append(f"{nom} & {int(r.n)} & {r.pct_cero:.1f}\\% & {r.pct_tres:.1f}\\% & {f(r.r_CP1_nplat)} & "
                     f"{r.IG_T:.1f}\\% / {r.IG_NT:.1f}\\% & {irr} & {dist} \\\\")
    escribir(out, "S7_escenarios", r"""
\begin{table}[h!]
\caption{Main results under closure scenarios. Rows with a share of the 97 establishments without evidence closed average 200 random draws (seed 12345); the regression is fitted only for the deterministic scenarios. The share of reviews held by establishments on all three platforms (43.5\%) is identical in every scenario, because the absent establishments have no reviews.}\label{tab:S7_scen}
\footnotesize\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}>{\raggedright\arraybackslash}p{0.2\textwidth}>{\centering\arraybackslash}p{0.045\textwidth}>{\centering\arraybackslash}p{0.07\textwidth}>{\centering\arraybackslash}p{0.07\textwidth}>{\centering\arraybackslash}p{0.08\textwidth}>{\centering\arraybackslash}p{0.11\textwidth}>{\centering\arraybackslash}p{0.17\textwidth}>{\centering\arraybackslash}p{0.11\textwidth}@{}}
\toprule
\textbf{Scenario} & \textbf{n} & \textbf{No platform} & \textbf{All three} & \textbf{$r$ (PC1, platforms)} & \textbf{Instagram: T / NT} & \textbf{IRR Instagram [95\% CI]} & \textbf{IRR distance ($p$)} \\
\midrule
""" + "\n".join(filas) + r"""
\bottomrule
\end{tabular}

{\footnotesize\textsuperscript{a}Only the six establishments with dated evidence of operation remain. T: Traditional; NT: New Traditional.\par}
\end{table}""")

    # ── S7 · tipo × ausencia ─────────────────────────────────────────────────
    J = pd.read_csv(sen / "J_sin_plataforma_por_tipo_censo.csv").set_index("tipo_raw")
    det = pd.read_csv(sen / "J_116_detalle.csv")
    comb = det.categoria_combinada.str.replace("Sin clasificar → ", "", regex=False)
    filas = []
    otros = J.loc[["Parrilla", "Saludable", "Casa Cultural", "Hostal", "Catering"]].sum()
    J.loc["Otros"] = [otros.n, otros.sin_plataforma, 100 * otros.sin_plataforma / otros.n]
    TIPO_EN["Otros"] = "Other"
    for t in ["New Traditional", "Traditional", "International", "Fast Food", "Café", "Regional Ecuadorian cuisine",
              "Bar", "Other", "Unclassified"]:
        k = {v: k for k, v in TIPO_EN.items()}[t]
        r = J.loc[k]
        filas.append(f"{t} & {int(r.n)} & {int(r.sin_plataforma)} & {r.pct_sin_plataforma:.1f}\\% \\\\")
    assert int(J.drop("Otros").n.sum()) == 420 and int(J.drop("Otros").sin_plataforma.sum()) == 116
    escribir(out, "S7_tipos", r"""
\begin{table}[h!]
\caption{Establishments outside the three platforms in June 2026, by gastronomic type (original June labels; denominators are the census counts of each type).}\label{tab:S7_types}
\small
\begin{tabular}{@{}lccc@{}}
\toprule
\textbf{Gastronomic type} & \textbf{In the census} & \textbf{Without presence} & \textbf{Share} \\
\midrule
""" + "\n".join(filas) + r"""
\bottomrule
\end{tabular}
\end{table}""")

    # ── S8 · ancho de banda ──────────────────────────────────────────────────
    B = pd.DataFrame(js["B_kde"])
    filas = [f"{int(r.h_m)}{' (article)' if r.h_m == 125 else ''} & {r.sep_m:.0f} & {f(r.rho_AB)} & {r.conc_ratio:.2f} & "
             f"{r.P90_P10_C:.1f} & {f(r.rho_B_vs_B125)} & {r.jaccard_top10_B_vs_B125:.2f} \\\\" for r in B.itertuples()]
    escribir(out, "S8_kde", r"""
\begin{table}[h!]
\caption{Kernel density surfaces under six bandwidths (same kernel, 10~m grid and domain). Separation and $\rho_{AB}$ compare the establishment density (A) with the review-weighted surface (B); the last two columns compare each surface B with the one used in the article ($h = 125$~m): rank correlation and Jaccard overlap of the cells in the top decile.}\label{tab:S8_kde}
\footnotesize\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}>{\centering\arraybackslash}p{0.09\textwidth}>{\centering\arraybackslash}p{0.13\textwidth}>{\centering\arraybackslash}p{0.08\textwidth}>{\centering\arraybackslash}p{0.12\textwidth}>{\centering\arraybackslash}p{0.1\textwidth}>{\centering\arraybackslash}p{0.1\textwidth}>{\centering\arraybackslash}p{0.12\textwidth}@{}}
\toprule
\textbf{$h$ (m)} & \textbf{Separation of maxima (m)} & \textbf{$\rho_{AB}$} & \textbf{Concentration B/A} & \textbf{P90/P10 of C} & \textbf{$\rho$ with $B_{125}$} & \textbf{Top-decile Jaccard} \\
\midrule
""" + "\n".join(filas) + r"""
\bottomrule
\end{tabular}
\end{table}""")

    # ── S8 · mallas ──────────────────────────────────────────────────────────
    C = pd.read_csv(sen / "C_malla_MAUP.csv")
    C["res_fdr"] = C.resenas_hot_FDR + C.resenas_cold_FDR
    filas = []
    for lado, g in C.groupby("lado_m"):
        filas.append(f"{int(lado)}{' (article)' if lado == 150 else ''} & {rango(g.celdas.min(), g.celdas.max())} & "
                     f"{rango(g.moran_I_resenas.min(), g.moran_I_resenas.max(), 2)} & "
                     f"{rango(g.moran_I_CP1.min(), g.moran_I_CP1.max(), 2)} & "
                     f"{rango(g.res_fdr.min(), g.res_fdr.max())} & {rango(g.CP1_hot_FDR.min(), g.CP1_hot_FDR.max())} & "
                     f"{rango(g.jaccard_estab_vs_base.min(), g.jaccard_estab_vs_base.max(), 2)} \\\\")
    assert (C.moran_p_resenas < 0.05).all() and (C.moran_p_CP1 < 0.05).all() and (C.CP1_cold_FDR == 0).all()
    escribir(out, "S8_mallas", r"""
\begin{table}[h!]
\caption{Global and local spatial statistics under five cell sizes and four grid origins (the original origin and shifts of half a cell east, north, and both). Each cell shows the range over the four origins. Moran's I is significant ($p < 0.05$, 9,999 permutations) in all twenty grids for both variables. Gi* cells counted are those surviving the Benjamini--Hochberg correction; no grid produced an FDR-significant cold cell for the index. The last column compares the establishments lying in FDR hot cells of the index with those of the article's grid (Jaccard index).}\label{tab:S8_grid}
\footnotesize\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}>{\centering\arraybackslash}p{0.1\textwidth}>{\centering\arraybackslash}p{0.11\textwidth}>{\centering\arraybackslash}p{0.13\textwidth}>{\centering\arraybackslash}p{0.13\textwidth}>{\centering\arraybackslash}p{0.12\textwidth}>{\centering\arraybackslash}p{0.12\textwidth}>{\centering\arraybackslash}p{0.12\textwidth}@{}}
\toprule
\textbf{Cell (m)} & \textbf{Occupied cells} & \textbf{Moran's I, reviews} & \textbf{Moran's I, index} & \textbf{FDR cells, reviews} & \textbf{FDR hot cells, index} & \textbf{Overlap with article} \\
\midrule
""" + "\n".join(filas) + r"""
\bottomrule
\end{tabular}
\end{table}""")

    # ── S8 · borde ───────────────────────────────────────────────────────────
    E = pd.read_csv(sen / "E_efecto_borde.csv")
    E = E[E.variante == "indice_fijo"]
    filas = [f"{'None (article)' if r.buffer_m == 0 else str(int(r.buffer_m)) + (' ($= h$)' if r.buffer_m == 125 else ' ($= 2h$)')} & "
             f"{int(r.n)} & {int(r.excluidos)} ({int(r.excluidos_ausentes)}) & {f(r.moran_I_CP1)} & "
             f"{int(r.CP1_hot_FDR)} & {int(r.celdas_hot_base_que_persisten)} of {int(r.celdas_hot_base_total)} & "
             f"{r.kde_sep_m:.0f} & {f(r.kde_rho_AB)} \\\\" for r in E.itertuples()]
    escribir(out, "S8_borde", r"""
\begin{table}[h!]
\caption{Edge-effect check. Establishments within the buffer distance of the Historic Centre limit, or outside it, are excluded and every statistic is recomputed with the index estimated on the full census (re-estimating it on the reduced sample changes no figure in the table by more than 0.001). Moran's I is significant in every row (9,999 permutations, $p < 0.01$).}\label{tab:S8_edge}
\footnotesize\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}>{\raggedright\arraybackslash}p{0.12\textwidth}>{\centering\arraybackslash}p{0.05\textwidth}>{\centering\arraybackslash}p{0.1\textwidth}>{\centering\arraybackslash}p{0.09\textwidth}>{\centering\arraybackslash}p{0.08\textwidth}>{\centering\arraybackslash}p{0.1\textwidth}>{\centering\arraybackslash}p{0.09\textwidth}>{\centering\arraybackslash}p{0.07\textwidth}@{}}
\toprule
\textbf{Buffer (m)} & \textbf{n} & \textbf{Excluded (of them absent)} & \textbf{Moran's I, index} & \textbf{FDR hot cells} & \textbf{Article cells that persist} & \textbf{KDE separation (m)} & \textbf{$\rho_{AB}$} \\
\midrule
""" + "\n".join(filas) + r"""
\bottomrule
\end{tabular}
\end{table}""")
    Ef = pd.read_csv(sen / "E_efecto_borde.csv")
    a, b = Ef[Ef.variante == "indice_fijo"].set_index("buffer_m"), Ef[Ef.variante == "indice_reestimado"].set_index("buffer_m")
    dif = (a[["moran_I_CP1", "kde_rho_AB", "r_CP1_nplat"]] - b[["moran_I_CP1", "kde_rho_AB", "r_CP1_nplat"]]).abs().max().max()
    assert (a.moran_p_CP1 < 0.01).all() and (b.moran_p_CP1 < 0.01).all()
    assert dif <= 0.001 and (a.CP1_hot_FDR == b.CP1_hot_FDR).all(), dif

    # ── Cifras sueltas que cita la prosa ─────────────────────────────────────
    nucleo = pd.read_csv(sen / "C2_nucleo_robusto.csv")
    censo = pd.read_csv(raiz / "final_figures_CODE" / "restaurantes_quito_CH_clean.csv")
    frec = pd.read_csv(sen / "C2_frecuencia_hot_por_local.csv")
    ver = pd.read_csv(raiz / "revision_R1" / "datos" / "exportaciones" / "verificacion_116_final.csv")
    cerr = sorted(ver.loc[ver.FINAL_estado == "Cerrado/trasladado", "id_censo"])
    assert cerr == sorted(sum(CIERRES.values(), [])), "los criterios de cierre no cuadran con la verificación"
    I = js["I_verificacion"]
    Dp = js["D_puntos"]
    cifras = {
        "nucleo_n": len(nucleo), "nucleo_en_todas": int((frec.frecuencia_hot == 1).sum()),
        "nucleo_lat": [round(nucleo.lat.min(), 4), round(nucleo.lat.max(), 4)],
        "nucleo_lon": [round(nucleo.lon.min(), 4), round(nucleo.lon.max(), 4)],
        "nucleo_pct_3plat": round(100 * (nucleo.n_plataformas == 3).mean(), 1),
        "nucleo_sin_plataforma": int((nucleo.n_plataformas == 0).sum()),
        "censo_pct_3plat": round(100 * (censo.n_plataformas == 3).mean(), 1) if "n_plataformas" in censo else None,
        "cierres_por_criterio": {k: len(v) for k, v in CIERRES.items()},
        "estado": I["estado"], "SV": [I["SV_con_fecha"], I["SV_min"], I["SV_mediana"], I["SV_max"], I["SV_por_anio"]],
        "FB": I["FB_presente"], "GM_nueva": I["GM_ficha_oct2026"], "TA": [I["TA_116_si"], I["TA_4_si"]],
        "IG_incidental": I["IGTT_hallazgo"], "presencia_alternativa": I["presencia_alternativa"],
        "cruce_estado_presencia": I["cruce_estado_presencia"],
        "moran_puntos": Dp["moran_puntos"], "gi_puntos": Dp["gi_puntos_CP1"],
        "join_counts": Dp["local_join_counts"], "superficie_proporcion": Dp["superficie_proporcion"],
        "borde": {k: v for k, v in js["E_borde"].items() if k != "escenarios"},
        "caracterizacion": {k: v for k, v in js["J_caracterizacion"].items() if k.startswith(("116", "dist", "mann"))},
        "por_categoria": js["J_caracterizacion"]["por_categoria"],
        "consenso": jt["consenso"], "J": [jt["J_vs_original"], jt["J_vs_consenso"]],
        "desacuerdo": jt["descomposicion_desacuerdo"], "tarjeta": jt["informacion_tarjeta"],
        "motivos_ND": jt["motivos_no_determinable_chefs"],
    }
    (out / "_cifras_texto.json").write_text(json.dumps(cifras, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(cifras, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--raiz", default=".")
    main(Path(a.parse_args().raiz))
