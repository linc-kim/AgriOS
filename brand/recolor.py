"""
Generate monochrome and reverse-white variants from the isolated color pieces.

Flattens every fill (including gradient fills) to a single solid color, keeping
geometry and fill-rule holes intact. Produces, for lockup / emblem / wordmark:
  *-mono.svg      solid ink  (#111111)   for documents, invoices, watermarks
  *-white.svg     solid white (#ffffff)  for dark UI, hero, photography
"""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "variants"
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)

DRAW = {f"{{{SVG}}}{t}" for t in ("path", "rect", "circle", "ellipse", "polygon", "polyline")}
MODES = {"mono": "#111111", "white": "#ffffff"}
SOURCES = ["agrios-lockup", "agrios-emblem", "agrios-wordmark"]

def recolor(src: Path, color: str, out: Path) -> None:
    tree = ET.parse(src)
    root = tree.getroot()
    # Drop gradient defs — everything becomes solid.
    for defs in root.findall(f"{{{SVG}}}defs"):
        root.remove(defs)
    for el in root.iter():
        if el.tag in DRAW:
            el.set("fill", color)
            el.attrib.pop("stroke", None)
            style = el.get("style")
            if style:
                style = re.sub(r"fill\s*:[^;]*;?", "", style)
                style = re.sub(r"stroke\s*:[^;]*;?", "", style)
                el.set("style", style.strip())
    tree.write(out, encoding="utf-8", xml_declaration=True)

for name in SOURCES:
    src = ROOT / f"{name}.svg"
    for mode, color in MODES.items():
        out = ROOT / f"{name}-{mode}.svg"
        recolor(src, color, out)
        print("wrote", out.name)
