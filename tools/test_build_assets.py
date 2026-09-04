#!/usr/bin/env python3
"""Self-check for the pieces of build_assets that can silently go wrong:
streak counting and the SMIL keyTimes the typing loop generates.

Run: python3 tools/test_build_assets.py
"""

import os
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_assets as b


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
    labels = [n for _, items in b.STACK for n, _ in items]
    assert labels, "no stack labels to check"
    for label in labels:
        frag, w = b.chip(0, 0, label, "#fff", palette)
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
    print("chip bounds ok (%d labels)" % len(labels))


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
    test_assets_are_wellformed_svg()
    print("OK")
