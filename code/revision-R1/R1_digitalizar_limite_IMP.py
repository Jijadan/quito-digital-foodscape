# -*- coding: utf-8 -*-
"""
R1 · Digitalización del límite del Centro Histórico de Quito desde el Diagnóstico del IMP
=========================================================================================

Fuente: Instituto Metropolitano de Patrimonio (IMP), Diagnóstico Centro Histórico de Quito
(Plan Urbanístico Complementario para el CHQ), p. 98, Figura 51 ("Predios con destino
económico habitacional"; elaboración IMP, Oficina Plan CHQ, 2017; fuente STHV 2017).

El mapa del PDF es vectorial y lleva una cuadrícula rotulada en coordenadas planas
(497 500–501 000 E; 9 974 000–9 976 500 N) del sistema TM-Quito del Distrito
Metropolitano (SIRES-DMQ: Mercator Transversa, meridiano central 78°30′ O,
factor de escala 1,0004584, falso este 500 000 m, falso norte 10 000 000 m, WGS84).
La línea roja del límite del CHQ (núcleo central + zona de amortiguamiento) se lee
directamente de las instrucciones de dibujo del PDF y se transforma a UTM 17S con
una relación afín obtenida de las marcas de la cuadrícula. No hay trazado a mano.

Controles que imprime el script:
  · superficie del polígono frente a la oficial (375,25 ha; IMP, p. 49 y 106)
  · cuántos de los 420 locales del censo quedan dentro
  · si la Plaza Grande queda dentro

Uso (desde la raíz del proyecto; requiere pymupdf):
    python R1_v2_borrador/codigo/R1_digitalizar_limite_IMP.py --pdf "Mapas/1_Diagnóstico_del_CHQ.pdf"
"""
import argparse
from pathlib import Path

import fitz  # pymupdf
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import linemerge, polygonize, unary_union

TMQ = ("+proj=tmerc +lat_0=0 +lon_0=-78.5 +k=1.0004584 +x_0=500000 +y_0=10000000 "
       "+ellps=WGS84 +towgs84=0,0,0 +units=m +no_defs")
PAGINA = 98                 # numeración impresa = numeración del PDF en este documento
COLOR_LIMITE = (0.9, 0.0, 0.0)


def main(pdf: Path, raiz: Path, salida: Path):
    pg = fitz.open(pdf)[PAGINA - 1]

    # 1. Marcas de la cuadrícula (texto con las coordenadas) → relación afín
    palabras = pg.get_text("words")
    xs, es, ys, ns = [], [], [], []
    for x0, y0, x1, y1, t, *_ in palabras:
        try:
            v = float(t)
        except ValueError:
            continue
        if 497000 <= v <= 502000 and y0 < 100:          # rótulos superiores (este)
            xs.append((x0 + x1) / 2); es.append(v)
        elif 9973000 <= v <= 9977500 and x0 < 560:       # rótulos izquierdos (norte)
            ys.append((y0 + y1) / 2); ns.append(v)
    ax_, bx_ = np.polyfit(xs, es, 1)
    ay_, by_ = np.polyfit(ys, ns, 1)
    res_e = np.abs(np.polyval([ax_, bx_], xs) - es).max()
    res_n = np.abs(np.polyval([ay_, by_], ys) - ns).max()

    # 2. Trazo rojo del límite
    trazo = [d for d in pg.get_drawings()
             if tuple(round(c, 2) for c in (d.get("color") or ())) == COLOR_LIMITE]
    assert len(trazo) == 1, f"se esperaba 1 trazo rojo, hay {len(trazo)}"
    segs = []
    for it in trazo[0]["items"]:
        a, b = (it[1], it[2]) if it[0] == "l" else (it[1], it[4])
        segs.append(LineString([(ax_ * a.x + bx_, ay_ * a.y + by_), (ax_ * b.x + bx_, ay_ * b.y + by_)]))
    poligonos = list(polygonize(linemerge(unary_union(segs))))
    poligono = max(poligonos, key=lambda p: p.area)

    g = gpd.GeoDataFrame({"fuente": ["IMP, Diagnóstico CHQ, p. 98 (Fig. 51); STHV 2017"],
                          "descripcion": ["Límite del CHQ: núcleo central + zona de amortiguamiento"]},
                         geometry=[poligono], crs=TMQ).to_crs("EPSG:32717")
    salida.parent.mkdir(parents=True, exist_ok=True)
    g.to_file(salida, driver="GPKG")

    # 3. Controles
    P = g.geometry.iloc[0]
    d = pd.read_csv(raiz / "final_figures_CODE" / "restaurantes_quito_CH_clean.csv")
    tr = Transformer.from_crs("EPSG:4326", "EPSG:32717", always_xy=True)
    X, Y = tr.transform(d.lon.values, d.lat.values)
    dentro = np.array([P.covers(Point(x, y)) for x, y in zip(X, Y)])
    dist_fuera = np.array([P.exterior.distance(Point(x, y)) for x, y, i in zip(X, Y, dentro) if not i])
    pgx, pgy = tr.transform(-78.512500, -0.220491)
    print(f"residuo máximo de la cuadrícula: E {res_e:.2f} m · N {res_n:.2f} m")
    print(f"tramos del trazo: {len(segs)} · polígonos cerrados: {len(poligonos)}")
    print(f"superficie: {P.area / 1e4:.2f} ha (oficial: 375,25 ha; diferencia {100 * (P.area / 1e4 / 375.25 - 1):+.1f} %)")
    print(f"locales dentro: {dentro.sum()} de {len(d)} · fuera: {(~dentro).sum()} "
          f"(distancias al límite, m: {', '.join(str(int(v)) for v in sorted(dist_fuera))})")
    print(f"Plaza Grande dentro: {P.covers(Point(pgx, pgy))}")
    print(f"guardado: {salida}")


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--pdf", required=True)
    a.add_argument("--raiz", default=".")
    a.add_argument("--salida", default="R1_v2_borrador/datos/limite_CHQ_IMP2019_digitalizado.gpkg")
    x = a.parse_args()
    main(Path(x.pdf), Path(x.raiz), Path(x.raiz) / x.salida)
