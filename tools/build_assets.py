#!/usr/bin/env python3
"""Render every decorative and data SVG the profile README uses.

Each asset is written twice, once per GitHub colour scheme, and the README
picks between them with <picture media="(prefers-color-scheme: ...)">. Nothing
here is fetched at read time: the workflow commits the output to the `output`
branch, so a dead third-party service can never blank the profile.

Stdlib only. Needs GITHUB_TOKEN in the environment for the GraphQL calls.
"""

import csv
import json
import os
import sys
import textwrap
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icons import glyph                                    # noqa: E402

USER = os.environ.get("PROFILE_USER", "Chirudeva-Reddy")
OUT = os.environ.get("OUT_DIR", "dist")
API = "https://api.github.com/graphql"

MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
SANS = "-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif"

# ponytail: monospace advance width is a fixed ratio, so text width needs no
# font metrics. Only the typing lines rely on this, and they are monospace.
MONO_ADVANCE = 0.60

THEMES = {
    "": {  # light
        "accent": "#2563EB",
        "accent_soft": "#60A5FA",
        "text": "#1F2328",
        "muted": "#59636E",
        "line": "#D1D9E0",
        "surface": "#F6F8FA",
        "inset": "#FCFDFE",
        "wave_from": "#0F172A",
        "wave_to": "#2563EB",
        "on_wave": "#F8FAFC",
        "on_wave_muted": "#CBD5E1",
    },
    "-dark": {
        "accent": "#58A6FF",
        "accent_soft": "#388BFD",
        "text": "#E6EDF3",
        "muted": "#9198A1",
        "line": "#3D444D",
        "surface": "#151B23",
        "inset": "#0D1117",
        "wave_from": "#0B1220",
        "wave_to": "#1D4ED8",
        "on_wave": "#F8FAFC",
        "on_wave_muted": "#CBD5E1",
    },
}

TYPING_LINES = [
    "AI engineer, applied machine learning",
    "The model is usually the easy part",
    "I care about the eval, not just the demo",
    "Currently living in RAG evaluation and computer vision",
]

FOOTER_LINES = [
    "Thanks for scrolling this far",
    "Open to AI engineering roles",
    "Hard, practical problems welcome",
    "chirudevareddy03@gmail.com",
]

SOCIAL = [
    ("linkedin", "LinkedIn", "#0A66C2", "linkedin"),
    ("email", "Email", "#EA4335", "gmail"),
    ("instagram", "Instagram", "#E4405F", "instagram"),
]

# (label, brand colour, Simple Icons slug). The colour is the official brand
# hex; contrast() lifts the few that would vanish into the card.
STACK = [
    ("AI and machine learning",
     [("Python", "#3776AB", "python"),
      ("PyTorch", "#EE4C2C", "pytorch"),
      ("TensorFlow", "#FF6F00", "tensorflow"),
      ("scikit-learn", "#F7931E", "scikitlearn"),
      ("CUDA", "#76B900", "nvidia"),
      ("MLflow", "#0194E2", "mlflow")]),
    ("Data and applications",
     [("NumPy", "#4D77CF", "numpy"),
      ("Pandas", "#150458", "pandas"),
      ("Streamlit", "#FF4B4B", "streamlit"),
      ("Plotly", "#3F4F75", "plotly"),
      ("Django", "#092E20", "django"),
      ("Node.js", "#339933", "nodedotjs"),
      ("PostgreSQL", "#4169E1", "postgresql"),
      ("MongoDB", "#47A248", "mongodb")]),
    ("Platforms",
     [("AWS", "#FF9900", "amazonwebservices"),
      ("Azure", "#0078D4", "microsoftazure"),
      ("Firebase", "#DD2C00", "firebase"),
      ("Vercel", "#000000", "vercel")]),
]


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def graphql(query, variables):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set")
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": "bearer " + token,
                 "Content-Type": "application/json",
                 "User-Agent": "profile-asset-builder"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise RuntimeError("GraphQL: " + json.dumps(payload["errors"])[:400])
    return payload["data"]


PROFILE_Q = """
query($login:String!){
  user(login:$login){
    createdAt
    pullRequests{totalCount}
    issues{totalCount}
    repositories(first:100, ownerAffiliations:OWNER, isFork:false,
                 orderBy:{field:STARGAZERS, direction:DESC}){
      nodes{
        stargazerCount
        languages(first:12, orderBy:{field:SIZE, direction:DESC}){
          edges{ size node{ name color } }
        }
      }
    }
  }
}
"""

YEAR_Q = """
query($login:String!,$from:DateTime!,$to:DateTime!){
  user(login:$login){
    contributionsCollection(from:$from, to:$to){
      totalCommitContributions
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount } }
      }
    }
  }
}
"""


def fetch_stats():
    """Contribution totals, streaks, stars and language mix for USER."""
    prof = graphql(PROFILE_Q, {"login": USER})["user"]
    created = datetime.strptime(prof["createdAt"][:10], "%Y-%m-%d").date()

    days, total, commits = {}, 0, 0
    year = created.year
    today = date.today()
    while year <= today.year:
        frm = max(created, date(year, 1, 1))
        to = min(today, date(year, 12, 31))
        cc = graphql(YEAR_Q, {
            "login": USER,
            "from": frm.isoformat() + "T00:00:00Z",
            "to": to.isoformat() + "T23:59:59Z",
        })["user"]["contributionsCollection"]
        total += cc["contributionCalendar"]["totalContributions"]
        commits += cc["totalCommitContributions"]
        for w in cc["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
        year += 1

    stars = sum(r["stargazerCount"] for r in prof["repositories"]["nodes"])

    sizes = {}
    colors = {}
    for repo in prof["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8B949E"
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:5]
    grand = sum(sizes.values()) or 1
    languages = [(n, s / grand * 100, colors[n]) for n, s in top]

    current, longest = streaks(days)
    return {
        "total": total, "commits": commits, "stars": stars,
        "prs": prof["pullRequests"]["totalCount"],
        "issues": prof["issues"]["totalCount"],
        "current": current, "longest": longest,
        "since": created, "languages": languages,
    }


def streaks(days):
    """Current and longest run of consecutive active days.

    Today counts only when it already has contributions, so the current streak
    never breaks just because the day is still young.
    """
    if not days:
        return 0, 0
    today = date.today()
    longest = run = 0
    for key in sorted(days):
        if days[key] > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    current = 0
    cursor = today
    if days.get(cursor.isoformat(), 0) == 0:
        cursor -= timedelta(days=1)
    while days.get(cursor.isoformat(), 0) > 0:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def typing(lines, center_x, y, size, color, cursor_color, hold=2600, per_char=55):
    """SMIL typing loop: one clipped <text> per line, sequenced end-to-end.

    <img>-embedded SVG runs declarative animation but never scripts, so the
    whole cycle is expressed as begin/dur offsets computed here. Each line is
    centred on its own width so short lines do not hang off to one side.
    """
    char = size * MONO_ADVANCE
    spans = [(len(t) * per_char) + hold + 600 for t in lines]
    total = sum(spans)
    out, start = [], 0
    for i, text in enumerate(lines):
        width = len(text) * char
        x = round(center_x - width / 2, 2)
        typed = len(text) * per_char
        mine = spans[i]
        # keyTimes across the whole loop: type in, hold, wipe, stay hidden.
        t1 = typed / total
        t2 = (typed + hold) / total
        t3 = mine / total
        begin = round(start / total, 5)
        kt = [0, begin, begin + t1, begin + t2, begin + t3, 1]
        kt = [min(1, max(0, round(v, 5))) for v in kt]
        vals = [0, 0, width, width, 0, 0]

        # Every line owns a caret, and all of them animate at once, so without
        # a gate the idle lines park their carets on screen and the banner
        # shows a row of stray bars beside whichever line is typing. The group
        # is opaque only during this line's slot; the caret blink multiplies
        # against it, so a hidden group hides its caret too.
        end = min(1.0, round((start + mine) / total, 5))
        if begin <= 0:
            gate_kt, gate_v = [0, end, 1], [1, 0, 0]
        else:
            gate_kt, gate_v = [0, begin, end, 1], [0, 1, 0, 0]

        out.append(
            '<g opacity="0">'
            '<animate attributeName="opacity" calcMode="discrete" dur="{dur}ms" '
            'repeatCount="indefinite" keyTimes="{gkt}" values="{gv}"/>'
            '<clipPath id="clip{i}"><rect x="{x}" y="{yy}" height="{h}">'
            '<animate attributeName="width" dur="{dur}ms" repeatCount="indefinite" '
            'calcMode="linear" keyTimes="{kt}" values="{vals}"/></rect></clipPath>'
            # textLength pins the glyphs to the width the clip rect was sized
            # for, so a different monospace font cannot desync the two.
            '<text x="{x}" y="{y}" clip-path="url(#clip{i})" font-family="{ff}" '
            'font-size="{s}" font-weight="500" fill="{c}" text-anchor="start" '
            'textLength="{tl}" lengthAdjust="spacing" '
            'xml:space="preserve">{t}</text>'
            '<rect y="{yy}" width="2" height="{h}" fill="{cc}">'
            '<animate attributeName="x" dur="{dur}ms" repeatCount="indefinite" '
            'calcMode="linear" keyTimes="{kt}" values="{cx}"/>'
            '<animate attributeName="opacity" dur="900ms" repeatCount="indefinite" '
            'values="1;1;0;0;1" keyTimes="0;0.4;0.5;0.9;1"/></rect>'
            '</g>'.format(
                i=i, x=x, y=y, yy=y - size * 0.82, h=size * 1.12,
                dur=total, kt=";".join(str(v) for v in kt),
                gkt=";".join(str(v) for v in gate_kt),
                gv=";".join(str(v) for v in gate_v),
                vals=";".join(str(round(v, 2)) for v in vals),
                cx=";".join(str(round(x + v, 2)) for v in vals),
                ff=MONO, s=size, c=color, cc=cursor_color, t=esc(text),
                tl=round(width, 2)))
        start += mine
    return "".join(out)


def wave(theme, width, height, flip=False):
    """Gradient band whose free edge is a wave rather than a hard rule.

    Drawn with a flat top and a curved bottom; the footer reuses it rotated so
    the curve meets the page instead of the band butting against the text.
    """
    p = theme

    def band(edge, c1, c2, tail):
        return ('M0,0 H{w} V{e} C{x1},{a} {x2},{b} 0,{t} Z'.format(
            w=width, e=edge * height, a=c1 * height, b=c2 * height,
            t=tail * height, x1=width * 0.72, x2=width * 0.28))

    g = ' transform="rotate(180 {} {})"'.format(width / 2, height / 2) if flip else ""
    return (
        '<defs><linearGradient id="wave" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="{f}"/><stop offset="1" stop-color="{t}"/>'
        '</linearGradient></defs>'
        '<g{g}><path d="{body}" fill="url(#wave)"/>'
        '<path d="{o1}" fill="#FFFFFF" opacity="0.07"/>'
        '<path d="{o2}" fill="#FFFFFF" opacity="0.05"/></g>'.format(
            f=p["wave_from"], t=p["wave_to"], g=g,
            body=band(0.80, 1.06, 0.58, 0.88),
            o1=band(0.62, 0.88, 0.44, 0.70),
            o2=band(0.46, 0.70, 0.30, 0.54)))


def svg(width, height, body, title):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            'viewBox="0 0 {w} {h}" role="img" aria-label="{t}">'
            '<title>{t}</title>{b}</svg>'.format(
                w=width, h=height, b=body, t=esc(title)))


def build_banner(p):
    w, h = 900, 260
    wave_h = 170
    body = [wave(p, w, wave_h)]
    body.append(
        '<text x="{x}" y="86" font-family="{ff}" font-size="46" font-weight="700" '
        'fill="{c}" text-anchor="middle">Chirudeva Reddy</text>'.format(
            x=w / 2, ff=SANS, c=p["on_wave"]))
    body.append(
        '<text x="{x}" y="120" font-family="{ff}" font-size="15" font-weight="500" '
        'fill="{c}" text-anchor="middle">AI Engineer &#183; Applied Machine '
        'Learning &amp; Evaluation</text>'.format(
            x=w / 2, ff=SANS, c=p["on_wave_muted"]))
    body.append(typing(TYPING_LINES, w / 2, 224, 19,
                       p["accent"], p["accent_soft"]))
    return svg(w, h, "".join(body), "Chirudeva Reddy, AI engineer")


def build_footer(p):
    w, h = 900, 190
    body = [typing(FOOTER_LINES, w / 2, 34, 16, p["muted"], p["muted"])]
    body.append('<g transform="translate(0,60)">' + wave(p, w, 130, flip=True) + '</g>')
    return svg(w, h, "".join(body), "Open to AI engineering roles")


CHIP_SIZE = 14.5    # label font size
CHIP_H = 38         # pill height
CHIP_ICON = 19      # brand glyph box
CHIP_PAD = 14       # left padding before the glyph
CHIP_LEAD = CHIP_PAD + CHIP_ICON + 10   # glyph plus the gap before the label
CHIP_TAIL = 16      # padding after the label
CHIP_GAP = 9        # horizontal gap between pills
CHIP_ROW = CHIP_H + 10                  # pitch of a wrapped row

# ponytail: the label sets the pill width, and the font is whatever the reader
# has installed, so a proportional guess drifts and the text spills out. Text
# is monospace (a fixed 0.6em advance) and pinned with textLength, which makes
# the reserved width exact everywhere instead of merely close on this machine.


def chip_text_width(label):
    return len(label) * CHIP_SIZE * MONO_ADVANCE


def rgb(hex_color):
    """(r, g, b) from #RGB or #RRGGBB, so a shorthand colour is not a crash."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError("not a hex colour: %r" % (hex_color,))
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(hex_color):
    """Relative brightness, 0 (black) to 1 (white)."""
    r, g, b = (c / 255.0 for c in rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def mix(hex_color, other, amount):
    return "#{:02X}{:02X}{:02X}".format(
        *(int(round(a + (b - a) * amount))
          for a, b in zip(rgb(hex_color), rgb(other))))


def contrast(color, p):
    """Brand colour, lifted when it would disappear into the card.

    Simple Icons ships the official hex and several of them (Pandas #150458,
    Django #092E20, Vercel #000000) sit almost on top of the dark surface.
    Blending toward the card keeps the hue recognisable while staying legible;
    the light theme gets the same treatment for anything near-white.
    """
    dark = luminance(p["surface"]) < 0.5
    lum = luminance(color)
    if dark and lum < 0.24:
        return mix(color, "#FFFFFF", 0.62)
    if not dark and lum > 0.82:
        return mix(color, "#000000", 0.45)
    return color


def chip(x, y, label, color, p, slug=None):
    """One rounded pill: brand glyph, then the label. Returns (svg, width)."""
    tw = chip_text_width(label)
    w = CHIP_LEAD + tw + CHIP_TAIL
    mark = glyph(slug, x + CHIP_PAD, y + (CHIP_H - CHIP_ICON) / 2.0,
                 CHIP_ICON, contrast(color, p)) if slug else (
        '<circle cx="{cx}" cy="{cy}" r="5.5" fill="{c}"/>'.format(
            cx=x + CHIP_PAD + CHIP_ICON / 2.0, cy=y + CHIP_H / 2.0,
            c=contrast(color, p)))
    return ('<g><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
            'fill="{s}" stroke="{l}"/>{mark}'
            '<text x="{tx}" y="{ty}" font-family="{ff}" font-size="{fs}" '
            'textLength="{tw}" lengthAdjust="spacing" fill="{t}" '
            'xml:space="preserve">{n}</text></g>'.format(
                x=x, y=y, w=round(w, 2), h=CHIP_H, r=CHIP_H / 2.0,
                s=p["surface"], l=p["line"], mark=mark,
                tx=x + CHIP_LEAD, ty=y + CHIP_H / 2.0 + CHIP_SIZE * 0.36,
                ff=MONO, fs=CHIP_SIZE, tw=round(tw, 2),
                t=p["text"], n=esc(label))), w


def build_stack(p):
    w = 900
    x_pad, y = 4, 26
    body = []
    for heading, items in STACK:
        body.append('<text x="{x}" y="{y}" font-family="{ff}" font-size="12" '
                    'font-weight="700" letter-spacing="0.08em" fill="{c}">{t}</text>'
                    .format(x=x_pad, y=y, ff=SANS, c=p["muted"],
                            t=esc(heading.upper())))
        y += 16
        cx = x_pad
        for label, color, slug in items:
            cw = CHIP_LEAD + chip_text_width(label) + CHIP_TAIL
            if cx > x_pad and cx + cw > w - x_pad:      # wrap before drawing
                cx = x_pad
                y += CHIP_ROW
            piece, cw = chip(cx, y, label, color, p, slug)
            body.append(piece)
            cx += cw + CHIP_GAP
        y += CHIP_H + 30
    return svg(w, y - 22, "".join(body), "Tools and platforms I use")


def metric(x, y, value, label, p, accent=False):
    return ('<text x="{x}" y="{y}" font-family="{ff}" font-size="26" '
            'font-weight="700" fill="{c}" text-anchor="middle">{v}</text>'
            '<text x="{x}" y="{y2}" font-family="{ff}" font-size="11.5" '
            'fill="{m}" text-anchor="middle">{l}</text>'.format(
                x=x, y=y, y2=y + 19, ff=SANS,
                c=p["accent"] if accent else p["text"], m=p["muted"],
                v=esc("{:,}".format(value) if isinstance(value, int) else value),
                l=esc(label)))


def build_activity(p, s):
    w, h = 900, 250
    body = ['<rect x="0.5" y="0.5" width="{}" height="{}" rx="12" fill="{}" '
            'stroke="{}"/>'.format(w - 1, h - 1, p["surface"], p["line"])]
    body.append('<text x="26" y="34" font-family="{ff}" font-size="13" '
                'font-weight="700" letter-spacing="0.08em" fill="{c}">'
                'GITHUB ACTIVITY</text>'.format(ff=SANS, c=p["muted"]))

    cells = [(s["total"], "Contributions", True), (s["current"], "Current streak", True),
             (s["longest"], "Longest streak", False), (s["commits"], "Commits", False),
             (s["stars"], "Stars earned", False), (s["prs"], "Pull requests", False)]
    step = w / len(cells)
    for i, (v, label, hot) in enumerate(cells):
        body.append(metric(step * (i + 0.5), 92, v, label, p, accent=hot))
    body.append('<text x="{x}" y="128" font-family="{ff}" font-size="10.5" '
                'fill="{c}" text-anchor="middle">since {d}</text>'.format(
                    x=step * 0.5, ff=SANS, c=p["muted"],
                    d=s["since"].strftime("%d %b %Y")))

    body.append('<text x="26" y="172" font-family="{ff}" font-size="13" '
                'font-weight="700" letter-spacing="0.08em" fill="{c}">'
                'TOP LANGUAGES</text>'.format(ff=SANS, c=p["muted"]))
    bar_x, bar_w, bar_y = 26, w - 52, 186
    cursor = bar_x
    for i, (name, pct, color) in enumerate(s["languages"]):
        seg = bar_w * pct / 100
        body.append('<rect x="{x}" y="{y}" width="{w}" height="10" rx="5" '
                    'fill="{c}"/>'.format(x=cursor, y=bar_y,
                                          w=max(seg - 2, 1), c=color))
        cursor += seg
    # Same fixed-advance trick as the chips: the legend is laid out by hand, so
    # its widths have to be exact rather than estimated.
    size = 12
    lx = bar_x
    for name, pct, color in s["languages"]:
        label = "{} {}%".format(name, round(pct, 1))
        tw = len(label) * size * MONO_ADVANCE
        if lx + 14 + tw > bar_x + bar_w:
            break  # degrade by dropping the tail rather than spilling out
        body.append('<circle cx="{cx}" cy="{cy}" r="4" fill="{c}"/>'
                    '<text x="{tx}" y="{ty}" font-family="{ff}" font-size="{fs}" '
                    'textLength="{tw}" lengthAdjust="spacing" fill="{t}" '
                    'xml:space="preserve">{n}</text>'.format(
                        cx=lx + 4, cy=218, c=color, tx=lx + 14, ty=222,
                        ff=MONO, fs=size, tw=round(tw, 2), t=p["text"],
                        n=esc(label)))
        lx += 14 + tw + 22
    return svg(w, h, "".join(body), "GitHub activity and top languages")


def build_social(p, label, color, slug=None):
    """One pill per link. Each is its own file so the README can wrap it in an
    <a>; an <img>-embedded SVG cannot carry its own clickable regions."""
    frag, w = chip(1, 1, label, color, p, slug)
    return svg(round(w + 2, 2), CHIP_H + 2, frag, label)


TRAINING_CSV = os.environ.get("TRAINING_CSV", "data/training.csv")
TRAINING_WEEKS = 16


def load_training(path=None):
    """Read the training log: 'date,minutes', one row per session.

    A hand-kept CSV rather than Strava or Hevy, because both need an OAuth
    token per reader and this file needs nothing at all. Bad rows are skipped
    instead of failing the build, so a half-pasted export still renders.
    """
    path = path or TRAINING_CSV
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        body = [ln for ln in fh if not ln.lstrip().startswith("#")]
    for row in csv.DictReader(body):
        try:
            day = datetime.strptime((row.get("date") or "").strip()[:10],
                                    "%Y-%m-%d").date()
            minutes = int(float(row.get("minutes") or 0))
        except (ValueError, TypeError):
            continue
        if minutes > 0:
            rows.append((day, minutes))
    return sorted(rows)


def week_start(day):
    return day - timedelta(days=day.weekday())


def weekly_minutes(sessions, weeks=None, today=None):
    """Total minutes per week, oldest first, ending with the current week.

    weeks resolves at call time, not as a default argument: a default would
    freeze TRAINING_WEEKS at import and quietly ignore a later change.
    """
    weeks = weeks or TRAINING_WEEKS
    today = today or date.today()
    end = week_start(today)
    first = end - timedelta(weeks=weeks - 1)
    buckets = [0] * weeks
    for day, minutes in sessions:
        start = week_start(day)
        if first <= start <= end:
            buckets[(start - first).days // 7] += minutes
    return buckets


def week_streak(sessions, today=None):
    """Consecutive trained weeks. The current week counts only once it has a
    session, so a quiet Monday does not appear to end the run."""
    today = today or date.today()
    trained = {week_start(d) for d, _ in sessions}
    cursor = week_start(today)
    if cursor not in trained:
        cursor -= timedelta(weeks=1)
    streak = 0
    while cursor in trained:
        streak += 1
        cursor -= timedelta(weeks=1)
    return streak


REST_STUB = 3   # height of the marker drawn for a week with no session


def bars(x, y, w, h, values, p):
    """One column per week, scaled to the tallest week in the window.

    ponytail: this replaced a line chart. A line has to join the weeks with no
    session to the ones on either side, so any break in training, and every
    unfinished week at the right-hand end, dragged the trace flat along the
    baseline and read as broken rendering rather than as a rest week. Columns
    have no such obligation: a rest week is simply a stub on the baseline, and
    the gap reads as a gap.
    """
    if not values or not any(values):
        return ""
    peak = max(values)
    slot = w / len(values)
    bw = min(slot * 0.62, 30)
    trained = [v for v in values if v]
    avg = sum(trained) / len(trained)

    out = []
    # Baseline, so the rest weeks sit on something rather than float.
    out.append('<line x1="{a}" y1="{y}" x2="{b}" y2="{y}" stroke="{c}" '
               'stroke-width="1" opacity="0.5"/>'.format(
                   a=round(x, 2), b=round(x + w, 2), y=round(y + h, 2),
                   c=p["line"]))
    # Mean of the weeks actually trained. Skipping the rest weeks keeps this a
    # typical session week rather than a number dragged down by time off.
    ay = y + h - (avg / peak) * h
    out.append('<line x1="{a}" y1="{ay}" x2="{b}" y2="{ay}" stroke="{c}" '
               'stroke-width="1" stroke-dasharray="3 5" opacity="0.6"/>'
               '<text x="{tx}" y="{ty}" font-family="{ff}" font-size="9.5" '
               'fill="{c}" text-anchor="end">avg {v} min</text>'.format(
                   a=round(x, 2), b=round(x + w, 2), ay=round(ay, 2),
                   c=p["muted"], tx=round(x + w, 2), ty=round(ay - 4, 2),
                   ff=SANS, v=int(round(avg))))

    last = max(i for i, v in enumerate(values) if v)
    for i, v in enumerate(values):
        bx = x + slot * i + (slot - bw) / 2.0
        if not v:
            out.append('<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="1.5" '
                       'fill="{c}" opacity="0.45"/>'.format(
                           x=round(bx, 2), y=round(y + h - REST_STUB, 2),
                           w=round(bw, 2), h=REST_STUB, c=p["muted"]))
            continue
        bh = max((v / peak) * h, REST_STUB + 1)
        out.append('<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" '
                   'fill="{c}"{o}><title>{v} min</title></rect>'.format(
                       x=round(bx, 2), y=round(y + h - bh, 2), w=round(bw, 2),
                       h=round(bh, 2),
                       c=p["accent"] if i == last else p["accent_soft"],
                       o="" if i == last else ' opacity="0.78"', v=v))
    return "".join(out)


def build_training(p, sessions, today=None):
    today = today or date.today()
    w, h = 900, 210
    body = ['<rect x="0.5" y="0.5" width="{}" height="{}" rx="12" fill="{}" '
            'stroke="{}"/>'.format(w - 1, h - 1, p["surface"], p["line"])]
    body.append('<text x="26" y="34" font-family="{ff}" font-size="13" '
                'font-weight="700" letter-spacing="0.08em" fill="{c}">'
                'TRAINING LOG</text>'.format(ff=SANS, c=p["muted"]))

    if not sessions:
        # Honest empty state. Inventing sessions would put fabricated numbers
        # on a public profile, so the card says there is nothing logged yet.
        body.append('<text x="{x}" y="112" font-family="{ff}" font-size="14" '
                    'fill="{c}" text-anchor="middle">No sessions logged yet. '
                    'Add rows to data/training.csv and this fills in.</text>'
                    .format(x=w / 2, ff=SANS, c=p["muted"]))
        return svg(w, h, "".join(body), "Training log, no sessions recorded yet")

    weeks = weekly_minutes(sessions, TRAINING_WEEKS, today)
    year_ago = today - timedelta(days=365)
    recent = [(d, m) for d, m in sessions if d >= year_ago]
    avg = round(sum(m for _, m in recent) / len(recent)) if recent else 0
    cells = [(len(recent), "Sessions, 12 months", True),
             (week_streak(sessions, today), "Week streak", True),
             ("{} min".format(avg), "Average session", False),
             ("{:,}".format(sum(weeks)),
              "Minutes, {} weeks".format(TRAINING_WEEKS), False)]
    step = w / len(cells)
    for i, (value, label, hot) in enumerate(cells):
        body.append(metric(step * (i + 0.5), 78, value, label, p, accent=hot))

    body.append(bars(26, 116, w - 52, 62, weeks, p))
    body.append('<text x="26" y="196" font-family="{ff}" font-size="10.5" '
                'fill="{c}">{n} weeks ago</text>'
                '<text x="{r}" y="196" font-family="{ff}" font-size="10.5" '
                'fill="{c}" text-anchor="end">this week</text>'.format(
                    ff=SANS, c=p["muted"], n=TRAINING_WEEKS, r=w - 26))
    return svg(w, h, "".join(body), "Weekly training minutes")


# (file slug, name, headline figure, what the figure is, one-liner, tags,
# has a live demo). Figures are the ones the repos commit, not rounded up.
PROJECTS = [
    ("claimlens", "ClaimLens", "82.0 / 64.6", "Box mAP@50, parts / damage models",
     "Vehicle damage segmentation priced from a crawled UAE parts catalogue. "
     "When the evidence is thin it asks for an inspection instead of a price.",
     ["YOLOv8n-seg", "Shapely", "CBUAE 50% rule"], True),
    ("body2health", "body2health", "2.40 cm", "waist MAE, subject-disjoint BodyM split",
     "Waist, hip and chest girths from two phone photos. An SMPL-X fit marks "
     "the run unreportable when render-back disagrees.",
     ["SAM 2.1", "ResNet-18", "InfoNCE", "SMPL-X"], False),
    ("hallucination", "Hallucination detection", "0.6511",
     "AUROC, RAGTruth held-out",
     "Reads hallucination risk out of Qwen2.5-1.5B hidden states before any "
     "text is generated, with fusion weights frozen from train.",
     ["Qwen2.5", "Mahalanobis", "logit lens"], True),
    ("road-accident", "Road accident severity", "0.806", "macro F1, held-out",
     "Severity classification and crash-hotspot mapping over Chicago crash "
     "records, five model families under stratified CV.",
     ["LightGBM", "SHAP", "DBSCAN"], True),
    ("duet", "duet", "--selftest", "proves the read-only sandbox with a canary file",
     "One bash script asks Claude Code and Codex the same question "
     "independently and leads with where they disagree.",
     ["bash", "Claude Code", "Codex"], False),
    ("salon-erp", "Salon ERP", "Odoo 19", "installable module, here for the data model",
     "Guarded booking states, an append-only loyalty ledger, and an interval "
     "constraint that blocks double-booking even under sudo.",
     ["Odoo", "PostgreSQL", "Python"], False),
]

CARD_W, CARD_H = 440, 262
CARD_PAD = 28
DESC_SIZE = 12
DESC_COLS = int((CARD_W - 2 * CARD_PAD) / (DESC_SIZE * MONO_ADVANCE))
DESC_LINES = 3
TAG_SIZE = 11
TAG_H = 22


def mono_text(x, y, text, size, color, weight=400):
    """Monospace text pinned to its computed width, like the chips."""
    tw = len(text) * size * MONO_ADVANCE
    return ('<text x="{x}" y="{y}" font-family="{ff}" font-size="{s}" '
            'font-weight="{wt}" textLength="{tw}" lengthAdjust="spacing" '
            'fill="{c}" xml:space="preserve">{t}</text>'.format(
                x=round(x, 2), y=round(y, 2), ff=MONO, s=size, wt=weight,
                tw=round(tw, 2), c=color, t=esc(text))), tw


def build_project(p, project):
    """One featured-work card: a machined shell around an inset panel, the
    headline figure in the accent, the pitch, then the tags.

    Each card is its own file so the README can link it; an <img> SVG cannot
    carry clickable regions.

    ponytail: no entry animation. A CSS rise-in that starts at opacity 0 left
    the card blank wherever the animation did not run (static renderers,
    link previews), and a blank project card is worse than a still one.
    """
    _, name, figure, figure_label, desc, tags, live = project
    w, h, x0 = CARD_W, CARD_H, CARD_PAD
    body = [
        '<rect x="0.5" y="0.5" width="{w}" height="{h}" rx="18" fill="{s}" '
        'stroke="{l}"/>'.format(w=w - 1, h=h - 1, s=p["surface"], l=p["line"]),
        '<rect x="6" y="6" width="{w}" height="{h}" rx="13" fill="{i}" '
        'stroke="{l}" stroke-opacity="0.6"/>'.format(
            w=w - 12, h=h - 12, i=p["inset"], l=p["line"]),
        '<text x="{x}" y="48" font-family="{ff}" font-size="19" font-weight="700" '
        'fill="{c}">{n}</text>'.format(x=x0, ff=SANS, c=p["text"], n=esc(name)),
    ]
    if live:
        label = "live demo"
        lw = len(label) * TAG_SIZE * MONO_ADVANCE + 22
        lx = w - x0 - lw
        body.append('<rect x="{x}" y="31" width="{w}" height="{h}" rx="{r}" '
                    'fill="none" stroke="{c}" stroke-opacity="0.55"/>'.format(
                        x=round(lx, 2), w=round(lw, 2), h=TAG_H, r=TAG_H / 2,
                        c=p["accent"]))
        body.append(mono_text(lx + 11, 31 + TAG_H / 2 + TAG_SIZE * 0.36,
                              label, TAG_SIZE, p["accent"], 600)[0])

    body.append('<text x="{x}" y="104" font-family="{ff}" font-size="34" '
                'font-weight="700" letter-spacing="-0.02em" fill="{c}">{v}'
                '</text>'.format(x=x0, ff=SANS, c=p["accent"], v=esc(figure)))
    body.append('<text x="{x}" y="126" font-family="{ff}" font-size="12.5" '
                'fill="{c}">{t}</text>'.format(x=x0, ff=SANS, c=p["muted"],
                                               t=esc(figure_label)))

    for i, line in enumerate(textwrap.wrap(desc, DESC_COLS)[:DESC_LINES]):
        body.append(mono_text(x0, 162 + i * 18, line, DESC_SIZE, p["text"])[0])

    tx, ty = x0, h - x0 - TAG_H + 4
    for tag in tags:
        tw = len(tag) * TAG_SIZE * MONO_ADVANCE
        if tx + tw + 20 > w - x0:
            break   # drop the tail rather than spill past the card
        body.append('<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
                    'fill="{s}" stroke="{l}"/>'.format(
                        x=round(tx, 2), y=ty, w=round(tw + 20, 2), h=TAG_H,
                        r=TAG_H / 2, s=p["surface"], l=p["line"]))
        body.append(mono_text(tx + 10, ty + TAG_H / 2 + TAG_SIZE * 0.36, tag,
                              TAG_SIZE, p["muted"])[0])
        tx += tw + 20 + 8
    return svg(w, h, "".join(body), "{}: {}".format(name, desc))


REPO_H = 40


def build_repo_link(p, name):
    """A "repository" pill for a card that links to its live demo. It is as
    wide as a card and pins the pill to the card's left edge, so in the README
    each strip lines up under its own card."""
    label = "repository \u2197"
    lw = len(label) * TAG_SIZE * MONO_ADVANCE + 22
    return svg(CARD_W, REPO_H,
               '<rect x="{x}" y="6" width="{w}" height="{h}" rx="{r}" '
               'fill="{s}" stroke="{c}" stroke-opacity="0.55"/>'.format(
                   x=CARD_PAD, w=round(lw, 2), h=TAG_H, r=TAG_H / 2,
                   s=p["surface"], c=p["accent"])
               + mono_text(CARD_PAD + 11, 6 + TAG_H / 2 + TAG_SIZE * 0.36,
                           label, TAG_SIZE, p["accent"], 600)[0],
               "{} repository".format(name))


def build_spacer():
    """Fills a card's slot in a row of repo strips when that card has none."""
    return svg(CARD_W, REPO_H, "", "")


def write(name, content):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print("wrote {} ({:,} bytes)".format(path, len(content)))


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        stats = fetch_stats()
    except (RuntimeError, urllib.error.URLError, OSError) as exc:
        # ponytail: the decorative assets do not need the API, so a rate limit
        # or outage still refreshes them and leaves the last activity card in
        # place on the output branch.
        print("stats unavailable, skipping activity card: {}".format(exc),
              file=sys.stderr)
        stats = None

    sessions = load_training()
    print("training sessions loaded: {}".format(len(sessions)))

    write("project-spacer.svg", build_spacer())
    for suffix, palette in THEMES.items():
        write("banner{}.svg".format(suffix), build_banner(palette))
        write("footer{}.svg".format(suffix), build_footer(palette))
        write("stack{}.svg".format(suffix), build_stack(palette))
        write("training{}.svg".format(suffix), build_training(palette, sessions))
        for project in PROJECTS:
            write("project-{}{}.svg".format(project[0], suffix),
                  build_project(palette, project))
            if project[6]:
                write("project-{}-repo{}.svg".format(project[0], suffix),
                      build_repo_link(palette, project[1]))
        for name, label, color, icon in SOCIAL:
            write("social-{}{}.svg".format(name, suffix),
                  build_social(palette, label, color, icon))
        if stats:
            write("activity{}.svg".format(suffix), build_activity(palette, stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
