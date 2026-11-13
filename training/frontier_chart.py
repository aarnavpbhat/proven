"""Draw docs/frontier.svg: claims decided against wrong claims shown, local pools and Sonnet.

    python training/frontier_chart.py > docs/frontier.svg

The numbers are the measured-suite rows of docs/finetune.md sections 8b and 8c (continued 14B
term model): for each tier, six local configurations from 8 terms to about 50, and Sonnet.
No dependency; the figure is plain SVG so it renders on GitHub.
"""
from __future__ import annotations

from html import escape

CONFIGS = ["14B greedy, 8 terms", "14B + 3B pools, two agree (~13 terms)", "three-model pool, two agree (~17 terms)",
           "14B pool (~25 terms)", "14B + 3B pools (~40 terms)", "three-model pool (~50 terms)"]
# tier: (wrong claims in the measured halves, [(wrong shown, decided %)] per config, Sonnet (wrong shown, decided %))
TIERS = {
    "Unseen, held-out": (330, [(33, 61.9), (47, 70.2), (54, 73.9), (71, 76.5), (79, 79.1), (89, 81.0)], (40, 81.7)),
    "Unseen, paraphrase": (330, [(42, 49.2), (54, 55.4), (62, 59.9), (74, 61.7), (87, 64.2), (99, 68.2)], (39, 63.3)),
    "Sealed, held-out": (270, [(32, 59.5), (38, 72.8), (43, 76.7), (51, 77.0), (64, 80.8), (71, 84.4)], (35, 80.5)),
    "Sealed, paraphrase": (270, [(26, 49.5), (38, 58.3), (45, 62.5), (52, 63.7), (63, 66.9), (71, 69.6)], (29, 62.2)),
}
LOCAL, SONNET, INK, MUTED, GRID, SURFACE = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
PW, PH, GAP, LEFT, TOP, ROW = 280, 190, 40, 58, 124, 262
X0, X1, Y0, Y1 = 5.0, 35.0, 45.0, 90.0


def main() -> None:
    width = LEFT + 2 * PW + GAP + 24
    height = TOP + ROW + PH + 52
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
           f'font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif" role="img" '
           f'aria-label="Claims decided against wrong claims shown to the reviewer, local pools and Claude Sonnet">',
           f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>',
           f'<text x="{LEFT}" y="28" font-size="16" font-weight="600" fill="{INK}">A wider net decides more claims and '
           f'shows the reviewer more wrong ones</text>',
           f'<text x="{LEFT}" y="48" font-size="12" fill="{MUTED}">Each blue point is one local configuration, from 8 search '
           f'terms a claim (left) to about 50 (right).</text>',
           f'<text x="{LEFT}" y="64" font-size="12" fill="{MUTED}">Up is better, left is cheaper for the reviewer. '
           f'No unsafe result at any point.</text>',
           f'<circle cx="{LEFT + 5}" cy="84" r="5" fill="{LOCAL}"/><text x="{LEFT + 16}" y="88" font-size="12" fill="{INK}">'
           f'Fine-tuned local models (3B copy + 14B/3B term models)</text>',
           f'<rect x="{LEFT + 346}" y="79" width="10" height="10" fill="{SONNET}" transform="rotate(45 {LEFT + 351} 84)"/>'
           f'<text x="{LEFT + 364}" y="88" font-size="12" fill="{INK}">Claude Sonnet 5.5 (up to 8 terms)</text>']
    for i, (tier, (total, points, sonnet)) in enumerate(TIERS.items()):
        ox, oy = LEFT + (i % 2) * (PW + GAP), TOP + (i // 2) * ROW

        def sx(wrong: float) -> float:
            return ox + (100 * wrong / total - X0) / (X1 - X0) * PW

        def sy(decided: float) -> float:
            return oy + PH - (decided - Y0) / (Y1 - Y0) * PH

        out.append(f'<text x="{ox}" y="{oy - 10}" font-size="12" font-weight="600" fill="{INK}">{escape(tier)}</text>')
        for tick in range(50, 91, 10):
            y = sy(tick)
            out.append(f'<line x1="{ox}" x2="{ox + PW}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
            if i % 2 == 0:
                out.append(f'<text x="{ox - 8}" y="{y + 4:.1f}" font-size="11" text-anchor="end" fill="{MUTED}">{tick}%</text>')
        for tick in range(10, 31, 10):
            x = ox + (tick - X0) / (X1 - X0) * PW
            out.append(f'<text x="{x:.1f}" y="{oy + PH + 16}" font-size="11" text-anchor="middle" fill="{MUTED}">{tick}%</text>')
        out.append(f'<line x1="{ox}" x2="{ox + PW}" y1="{oy + PH}" y2="{oy + PH}" stroke="{MUTED}"/>')
        path = " ".join(f"{'M' if j == 0 else 'L'}{sx(w):.1f},{sy(d):.1f}" for j, (w, d) in enumerate(points))
        out.append(f'<path d="{path}" fill="none" stroke="{LOCAL}" stroke-width="2"/>')
        for name, (w, d) in zip(CONFIGS, points):
            out.append(f'<circle cx="{sx(w):.1f}" cy="{sy(d):.1f}" r="4.5" fill="{LOCAL}" stroke="{SURFACE}" stroke-width="2">'
                       f'<title>{escape(name)}: {d}% decided, {w} of {total} wrong claims shown</title></circle>')
        w, d = points[0]
        out.append(f'<text x="{sx(w) + 9:.1f}" y="{sy(d) + 4:.1f}" font-size="11" fill="{MUTED}">8 terms: {d}%</text>')
        w, d = points[-1]
        out.append(f'<text x="{sx(w):.1f}" y="{sy(d) - 10:.1f}" font-size="11" text-anchor="end" fill="{INK}">~50 terms: {d}%</text>')
        w, d = sonnet
        x, y = sx(w), sy(d)
        out.append(f'<rect x="{x - 5:.1f}" y="{y - 5:.1f}" width="10" height="10" fill="{SONNET}" stroke="{SURFACE}" stroke-width="2" '
                   f'transform="rotate(45 {x:.1f} {y:.1f})"><title>Claude Sonnet 5.5: {d}% decided, {w} of {total} wrong claims '
                   f'shown</title></rect>')
        out.append(f'<text x="{x:.1f}" y="{y - 11:.1f}" font-size="11" text-anchor="middle" fill="{INK}">Sonnet {d}%</text>')
    mid = TOP + (ROW + PH) / 2
    out.append(f'<text x="{LEFT - 44}" y="{mid}" font-size="11" fill="{MUTED}" text-anchor="middle" '
               f'transform="rotate(-90 {LEFT - 44} {mid})">claims decided, fully taught</text>')
    out.append(f'<text x="{LEFT + (2 * PW + GAP) / 2}" y="{TOP + ROW + PH + 38}" font-size="11" fill="{MUTED}" text-anchor="middle">'
               f'wrong claims shown to the reviewer as supported (share of all wrong claims)</text>')
    out.append("</svg>")
    print("\n".join(out))


if __name__ == "__main__":
    main()
