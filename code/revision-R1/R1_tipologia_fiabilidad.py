# -*- coding: utf-8 -*-
"""
R1 · Fiabilidad de la tipología gastronómica (Material Suplementario S6.9.6)
============================================================================

Script NUEVO de la revisión R1. No modifica ningún archivo original ni los
resultados del manuscrito enviado: solo LEE la base del censo, la llave de
códigos ciegos y la exportación de la web app, y ESCRIBE en
R1_v2_borrador/resultados/.

Qué calcula (exactamente lo que promete S6.9.6):
  1. α de Krippendorff nominal entre los 4 chefs (C1–C4), "no determinable"
     = dato faltante; unidades con <2 respuestas válidas fuera del cálculo.
     Tres niveles: (a) categorías del artículo (Otros agrupado),
     (b) 13 categorías, (c) Tradicional vs Nuevo Tradicional en los 51
     locales de esos dos estratos.
     IC 95 %: bootstrap por locales (unidades), 10 000 réplicas, semilla 12345.
  2. Acuerdo porcentual (pares) y matriz de confusión chefs × etiqueta original.
  3. Etiqueta de consenso (≥3 de 4 chefs); % de acuerdo y κ de Cohen con la
     etiqueta original.
  4. Sensibilidad: % con Instagram en Tradicional y Nuevo Tradicional
     sustituyendo, en los locales muestreados, la etiqueta original por la de
     consenso.
  5. Codificación de J (primer autor) contra la etiqueta original (aparte).
  6. Diagnósticos de independencia (acuerdo por pares, tiempos).

Uso (desde la carpeta raíz del proyecto):
    python R1_v2_borrador/codigo/R1_tipologia_fiabilidad.py
    python R1_v2_borrador/codigo/R1_tipologia_fiabilidad.py --raiz "/ruta/al/proyecto"
"""
import argparse
import itertools
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

SEMILLA = 12345
N_BOOT = 10_000

# ── Etiquetas ───────────────────────────────────────────────────────────────
APP_A_BASE = {
    "tradicional": "Tradicional",
    "nuevo_tradicional": "Nuevo Tradicional",
    "regional": "Comida Ecuatoriana",       # = "Cocina ecuatoriana regional"
    "internacional": "Internacional",
    "fast_food": "Fast Food",
    "bar": "Bar",
    "cafeteria": "Cafetería",
    "parrilla": "Parrilla",
    "saludable": "Saludable",
    "casa_cultural": "Casa Cultural",
    "hostal": "Hostal",
    "catering": "Catering",
    "no_determinable": np.nan,               # faltante (S6.9.6)
}
OTROS = {"Parrilla", "Saludable", "Casa Cultural", "Hostal", "Catering"}
CHEFS = ["C1", "C2", "C3", "C4"]


def a_articulo(x):
    """Categorías del artículo: los 5 tipos poco frecuentes se agrupan en Otros."""
    if pd.isna(x):
        return x
    return "Otros" if x in OTROS else x


# ── α de Krippendorff nominal (matriz de coincidencias) ────────────────────
def alfa_nominal(matriz):
    """matriz: DataFrame unidades × codificadores con etiquetas (NaN = faltante).
    Devuelve (alfa, n_pareables, n_unidades_usadas)."""
    valores = []
    for _, fila in matriz.iterrows():
        v = [x for x in fila.tolist() if pd.notna(x)]
        if len(v) >= 2:
            valores.append(v)
    if not valores:
        return np.nan, 0, 0
    cats = sorted({c for v in valores for c in v})
    idx = {c: i for i, c in enumerate(cats)}
    o = np.zeros((len(cats), len(cats)))
    for v in valores:
        m = len(v)
        cnt = Counter(v)
        for c, nc in cnt.items():
            for k, nk in cnt.items():
                pares = nc * (nk - 1) if c == k else nc * nk
                o[idx[c], idx[k]] += pares / (m - 1)
    n_c = o.sum(axis=1)
    n = n_c.sum()
    d_o = o.sum() - np.trace(o)
    d_e = (n * n - (n_c ** 2).sum()) / (n - 1)
    if d_e == 0:
        return np.nan, int(n), len(valores)
    return 1 - d_o / d_e, int(n), len(valores)


def alfa_bootstrap(matriz, n_boot=N_BOOT, semilla=SEMILLA):
    """IC 95 % percentil remuestreando locales (unidades) con reemplazo."""
    rng = np.random.default_rng(semilla)
    filas = matriz.reset_index(drop=True)
    n = len(filas)
    res = np.empty(n_boot)
    for b in range(n_boot):
        muestra = filas.iloc[rng.integers(0, n, n)]
        res[b] = alfa_nominal(muestra)[0]
    res = res[~np.isnan(res)]
    return np.percentile(res, [2.5, 97.5]), res


def acuerdo_porcentual(matriz):
    """Proporción de pares (entre codificadores con respuesta válida) que coinciden."""
    acu = tot = 0
    for _, fila in matriz.iterrows():
        v = [x for x in fila.tolist() if pd.notna(x)]
        for a, b in itertools.combinations(v, 2):
            tot += 1
            acu += a == b
    return acu / tot if tot else np.nan, tot


def kappa_cohen(a, b):
    a, b = pd.Series(a).reset_index(drop=True), pd.Series(b).reset_index(drop=True)
    ok = a.notna() & b.notna()
    a, b = a[ok], b[ok]
    cats = sorted(set(a) | set(b))
    po = (a == b).mean()
    pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else np.nan, int(ok.sum()), po


def consenso(fila, minimo=3):
    v = [x for x in fila.tolist() if pd.notna(x)]
    if not v:
        return np.nan
    c, n = Counter(v).most_common(1)[0]
    return c if n >= minimo else np.nan


# ── Principal ───────────────────────────────────────────────────────────────
def main(raiz: Path, salida: Path, respuestas: Path):
    salida.mkdir(parents=True, exist_ok=True)
    censo = pd.read_csv(raiz / "final_figures_CODE" / "restaurantes_quito_CH_clean.csv")
    censo["id_censo"] = np.arange(1, len(censo) + 1)   # id = fila 1..420 (igual que revision_R1)
    llave = pd.read_csv(raiz / "GMaps codificacion" / "privado" / "llave_codigos_ciegos_NO_COMPARTIR.csv")
    r = pd.read_csv(respuestas)

    # Comprobaciones de integridad ------------------------------------------
    chk = {}
    chk["filas_respuestas"] = len(r)
    chk["respuestas_por_codificador"] = r.codificador.value_counts().to_dict()
    chk["duplicados_codificador_local"] = int(r.duplicated(["codificador", "codigo_ciego"]).sum())
    chk["codigos_sin_llave"] = sorted(set(r.codigo_ciego) - set(llave.codigo_ciego))
    chk["llave_sin_respuesta"] = sorted(set(llave.codigo_ciego) - set(r.codigo_ciego))
    m = llave.merge(censo[["id_censo", "Nombre", "Tipo Restaurante", "Tiene IG"]], on="id_censo", how="left")
    chk["llave_coincide_con_censo"] = bool((m.tipo_restaurante_original == m["Tipo Restaurante"]).all())
    assert chk["duplicados_codificador_local"] == 0 and not chk["codigos_sin_llave"] and not chk["llave_sin_respuesta"]
    assert chk["llave_coincide_con_censo"]

    r["cat13"] = r.respuesta.map(APP_A_BASE)
    sin_mapa = set(r.respuesta) - set(APP_A_BASE)
    assert not sin_mapa, f"respuestas no reconocidas: {sin_mapa}"
    ancho = r.pivot(index="codigo_ciego", columns="codificador", values="cat13")
    ancho = ancho.join(llave.set_index("codigo_ciego")[["id_censo", "estrato", "tipo_restaurante_original"]])
    chefs13 = ancho[CHEFS]
    chefsA = chefs13.apply(lambda s: s.map(a_articulo))

    # 1. α en tres niveles -----------------------------------------------------
    resultados = {}
    mask_tnt = ancho.estrato.isin(["Tradicional", "Nuevo Tradicional"])
    niveles = {
        "a_categorias_articulo": chefsA,
        "b_13_categorias": chefs13,
        # (c) primaria: 51 locales T/NT; cualquier otra respuesta se conserva como
        #     tercera categoría "Otra" (no se descarta el desacuerdo).
        "c_T_vs_NT_51_con_Otra": chefs13[mask_tnt].apply(
            lambda s: s.map(lambda x: x if pd.isna(x) or x in ("Tradicional", "Nuevo Tradicional") else "Otra")),
        # (c') variante estricta: solo respuestas T o NT (las demás = faltante)
        "c2_T_vs_NT_51_solo_TyNT": chefs13[mask_tnt].apply(
            lambda s: s.where(s.isin(["Tradicional", "Nuevo Tradicional"]))),
    }
    for nombre, mat in niveles.items():
        a, npar, nu = alfa_nominal(mat)
        ic, _ = alfa_bootstrap(mat)
        pa, npairs = acuerdo_porcentual(mat)
        resultados[nombre] = {
            "alfa": round(a, 3), "IC95": [round(ic[0], 3), round(ic[1], 3)],
            "unidades_usadas": nu, "respuestas_pareables": npar,
            "acuerdo_porcentual_pares": round(pa, 3), "n_pares": npairs,
        }

    # 2. Matriz de confusión: respuestas de chefs × etiqueta original -----------
    largo = ancho.reset_index().melt(id_vars=["codigo_ciego", "estrato", "tipo_restaurante_original"],
                                     value_vars=CHEFS, var_name="chef", value_name="respuesta")
    largo["respuesta"] = largo["respuesta"].fillna("No determinable")
    conf = pd.crosstab(largo.tipo_restaurante_original, largo.respuesta, margins=True)
    conf.to_csv(salida / "S6_confusion_chefs_vs_original.csv")

    # 3. Consenso (≥3 de 4) ----------------------------------------------------
    ancho["consenso13"] = chefs13.apply(consenso, axis=1)
    ancho["n_validas"] = chefs13.notna().sum(axis=1)
    ancho["n_mayoria"] = chefs13.apply(
        lambda f: Counter([x for x in f if pd.notna(x)]).most_common(1)[0][1] if f.notna().any() else 0, axis=1)
    con = ancho.dropna(subset=["consenso13"])
    resultados["consenso"] = {
        "locales_con_consenso": int(len(con)), "locales_total": int(len(ancho)),
        "acuerdo_con_original": round(float((con.consenso13 == con.tipo_restaurante_original).mean()), 3),
        "n_acuerdo": int((con.consenso13 == con.tipo_restaurante_original).sum()),
    }
    k, nk, po = kappa_cohen(con.consenso13, con.tipo_restaurante_original)
    resultados["consenso"]["kappa_cohen_vs_original"] = round(k, 3)
    # por estrato
    por_estrato = []
    for est, g in ancho.groupby("estrato"):
        gc = g.dropna(subset=["consenso13"])
        por_estrato.append({
            "estrato": est, "n": len(g), "con_consenso": len(gc),
            "consenso_igual_original": int((gc.consenso13 == gc.tipo_restaurante_original).sum()),
            "consenso_distinto": int((gc.consenso13 != gc.tipo_restaurante_original).sum()),
            "sin_consenso": int(len(g) - len(gc)),
        })
    pd.DataFrame(por_estrato).to_csv(salida / "S6_consenso_por_estrato.csv", index=False)
    pd.crosstab(ancho.tipo_restaurante_original, ancho.consenso13.fillna("Sin consenso"), margins=True)\
        .to_csv(salida / "S6_consenso_vs_original.csv")

    # 4. Sensibilidad Instagram T vs NT ---------------------------------------
    base = censo[["id_censo", "Tipo Restaurante", "Tiene IG"]].copy()
    sust = ancho.set_index("id_censo")["consenso13"]
    base["tipo_sens"] = base["Tipo Restaurante"]
    cambia = base.id_censo.isin(sust.dropna().index)
    base.loc[cambia, "tipo_sens"] = base.loc[cambia, "id_censo"].map(sust)

    def ig(tipo_col, cat):
        g = base[base[tipo_col] == cat]
        return int(g["Tiene IG"].sum()), int(len(g))
    sens = {}
    for col, etiqueta in [("Tipo Restaurante", "original"), ("tipo_sens", "con_consenso")]:
        for cat in ["Tradicional", "Nuevo Tradicional"]:
            s, n = ig(col, cat)
            sens[f"{etiqueta}_{cat}"] = {"con_IG": s, "n": n, "pct": round(100 * s / n, 1)}
    # Fisher exacto T vs NT en ambos escenarios
    from scipy.stats import fisher_exact
    for etiqueta, col in [("original", "Tipo Restaurante"), ("con_consenso", "tipo_sens")]:
        a, na = ig(col, "Nuevo Tradicional")
        b, nb = ig(col, "Tradicional")
        orr, p = fisher_exact([[a, na - a], [b, nb - b]])
        sens[f"fisher_{etiqueta}"] = {"OR": round(orr, 2), "p": float(f"{p:.3g}")}
    # Escenario más desfavorable: los locales sin consenso del estrato NT pasan a T y viceversa
    resultados["sensibilidad_instagram"] = sens

    # 5. J (primer autor, no ciego) -------------------------------------------
    rj = r[r.codificador == "J"].set_index("codigo_ciego")["cat13"]
    ancho["J"] = rj
    kj, nj, poj = kappa_cohen(ancho.J, ancho.tipo_restaurante_original)
    resultados["J_vs_original"] = {"n_validas": nj, "acuerdo": round(poj, 3), "kappa": round(kj, 3),
                                   "no_determinable": int(ancho.J.isna().sum())}
    kjc, njc, pojc = kappa_cohen(ancho.J, ancho.consenso13)
    resultados["J_vs_consenso"] = {"n_validas": njc, "acuerdo": round(pojc, 3), "kappa": round(kjc, 3)}

    # 6. Diagnósticos ---------------------------------------------------------
    pares = []
    for a_, b_ in itertools.combinations(CHEFS + ["J"], 2):
        ok = ancho[a_].notna() & ancho[b_].notna()
        pares.append({"par": f"{a_}-{b_}", "n": int(ok.sum()),
                      "acuerdo": round(float((ancho.loc[ok, a_] == ancho.loc[ok, b_]).mean()), 3),
                      "kappa": round(kappa_cohen(ancho.loc[ok, a_], ancho.loc[ok, b_])[0], 3)})
    pd.DataFrame(pares).to_csv(salida / "S6_acuerdo_por_pares.csv", index=False)
    tiempos = r.groupby("codificador").agg(
        inicio=("timestamp", "min"), fin=("timestamp", "max"),
        mediana_s=("tiempo_ms", lambda x: round(x.median() / 1000, 1)),
        conoce_local=("conoce_local", "sum"),
        no_determinable=("respuesta", lambda x: int((x == "no_determinable").sum())),
        confianza_alta=("confianza", lambda x: int((x == "alta").sum())),
        confianza_media=("confianza", lambda x: int((x == "media").sum())),
        confianza_baja=("confianza", lambda x: int((x == "baja").sum())))
    tiempos.to_csv(salida / "S6_diagnostico_codificadores.csv")
    resultados["motivos_no_determinable_chefs"] = r[r.codificador.isin(CHEFS)].motivo_nd.value_counts().to_dict()

    # Tabla larga por local (para revisión de Johann; contiene etiquetas: PRIVADA)
    ancho = ancho.join(censo.set_index("id_censo")[["Nombre", "Tiene IG"]], on="id_censo")
    ancho.reset_index().to_csv(salida / "PRIVADO_S6_respuestas_por_local.csv", index=False)

    # 7. ¿De dónde viene el desacuerdo? (sesión 1, pregunta sobre el sistema de puntos)
    #    El sistema de puntos de S6.5 solo decide entre Tradicional y Nuevo Tradicional
    #    (paso 9). Se descompone la masa de desacuerdo de la matriz de coincidencias
    #    por par de categorías y se calcula el α que resultaría si TODO el desacuerdo
    #    T↔NT desapareciera (cota superior del efecto del sistema de puntos).
    pares = Counter(); total = 0.0
    for _, f in chefs13.iterrows():
        v = [x for x in f.tolist() if pd.notna(x)]
        m = len(v)
        if m < 2:
            continue
        for a_, b_ in itertools.permutations(range(m), 2):
            total += 1 / (m - 1)
            if v[a_] != v[b_]:
                pares[" ↔ ".join(sorted((v[a_], v[b_])))] += 1 / (m - 1)
    masa = sum(pares.values())
    desc = pd.DataFrame([{"par": k, "masa": round(x, 2), "pct_desacuerdo": round(100 * x / masa, 1)}
                         for k, x in pares.most_common()])
    desc.to_csv(salida / "S6_descomposicion_desacuerdo.csv", index=False)
    fusion = chefs13.apply(lambda s: s.map(lambda x: "T+NT" if x in ("Tradicional", "Nuevo Tradicional") else x))
    resultados["descomposicion_desacuerdo"] = {
        "pct_desacuerdo_T_NT": float(desc.loc[desc.par == "Nuevo Tradicional ↔ Tradicional", "pct_desacuerdo"].sum()),
        "alfa_si_T_y_NT_fueran_una_categoria": round(alfa_nominal(fusion)[0], 3),
        "no_determinable_chefs": int(r[r.codificador.isin(CHEFS)].respuesta.eq("no_determinable").sum()),
        "respuestas_chefs": int(r.codificador.isin(CHEFS).sum())}

    # 8. Información disponible en la tarjeta (diagnóstico; IC por bootstrap de la diferencia)
    loc = pd.read_csv(raiz / "GMaps codificacion" / "app" / "locales.csv")
    w2 = ancho.reset_index().merge(loc[["codigo_ciego", "tiene_menu", "tiene_interior"]], on="codigo_ciego")
    aA = lambda g: alfa_nominal(g[CHEFS].apply(lambda s: s.map(a_articulo)))[0]
    info = {}
    for col in ["tiene_menu", "tiene_interior"]:
        si, no = w2[w2[col] == "Sí"], w2[w2[col] == "No"]
        rng = np.random.default_rng(SEMILLA); dif = []
        for _ in range(2000):
            dif.append(aA(si.iloc[rng.integers(0, len(si), len(si))]) - aA(no.iloc[rng.integers(0, len(no), len(no))]))
        info[col] = {"n_si": len(si), "alfa_si": round(aA(si), 3), "n_no": len(no), "alfa_no": round(aA(no), 3),
                     "IC95_diferencia": [round(float(np.nanpercentile(dif, 2.5)), 3), round(float(np.nanpercentile(dif, 97.5)), 3)]}
    resultados["informacion_tarjeta"] = info

    # 9. Intervalos de confianza del acuerdo consenso–original (bootstrap por locales)
    rng = np.random.default_rng(SEMILLA); acc, kap = [], []
    for _ in range(N_BOOT):
        s = con.iloc[rng.integers(0, len(con), len(con))]
        acc.append(float((s.consenso13 == s.tipo_restaurante_original).mean()))
        kap.append(kappa_cohen(s.consenso13, s.tipo_restaurante_original)[0])
    resultados["consenso"]["IC95_acuerdo"] = [round(float(np.percentile(acc, 2.5)), 3), round(float(np.percentile(acc, 97.5)), 3)]
    resultados["consenso"]["IC95_kappa"] = [round(float(np.nanpercentile(kap, 2.5)), 3), round(float(np.nanpercentile(kap, 97.5)), 3)]
    tnt = con[con.estrato.isin(["Tradicional", "Nuevo Tradicional"])]
    resultados["consenso"]["estratos_T_NT"] = {"con_consenso": int(len(tnt)),
                                               "coinciden": int((tnt.consenso13 == tnt.tipo_restaurante_original).sum())}

    resultados["integridad"] = chk
    with open(salida / "S6_fiabilidad_resultados.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(resultados, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--raiz", default=".", help="carpeta raíz del proyecto")
    p.add_argument("--respuestas", default="R1_v2_borrador/datos/respuestas_2026-10-21.csv")
    p.add_argument("--salida", default="R1_v2_borrador/resultados/tipologia")
    a = p.parse_args()
    raiz = Path(a.raiz)
    main(raiz, raiz / a.salida, raiz / a.respuestas)
