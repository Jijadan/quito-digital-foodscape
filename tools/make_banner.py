"""Genera los banners del README (EN y ES) a partir de los datos publicados en este repositorio.
Uso: python tools/make_banner.py   (requiere pandas, geopandas, matplotlib)"""
from pathlib import Path
import pandas as pd, geopandas as gpd, matplotlib as mpl, matplotlib.pyplot as plt
from matplotlib import font_manager as fm

R = Path(__file__).resolve().parents[1]
df = pd.read_csv(R / "data/restaurantes_quito_CH_clean.csv")
df["n_plat"] = df["existe_gmaps"].astype(str).str.upper().eq("TRUE").astype(int) + df["Tiene IG"].astype(int) + df["Tiene TikTok"].astype(int)
lim = gpd.read_file(R / "data/geo/historic_centre_limit_IMP2019.geojson")
pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326).to_crs(32717)
lim = lim.to_crs(32717)
assert len(df) == 420 and df.n_plat.value_counts().to_dict() == {1: 207, 0: 116, 3: 61, 2: 36}

mpl.rcParams["font.family"] = "Inter"
BG, PANEL, TXT, MUTED, GOLD = "#14110F", "#1E1A17", "#EFE6DA", "#9C8F82", "#D8B15A"
COL = {0: "#5B524A", 1: "#7FA7C9", 2: "#B58BD6", 3: GOLD}
SIZE = {0: 14, 1: 22, 2: 34, 3: 52}

TXTS = {
 "en": dict(kicker="FRONTIERS IN NUTRITION · DATA & CODE",
            title="Findability before visibility",
            sub="Digital thresholds and the stratification of food heritage\nin the Historic Centre of Quito",
            stats=[("420", "registered food\nestablishments"), ("27.6%", "absent from all three\nplatforms (upper bound)"),
                   ("14.5%", "on all three platforms\nhold 43.5% of reviews"), ("r = 0.898", "index vs. number\nof platforms")],
            leg="Platforms with presence (Google Maps · Instagram · TikTok)", legs=["none", "one", "two", "three"],
            foot="Dashed line: Historic Centre limit (IMP 2019) · n = 420 · June 2026"),
 "es": dict(kicker="FRONTIERS IN NUTRITION · DATOS Y CÓDIGO",
            title="Encontrabilidad antes que visibilidad",
            sub="Umbrales digitales y estratificación del patrimonio alimentario\nen el Centro Histórico de Quito",
            stats=[("420", "establecimientos de\ncomida registrados"), ("27,6 %", "ausentes de las tres\nplataformas (cota superior)"),
                   ("14,5 %", "presentes en las tres\nconcentran el 43,5 % de reseñas"), ("r = 0,898", "índice frente al número\nde plataformas")],
            leg="Plataformas con presencia (Google Maps · Instagram · TikTok)", legs=["ninguna", "una", "dos", "tres"],
            foot="Línea discontinua: límite del Centro Histórico (IMP 2019) · n = 420 · junio de 2026"),
}

for lang, T in TXTS.items():
    fig = plt.figure(figsize=(16, 7.2), dpi=150, facecolor=BG)
    fig.text(0.045, 0.87, T["kicker"], color=GOLD, fontsize=11, fontweight="semibold")
    fig.text(0.045, 0.745, T["title"], color=TXT, fontsize=34 if lang == "en" else 28.5, fontweight="bold", family="Inter Display")
    fig.text(0.045, 0.665, T["sub"], color=MUTED, fontsize=14.5, linespacing=1.45, va="top")
    for i, (big, small) in enumerate(T["stats"]):
        x = 0.045 + (i % 2) * 0.235; y = 0.40 - (i // 2) * 0.215
        fig.text(x, y, big, color=GOLD if i else TXT, fontsize=25, fontweight="bold", family="Inter Display")
        fig.text(x, y - 0.02, small, color=MUTED, fontsize=10.5, linespacing=1.35, va="top")
    ax = fig.add_axes([0.52, 0.09, 0.45, 0.78]); ax.set_facecolor(BG)
    lim.boundary.plot(ax=ax, color="#8A7E72", linewidth=1.1, linestyle=(0, (4, 3)))
    for k in [0, 1, 2, 3]:
        s = pts[pts.n_plat == k]
        ax.scatter(s.geometry.x, s.geometry.y, s=SIZE[k], c=COL[k], alpha=0.9 if k else 0.75,
                   edgecolors=BG, linewidths=0.4, zorder=2 + k, label=T["legs"][k])
    x0, y0, x1, y1 = pts.total_bounds; bx0, by0, bx1, by1 = lim.total_bounds
    x0, y0, x1, y1 = min(x0, bx0), min(y0, by0), max(x1, bx1), max(y1, by1)
    pad = 80; ax.set_xlim(x0 - pad, x1 + pad); ax.set_ylim(y0 - pad, y1 + pad)
    ax.set_aspect("equal"); ax.axis("off")
    lg = ax.legend(title=T["leg"], loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=4, frameon=False,
                   fontsize=9.5, title_fontsize=9.5, labelcolor=MUTED, handletextpad=0.3, columnspacing=1.6)
    lg.get_title().set_color(MUTED)
    fig.text(0.745, 0.035, T["foot"], color="#6E655C", fontsize=9.5, ha="center")
    out = R / f"assets/img/banner_{lang}.png"
    fig.savefig(out, facecolor=BG, dpi=150); plt.close(fig)
    print(out)
