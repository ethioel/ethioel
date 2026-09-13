#!/usr/bin/env python3
"""robo_walk.py — animated robot sweeping the GitHub contribution grid.
it generates dist/robot-dark.svg and dist/robot-light.svg."""

import json
import os
import urllib.request

CYCLE = 24                    # seconds for one full sweep
CELL, GAP, PAD = 12, 3, 6     # grid geometry (px)

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


def visit_order(rows, cols):
    """Serpentine path: down col 0, up col 1, down col 2 ..."""
    return [
        (c, r)
        for c in range(cols)
        for r in (range(rows) if c % 2 == 0 else reversed(range(rows)))
    ]


def level(n):
    return 0 if n == 0 else 1 if n <= 3 else 2 if n <= 7 else 3 if n <= 12 else 4


BOT = (
    '<g>'
    '<animateMotion dur="{d}s" repeatCount="indefinite" calcMode="paced" path="{p}"/>'
    '<line x1="0" y1="-13" x2="0" y2="-9" stroke="#9CA3AF" stroke-width="2"/>'
    '<circle cx="0" cy="-14.5" r="1.8" fill="{e}"/>'
    '<rect x="-8" y="-9" width="16" height="12" rx="3.5" fill="#D1D5DB" stroke="#6B7280"/>'
    '<circle cx="-3.2" cy="-3.4" r="1.7" fill="{e}"/>'
    '<circle cx="3.2" cy="-3.4" r="1.7" fill="{e}"/>'
    '<rect x="-4.5" y="3" width="9" height="7" rx="2" fill="#6B7280"/>'
    '</g>'
)


def build(weeks, palette):
    rows, cols = 7, len(weeks)
    order = visit_order(rows, cols)
    total = len(order) - 1
    cx = lambda c: PAD + c * (CELL + GAP) + CELL / 2
    cy = lambda r: PAD + r * (CELL + GAP) + CELL / 2
    path = "M " + " L ".join(f"{cx(c):g} {cy(r):g}" for c, r in order)

    cells = []
    for c, week in enumerate(weeks):
        for r, day in enumerate(week["contributionDays"]):
            x, y = PAD + c * (CELL + GAP), PAD + r * (CELL + GAP)
            anim = ""
            if day["contributionCount"]:
                t1 = order.index((c, r)) / total
                t2 = min(t1 + 0.008, 0.999)
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
        f'{BOT.format(d=CYCLE, p=path, e=EYE)}</svg>'
    )


if __name__ == "__main__":
    weeks = fetch_weeks()
    os.makedirs("dist", exist_ok=True)
    open("dist/robot-dark.svg", "w").write(build(weeks, DARK))
    open("dist/robot-light.svg", "w").write(build(weeks, LIGHT))
    print(f"ok - {len(weeks)} weeks -> dist/robot-dark.svg, dist/robot-light.svg")
