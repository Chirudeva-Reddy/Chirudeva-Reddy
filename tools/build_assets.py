#!/usr/bin/env python3
"""Render every decorative and data SVG the profile README uses.

Each asset is written twice, once per GitHub colour scheme, and the README
picks between them with <picture media="(prefers-color-scheme: ...)">. Nothing
here is fetched at read time: the workflow commits the output to the `output`
branch, so a dead third-party service can never blank the profile.

Stdlib only. Needs GITHUB_TOKEN in the environment for the GraphQL calls.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

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
        "wave_from": "#0B1220",
        "wave_to": "#1D4ED8",
        "on_wave": "#F8FAFC",
        "on_wave_muted": "#CBD5E1",
    },
}

TYPING_LINES = [
    "AI engineer, mostly health and fitness",
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
    ("linkedin", "LinkedIn", "#0A66C2"),
    ("email", "Email", "#EA4335"),
    ("instagram", "Instagram", "#E4405F"),
]

STACK = [
    ("AI and machine learning",
     [("Python", "#3776AB"), ("PyTorch", "#EE4C2C"), ("TensorFlow", "#FF6F00"),
      ("scikit-learn", "#F7931E"), ("CUDA", "#76B900"), ("MLflow", "#0194E2")]),
    ("Data and applications",
     [("NumPy", "#4D77CF"), ("Pandas", "#150458"), ("Streamlit", "#FF4B4B"),
      ("Plotly", "#3F4F75"), ("Django", "#092E20"), ("Node.js", "#339933"),
      ("PostgreSQL", "#4169E1"), ("MongoDB", "#47A248")]),
    ("Platforms",
     [("AWS", "#FF9900"), ("Azure", "#0078D4"), ("Firebase", "#DD2C00"),
      ("Vercel", "#888888")]),
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
        'fill="{c}" text-anchor="middle">AI Engineer &#183; Health, Fitness '
        '&amp; Useful Systems</text>'.format(
            x=w / 2, ff=SANS, c=p["on_wave_muted"]))
    body.append(typing(TYPING_LINES, w / 2, 224, 19,
                       p["accent"], p["accent_soft"]))
    return svg(w, h, "".join(body), "Chirudeva Reddy, AI engineer")


def build_footer(p):
    w, h = 900, 190
    body = [typing(FOOTER_LINES, w / 2, 34, 16, p["muted"], p["muted"])]
    body.append('<g transform="translate(0,60)">' + wave(p, w, 130, flip=True) + '</g>')
    return svg(w, h, "".join(body), "Open to AI engineering roles")


CHIP_SIZE = 12.5
CHIP_LEAD = 24      # dot plus the gap before the label
CHIP_TAIL = 13      # padding after the label

# ponytail: the label sets the pill width, and the font is whatever the reader
# has installed, so a proportional guess drifts and the text spills out. Text
# is monospace (a fixed 0.6em advance) and pinned with textLength, which makes
# the reserved width exact everywhere instead of merely close on this machine.


def chip_text_width(label):
    return len(label) * CHIP_SIZE * MONO_ADVANCE


def chip(x, y, label, color, p):
    tw = chip_text_width(label)
    w = CHIP_LEAD + tw + CHIP_TAIL
    return ('<g><rect x="{x}" y="{y}" width="{w}" height="28" rx="14" '
            'fill="{s}" stroke="{l}"/>'
            '<circle cx="{cx}" cy="{cy}" r="4.5" fill="{c}"/>'
            '<text x="{tx}" y="{ty}" font-family="{ff}" font-size="{fs}" '
            'textLength="{tw}" lengthAdjust="spacing" fill="{t}" '
            'xml:space="preserve">{n}</text></g>'.format(
                x=x, y=y, w=round(w, 2), s=p["surface"], l=p["line"], c=color,
                cx=x + 13, cy=y + 14, tx=x + CHIP_LEAD, ty=y + 18,
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
        y += 14
        cx = x_pad
        for label, color in items:
            piece, cw = chip(cx, y, label, color, p)
            if cx + cw > w - x_pad:  # wrap
                cx = x_pad
                y += 36
                piece, cw = chip(cx, y, label, color, p)
            body.append(piece)
            cx += cw + 8
        y += 58
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


def build_social(p, label, color):
    """One pill per link. Each is its own file so the README can wrap it in an
    <a>; an <img>-embedded SVG cannot carry its own clickable regions."""
    frag, w = chip(1, 1, label, color, p)
    return svg(round(w + 2, 2), 30, frag, label)


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

    for suffix, palette in THEMES.items():
        write("banner{}.svg".format(suffix), build_banner(palette))
        write("footer{}.svg".format(suffix), build_footer(palette))
        write("stack{}.svg".format(suffix), build_stack(palette))
        for slug, label, color in SOCIAL:
            write("social-{}{}.svg".format(slug, suffix),
                  build_social(palette, label, color))
        if stats:
            write("activity{}.svg".format(suffix), build_activity(palette, stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
