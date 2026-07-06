"""
Split the Inkscape-converted AgriOS artboard into clean, isolated vector pieces.

The .ai artboard packs several lockups (color + reverse-white) into one flat
layer. Using the object bounding boxes from `inkscape --query-all`, we lift out
the COLOR pieces we need, each into its own tight-viewBox SVG that keeps the
original gradients and layer transform (so geometry stays pixel-identical):

  variants/agrios-lockup.svg    stacked: emblem over "AgriOS"
  variants/agrios-emblem.svg    sprout + swoosh only
  variants/agrios-wordmark.svg  "AgriOS" only
"""
from __future__ import annotations
import copy
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "agrios-vector-inkscape.svg"
OUT = ROOT / "variants"
OUT.mkdir(exist_ok=True)

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", XLINK)

# id -> (x, y, w, h) from _qall.txt (document coords, post-transform)
qall = {}
for line in (ROOT / "_qall.txt").read_text().splitlines():
    p = line.split(",")
    if len(p) == 5 and p[0] not in ("svg1", "layer-MC0"):
        try:
            qall[p[0]] = tuple(float(v) for v in p[1:])
        except ValueError:
            pass

# Color clusters (ids identified from geometry; verified by fill below).
clusters = {
    "agrios-lockup":   ["path2", "path3", "path9", "path14", "path1", "text1"],
    "agrios-emblem":   ["path23", "path24", "path30", "path35"],
    "agrios-wordmark": ["path21", "path22", "text22"],
}

tree = ET.parse(SRC)
root = tree.getroot()
defs = root.find(f"{{{SVG}}}defs")
layer = next(g for g in root.iter(f"{{{SVG}}}g") if g.get("id") == "layer-MC0")
layer_tf = layer.get("transform")
children = {c.get("id"): c for c in list(layer)}

def summarize_fill(el) -> str:
    fills = set()
    for e in el.iter():
        s = (e.get("fill") or "") + " " + (e.get("style") or "")
        for tok in ("url(#", "#ffffff", "#66b701", "#0359b4"):
            if tok in s:
                fills.add(tok)
    return ",".join(sorted(fills)) or "?"

pad = 8.0
for name, ids in clusters.items():
    xs = [qall[i][0] for i in ids]
    ys = [qall[i][1] for i in ids]
    xe = [qall[i][0] + qall[i][2] for i in ids]
    ye = [qall[i][1] + qall[i][3] for i in ids]
    minx, miny, maxx, maxy = min(xs) - pad, min(ys) - pad, max(xe) + pad, max(ye) + pad
    w, h = maxx - minx, maxy - miny

    new = ET.Element(f"{{{SVG}}}svg", {
        "viewBox": f"{minx:.3f} {miny:.3f} {w:.3f} {h:.3f}",
        "width": f"{w:.3f}", "height": f"{h:.3f}",
    })
    if defs is not None:
        new.append(copy.deepcopy(defs))
    g = ET.SubElement(new, f"{{{SVG}}}g")
    if layer_tf:
        g.set("transform", layer_tf)
    for i in ids:
        g.append(copy.deepcopy(children[i]))

    ET.ElementTree(new).write(OUT / f"{name}.svg", encoding="utf-8", xml_declaration=True)
    print(f"{name:16s} viewBox=({minx:.0f},{miny:.0f},{w:.0f},{h:.0f}) "
          f"ids={len(ids)} fills=[{ ' '.join(summarize_fill(children[i]) for i in ids) }]")

print("wrote ->", OUT)
