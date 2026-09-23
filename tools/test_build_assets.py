#!/usr/bin/env python3
"""Self-check for the pieces of build_assets that can silently go wrong:
streak counting and the SMIL keyTimes the typing loop generates.

Run: python3 tools/test_build_assets.py
"""

import os
import sys
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_assets as b
import import_hevy as ih
import icons


def days_from(spec, end=None):
    """spec is newest-last counts ending today unless end given."""
    end = end or date.today()
    return {(end - timedelta(days=len(spec) - 1 - i)).isoformat(): n
            for i, n in enumerate(spec)}


def test_streaks():
    assert b.streaks({}) == (0, 0)

    # Active today: the run including today counts.
    assert b.streaks(days_from([0, 1, 1, 1])) == (3, 3)

    # Nothing today but yesterday active: the day is still young, so the
    # streak must survive rather than reset to zero.
    assert b.streaks(days_from([1, 1, 1, 0])) == (3, 3)

    # Two days idle: the current streak is genuinely broken.
    assert b.streaks(days_from([1, 1, 1, 0, 0])) == (0, 3)

    # Longest is historic, current is shorter.
    assert b.streaks(days_from([1, 1, 1, 1, 1, 0, 1, 1])) == (2, 5)

    # A gap must not be bridged into one long run.
    assert b.streaks(days_from([1, 1, 0, 1, 1, 1])) == (3, 3)
    print("streaks ok")


def test_typing_keytimes():
    """keyTimes must be non-decreasing and inside [0,1] or the SVG is invalid
    and browsers drop the whole animation."""
    lines = ["short", "a considerably longer line of text", "mid length"]
    frag = b.typing(lines, 10, 40, 18, "#000", "#111")
    root = ET.fromstring("<svg xmlns='http://www.w3.org/2000/svg'>"
                         + frag.replace("xml:space", "space") + "</svg>")
    animates = [e for e in root.iter() if e.tag.endswith("animate")]
    assert animates, "no <animate> emitted"
    checked = 0
    for a in animates:
        if "keyTimes" not in a.attrib:
            continue
        kt = [float(v) for v in a.attrib["keyTimes"].split(";")]
        vals = a.attrib["values"].split(";")
        assert len(kt) == len(vals), "keyTimes/values length mismatch"
        assert kt[0] == 0 and kt[-1] == 1, "keyTimes must span 0..1: %s" % kt
        assert all(x <= y for x, y in zip(kt, kt[1:])), \
            "keyTimes must not decrease: %s" % kt
        checked += 1
    assert checked >= len(lines), "expected a clip animation per line"
    print("typing keyTimes ok (%d animations)" % checked)


def test_only_one_typing_line_is_visible_at_a_time():
    """Each line's group is opaque only during its own slot. Without this the
    idle lines leave their carets parked on screen next to the active line."""
    lines = ["one", "line two", "the third line"]
    frag = b.typing(lines, 200, 40, 18, "#000", "#111")
    root = ET.fromstring("<svg xmlns='http://www.w3.org/2000/svg'>"
                         + frag.replace("xml:space", "space") + "</svg>")
    groups = [g for g in root.iter() if g.tag.endswith("}g")]
    assert len(groups) == len(lines), "expected one gated group per line"

    windows = []
    for g in groups:
        assert g.attrib.get("opacity") == "0", "group must start hidden"
        gate = next(a for a in g if a.tag.endswith("animate")
                    and a.attrib.get("calcMode") == "discrete")
        kt = [float(v) for v in gate.attrib["keyTimes"].split(";")]
        vals = [int(v) for v in gate.attrib["values"].split(";")]
        assert len(kt) == len(vals)
        assert kt[0] == 0 and kt[-1] == 1
        assert all(x <= y for x, y in zip(kt, kt[1:])), kt
        on = [(kt[i], kt[i + 1]) for i in range(len(vals) - 1) if vals[i] == 1]
        assert len(on) == 1, "a line should be visible in exactly one window"
        windows.append(on[0])

    windows.sort()
    for (_, prev_end), (next_start, _) in zip(windows, windows[1:]):
        assert prev_end <= next_start + 1e-9, \
            "visible windows overlap: %s" % (windows,)
    assert abs(windows[0][0]) < 1e-9, "first window should open the loop"
    assert abs(windows[-1][1] - 1) < 1e-9, "last window should close the loop"
    print("typing gating ok (%d non-overlapping windows)" % len(windows))


def test_chip_text_stays_inside_its_pill():
    """The pill is drawn at a width computed from the label, and the label is
    pinned with textLength. Both must agree, or the text spills out of the
    rounded rect the way it did when the width was estimated for a
    proportional font."""
    palette = b.THEMES["-dark"]
    entries = [(n, s) for _, items in b.STACK for n, _, s in items]
    assert entries, "no stack labels to check"
    for label, slug in entries:
        frag, w = b.chip(0, 0, label, "#fff", palette, slug)
        el = ET.fromstring("<svg xmlns='http://www.w3.org/2000/svg'>"
                           + frag.replace("xml:space", "space") + "</svg>")
        rect = next(e for e in el.iter() if e.tag.endswith("rect"))
        text = next(e for e in el.iter() if e.tag.endswith("text"))
        pill = float(rect.attrib["width"])
        start = float(text.attrib["x"])
        length = float(text.attrib["textLength"])
        assert abs(pill - w) < 0.01, "%s: returned width disagrees with rect" % label
        assert start + length <= pill, (
            "%s: text ends at %.1f but pill is only %.1f wide"
            % (label, start + length, pill))
        assert pill - (start + length) >= 6, (
            "%s: only %.1f px of right padding, too tight"
            % (label, pill - (start + length)))
        # The glyph sits between the left padding and the label.
        mark = next(e for e in el.iter() if e.tag.endswith("path"))
        assert "scale" in mark.attrib["transform"], label
    print("chip bounds ok (%d labels)" % len(entries))


def test_every_declared_icon_slug_exists():
    """A slug with a typo renders nothing at all, and an empty pill looks like
    a styling bug rather than a missing glyph. Fail the build instead."""
    used = [s for _, items in b.STACK for _, _, s in items]
    used += [s for _, _, _, s in b.SOCIAL]
    missing = [s for s in used if s not in icons.ICONS]
    assert not missing, "no vendored glyph for: %s" % missing
    for slug in used:
        frag = icons.glyph(slug, 0, 0, 18, "#fff")
        assert frag, slug
        ET.fromstring("<svg xmlns='http://www.w3.org/2000/svg'>" + frag + "</svg>")
    assert icons.glyph("definitely-not-a-brand", 0, 0, 18, "#fff") == "", \
        "an unknown slug must degrade to nothing, not raise"
    print("icon slugs ok (%d glyphs)" % len(used))


def test_dark_brand_colours_are_lifted_off_the_dark_card():
    """Pandas (#150458), Django (#092E20) and Vercel (#000000) are close enough
    to the dark surface to disappear. contrast() must move them, and must leave
    an already-legible colour alone."""
    dark, light = b.THEMES["-dark"], b.THEMES[""]
    for sunk in ("#150458", "#092E20", "#000000"):
        lifted = b.contrast(sunk, dark)
        assert lifted != sunk, "%s was left unreadable on the dark card" % sunk
        assert b.luminance(lifted) > b.luminance(dark["surface"]) + 0.15, (
            "%s -> %s is still too close to the surface" % (sunk, lifted))
    assert b.contrast("#FF9900", dark) == "#FF9900", "a bright brand was altered"
    assert b.contrast("#3776AB", light) == "#3776AB", "a mid brand was altered"
    assert b.contrast("#FFFFFF", light) != "#FFFFFF", "white must darken on light"
    print("brand contrast ok")


def test_stack_pills_do_not_overlap_or_leave_the_card():
    """Pills are packed by hand and wrap on width. A row that overflows or a
    wrap that lands on top of the previous row is invisible in code review."""
    for suffix, palette in b.THEMES.items():
        doc = b.build_stack(palette)
        root = ET.fromstring(doc)
        width = float(root.attrib["width"])
        height = float(root.attrib["height"])
        boxes = []
        for e in root.iter():
            if not e.tag.endswith("rect"):
                continue
            x, y = float(e.attrib["x"]), float(e.attrib["y"])
            bw, bh = float(e.attrib["width"]), float(e.attrib["height"])
            assert x >= 0 and x + bw <= width + 0.01, \
                "pill runs from %.1f to %.1f in a %.0f wide card" % (x, x + bw, width)
            assert y >= 0 and y + bh <= height + 0.01, \
                "pill bottom %.1f falls outside a %.0f tall card" % (y + bh, height)
            boxes.append((x, y, bw, bh))
        for i, (ax, ay, aw, ah) in enumerate(boxes):
            for bx, by, bw2, bh2 in boxes[i + 1:]:
                overlap = (ax < bx + bw2 and bx < ax + aw
                           and ay < by + bh2 and by < ay + ah)
                assert not overlap, \
                    "pills overlap: (%.0f,%.0f) and (%.0f,%.0f)" % (ax, ay, bx, by)
        assert len(boxes) == sum(len(i) for _, i in b.STACK), \
            "expected one pill per stack entry in %s" % (suffix or "light")
    print("stack packing ok")


def test_language_legend_stays_in_card():
    """Legend entries are placed by hand; long names must be dropped rather
    than drawn past the edge of the card."""
    long_names = [("ReallyLongLanguageName%d" % i, 20.0, "#fff") for i in range(5)]
    stats = {"total": 1, "commits": 1, "stars": 1, "prs": 1, "issues": 1,
             "current": 1, "longest": 1, "since": date(2024, 1, 1),
             "languages": long_names}
    doc = b.build_activity(b.THEMES[""], stats)
    root = ET.fromstring(doc)
    card_right = 900 - 26
    for t in root.iter():
        if t.tag.endswith("text") and "textLength" in t.attrib:
            end = float(t.attrib["x"]) + float(t.attrib["textLength"])
            assert end <= card_right + 0.01, "legend text runs to %.1f" % end
    print("legend clipping ok")


def test_training_parsing_and_bucketing():
    import tempfile
    monday = date(2026, 8, 31)          # a Monday
    csv_text = ("# comment line, must be ignored\n"
                "date,minutes\n"
                "2026-08-31,60\n"
                "2026-09-02,45\n"
                "2026-08-24,30\n"
                "not-a-date,60\n"      # skipped, not fatal
                "2026-08-25,\n"         # blank minutes, skipped
                "2026-08-26,0\n")      # zero, skipped
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
        fh.write(csv_text)
        path = fh.name
    rows = b.load_training(path)
    assert [m for _, m in rows] == [30, 60, 45], rows
    assert rows == sorted(rows), "rows must come back in date order"
    assert b.load_training(path + ".missing") == [], "missing file must be empty"

    weeks = b.weekly_minutes(rows, weeks=3, today=date(2026, 9, 4))
    assert weeks == [0, 30, 105], weeks   # 60+45 land in the same week
    print("training parsing ok")


def test_week_streak():
    def sess(*mondays):
        return [(date(2026, 8, d), 60) for d in mondays]
    today = date(2026, 9, 4)              # Friday of the w/c 31 Aug week
    assert b.week_streak([], today) == 0
    # Trained this week and the two before it.
    assert b.week_streak(sess(31, 24, 17), today) == 3
    # Nothing yet this week: the run through last week must survive.
    assert b.week_streak(sess(24, 17), today) == 2
    # A missed week genuinely breaks it.
    assert b.week_streak(sess(24, 10), today) == 1
    print("week streak ok")


def bar_rects(frag):
    root = ET.fromstring("<svg xmlns='http://www.w3.org/2000/svg'>"
                         + frag + "</svg>")
    return [e for e in root.iter() if e.tag.endswith("rect")]


def test_bars_stay_inside_their_box():
    """Columns are placed by hand, so a tall week must not draw above the box
    or past either edge."""
    x, y, w, h = 26, 116, 848, 62
    palette = b.THEMES[""]
    vals = [0, 5, 200, 3, 0, 87]
    rects = bar_rects(b.bars(x, y, w, h, vals, palette))
    assert len(rects) == len(vals), "expected one column per week"
    for r in rects:
        rx, ry = float(r.attrib["x"]), float(r.attrib["y"])
        rw, rh = float(r.attrib["width"]), float(r.attrib["height"])
        assert x - 0.01 <= rx and rx + rw <= x + w + 0.01, \
            "column runs from %.1f to %.1f" % (rx, rx + rw)
        assert y - 0.01 <= ry and ry + rh <= y + h + 0.01, \
            "column runs from %.1f to %.1f vertically" % (ry, ry + rh)
    peak = max(rects, key=lambda r: float(r.attrib["height"]))
    assert abs(float(peak.attrib["y"]) - y) < 0.01, "the peak should touch the top"
    assert b.bars(x, y, w, h, [0, 0, 0], palette) == "", \
        "all-zero data should draw nothing rather than a row of fake columns"
    assert b.bars(x, y, w, h, [], palette) == ""
    print("bar bounds ok")


def test_a_rest_week_does_not_flatten_the_chart():
    """The whole point of columns over a line: trailing weeks with no session
    must read as gaps, not drag a trace flat along the baseline."""
    x, y, w, h = 26, 116, 848, 62
    palette = b.THEMES[""]
    vals = [60, 90, 120, 0, 0, 0]          # three weeks off at the end
    rects = bar_rects(b.bars(x, y, w, h, vals, palette))
    heights = [float(r.attrib["height"]) for r in rects]
    trained, rested = heights[:3], heights[3:]
    assert all(v > b.REST_STUB for v in trained), heights
    assert all(v == b.REST_STUB for v in rested), \
        "a rest week must be a baseline stub, not a scaled column"
    # The trained weeks keep their full range instead of being squashed toward
    # the baseline by the empty ones.
    assert abs(max(trained) - h) < 0.01, "the peak lost its scale"
    assert len({round(v, 2) for v in trained}) == 3, \
        "distinct weeks collapsed to the same height"
    print("rest weeks read as gaps ok")


def test_training_card_empty_state_invents_nothing():
    doc = b.build_training(b.THEMES[""], [])
    ET.fromstring(doc)
    assert "No sessions logged yet" in doc
    assert not re.search(r'<(polyline|circle)', doc), \
        "empty log must not draw a chart"
    assert doc.count("<rect") == 1, "empty log must draw only the card itself"
    assert not re.search(r'font-size="26"', doc), \
        "empty log must not show headline numbers"
    print("training empty state ok")


def test_hevy_import():
    """The importer collapses set rows into sessions and refuses to invent or
    silently keep nonsense durations."""
    import tempfile, io, contextlib
    src = (
        'title,start_time,end_time,exercise_title,weight_kg,reps\n'
        # three sets, one session, 40 minutes
        '"Upper-A","Sep 2, 2026, 6:59 PM","Sep 2, 2026, 7:39 PM","Pushdown",50,10\n'
        '"Upper-A","Sep 2, 2026, 6:59 PM","Sep 2, 2026, 7:39 PM","Pushdown",54,8\n'
        '"Upper-A","Sep 2, 2026, 6:59 PM","Sep 2, 2026, 7:39 PM","Curl",30,10\n'
        # a separate 45 minute session on another day
        '"Lower-A","Sep 4, 2026, 9:00 AM","Sep 4, 2026, 9:45 AM","Squat",100,5\n'
        # timer never stopped: must be dropped, not counted
        '"Ghost","Sep 5, 2026, 8:00 PM","Sep 6, 2026, 9:00 AM","Bench",60,5\n'
        # zero length: must be dropped
        '"Zero","Sep 6, 2026, 8:00 PM","Sep 6, 2026, 8:00 PM","Bench",60,5\n'
        # unreadable stamp: skipped without killing the run
        '"Bad","not a date","also not a date","Bench",60,5\n')
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
        fh.write(src); path = fh.name
    sessions, skipped, dropped = ih.read_sessions(path)
    assert sessions == [(date(2026, 9, 2), 40), (date(2026, 9, 4), 45)], sessions
    assert len(skipped) == 1, skipped
    assert len(dropped) == 2, dropped

    # A non-Hevy csv must fail loudly rather than writing an empty log.
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
        fh.write("a,b\n1,2\n"); wrong = fh.name
    try:
        ih.read_sessions(wrong)
        raise AssertionError("expected a SystemExit on a non-Hevy file")
    except SystemExit as exc:
        assert "missing column" in str(exc), exc

    # Round trip: what the importer writes, the renderer must read back.
    out = tempfile.mktemp(suffix=".csv")
    with contextlib.redirect_stdout(io.StringIO()):
        ih.main([path, "--out", out])
    assert b.load_training(out) == sessions, "importer output must reload"

    # --dry-run must not create the file.
    ghost = tempfile.mktemp(suffix=".csv")
    with contextlib.redirect_stdout(io.StringIO()):
        ih.main([path, "--out", ghost, "--dry-run"])
    assert not os.path.exists(ghost), "dry run wrote a file"
    print("hevy import ok")


def test_week_window_labels_follow_the_constant():
    """The window length appears in a metric label and an axis label. Both
    must derive from TRAINING_WEEKS, or changing it leaves the card claiming
    a range it no longer plots."""
    original = b.TRAINING_WEEKS
    try:
        for weeks in (16, 26, 8):
            b.TRAINING_WEEKS = weeks
            doc = b.build_training(b.THEMES[""],
                                   [(date(2026, 9, 1), 60), (date(2026, 8, 25), 45)],
                                   today=date(2026, 9, 4))
            assert "Minutes, %d weeks" % weeks in doc, \
                "metric label did not follow the constant at %d" % weeks
            assert "%d weeks ago" % weeks in doc, \
                "axis label did not follow the constant at %d" % weeks
            others = {26, 16, 8} - {weeks}
            for stale in others:
                assert "%d weeks" % stale not in doc, \
                    "found stale '%d weeks' while set to %d" % (stale, weeks)
            assert len(b.weekly_minutes([])) == weeks, \
                "weekly_minutes ignored the constant when called bare"
            root = ET.fromstring(doc)
            cols = [e for e in root.iter() if e.tag.endswith("rect")]
            # one card background plus one column per week in the window
            assert len(cols) == weeks + 1, \
                "plotted %d columns for a %d week window" % (len(cols) - 1, weeks)
    finally:
        b.TRAINING_WEEKS = original
    print("week window labels ok")


def test_assets_are_wellformed_svg():
    """Every builder must emit parseable XML; a stray & would blank the image."""
    stats = {"total": 1126, "commits": 409, "stars": 10, "prs": 68, "issues": 3,
             "current": 5, "longest": 19, "since": date(2024, 11, 19),
             "languages": [("Python", 61.4, "#3572A5"),
                           ("JavaScript", 18.2, "#f1e05a"),
                           ("Shell", 9.1, "#89e051")]}
    for suffix, palette in b.THEMES.items():
        for name, doc in (("banner", b.build_banner(palette)),
                          ("footer", b.build_footer(palette)),
                          ("stack", b.build_stack(palette)),
                          ("activity", b.build_activity(palette, stats))):
            ET.fromstring(doc)  # raises on malformed XML
            assert doc.startswith("<svg"), name
            assert "&amp;" in doc or "&" not in doc, \
                "%s%s has a raw ampersand" % (name, suffix)
    print("all assets are well-formed svg")


if __name__ == "__main__":
    test_streaks()
    test_only_one_typing_line_is_visible_at_a_time()
    test_chip_text_stays_inside_its_pill()
    test_language_legend_stays_in_card()
    test_typing_keytimes()
    test_training_parsing_and_bucketing()
    test_week_streak()
    test_every_declared_icon_slug_exists()
    test_dark_brand_colours_are_lifted_off_the_dark_card()
    test_stack_pills_do_not_overlap_or_leave_the_card()
    test_bars_stay_inside_their_box()
    test_a_rest_week_does_not_flatten_the_chart()
    test_training_card_empty_state_invents_nothing()
    test_hevy_import()
    test_week_window_labels_follow_the_constant()
    test_assets_are_wellformed_svg()
    print("OK")
