#!/usr/bin/env python3
"""robo_walk.py — robot roams the contribution grid like a rover.
Generates dist/robot-dark.svg and dist/robot-light.svg."""

import json
import os
import random
import urllib.request

CYCLE   = 24        # seconds per full sweep (lower = faster)
CELL    = 12        # cell size (px)
GAP     = 3         # gap between cells (px)
PAD     = 6         # outer padding (px)
SAMPLES = 10        # bezier samples per segment for arclength
SEED    = 42        # fixed seed -> stable organic path
JITTER  = 1.8       # waypoint jitter in px (organic look)

DARK  = ["#161B22", "#2A2140", "#423066", "#5F4490", "#7D52AD"]
LIGHT = ["#EBEDF0", "#E7DEF4", "#CFBAEC", "#AA88D6", "#7D52AD"]
EYE   = "#7D52AD"

USER  = os.environ["GITHUB_REPOSITORY_OWNER"]
TOKEN = os.environ.get("GH_PAT") or os.environ["GITHUB_TOKEN"]

QUERY = """query($u:String!){
  user(login:$u){
    contributionsCollection{
      contributionCalendar{ weeks{ contributionDays{ contributionCount } } }
    }
  }
}"""


def fetch_weeks():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"u": USER}}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "robo-walk"},
    )
    with urllib.request.urlopen(req) as res:
        body = json.load(res)
    return body["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]


def make_path(rows, cols, rng):
    """Boustrophedon waypoints with organic jitter.
    Returns: [(cell, (x, y)), ...] — every cell exactly once."""
    pts = []
    for r in range(rows):
        col_range = range(cols) if r % 2 == 0 else reversed(range(cols))
        for c in col_range:
            x = PAD + c * (CELL + GAP) + CELL / 2 + rng.uniform(-JITTER, JITTER)
            y = PAD + r * (CELL + GAP) + CELL / 2 + rng.uniform(-JITTER, JITTER)
            pts.append(((c, r), (x, y)))
    return pts


def catmull_rom_curves(points):
    """Control points -> cubic bezier segments (smooth through all points)."""
    curves = []
    p = [q for _, q in points]
    n = len(p)
    for i in range(n - 1):
        p0 = p[i - 1] if i > 0 else p[i]
        p1, p2 = p[i], p[i + 1]
        p3 = p[i + 2] if i + 2 < n else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        curves.append((p1, c1, c2, p2))
    return curves


def bez(p0, c1, c2, p1, t):
    mt = 1 - t
    return (
        mt**3 * p0[0] + 3 * mt**2 * t * c1[0] + 3 * mt * t**2 * c2[0] + t**3 * p1[0],
        mt**3 * p0[1] + 3 * mt**2 * t * c1[1] + 3 * mt * t**2 * c2[1] + t**3 * p1[1],
    )


def path_data_and_fractions(points):
    """SVG path string + arclength fraction at each waypoint
    (constant-speed timeline so fades match the glide exactly)."""
    curves = catmull_rom_curves(points)
    d = f"M {points[0][1][0]:.1f} {points[0][1][1]:.1f} " + " ".join(
        f"C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p1[0]:.1f} {p1[1]:.1f}"
        for _, c1, c2, p1 in curves
    )
    fracs, acc = [0.0], 0.0
    for p0, c1, c2, p1 in curves:
        prev = p0
        for s in range(1, SAMPLES + 1):
            cur = bez(p0, c1, c2, p1, s / SAMPLES)
            acc += ((cur[0] - prev[0]) ** 2 + (cur[1] - prev[1]) ** 2) ** 0.5
            prev = cur
        fracs.append(acc)
    total = fracs[-1]
    return d, [f / total for f in fracs]


def level(n):
    return 0 if n == 0 else 1 if n <= 3 else 2 if n <= 7 else 3 if n <= 12 else 4

BOT = (
    '<g>'
    '<animateMotion dur="{d}s" repeatCount="indefinite" calcMode="paced" '
    'rotate="auto" path="{p}"/>'
    '<animateTransform attributeName="transform" additive="sum" type="translate" '
    'values="0 0; 0 -1; 0 0" dur="1.4s" repeatCount="indefinite"/>'
    '<line x1="7" y1="0" x2="11" y2="0" stroke="#9CA3AF" stroke-width="2"/>'
    '<circle cx="12.5" cy="0" r="1.8" fill="{e}"/>'
    '<rect x="-10" y="-4.5" width="6" height="9" rx="2" fill="#6B7280"/>'
    '<rect x="-7" y="-8" width="14" height="16" rx="4" fill="#D1D5DB" stroke="#6B7280"/>'
    '<circle cx="3.4" cy="-3.4" r="1.7" fill="{e}"/>'
    '<circle cx="3.4" cy="3.4" r="1.7" fill="{e}"/>'
    '</g>'
)


def build(weeks, palette, rng):
    rows, cols = 7, len(weeks)
    points = make_path(rows, cols, rng)
    d, fracs = path_data_and_fractions(points)
    cell_index = {cell: i for i, (cell, _) in enumerate(points)}

    cells = []
    for c, week in enumerate(weeks):
        for r, day in enumerate(week["contributionDays"]):
            x, y = PAD + c * (CELL + GAP), PAD + r * (CELL + GAP)
            anim = ""
            if day["contributionCount"]:
                t1 = fracs[cell_index[(c, r)]]
                t2 = min(t1 + 0.01, 0.999)
                anim = (
                    f'<animate attributeName="opacity" values="1;1;0;0" '
                    f'keyTimes="0;{t1:.4f};{t2:.4f};1" '
                    f'dur="{CYCLE}s" repeatCount="indefinite"/>'
                )
            cells.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
                f'rx="2.5" fill="{palette[level(day["contributionCount"])]}">{anim}</rect>'
            )

    w = PAD * 2 + cols * (CELL + GAP) - GAP
    h = PAD * 2 + rows * (CELL + GAP) - GAP
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{"".join(cells)}'
        f'{BOT.format(d=CYCLE, p=d, e=EYE)}</svg>'
    )


if __name__ == "__main__":
    weeks = fetch_weeks()
    os.makedirs("dist", exist_ok=True)
    open("dist/robot-dark.svg", "w").write(build(weeks, DARK, random.Random(SEED)))
    open("dist/robot-light.svg", "w").write(build(weeks, LIGHT, random.Random(SEED)))
    print(f"ok - {len(weeks)} weeks -> dist/robot-dark.svg, dist/robot-light.svg")
