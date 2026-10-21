"""Genera las tarjetas SVG del perfil (cabecera, ciudad de contribuciones y lenguajes).

Uso:
    GH_TOKEN=... python scripts/generate.py      # datos reales desde la API de GitHub
    python scripts/generate.py --demo            # datos de ejemplo, sin red salvo el avatar
"""
import datetime as dt
import io
import json
import os
import random
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CONFIG = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
ACCENT = CONFIG.get("accent", "#3ddc97")

SANS = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"
BG_TOP, BG_BOTTOM, BORDER = "#0e1528", "#0a0f1e", "#22304f"
MUTED, TEXT = "#8b98b8", "#e6edf7"
GREENS = ["#1b2a3d", "#0e4f3a", "#13795a", "#1fae7d", ACCENT]

QUERY = """
query($login: String!) {
  user(login: $login) {
    name login avatarUrl(size: 200)
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, first: 100, isFork: false) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
  }
}
"""


def fetch(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def load_live(token):
    body = json.dumps({"query": QUERY, "variables": {"login": CONFIG["login"]}}).encode()
    res = json.loads(fetch("https://api.github.com/graphql", body,
                           {"Authorization": f"bearer {token}", "Content-Type": "application/json"}))
    if "errors" in res:
        sys.exit(f"Error de la API de GitHub: {res['errors']}")
    u = res["data"]["user"]
    langs = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            color = e["node"]["color"] or "#8b98b8"
            langs.setdefault(name, [name, color, 0])[2] += e["size"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    if not CONFIG.get("name"):
        CONFIG["name"] = u["name"] or u["login"]
    return {
        "repos": u["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "followers": u["followers"]["totalCount"],
        "languages": sorted(langs.values(), key=lambda x: -x[2]),
        "days": days,
        "avatar": u["avatarUrl"],
    }


def load_demo():
    CONFIG["name"] = CONFIG.get("name") or CONFIG["login"]
    data = json.loads((ROOT / "scripts" / "demo.json").read_text(encoding="utf-8"))
    rnd = random.Random(20)
    start = dt.date.today() - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)  # el calendario de GitHub empieza en domingo
    days, streak = [], 0
    for i in range((dt.date.today() - start).days + 1):
        d = start + dt.timedelta(days=i)
        busy = 0.35 + 0.45 * (i / 365)  # más actividad en los últimos meses
        streak = streak + 1 if rnd.random() < busy else 0
        n = 0 if streak == 0 else rnd.choice([1, 2, 3, 4, 6, 8]) + min(streak, 6)
        days.append((d.isoformat(), n))
    data["days"] = days
    data["avatar"] = f"https://avatars.githubusercontent.com/{CONFIG['login']}?s=200"
    return data


def card(width, height, inner, extra_style=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{BG_TOP}"/><stop offset="1" stop-color="{BG_BOTTOM}"/>
  </linearGradient>
  <style>
    .sans {{ font-family: {SANS}; }}
    .mono {{ font-family: {MONO}; }}
    @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    .fade {{ animation: fade .8s ease-out both; }}
    {extra_style}
  </style>
</defs>
<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="18" fill="url(#bg)" stroke="{BORDER}" stroke-width="2"/>
{inner}
</svg>
"""


# Iconos sencillos de 14x14, dibujados a partir de (0, 0)
ICONS = {
    "repo": '<rect x="1.5" y="1" width="11" height="12" rx="2" fill="none" stroke="{c}" stroke-width="1.6"/>'
            '<line x1="4.5" y1="1" x2="4.5" y2="13" stroke="{c}" stroke-width="1.6"/>',
    "star": '<polygon points="7,0.8 8.9,4.9 13.3,5.3 10,8.3 11,12.7 7,10.4 3,12.7 4,8.3 0.7,5.3 5.1,4.9" '
            'fill="none" stroke="{c}" stroke-width="1.5" stroke-linejoin="round"/>',
    "commit": '<circle cx="7" cy="7" r="3.2" fill="none" stroke="{c}" stroke-width="1.6"/>'
              '<line x1="0" y1="7" x2="3.8" y2="7" stroke="{c}" stroke-width="1.6"/>'
              '<line x1="10.2" y1="7" x2="14" y2="7" stroke="{c}" stroke-width="1.6"/>',
    "people": '<circle cx="5" cy="4.5" r="2.6" fill="none" stroke="{c}" stroke-width="1.5"/>'
              '<path d="M0.8 13c0-2.6 1.9-4.4 4.2-4.4s4.2 1.8 4.2 4.4" fill="none" stroke="{c}" stroke-width="1.5"/>'
              '<circle cx="10.5" cy="5" r="2" fill="none" stroke="{c}" stroke-width="1.4"/>'
              '<path d="M10.5 8.8c1.6 0 2.8 1.4 2.8 3.6" fill="none" stroke="{c}" stroke-width="1.4"/>',
}


# Gatitos pixel art. X = pelo, E = ojos, N = nariz, P = interior de las orejas, C = ojos cerrados
CAT_COLORS = {"X": "#ece9f7", "E": ACCENT, "N": "#ff8fb1", "P": "#ffb3c9", "C": "#2b3150"}
CAT_WALK = [
    [".........X...X..",
     ".........XP.PX..",
     ".X.......XXXXX..",
     "..X......XEXEX..",
     "...X.....XXNXX..",
     "...XXXXXXXXXXX..",
     "...XXXXXXXXXX...",
     "...XXXXXXXXXX...",
     "...X.X....X.X...",
     "...X.X....X.X..."],
    [".........X...X..",
     ".........XP.PX..",
     "..X......XXXXX..",
     "..X......XEXEX..",
     "...X.....XXNXX..",
     "...XXXXXXXXXXX..",
     "...XXXXXXXXXX...",
     "...XXXXXXXXXX...",
     "....XX....XX....",
     "....X......X...."],
]
CAT_SLEEP = [
    "..X...X.........",
    "..XP.PX.........",
    "..XXXXXXXXXXX...",
    ".XXCXCXXXXXXXX..",
    ".XXXNXXXXXXXXXX.",
    "..XXXXXXXXXXXXX.",
    "...XXXXXXXXXXXXX",
    ".....XXXXXXXXXX.",
]


def sprite(rows, x, y, px):
    out = []
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in CAT_COLORS:
                out.append(f'<rect x="{x + i * px:.1f}" y="{y + j * px:.1f}" width="{px}" height="{px}" '
                           f'fill="{CAT_COLORS[ch]}"/>')
    return "".join(out)


def paw(x, y, s, color):
    """Huella de gato centrada en (x, y) con tamaño s."""
    return (f'<g fill="{color}"><ellipse cx="{x}" cy="{y + s * .25}" rx="{s * .38}" ry="{s * .3}"/>'
            + "".join(f'<circle cx="{x + dx * s}" cy="{y + dy * s}" r="{s * .15}"/>'
                      for dx, dy in ((-.38, -.12), (-.14, -.38), (.14, -.38), (.38, -.12)))
            + '</g>')


def pixel_avatar(url, x, y, size, grid=46):
    try:
        img = Image.open(io.BytesIO(fetch(url))).convert("RGB").resize((grid, grid), Image.LANCZOS)
    except Exception as e:  # sin avatar la tarjeta sigue siendo válida
        print(f"Aviso: no se pudo descargar el avatar ({e})", file=sys.stderr)
        return ""
    step = size / grid
    r = grid / 2
    dots = []
    for j in range(grid):
        for i in range(grid):
            if (i + 0.5 - r) ** 2 + (j + 0.5 - r) ** 2 > (r - 0.6) ** 2:
                continue
            red, g, b = img.getpixel((i, j))
            # Los píxeles más luminosos se ven como puntos más grandes, como en una pantalla LED
            lum = (0.299 * red + 0.587 * g + 0.114 * b) / 255
            rad = step * (0.28 + 0.2 * lum)
            dots.append(f'<circle cx="{x + (i + .5) * step:.1f}" cy="{y + (j + .5) * step:.1f}" '
                        f'r="{rad:.2f}" fill="#{red:02x}{g:02x}{b:02x}"/>')
    scan = (f'<rect class="scan" x="{x}" y="{y}" width="{size}" height="6" fill="{ACCENT}" opacity=".25"/>')
    return (f'<clipPath id="av"><circle cx="{x + size / 2}" cy="{y + size / 2}" r="{size / 2}"/></clipPath>'
            f'<g class="fade">{"".join(dots)}</g><g clip-path="url(#av)">{scan}</g>'
            f'<circle cx="{x + size / 2}" cy="{y + size / 2}" r="{size / 2 + 6}" fill="none" '
            f'stroke="{ACCENT}" stroke-opacity=".35" stroke-width="1.5" stroke-dasharray="3 6"/>')


def header_svg(data):
    w, h = 900, 320
    total = sum(n for _, n in data["days"])
    rows = [("repo", f'{data["repos"]}', "repositorios"), ("star", f'{data["stars"]}', "estrellas"),
            ("commit", f"{total}", "contribuciones este año"), ("people", f'{data["followers"]}', "seguidores")]
    parts = [
        f'<text x="44" y="64" class="mono" font-size="15" fill="{ACCENT}">@{escape(CONFIG["login"])}  =^.^=</text>',
        f'<text x="44" y="112" class="sans" font-size="44" font-weight="700" fill="{TEXT}">{escape(CONFIG["name"])}</text>',
        f'<text x="44" y="142" class="sans" font-size="16" fill="{MUTED}">{escape(CONFIG["title"])}</text>',
    ]
    for k, (icon, num, label) in enumerate(rows):
        yy = 172 + k * 24
        parts.append(f'<g transform="translate(46 {yy - 11})">{ICONS[icon].format(c=ACCENT)}</g>'
                     f'<text x="70" y="{yy}" class="mono" font-size="14" fill="{TEXT}">'
                     f'<tspan font-weight="700">{num}</tspan><tspan fill="{MUTED}"> {label}</tspan></text>')
    px = 44
    for name, color, _ in data["languages"][:4]:
        pw = 34 + len(name) * 8
        parts.append(f'<g transform="translate({px} 272)"><rect width="{pw}" height="28" rx="14" fill="#141d33" '
                     f'stroke="{BORDER}"/><circle cx="16" cy="14" r="5" fill="{color}"/>'
                     f'<text x="27" y="18.5" class="mono" font-size="12" fill="{TEXT}">{escape(name)}</text></g>')
        px += pw + 10
    parts.append(pixel_avatar(data["avatar"], 610, 46, 240))
    style = "@keyframes scan { from { transform: translateY(0); } to { transform: translateY(254px); } } " \
            ".scan { animation: scan 4s linear infinite alternate; }"
    return card(w, h, "\n".join(parts), style)


def city_svg(data):
    w, h = 900, 315
    days = data["days"]
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)]
    counts = [n for _, n in days]
    peak = max(counts) or 1
    active = sum(1 for n in counts if n)
    busiest = max(days, key=lambda d: d[1])
    streak = best = 0
    for n in counts:
        streak = streak + 1 if n else 0
        best = max(best, streak)

    def level(n):
        if n == 0:
            return 0
        return min(4, 1 + int(3 * n / peak + 0.5))

    # Proyección isométrica: cada semana avanza un paso u y cada día un paso v
    ux, uy, vx, vy = 7.0, 2.3, -5.6, 3.6
    ox, oy = 480, 104
    bars = []
    for wi, week in enumerate(weeks):
        for di, (_, n) in enumerate(week):
            px, py = ox + wi * ux + di * vx, oy + wi * uy + di * vy
            hgt = 3 + (n / peak) * 80 if n else 1.5
            col = GREENS[level(n)]
            a = (px, py - hgt)
            b = (a[0] + ux, a[1] + uy)
            c = (b[0] + vx, b[1] + vy)
            d = (a[0] + vx, a[1] + vy)

            def pts(*ps):
                return " ".join(f"{x:.1f},{y:.1f}" for x, y in ps)

            down = lambda q: (q[0], q[1] + hgt)
            top = pts(a, b, c, d)
            left = pts(d, c, down(c), down(d))
            right = pts(b, c, down(c), down(b))
            delay = (wi + di) * 0.012
            bars.append((wi + di, f'<g class="bar" style="animation-delay:{delay:.2f}s">'
                                  f'<polygon points="{left}" fill="{col}" filter="url(#dk1)"/>'
                                  f'<polygon points="{right}" fill="{col}" filter="url(#dk2)"/>'
                                  f'<polygon points="{top}" fill="{col}"/></g>'))
    bars.sort(key=lambda b: b[0])
    fecha = dt.date.fromisoformat(busiest[0]).strftime("%d/%m")
    stats = [(f"{active}", "días activos"), (f"{best}", "racha más larga"), (f"{busiest[1]}", f"día récord ({fecha})")]
    parts = [
        f'<text x="40" y="58" class="sans" font-size="22" font-weight="700" fill="{TEXT}">La ciudad que construí este año 🐾</text>',
        f'<text x="40" y="104" class="mono" font-size="12" letter-spacing="2" fill="{ACCENT}">CONTRIBUCIONES</text>',
        f'<text x="40" y="150" class="mono" font-size="44" font-weight="700" fill="{TEXT}">{sum(counts)}</text>',
    ]
    for k, (num, label) in enumerate(stats):
        parts.append(f'<text x="40" y="{196 + k * 26}" class="mono" font-size="14" fill="{MUTED}">'
                     f'<tspan fill="{TEXT}" font-weight="700">{num}</tspan> {label}</text>')
    parts.append('<g>' + "".join(b for _, b in bars) + '</g>')
    # Huellas y un gato que cruza la tarjeta de lado a lado
    parts.append('<g opacity=".18">' + "".join(paw(60 + k * 46, 292 - (k % 2) * 7, 9, ACCENT) for k in range(18)) + '</g>')
    parts.append('<g class="walk">'
                 f'<g class="f0">{sprite(CAT_WALK[0], 0, 0, 3)}</g>'
                 f'<g class="f1">{sprite(CAT_WALK[1], 0, 0, 3)}</g></g>')
    defs = ('<filter id="dk1"><feComponentTransfer><feFuncR type="linear" slope=".55"/><feFuncG type="linear" slope=".55"/>'
            '<feFuncB type="linear" slope=".55"/></feComponentTransfer></filter>'
            '<filter id="dk2"><feComponentTransfer><feFuncR type="linear" slope=".75"/><feFuncG type="linear" slope=".75"/>'
            '<feFuncB type="linear" slope=".75"/></feComponentTransfer></filter>')
    style = ("@keyframes rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } } "
             ".bar { animation: rise .5s ease-out both; } "
             "@keyframes walk { from { transform: translate(-60px, 262px); } to { transform: translate(900px, 262px); } } "
             ".walk { animation: walk 14s linear infinite; } "
             "@keyframes step { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } } "
             ".f0 { animation: step .5s infinite; } .f1 { animation: step .5s infinite reverse; }")
    return card(w, h, defs + "\n".join(parts), style)


def stack_svg(data):
    langs = data["languages"]
    total = sum(s for _, _, s in langs) or 1
    top = langs[:6]
    w, h = 900, 110 + len(top) * 34
    parts = [
        f'<text x="40" y="52" class="sans" font-size="22" font-weight="700" fill="{TEXT}">Lenguajes</text>',
        f'<text x="40" y="76" class="mono" font-size="12" fill="{ACCENT}">ponderado por tamaño de código en mis repos</text>',
        sprite(CAT_SLEEP, w - 120, 38, 4.5),
        f'<g class="mono" fill="{MUTED}" font-size="13"><text class="z z1" x="{w - 128}" y="48">z</text>'
        f'<text class="z z2" x="{w - 140}" y="36">z</text><text class="z z3" x="{w - 154}" y="24">Z</text></g>',
    ]
    bar_x, bar_w = 300, 510
    for k, (name, color, size) in enumerate(top):
        y = 112 + k * 34
        pct = 100 * size / total
        fill = max(4, bar_w * pct / 100)
        parts.append(
            f'<circle cx="46" cy="{y - 5}" r="6" fill="{color}"/>'
            f'<text x="62" y="{y}" class="mono" font-size="15" fill="{TEXT}">{escape(name)}</text>'
            f'<text x="{bar_x - 20}" y="{y}" text-anchor="end" class="mono" font-size="14" fill="{MUTED}">{pct:.0f}%</text>'
            f'<rect x="{bar_x}" y="{y - 11}" width="{bar_w}" height="10" rx="5" fill="#16203a"/>'
            f'<rect class="grow" style="animation-delay:{k * 0.12:.2f}s" x="{bar_x}" y="{y - 11}" '
            f'width="{fill:.1f}" height="10" rx="5" fill="{color}"/>'
            f'<g class="fade" style="animation-delay:{0.9 + k * 0.12:.2f}s">{paw(bar_x + fill + 14, y - 7, 13, color)}</g>')
    style = ("@keyframes grow { from { transform: scaleX(0); } to { transform: scaleX(1); } } "
             f".grow {{ transform-origin: {bar_x}px 0; animation: grow 1s cubic-bezier(.2,.8,.2,1) both; }} "
             "@keyframes zz { 0% { opacity: 0; } 30%, 70% { opacity: 1; } 100% { opacity: 0; } } "
             ".z { animation: zz 3s infinite; } .z2 { animation-delay: .6s; } .z3 { animation-delay: 1.2s; }")
    return card(w, h, "\n".join(parts), style)


def main():
    if "--demo" in sys.argv:
        data = load_demo()
    else:
        token = os.environ.get("GH_TOKEN")
        if not token:
            sys.exit("Falta GH_TOKEN (o usa --demo)")
        data = load_live(token)
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "header.svg").write_text(header_svg(data), encoding="utf-8")
    (ASSETS / "city.svg").write_text(city_svg(data), encoding="utf-8")
    (ASSETS / "stack.svg").write_text(stack_svg(data), encoding="utf-8")
    print("Tarjetas generadas en", ASSETS)


if __name__ == "__main__":
    main()
