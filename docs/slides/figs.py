from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager as fm
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
from PIL import Image, ImageDraw, ImageFont

# Claude generó las figuras con IBM Plex Sans y Archivo instaladas en ~/.fonts.
# Esas fuentes no existen en un clon normal ni en Windows. Si están, se respetan;
# si no, se usa DejaVu Sans, que viene dentro de matplotlib y hace al generador
# reproducible sin descargar nada de la red.
FONT_DIR = Path.home() / ".fonts"
FONT_PATHS = {
    "regular": FONT_DIR / "IBMPlexSans-Regular.ttf",
    "semibold": FONT_DIR / "IBMPlexSans-SemiBold.ttf",
    "title": FONT_DIR / "Archivo-SemiBold.ttf",
}
if all(path.exists() for path in FONT_PATHS.values()):
    for path in FONT_PATHS.values():
        fm.fontManager.addfont(path)
    REG = fm.FontProperties(fname=FONT_PATHS["regular"])
    SB = fm.FontProperties(fname=FONT_PATHS["semibold"])
    TSB = fm.FontProperties(fname=FONT_PATHS["title"])
    PIL_BOLD = FONT_PATHS["semibold"]
    font_family = "IBM Plex Sans"
else:
    REG = fm.FontProperties(family="DejaVu Sans")
    SB = fm.FontProperties(family="DejaVu Sans", weight="semibold")
    TSB = fm.FontProperties(family="DejaVu Sans", weight="semibold")
    PIL_BOLD = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans-Bold.ttf"
    font_family = "DejaVu Sans"

plt.rcParams.update({"font.family": font_family, "font.size": 15, "axes.edgecolor": "#1A1A1820"})

PAPER = "#FAF8F5"
SUNK = "#F2EEE8"
INK = "#1A1A18"
INK2 = "#5F5F59"
OBS = "#8A8A84"
REC = "#D6451A"
OK = "#3F7A4A"
RULE = "#DEDAD3"
OUT = Path(__file__).resolve().parent / "assets"
SOURCE_SCREENSHOT = Path(__file__).resolve().parents[1] / "assets" / "reposicion.png"


def c(x, d=4):
    return f"{x:.{d}f}".replace(".", ",")


def fig(w, h, k=1.0):
    f = plt.figure(figsize=(w / 100 / k, h / 100 / k), dpi=100)
    f.patch.set_facecolor(PAPER)
    return f


def save(f, name):
    f.savefig(OUT / name, dpi=240, facecolor=PAPER)
    plt.close(f)


def clean(ax):
    ax.set_facecolor(PAPER)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(colors=INK2, length=0, labelsize=13)


def box(ax, x, y, w, h, text, fc=SUNK, ec=RULE, tc=INK, fp=REG, size=15):
    ax.add_patch(
        FancyBboxPatch(
            (x - w / 2, y - h / 2),
            w,
            h,
            boxstyle="round,pad=0,rounding_size=0.02",
            fc=fc,
            ec=ec,
            lw=1.2,
        )
    )
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        color=tc,
        fontproperties=fp,
        fontsize=size,
        linespacing=1.25,
    )


def arrow(ax, a, b, col=INK2, rad=0.0, lw=1.6):
    ax.add_patch(
        FancyArrowPatch(
            a,
            b,
            arrowstyle="-|>",
            mutation_scale=16,
            color=col,
            lw=lw,
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=2,
            shrinkB=2,
        )
    )


# 1 · flujo central (portada)
f = fig(1180, 150)
ax = f.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 1180)
ax.set_ylim(0, 150)
ax.axis("off")
steps = [
    "venta\nobservada",
    "demanda latente\nestimada",
    "pronóstico\nprobabilístico",
    "cuantil crítico\nq* = 0,625",
    "cantidad\na pedir",
]
xs = np.linspace(110, 1070, 5)
for i, (x, s) in enumerate(zip(xs, steps, strict=False)):
    if i == 4:
        box(ax, x, 75, 190, 86, s, fc=INK, ec=INK, tc=PAPER, fp=SB, size=17)
    elif i == 1:
        box(ax, x, 75, 190, 86, s, fc=PAPER, ec=REC, tc=REC, fp=SB, size=16)
    else:
        box(ax, x, 75, 190, 86, s, size=16)
    if i < 4:
        arrow(ax, (x + 97, 75), (xs[i + 1] - 97, 75))
save(f, "fig_flujo.png")

# 2 · spiral-down
f = fig(560, 430)
ax = f.add_axes([0, 0, 1, 1])
ax.set_xlim(-1.5, 1.5)
ax.set_ylim(-1.2, 1.18)
ax.axis("off")
labs = [
    "se pide poco",
    "hay quiebre",
    "se observa\nmenos venta",
    "el modelo aprende\nmenor demanda",
    "se vuelve a\npedir poco",
]
ang = np.deg2rad(90 - np.arange(5) * 72)
R = 0.82
pts = [(R * np.cos(a), R * np.sin(a)) for a in ang]
for i, (p, label) in enumerate(zip(pts, labs, strict=False)):
    col = REC if i == 1 else INK
    ax.text(
        p[0],
        p[1],
        label,
        ha="center",
        va="center",
        fontproperties=SB if i == 1 else REG,
        fontsize=15,
        color=col,
        bbox=dict(
            boxstyle="round,pad=0.45",
            fc=SUNK if i != 1 else PAPER,
            ec=REC if i == 1 else RULE,
            lw=1.2,
        ),
    )
for i in range(5):
    a0 = ang[i] - 0.44
    a1 = ang[(i + 1) % 5] + 0.44
    if i == 4:
        a1 = ang[0] + 0.44 - 2 * np.pi
    RA = 0.98
    arrow(
        ax,
        (RA * np.cos(a0), RA * np.sin(a0)),
        (RA * np.cos(a1), RA * np.sin(a1)),
        col=OBS,
        rad=-0.2,
    )
ax.text(0, 0, "spiral-down", ha="center", va="center", fontproperties=TSB, fontsize=19, color=INK2)
save(f, "fig_spiral.png")

# 3 · ablación
f = fig(600, 320, k=1.3)
ax = f.add_axes([0.42, 0.27, 0.52, 0.52])
clean(ax)
vals = [-18.19, -6.61]
labs = ["Entrenado sobre\nventa observada", "Entrenado sobre\ndemanda latente"]
ax.barh([1, 0], vals, color=[OBS, REC], height=0.55)
ax.set_yticks([1, 0])
ax.set_yticklabels(labs, fontsize=14, color=INK)
ax.axvline(0, color=INK, lw=1.2)
ax.set_xlim(-21, 1.5)
ax.set_xticks([-20, -15, -10, -5, 0])
ax.set_xticklabels(["−20 %", "−15 %", "−10 %", "−5 %", "0"])
for y, v in zip([1, 0], vals, strict=False):
    lab = c(v, 2).replace("-", "−") + " %"
    if abs(v) > 10:
        ax.text(
            v + 0.5, y, lab, ha="left", va="center", fontproperties=SB, fontsize=16, color=PAPER
        )
    else:
        ax.text(v - 0.5, y, lab, ha="right", va="center", fontproperties=SB, fontsize=16, color=REC)
f.text(0.02, 0.9, "Sesgo re-censurado · 0 = ideal", fontsize=13, color=INK2)
f.text(0.02, 0.05, "Reducción: 11,57 puntos", fontproperties=SB, fontsize=15, color=REC)
save(f, "fig_ablacion.png")

# 4 · ventana temporal
f = fig(1180, 250)
ax = f.add_axes([0.03, 0.1, 0.94, 0.8])
ax.set_xlim(-2, 99)
ax.set_ylim(-1.8, 10)
ax.axis("off")
ax.add_patch(Rectangle((0, 6.2), 90, 1.6, fc=SUNK, ec=RULE))
ax.add_patch(Rectangle((90, 6.2), 7, 1.6, fc=INK, ec=INK))
ax.text(45, 7, "train oficial · 90 días", ha="center", va="center", fontsize=15, color=INK)
ax.text(93.5, 7, "eval · 7", ha="center", va="center", fontsize=13, color=PAPER, fontproperties=SB)
ax.text(0, 8.6, "2024-03-28", fontsize=15, color=INK2)
ax.text(97, 8.6, "2024-07-02", fontsize=15, color=INK2, ha="right")
# origenes esquemáticos: step 3, h 7, último termina en día 97
ends = [97 - 3 * k for k in range(8)][::-1]
for i, e in enumerate(ends):
    o = e - 7
    y = 4.6 - i * 0.55
    ax.plot([0, o], [y, y], color=OBS, lw=2.2, solid_capstyle="butt")
    ax.plot([o, e], [y, y], color=REC, lw=2.2, solid_capstyle="butt")
ax.text(
    0,
    0.1,
    va="top",
    s="8 orígenes móviles · cada uno entrena con lo anterior (gris) y pronostica 7 días (coral)",
    fontsize=15,
    color=INK2,
)
save(f, "fig_ventana.png")

# 5 · pipeline
f = fig(1180, 210)
ax = f.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 1180)
ax.set_ylim(0, 210)
ax.axis("off")
st = [
    "descarga",
    "submuestreo\nreproducible",
    "recuperación\nde censura",
    "features\nancladas",
    "backtesting\nmóvil",
    "calibración\nCQR",
    "newsvendor",
    "artefacto\nAPI · UI",
]
xs = np.linspace(72, 1108, 8)
y = 120
ax.add_patch(
    Rectangle(
        (xs[3] - 68, y - 58), xs[4] - xs[3] + 136, 116, fc="none", ec=REC, lw=1.4, ls=(0, (4, 3))
    )
)
ax.text(
    (xs[3] + xs[4]) / 2,
    y - 74,
    "8 asserts antifugas, cada uno con su fuga inyectada",
    ha="center",
    va="center",
    fontsize=13,
    color=REC,
    fontproperties=SB,
)
for i, (x, s) in enumerate(zip(xs, st, strict=False)):
    box(
        ax,
        x,
        y,
        120,
        72,
        s,
        fc=INK if i == 7 else SUNK,
        ec=INK if i == 7 else RULE,
        tc=PAPER if i == 7 else INK,
        size=14,
    )
    if i < 7:
        arrow(ax, (x + 61, y), (xs[i + 1] - 61, y))
save(f, "fig_pipeline.png")

# 6 · features
f = fig(520, 300, k=1.3)
ax = f.add_axes([0.58, 0.06, 0.34, 0.8])
clean(ax)
ax.spines["bottom"].set_visible(False)
ax.set_xticks([])
names = [
    "Rezagos de demanda",
    "Calendario + plan",
    "Estadísticos móviles",
    "Jerarquía",
    "Historial de quiebres",
    "Otras",
]
v = [27, 18, 16, 7, 2, 3]
yy = np.arange(6)[::-1]
ax.barh(yy, v, color=INK, height=0.6)
ax.set_yticks(yy)
ax.set_yticklabels(names, fontsize=13, color=INK)
for a, b in zip(yy, v, strict=False):
    ax.text(b + 0.6, a, str(b), va="center", fontsize=14, fontproperties=SB, color=INK)
ax.set_xlim(0, 31)
f.text(0.02, 0.92, "73 features del artefacto real", fontsize=14, color=INK2)
save(f, "fig_features.png")


def mase_chart(name, rows, W, H, target=None, left=0.30, note=None):
    f = fig(W, H, k=1.2)
    ax = f.add_axes([left, 0.2, 0.78 - left, 0.66])
    clean(ax)
    n = len(rows)
    yy = np.arange(n)[::-1]
    lo = 0.7
    hi = max(r[3] for r in rows) + 0.07
    for y, (_lab, m, sd, worst, hl) in zip(yy, rows, strict=False):
        ax.barh(y, m - lo, left=lo, color=REC if hl else "#C9C5BE", height=0.56)
        ax.plot([m - sd, m + sd], [y, y], color=INK, lw=1.4)
        ax.plot([m - sd, m - sd], [y - 0.12, y + 0.12], color=INK, lw=1.4)
        ax.plot([m + sd, m + sd], [y - 0.12, y + 0.12], color=INK, lw=1.4)
        ax.plot(worst, y, marker="|", ms=16, mew=2.4, color=INK)
        ax.text(
            hi + 0.008,
            y,
            c(m),
            va="center",
            ha="left",
            fontproperties=SB if hl else REG,
            fontsize=15,
            color=INK,
        )
    ax.set_yticks(yy)
    ax.set_yticklabels([r[0] for r in rows], fontsize=14, color=INK)
    for t in ax.get_yticklabels():
        if t.get_text() == rows[0][0]:
            t.set_fontproperties(SB)
            t.set_fontsize(14)
    ax.set_xlim(lo, hi)
    ticks = np.arange(0.7, hi, 0.1)
    ax.set_xticks(ticks)
    ax.set_xticklabels([c(t, 1) for t in ticks])
    if target:
        ax.axvline(target, color=OK, lw=1.4, ls=(0, (4, 3)))
        ax.text(
            target,
            n - 0.35,
            "objetivo SMART · " + c(target),
            color=OK,
            fontsize=12.5,
            ha="center",
            fontproperties=SB,
        )
    f.text(
        0.02,
        0.05,
        note or "barra = media · bigote = ±1 desvío · | = peor origen",
        fontsize=12.5,
        color=INK2,
    )
    save(f, name)


mase_chart(
    "fig_clasico.png",
    [
        ("LightGBM global", 0.8386, 0.0549, 0.9029, True),
        ("Croston SBA", 0.9032, 0.0707, 0.9873, False),
        ("SARIMA", 0.9136, 0.0599, 0.9832, False),
        ("Media móvil 21 d", 0.9139, 0.0652, 0.9927, False),
        ("Prophet", 0.9698, 0.0704, 1.0502, False),
        ("Naive estacional", 1.1058, 0.0674, 1.1761, False),
    ],
    760,
    440,
)
mase_chart(
    "fig_resultado.png",
    [
        ("CQR + LightGBM", 0.8217, 0.0454, 0.8790, True),
        ("LightGBM puntual", 0.8222, 0.0457, 0.8791, False),
        ("Croston SBA", 0.8952, 0.0683, 0.9631, False),
        ("Media móvil 21 d", 0.9048, 0.0654, 0.9779, False),
        ("Naive estacional", 1.1002, 0.0636, 1.1579, False),
    ],
    760,
    420,
    target=1.1002 * 0.8,
)

# 7 · CQR bandas
f = fig(640, 330, k=1.3)
ax = f.add_axes([0.02, 0.06, 0.96, 0.9])
ax.set_xlim(-2.4, 2.4)
ax.set_ylim(0, 10)
ax.axis("off")
for y, w, cov, lab, col, al in [
    (7, 1.805, "88,0 %", "CQR", REC, 0.18),
    (3, 3.834, "98,7 %", "Conformal de residuos", OBS, 0.22),
]:
    ax.add_patch(Rectangle((-w / 2, y - 0.9), w, 1.8, fc=col, alpha=al, ec=col, lw=1.4))
    ax.plot([0, 0], [y - 0.9, y + 0.9], color=INK, lw=1.2, ls=(0, (3, 2)))
    ax.text(-2.35, y + 1.45, lab, fontproperties=SB, fontsize=12, color=INK, ha="left")
    ax.text(
        2.35,
        y + 1.45,
        f"{cov} · ancho {c(w,3)}",
        fontsize=11.5,
        color=INK,
        ha="right",
    )
ax.text(
    0, 0.4, "línea punteada = pronóstico · nominal 90 %", fontsize=12.5, color=INK2, ha="center"
)
save(f, "fig_cqr.png")

# 7b · cobertura por horizonte
f = fig(560, 300, k=1.3)
ax = f.add_axes([0.12, 0.14, 0.70, 0.68])
clean(ax)
ax.spines["left"].set_visible(False)
cv = [0.893, 0.893, 0.867, 0.887, 0.883, 0.854, 0.885]
h = np.arange(1, 8)
ax.axhline(0.90, color=INK, lw=1.2, ls=(0, (4, 3)))
ax.text(7.45, 0.90, "nominal\n90 %", fontsize=12, color=INK, va="center")
ax.axhline(0.880, color=OBS, lw=1, ls=":")
ax.text(7.45, 0.878, "global\n88,0 %", fontsize=12, color=INK2, va="center")
ax.plot(h, cv, color=INK, lw=1.8, marker="o", ms=6, mfc=PAPER)
ax.plot(6, 0.854, marker="o", ms=9, color=REC)
ax.text(6, 0.846, "0,854", ha="center", va="top", color=REC, fontproperties=SB, fontsize=14)
ax.set_xticks(h)
ax.set_xticklabels([f"h{i}" for i in h])
ax.set_ylim(0.83, 0.91)
ax.set_xlim(0.6, 7.4)
ax.set_yticks([0.84, 0.86, 0.88, 0.90])
ax.set_yticklabels(["84 %", "86 %", "88 %", "90 %"])
ax.set_title("Cobertura por paso del horizonte", loc="left", fontsize=14, color=INK2, pad=10)
save(f, "fig_cobertura_h.png")

# 8 · newsvendor esquema
f = fig(560, 330, k=1.3)
ax = f.add_axes([0.06, 0.2, 0.88, 0.7])
clean(ax)
ax.set_yticks([])
x = np.linspace(0, 10, 400)

k, th = 3.2, 1.0
y = x ** (k - 1) * np.exp(-x / th)
y /= y.max()
cdf = np.cumsum(y)
cdf /= cdf[-1]
q = x[np.searchsorted(cdf, 0.625)]
ax.fill_between(x, y, where=x <= q, color=INK, alpha=0.10)
ax.plot(x, y, color=INK, lw=1.8)
ax.axvline(q, color=REC, lw=2.2)
ax.text(
    q + 0.15,
    0.95,
    "cantidad a pedir\n= cuantil q* = 0,625",
    color=REC,
    fontproperties=SB,
    fontsize=14,
    va="top",
)
ax.text(q - 0.35, 0.25, "62,5 %", ha="right", fontsize=14, color=INK, fontproperties=SB)
ax.set_xticks([])
ax.set_xlabel("demanda (esquema, sin unidades)", fontsize=12.5, color=INK2)
ax.set_title("Distribución predictiva de una serie", loc="left", fontsize=14, color=INK2, pad=8)
save(f, "fig_newsvendor.png")

# 8b · toggle medido
f = fig(640, 330, k=1.3)
ax = f.add_axes([0.38, 0.24, 0.50, 0.62])
clean(ax)
cats = ["Pronóstico", "Orden", "Política"]
obs = [190.229, 210.958, 231.960]
rec = [238.413, 268.478, 278.596]
yy = np.arange(3)[::-1] * 1.0
ax.barh(yy + 0.18, obs, height=0.34, color=OBS, label="observada")
ax.barh(yy - 0.18, rec, height=0.34, color=REC, label="recuperada")
for y, a, b in zip(yy, obs, rec, strict=False):
    ax.text(a + 4, y + 0.18, c(a, 3), va="center", fontsize=13, color=INK)
    ax.text(b + 4, y - 0.18, c(b, 3), va="center", fontsize=13, color=INK, fontproperties=SB)
ax.set_yticks(yy)
ax.set_yticklabels(cats, fontsize=14, color=INK)
ax.set_xlim(0, 330)
ax.set_xticks([])
ax.spines["bottom"].set_visible(False)
ax.legend(loc="upper left", bbox_to_anchor=(-0.55, -0.04), ncol=2, frameon=False, fontsize=13)
ax.set_title(
    "Toggle medido · 25 series",
    loc="left",
    fontsize=13.5,
    color=INK2,
    pad=8,
    x=-0.55,
)
save(f, "fig_toggle.png")

# 10 · negativos
f = fig(1180, 300)
f.text(0.02, 0.87, "Clustering como feature", fontproperties=TSB, fontsize=18, color=INK)
a1 = f.add_axes([0.02, 0.30, 0.27, 0.30])
a1.axis("off")
a1.set_xlim(-13, 13)
a1.set_ylim(-1, 1)
a1.plot([-11, 11], [0, 0], color="#C9C5BE", lw=14, solid_capstyle="butt")
a1.axvline(0, color=INK, lw=1)
a1.plot(0.28, 0, marker="o", ms=12, color=INK)
a1.text(-11, -0.9, "−11", ha="center", va="top", fontsize=13, color=INK2)
a1.text(11, -0.9, "+11", ha="center", va="top", fontsize=13, color=INK2)
f.text(0.02, 0.66, "efecto medio +0,28 % de MASE", fontproperties=SB, fontsize=15, color=INK)
f.text(0.02, 0.08, "oscilación entre orígenes ≈ ±11 puntos", fontsize=15, color=INK2)
f.text(0.37, 0.87, "Optuna · 25 trials", fontproperties=TSB, fontsize=18, color=INK)
a2 = f.add_axes([0.37, 0.14, 0.26, 0.6])
a2.axis("off")
a2.set_xlim(0, 0.0215)
a2.set_ylim(-0.6, 1.6)
a2.barh([1, 0], [0.0042, 0.0134], color=[INK, "#C9C5BE"], height=0.5)
a2.text(
    0.0042 + 0.0005,
    1,
    "mejora de MASE 0,0042 (0,49 %)",
    va="center",
    fontsize=14,
    fontproperties=SB,
    color=INK,
)
a2.text(0.0134 + 0.0005, 0, "dispersión 0,0134", va="center", fontsize=14, color=INK)
f.text(0.66, 0.87, "Series con MASE > 1", fontproperties=TSB, fontsize=18, color=INK)
a3 = f.add_axes([0.66, 0.38, 0.27, 0.16])
a3.axis("off")
a3.set_xlim(0, 1)
a3.set_ylim(0, 1)
a3.add_patch(Rectangle((0, 0), 0.868, 1, fc="#C9C5BE"))
a3.add_patch(Rectangle((0.868, 0), 0.132, 1, fc=REC))
f.text(0.66, 0.66, "404 de 3.066 series · 13,2 %", fontproperties=SB, fontsize=15, color=REC)
f.text(0.66, 0.08, "nivel medio 2,120 vs 1,344", fontsize=14, color=INK2)
save(f, "fig_negativos.png")

# 9 · captura anotada
im = Image.open(SOURCE_SCREENSHOT).convert("RGB")
crop = im.crop((0, 0, 2880, 1216))
d = ImageDraw.Draw(crop)
fnt = ImageFont.truetype(PIL_BOLD, 40)
S = 1.6
marks = [
    (1, 470, 212),
    (2, 872, 245),
    (3, 807, 424),
    (4, 1772, 618),
    (5, 1608, 62),
    (6, 560, 168),
    (7, 236, 359),
]
for n, x, y in marks:
    X, Y = x * S, y * S
    r = 28
    d.ellipse((X - r - 4, Y - r - 4, X + r + 4, Y + r + 4), fill=PAPER)
    d.ellipse((X - r, Y - r, X + r, Y + r), fill=INK)
    d.text((X, Y - 2), str(n), font=fnt, fill=PAPER, anchor="mm")
d.rectangle((0, 0, 2879, 1215), outline="#DEDAD3", width=3)
crop.save(OUT / "reposicion_anotada.png", optimize=True)
print("ok")

# 5b · pipeline en dos filas
f = fig(760, 330)
ax = f.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 760)
ax.set_ylim(0, 330)
ax.axis("off")
st = [
    "descarga",
    "submuestreo\nreproducible",
    "recuperación\nde censura",
    "features ancladas\nen el origen",
    "backtesting\nde origen móvil",
    "calibración\nCQR",
    "newsvendor",
    "artefacto\nAPI · interfaces",
]
xs = [92, 284, 476, 668]
ys = [262, 140]
bw, bh = 176, 78
pos = [(xs[i % 4], ys[i // 4]) for i in range(8)]
for i, ((x, y), s) in enumerate(zip(pos, st, strict=False)):
    if i == 7:
        box(ax, x, y, bw, bh, s, fc=INK, ec=INK, tc=PAPER, fp=SB, size=13)
    elif i in (3, 4):
        box(ax, x, y, bw, bh, s, fc=PAPER, ec=REC, tc=INK, fp=SB, size=13)
    else:
        box(ax, x, y, bw, bh, s, size=13)
for i in range(7):
    (x0, y0), (x1, y1) = pos[i], pos[i + 1]
    if y0 == y1:
        arrow(ax, (x0 + bw / 2 + 1, y0), (x1 - bw / 2 - 1, y1))
    else:
        ym = (y0 + y1) / 2
        ax.plot([x0, x0, x1, x1], [y0 - bh / 2, ym, ym, ym], color=INK2, lw=1.6)
        arrow(ax, (x1, ym), (x1, y1 + bh / 2))
ax.plot([18, 40], [45, 45], color=REC, lw=2.4)
ax.text(
    50,
    45,
    "cubierto por los 8 asserts antifugas, cada uno con su fuga inyectada",
    fontsize=15,
    color=INK,
    va="center",
)
save(f, "fig_pipeline.png")

# 0 · el problema: dos errores con costo asimétrico (esquema, sin unidades)
f = fig(620, 360, k=1.25)
ax = f.add_axes([0.06, 0.2, 0.9, 0.64])
clean(ax)
ax.set_yticks([])
ax.set_xticks([])
qx = np.linspace(0, 10, 400)
short = np.clip(5.6 - qx, 0, None) ** 1.6 * 0.45
over = np.clip(qx - 5.6, 0, None) ** 1.6 * 0.9
ax.fill_between(qx, 0, short, color=OBS, alpha=0.35, lw=0)
ax.fill_between(qx, 0, over, color=REC, alpha=0.22, lw=0)
ax.plot(qx, short + over, color=INK, lw=2)
ax.axvline(5.6, color=INK, lw=1.2, ls=(0, (4, 3)))
ax.text(5.75, 8.7, "punto óptimo", ha="left", fontproperties=SB, fontsize=14, color=INK)
ax.text(0.12, 0.4, "de menos:\nquiebre", fontsize=13.5, color=INK, ha="left")
ax.text(9.75, 0.5, "de más:\nse vence", fontsize=13.5, color=REC, ha="right", fontproperties=SB)
ax.set_ylim(0, 9.4)
ax.set_xlim(0, 10)
ax.set_xlabel("cantidad pedida", fontsize=14, color=INK2)
f.text(0.06, 0.9, "Costo esperado de una orden (esquema)", fontsize=14, color=INK2)
save(f, "fig_problema.png")

# 3b · un día real con quiebre: serie 812_300 (tienda 812, producto 300), 2024-05-26.
# Valores copiados de data/interim/panel.parquet: hours_sale del día y, como referencia,
# el perfil horario medio de la misma serie en sus 58 días sin ninguna hora de quiebre.
DIA_VENTA = [0.0, 0.0, 0.2, 0.0, 0.1, 0.5, 1.3, 1.2, 2.4, 3.5, 1.8, 0.8,
             0.4, 0.7, 0.9, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
DIA_SIN_STOCK = [0] * 16 + [1] * 8
PERFIL_LIMPIO = [0.109, 0.052, 0.026, 0.022, 0.033, 0.167, 0.49, 0.843, 0.879, 1.081, 0.828, 0.572,
                 0.457, 0.398, 0.433, 0.578, 0.54, 0.429, 0.264, 0.213, 0.155, 0.159, 0.098, 0.048]
f = fig(620, 400, k=1.25)
ax = f.add_axes([0.08, 0.26, 0.88, 0.54])
clean(ax)
ax.spines["left"].set_visible(False)
hh = np.arange(24)
ax.axvspan(15.5, 23.5, color=INK, alpha=0.07, lw=0)
ax.bar(hh, DIA_VENTA, width=0.72, color=INK)
escala = sum(DIA_VENTA[:16]) / sum(PERFIL_LIMPIO[:16])  # ajusta el perfil a las horas con stock
perfil = np.array(PERFIL_LIMPIO) * escala
ax.plot(hh, perfil, color=REC, lw=2, ls=(0, (4, 3)))
ax.text(19.5, 3.3, "sin stock\ndesde las 16 h", ha="center", fontproperties=SB, fontsize=15, color=INK)
ax.set_xticks([0, 6, 12, 16, 22])
ax.set_xticklabels(["0 h", "6 h", "12 h", "16 h", "22 h"])
ax.set_yticks([])
ax.set_xlim(-0.8, 23.8)
ax.set_ylim(0, 4.1)
f.text(0.08, 0.9, "Un día real · serie 812_300 · 26 de mayo", fontsize=14, color=INK2)
f.text(0.08, 0.1, "barras: venta por hora · venta registrada del día 14,8", fontsize=13, color=INK2)
f.text(0.08, 0.03, "línea: perfil típico de la serie, escalado", fontsize=13, color=REC)
save(f, "fig_dia_quiebre.png")
