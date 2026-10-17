"""Build a sparse, diagram-led presentation. Run: python3 scripts/build_presentation.py."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ecu-copilot-presentation-mpl")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "design" / "presentation"
DIAGRAMS = OUT / "diagrams"
C = {
    "bg": "#FCFCFA",
    "ink": "#20252A",
    "muted": "#747A7F",
    "line": "#D6D8D7",
    "accent": "#BB4C2B",
    "soft": "#F1F1ED",
    "white": "#FCFCFA",
    "dark": "#20252A",
}
plt.rcParams.update({"font.family": "Liberation Sans", "svg.fonttype": "none", "pdf.fonttype": 42})
SLIDES = []
PLACEMENTS = []


def text(ax, x, y, value, size=24, color=None, weight="normal", width=None, bounds=None, mono=False, **kwargs):
    font_name = "Liberation Mono" if mono else "Liberation Sans"
    if width:
        renderer = ax.figure.canvas.get_renderer()
        font = FontProperties(family=font_name, size=size, weight=weight)
        wrapped = []
        for paragraph in value.split("\n"):
            line = ""
            for word in paragraph.split():
                candidate = f"{line} {word}".strip()
                if line and renderer.get_text_width_height_descent(candidate, font, False)[0] > width - 2:
                    wrapped.append(line)
                    line = word
                else:
                    line = candidate
            wrapped.append(line)
        value = "\n".join(wrapped)
    obj = ax.text(
        x, y, value, fontsize=size, fontfamily=font_name, color=color or C["ink"], weight=weight, va="top", linespacing=1.12, **kwargs
    )
    PLACEMENTS.append((ax.figure, obj, bounds))
    return obj


def line(ax, points, color="ink", lw=2, dashed=False, zorder=1):
    xs, ys = zip(*points, strict=False)
    ax.plot(xs, ys, color=C.get(color, color), lw=lw, ls=(0, (5, 5)) if dashed else "-", zorder=zorder)


def rect(ax, x, y, w, h, fill="none", edge="ink", lw=1.8, dashed=False):
    p = Rectangle(
        (x, y),
        w,
        h,
        facecolor=C.get(fill, fill),
        edgecolor=C.get(edge, edge),
        linewidth=lw,
        linestyle=(0, (5, 5)) if dashed else "solid",
        zorder=2,
    )
    ax.add_patch(p)
    return p


def arrow(ax, start, end, color="ink", both=False, dashed=False, lw=2):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="<->" if both else "-|>",
            mutation_scale=18,
            linewidth=lw,
            color=C.get(color, color),
            linestyle=(0, (5, 5)) if dashed else "solid",
            zorder=2,
            shrinkA=2,
            shrinkB=2,
        )
    )


def circle(ax, x, y, r, fill="bg", edge="ink", lw=2, dashed=False):
    ax.add_patch(
        Circle(
            (x, y),
            r,
            facecolor=C.get(fill, fill),
            edgecolor=C.get(edge, edge),
            linewidth=lw,
            linestyle=(0, (5, 5)) if dashed else "solid",
            zorder=2,
        )
    )


def slide(slug, section, title=None, dark=False):
    bg = C["dark"] if dark else C["bg"]
    fg = C["white"] if dark else C["ink"]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=bg)
    ax = fig.add_axes([0, 0, 1, 1], facecolor=bg)
    ax.set(xlim=(0, 1600), ylim=(900, 0))
    ax.axis("off")
    text(ax, 75, 35, "ECU COPILOT", size=11, weight="bold", color=fg)
    text(ax, 250, 35, "Morteza Molaei", size=11, color=C["muted"])
    text(ax, 1525, 35, section, size=11, color=C["muted"], ha="right")
    if title:
        text(ax, 75, 105, title, size=39, weight="bold", color=fg, bounds=(70, 98, 1460, 80))
    line(ax, [(75, 838), (1525, 838)], color="muted" if dark else "line", lw=0.8)
    text(ax, 75, 855, "Prototyp / simulierte Daten", size=11, color=C["muted"])
    text(ax, 1525, 850, f"{len(SLIDES) + 1:02d}", size=18, color=fg, ha="right", mono=True)
    SLIDES.append({"slug": slug, "title": title or "E-204 / Ruhestrom zu hoch", "section": section, "fig": fig})
    return ax


def chip(ax, x, y, w=230, h=180, color="ink"):
    rect(ax, x, y, w, h, edge=color, lw=2.5)
    rect(ax, x + w * 0.23, y + h * 0.24, w * 0.54, h * 0.52, edge=color, lw=1.3)
    for i in range(7):
        d = h * (i + 1) / 8
        line(ax, [(x - 19, y + d), (x, y + d)], color=color, lw=2)
        line(ax, [(x + w, y + d), (x + w + 19, y + d)], color=color, lw=2)
    for i in range(9):
        d = w * (i + 1) / 10
        line(ax, [(x + d, y - 19), (x + d, y)], color=color, lw=2)
        line(ax, [(x + d, y + h), (x + d, y + h + 19)], color=color, lw=2)


def document(ax, x, y, w=115, h=135):
    line(ax, [(x, y), (x + w - 26, y), (x + w, y + 26), (x + w, y + h), (x, y + h), (x, y)], lw=2)
    line(ax, [(x + w - 26, y), (x + w - 26, y + 26), (x + w, y + 26)], lw=1.3)
    for offset in (52, 74, 96):
        line(ax, [(x + 20, y + offset), (x + w - 20, y + offset)], color="muted", lw=1.2)


def person(ax, x, y):
    circle(ax, x, y, 26)
    line(ax, [(x, y + 26), (x, y + 108)], lw=2.5)
    line(ax, [(x - 55, y + 70), (x, y + 44), (x + 55, y + 70)], lw=2.5)
    line(ax, [(x - 42, y + 155), (x, y + 108), (x + 42, y + 155)], lw=2.5)


def node(ax, x, y, w, h, name, detail="", accent=False, dashed=False):
    rect(ax, x, y, w, h, edge="accent" if accent else "ink", dashed=dashed)
    text(
        ax, x + 24, y + 23, name, size=27, weight="bold", color=C["accent"] if accent else C["ink"], bounds=(x + 12, y + 8, w - 24, h - 16)
    )
    if detail:
        text(ax, x + 24, y + 78, detail, size=19, color=C["muted"], bounds=(x + 12, y + 8, w - 24, h - 16))


def make_slides():
    ax = slide("01-konzept", "Das Problem")
    text(ax, 75, 140, "E-204", size=105, weight="bold", mono=True, color=C["accent"])
    text(ax, 80, 310, "Ruhestrom zu hoch.", size=35)
    text(ax, 80, 530, "Gerät defekt?", size=38, weight="bold")
    text(ax, 80, 610, "Prüfung ungültig?", size=38, weight="bold")
    chip(ax, 1060, 200, 250, 195, color="accent")
    text(ax, 1185, 263, "ECU", size=30, weight="bold", mono=True, color=C["accent"], ha="center")
    text(ax, 1035, 470, "483 µA", size=49, mono=True)
    text(ax, 1040, 550, "Limit: 450 µA", size=22, color=C["muted"])
    text(ax, 1040, 650, "T1: 35 °C", size=30, mono=True)
    text(ax, 1040, 709, "gültig: 18–32 °C", size=22, color=C["muted"])
    text(ax, 80, 765, "Illustratives Beispiel · Variante B", size=16, color=C["muted"])

    ax = slide("02-systemkontext", "Kontext", "Systemkontext")
    chip(ax, 160, 285, 130, 100)
    text(ax, 225, 425, "Prüfdaten", size=25, ha="center")
    document(ax, 170, 570, 110, 125)
    text(ax, 225, 730, "Dokumente", size=25, ha="center")
    circle(ax, 790, 485, 125, edge="accent", lw=2.5)
    text(ax, 790, 465, "Copilot", size=39, weight="bold", ha="center", color=C["accent"])
    person(ax, 1360, 355)
    text(ax, 1360, 565, "Prüfingenieur", size=25, ha="center")
    arrow(ax, (350, 350), (680, 430))
    arrow(ax, (350, 640), (680, 545))
    arrow(ax, (1240, 415), (915, 445))
    text(ax, 1078, 365, "Frage", size=22, ha="center")
    arrow(ax, (915, 525), (1240, 525), color="accent")
    text(ax, 1078, 552, "Befund + Belege", size=22, ha="center")
    text(ax, 790, 725, "LLM-Anbieter", size=22, ha="center")
    arrow(ax, (790, 610), (790, 695), both=True, dashed=True)

    ax = slide("03-laufzeitarchitektur", "Software", "Was läuft wo?")
    rect(ax, 75, 225, 1090, 555, fill="soft", edge="line", lw=1)
    text(ax, 100, 247, "LOKAL", size=14, color=C["muted"], mono=True)
    node(ax, 125, 305, 960, 110, "Browser", "Dashboard")
    node(ax, 125, 515, 360, 145, "Twin", ":8001 · Simulator")
    node(ax, 650, 515, 435, 145, "Copilot", ":8000 · Agent / Tools / RAG", accent=True)
    arrow(ax, (300, 415), (300, 515), both=True)
    text(ax, 322, 448, "REST / SSE", size=16, color=C["muted"])
    arrow(ax, (855, 415), (855, 515), both=True)
    text(ax, 880, 448, "/ask", size=17, mono=True)
    arrow(ax, (650, 585), (485, 585), both=True)
    node(ax, 1245, 515, 280, 145, "LLM API", "extern", dashed=True)
    arrow(ax, (1085, 585), (1245, 585), both=True, color="accent")
    text(ax, 125, 720, "Dokumente / Index / Protokoll", size=20, color=C["muted"])
    text(ax, 650, 720, "Jaeger ← Traces", size=20, color=C["muted"])

    ax = slide("04-datenfluss", "Daten", "Der Datenfluss")
    text(ax, 80, 320, "Messwerte", size=28, weight="bold")
    text(ax, 80, 580, "Dokumente", size=28, weight="bold")
    text(ax, 440, 320, "Analyse", size=28, weight="bold")
    text(ax, 440, 374, "Gültigkeit / Trend / Cluster", size=17, color=C["muted"])
    text(ax, 440, 580, "Suche", size=28, weight="bold")
    text(ax, 440, 634, "Passende Abschnitte", size=18, color=C["muted"])
    arrow(ax, (315, 348), (420, 348))
    arrow(ax, (315, 608), (420, 608))
    line(ax, [(600, 348), (730, 348), (730, 473)])
    line(ax, [(565, 608), (730, 608), (730, 473)])
    arrow(ax, (730, 473), (840, 473))
    circle(ax, 930, 473, 88, edge="accent", lw=2.5)
    text(ax, 930, 448, "Agent", size=31, weight="bold", ha="center", color=C["accent"])
    arrow(ax, (1020, 473), (1095, 473), color="accent")
    text(ax, 1190, 430, "Belege\nprüfen", size=25, weight="bold", ha="center")
    arrow(ax, (1295, 473), (1360, 473))
    document(ax, 1390, 408, 110, 125)
    text(ax, 1445, 578, "Report", size=24, ha="center")

    ax = slide("05-untersuchungsablauf", "Ablauf", "Eine Untersuchung")
    lanes = [(170, "Dashboard"), (600, "Copilot"), (1010, "Werkzeuge"), (1400, "LLM")]
    for x, name in lanes:
        text(ax, x, 250, name, size=25, weight="bold", ha="center")
        line(ax, [(x, 310), (x, 780)], color="line", lw=1, dashed=True)
    for y, start, end, label, both, tone in [
        (345, 170, 600, "Frage", False, "ink"),
        (425, 600, 1400, "Tool wählen", True, "accent"),
        (505, 600, 1010, "Daten lesen", True, "ink"),
        (620, 600, 1400, "Report", True, "accent"),
        (750, 600, 170, "Befund + Belege", False, "ink"),
    ]:
        arrow(ax, (start, y), (end, y), color=tone, both=both)
        text(ax, (start + end) / 2, y - 38, label, size=21, ha="center")
    line(ax, [(600, 644), (655, 644), (655, 690)])
    arrow(ax, (655, 690), (600, 690))
    text(ax, 690, 649, "Belege prüfen", size=21)
    text(ax, 1010, 540, "bei Bedarf wiederholen", size=16, color=C["muted"], ha="center")

    ax = slide("06-belege-und-grenzen", "Einordnung", "Quelle gefunden. Ursache offen.", dark=True)
    text(ax, 80, 265, "WERKZEUGERGEBNIS", size=15, color=C["muted"], mono=True)
    text(ax, 80, 340, "483 µA", size=69, mono=True, color=C["white"])
    text(ax, 80, 465, "Wert nachvollziehbar", size=27, color=C["white"])
    text(ax, 750, 365, "≠", size=65, color=C["accent"], ha="center")
    text(ax, 940, 265, "HYPOTHESE", size=15, color=C["muted"], mono=True)
    text(ax, 940, 350, "Temperatur?", size=42, weight="bold", color=C["white"])
    text(ax, 940, 465, "Gegenprüfung nötig", size=27, color=C["white"])
    text(ax, 80, 680, "Ungültige Prüfung ≠ gesundes Bauteil.", size=34, color=C["white"])
    text(ax, 80, 760, "Illustratives Beispiel", size=15, color=C["muted"])

    ax = slide("07-benchmark", "Evaluation", "Ein Datenstand. Vier Systeme.")
    rect(ax, 660, 260, 280, 90, fill="soft", edge="line")
    text(ax, 800, 283, "Snapshot", size=27, weight="bold", ha="center")
    line(ax, [(800, 350), (800, 420)])
    line(ax, [(230, 420), (1370, 420)])
    for x, name, detail in [(230, "B0", "Regeln"), (610, "B1", "Chatbot"), (990, "V1S", "Agent"), (1370, "V2", "Agent + Analyse")]:
        arrow(ax, (x, 420), (x, 500))
        text(ax, x, 525, name, size=45, mono=True, weight="bold", ha="center", color=C["accent"] if name == "V2" else C["ink"])
        text(ax, x, 605, detail, size=23, ha="center")
        line(ax, [(x, 660), (x, 700)], color="line")
    line(ax, [(230, 700), (1370, 700)], color="line")
    text(ax, 800, 748, "Korrektheit / Zusatzbehauptungen / Zeit / Kosten", size=25, ha="center")
    text(ax, 800, 204, "3 Wiederholungen je System und Szenario", size=17, color=C["muted"], ha="center")

    ax = slide("08-stand-und-demo", "Demo", "Jetzt im Dashboard")
    labels = [(150, "Prüfung"), (475, "Vorgabe"), (800, "Frage"), (1125, "Belege"), (1450, "Entscheidung")]
    line(ax, [(150, 445), (1450, 445)], color="line", lw=2)
    for i, (x, label) in enumerate(labels):
        circle(ax, x, 445, 39, edge="accent" if i == 2 else "ink", lw=2)
        text(ax, x, 426, str(i + 1), size=25, mono=True, ha="center", color=C["accent"] if i == 2 else C["ink"])
        text(ax, x, 530, label, size=25, weight="bold", ha="center")
    text(ax, 80, 710, "Entscheidung wird protokolliert.", size=26)
    text(ax, 80, 765, "Re-Test derselben Einheit: noch offen.", size=20, color=C["muted"])

    ax = slide("09-forschung", "Quellen", "Literatur")
    for y, name, bibliographic, url in [
        (255, "CausalPulse", "Shyalika et al. / 2026 / arXiv:2603.29755", "https://arxiv.org/html/2603.29755"),
        (420, "Industrial Test-Failure Analysis", "Jansson et al. / 2026 / arXiv:2609.21843", "https://arxiv.org/html/2609.21843v1"),
        (585, "Automotive HiL + CI", "Abboush et al. / 2025 / Scientific Reports", "https://www.nature.com/articles/s41598-025-21416-5"),
    ]:
        text(ax, 80, y, name, size=32, weight="bold", url=url)
        text(ax, 82, y + 64, bibliographic, size=20, color=C["muted"])
    text(ax, 80, 765, "Vollständige Quellen: RECHERCHE.md", size=18, color=C["muted"])


def verify_layout():
    failures = []
    figures = {id(fig): fig for fig, _, _ in PLACEMENTS}
    for fig in figures.values():
        fig.canvas.draw()
    for fig, obj, bounds in PLACEMENTS:
        extent = obj.get_window_extent(fig.canvas.get_renderer())
        x0, y1, x1, y0 = extent.x0, 900 - extent.y0, extent.x1, 900 - extent.y1
        if x0 < -1 or x1 > 1601 or y0 < -1 or y1 > 901:
            failures.append(f"Canvas overflow: {obj.get_text()[:75]}")
        if bounds:
            x, y, w, h = bounds
            if x0 < x - 2 or x1 > x + w + 2 or y0 < y - 2 or y1 > y + h + 2:
                failures.append(f"Card overflow: {obj.get_text()[:90]} ({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}) vs {bounds}")
    if failures:
        raise RuntimeError("\n".join(failures))


def export():
    OUT.mkdir(parents=True, exist_ok=True)
    DIAGRAMS.mkdir(exist_ok=True)
    make_slides()
    verify_layout()
    with PdfPages(OUT / "ECU-Copilot-Praesentation.pdf") as pdf:
        pdf.infodict().update(
            {
                "Title": "ECU Copilot – Architektur und Datenfluss",
                "Author": "Morteza Molaei",
                "Subject": "Implementierter Prototyp, synthetische Daten, 17.10.2026",
            }
        )
        for item in SLIDES:
            fig, slug = item["fig"], item["slug"]
            fig.savefig(DIAGRAMS / f"{slug}.svg", facecolor=fig.get_facecolor(), metadata={"Title": item["title"]})
            fig.savefig(DIAGRAMS / f"{slug}.png", dpi=150, facecolor=fig.get_facecolor())
            pdf.savefig(fig, facecolor=fig.get_facecolor())
    paths = [
        "docker-compose.yml",
        "src/ecu_copilot/copilot/api.py",
        "src/ecu_copilot/copilot/agent.py",
        "src/ecu_copilot/copilot/tools.py",
        "src/ecu_copilot/copilot/verify.py",
        "src/ecu_copilot/copilot/twin_client.py",
        "src/ecu_copilot/copilot/static/index.html",
        "src/ecu_copilot/config.py",
        "src/ecu_copilot/twin/api.py",
        "src/ecu_copilot/twin/models.py",
        "src/ecu_copilot/twin/simulator.py",
        "src/ecu_copilot/rag/index.py",
        "src/ecu_copilot/rag/chunking.py",
        "evals/bench.py",
        "evals/baselines.py",
        "src/ecu_copilot/engineering/validity.py",
        "src/ecu_copilot/engineering/change.py",
        "src/ecu_copilot/engineering/cluster.py",
        "src/ecu_copilot/engineering/describe.py",
        "src/ecu_copilot/engineering/spec.py",
        "docs/spec/TS-DCU-EOL.json",
    ]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    manifest = {
        "presentation_date": "2026-10-17",
        "code_head_at_export": commit,
        "code_source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
        "slides": [{k: v for k, v in item.items() if k != "fig"} for item in SLIDES],
        "scope": "Architecture presentation only; no claim to independently validated production performance.",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    thumbs = [plt.imread(DIAGRAMS / f"{item['slug']}.png") for item in SLIDES]
    contact, axes = plt.subplots(3, 3, figsize=(24, 13.5), facecolor=C["bg"])
    for ax, thumb in zip(axes.flat, thumbs, strict=True):
        ax.imshow(thumb)
        ax.axis("off")
    contact.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01, wspace=0.025, hspace=0.025)
    contact.savefig(OUT / "Uebersicht.png", dpi=100)
    plt.close("all")
    print(f"Exported {len(SLIDES)} slides as PDF + SVG/PNG; text bounds checked; source hashes recorded.")


if __name__ == "__main__":
    export()
