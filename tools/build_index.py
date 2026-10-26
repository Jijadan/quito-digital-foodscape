"""Builds index.html (GitHub Pages landing page) from tools/index_template.html and the published data.
Genera index.html a partir de la plantilla y de los datos publicados.
Usage / Uso: python tools/build_index.py   (requires pandas, geopandas)"""
import json
from pathlib import Path
import pandas as pd, geopandas as gpd

R = Path(__file__).resolve().parents[1]
df = pd.read_csv(R / "data/restaurantes_quito_CH_clean.csv")
df["n_plat"] = df["existe_gmaps"].astype(str).str.upper().eq("TRUE").astype(int) + df["Tiene IG"].astype(int) + df["Tiene TikTok"].astype(int)
counts = df.n_plat.value_counts().to_dict()
assert len(df) == 420 and counts == {1: 207, 0: 116, 3: 61, 2: 36}

pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326).to_crs(32717)
lim = gpd.read_file(R / "data/geo/historic_centre_limit_IMP2019.geojson").to_crs(32717).geometry.iloc[0].simplify(4)
minx, miny, maxx, maxy = lim.bounds
for x, y in zip(pts.geometry.x, pts.geometry.y):
    minx, miny, maxx, maxy = min(minx, x), min(miny, y), max(maxx, x), max(maxy, y)
pad = 60
X = lambda x: round(x - minx + pad)
Y = lambda y: round(maxy - y + pad)          # SVG y grows downward
view = f"0 0 {round(maxx - minx + 2 * pad)} {round(maxy - miny + 2 * pad)}"
path = "M" + " L".join(f"{X(x)} {Y(y)}" for x, y in lim.exterior.coords) + " Z"
P = [[X(g.x), Y(g.y), int(n), str(name).strip()] for g, n, name in zip(pts.geometry, pts.n_plat, pts["Nombre"])]

html = (R / "tools/index_template.html").read_text(encoding="utf-8")
for k, v in {"__VIEWBOX__": view, "__LIMIT__": path,
             "__POINTS__": json.dumps(P, ensure_ascii=False).replace("</", "<\\/"),
             "__N0__": counts[0], "__N1__": counts[1], "__N2__": counts[2], "__N3__": counts[3]}.items():
    assert k in html, k
    html = html.replace(k, str(v))
(R / "index.html").write_text(html, encoding="utf-8")
print("index.html written:", view, len(P), "points")
