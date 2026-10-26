# -*- coding: utf-8 -*-
"""
R1 · Núcleo robusto de concentración del capital digital (complemento del bloque C)

Para cada uno de los 20 arreglos de malla del bloque C de R1_sensibilidad.py
(lados 100, 125, 150, 200 y 250 m × 4 orígenes) calcula qué locales caen en una
celda caliente de Gi* que sobrevive a Benjamini-Hochberg, y devuelve la fracción
de arreglos en que cada local está en una celda así (0–1). Un local con
frecuencia ≥ 0,75 pertenece al "núcleo robusto": su pertenencia a un cluster
no depende del tamaño ni del origen de la malla.

Solo lee; escribe resultados/sensibilidad/C2_frecuencia_hot_por_local.csv y
C2_nucleo_robusto.csv.

Uso (desde la raíz del proyecto):  python R1_v2_borrador/codigo/R1_nucleo_robusto.py
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

sys.path.insert(0, str(Path(__file__).parent))
import R1_sensibilidad as S  # noqa: E402


def main(raiz: Path):
    sal = raiz / "R1_v2_borrador" / "resultados" / "sensibilidad"
    sal.mkdir(parents=True, exist_ok=True)
    M = S.cargar_motor(raiz)
    d = S.preparar(M, raiz / "final_figures_CODE" / "restaurantes_quito_CH_clean.csv")
    cp1, _ = S.pca_cp1(M, d)
    d["CP1_pct"] = stats.rankdata(cp1) / len(cp1)
    cuenta = pd.Series(0, index=d.id_censo)
    n = 0
    for lado in [100.0, 125.0, 150.0, 200.0, 250.0]:
        for off in [(0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.5, 0.5)]:
            c, dd, _ = S.celdas(d, lado, off)
            w, _ = M.pesos_reina(c)
            vec = M.vecinos_con_autovecindad(w)
            _, Z, _, _ = M.getis_ord_star(c.CP1_suma.values, vec, n_perm=9)   # p analítico
            p = 2 * stats.norm.sf(np.abs(Z))
            rech = multipletests(p, alpha=0.05, method="fdr_bh")[0]
            hot = set(np.where((Z > 0) & rech)[0])
            cuenta[dd.loc[dd.celda.isin(hot), "id_censo"]] += 1
            n += 1
    d["frecuencia_hot"] = cuenta.values / n
    d[["id_censo", "frecuencia_hot"]].to_csv(sal / "C2_frecuencia_hot_por_local.csv", index=False)
    nucleo = d[d.frecuencia_hot >= 0.75]
    nucleo[["id_censo", "Nombre", "lat", "lon", "n_plataformas", "resenas", "tipo_raw", "frecuencia_hot"]]\
        .sort_values("frecuencia_hot", ascending=False).to_csv(sal / "C2_nucleo_robusto.csv", index=False)
    print(f"arreglos: {n} | locales en el núcleo (≥0,75): {len(nucleo)} | en todos: {(d.frecuencia_hot == 1).sum()}")
    print(f"lat {nucleo.lat.min():.4f} a {nucleo.lat.max():.4f} | lon {nucleo.lon.min():.4f} a {nucleo.lon.max():.4f}")
    print(f"% en 3 plataformas: núcleo {100*(nucleo.n_plataformas == 3).mean():.1f} | censo {100*(d.n_plataformas == 3).mean():.1f}")


if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--raiz", default=".")
    main(Path(a.parse_args().raiz))
