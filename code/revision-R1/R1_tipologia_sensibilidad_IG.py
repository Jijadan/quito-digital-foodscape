# -*- coding: utf-8 -*-
"""
R1 · Sensibilidad del contraste de Instagram (Tradicional frente a Nuevo Tradicional)
====================================================================================

Script NUEVO de la revisión R1 (Material Suplementario S6.9.7, tabla de sensibilidad).
Solo LEE el censo, la llave de códigos ciegos y la exportación de la app; ESCRIBE
R1_v2_borrador/resultados/tipologia/S6_sensibilidad_instagram.csv.

Para cada escenario se sustituye, SOLO en los 67 locales muestreados, la etiqueta
original de junio por la etiqueta del escenario; el resto del censo conserva la suya.
Después se calcula el % con Instagram en Tradicional y en Nuevo Tradicional y la
prueba exacta de Fisher (NT frente a T).

Escenarios
  original     etiquetas de junio (las del artículo)
  consenso     categoría elegida por ≥ 3 de los 4 chefs; sin consenso → se conserva la original
  pluralidad   categoría más frecuente entre los chefs si no hay empate; si hay empate → original
  confirmadas  se DESCARTAN los locales muestreados cuyo consenso no coincide con la original
               (o que no tienen consenso): solo quedan etiquetas confirmadas por los chefs
  C1 … C4      la respuesta de cada chef por separado; "no determinable" → se conserva la original

Uso (desde la carpeta raíz del proyecto):
    python R1_v2_borrador/codigo/R1_tipologia_sensibilidad_IG.py
"""
import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

APP_A_BASE = {
    "tradicional": "Tradicional", "nuevo_tradicional": "Nuevo Tradicional",
    "regional": "Comida Ecuatoriana", "internacional": "Internacional", "fast_food": "Fast Food",
    "bar": "Bar", "cafeteria": "Cafetería", "parrilla": "Parrilla", "saludable": "Saludable",
    "casa_cultural": "Casa Cultural", "hostal": "Hostal", "catering": "Catering",
    "no_determinable": np.nan,
}
CHEFS = ["C1", "C2", "C3", "C4"]


def moda_sin_empate(fila):
    v = [x for x in fila if pd.notna(x)]
    if not v:
        return np.nan
    c = Counter(v).most_common()
    return c[0][0] if len(c) == 1 or c[0][1] > c[1][1] else np.nan


def consenso(fila, minimo=3):
    v = [x for x in fila if pd.notna(x)]
    if not v:
        return np.nan
    c, n = Counter(v).most_common(1)[0]
    return c if n >= minimo else np.nan


def main(raiz: Path, respuestas: Path, salida: Path):
    censo = pd.read_csv(raiz / "final_figures_CODE" / "restaurantes_quito_CH_clean.csv")
    censo["id_censo"] = np.arange(1, len(censo) + 1)
    llave = pd.read_csv(raiz / "GMaps codificacion" / "privado" / "llave_codigos_ciegos_NO_COMPARTIR.csv")
    r = pd.read_csv(respuestas)
    r["cat"] = r.respuesta.map(APP_A_BASE)
    ancho = r.pivot(index="codigo_ciego", columns="codificador", values="cat")
    ancho = ancho.join(llave.set_index("codigo_ciego")[["id_censo", "tipo_restaurante_original"]]).set_index("id_censo")
    ch = ancho[CHEFS]
    original = ancho.tipo_restaurante_original
    cons = ch.apply(consenso, axis=1)

    etiquetas = {
        "original": original,
        "consenso": cons.fillna(original),
        "pluralidad": ch.apply(moda_sin_empate, axis=1).fillna(original),
        "confirmadas": original.where(cons == original),          # NaN → se descarta
    }
    for c in CHEFS:
        etiquetas[c] = ch[c].fillna(original)

    filas = []
    for nombre, etq in etiquetas.items():
        tipo = censo.set_index("id_censo")["Tipo Restaurante"].copy()
        tipo.loc[etq.index] = etq
        d = censo.set_index("id_censo").assign(tipo=tipo).dropna(subset=["tipo"])
        t = d[d.tipo == "Tradicional"]["Tiene IG"]
        nt = d[d.tipo == "Nuevo Tradicional"]["Tiene IG"]
        orr, p = fisher_exact([[int(nt.sum()), int(len(nt) - nt.sum())], [int(t.sum()), int(len(t) - t.sum())]])
        filas.append({"escenario": nombre,
                      "T_con_IG": int(t.sum()), "T_n": len(t), "T_pct": round(100 * t.mean(), 1),
                      "NT_con_IG": int(nt.sum()), "NT_n": len(nt), "NT_pct": round(100 * nt.mean(), 1),
                      "OR_fisher": round(orr, 2) if np.isfinite(orr) else np.inf, "p_fisher": float(f"{p:.3g}")})
    tab = pd.DataFrame(filas)
    salida.mkdir(parents=True, exist_ok=True)
    tab.to_csv(salida / "S6_sensibilidad_instagram.csv", index=False)
    print(tab.to_string(index=False))


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--raiz", default=".")
    a.add_argument("--respuestas", default="R1_v2_borrador/datos/respuestas_2026-10-21.csv")
    a.add_argument("--salida", default="R1_v2_borrador/resultados/tipologia")
    x = a.parse_args()
    main(Path(x.raiz), Path(x.raiz) / x.respuestas, Path(x.raiz) / x.salida)
