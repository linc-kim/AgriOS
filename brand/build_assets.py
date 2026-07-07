"""
Greena brand asset pipeline — single source of truth: brand/Greena.ai

One command regenerates every derived asset from the master .ai:

    backend/.venv/Scripts/python brand/build_assets.py

Pipeline (only the master .ai ever changes; this stays intact):
  1. Inkscape: Greena.ai -> plain SVG, text outlined (geometry preserved).
  2. Clean -> brand/greena-master.svg: strip ICC color-profile, icc-color(...),
     Illustrator metadata. This is the master SVG.
  3. Split the artboard into the color emblem / wordmark / lockups by clustering
     paths (proximity) and classifying by gradient + aspect + colour, ignoring the
     white/reverse duplicates -> brand/variants/greena-*.svg (+ mono / reverse).
  4. Favicon / app-icon / manifest / OG suite from the (name-neutral) emblem and
     lockup -> frontend/public/.

Requires Inkscape (C:\\Program Files\\Inkscape) and Pillow.
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
AI = ROOT / "Greena.ai"
MASTER = ROOT / "greena-master.svg"
WORK = ROOT / "_work"
VARIANTS = ROOT / "variants"
PUBLIC = ROOT.parent / "frontend" / "public"
ICONS = PUBLIC / "icons"
INKSCAPE = Path(r"C:\Program Files\Inkscape\bin\inkscape.exe")
SVG = "http://www.w3.org/2000/svg"
PATH = f"{{{SVG}}}path"
ET.register_namespace("", SVG)

for d in (WORK, VARIANTS, ICONS):
    d.mkdir(parents=True, exist_ok=True)


def inkscape(*args: str) -> str:
    return subprocess.run(
        [str(INKSCAPE), *args], check=True, capture_output=True, text=True
    ).stdout


# ── 1 + 2. master .ai -> clean master SVG ─────────────────────────────────────

def build_master() -> None:
    raw = WORK / "master-raw.svg"
    inkscape(str(AI), "--export-type=svg", "--export-plain-svg",
             "--export-text-to-path", f"--export-filename={raw}")
    s = re.sub(r"\s*icc-color\([^)]*\)", "", raw.read_text(encoding="utf-8"))
    root = ET.fromstring(s)
    defs = root.find(f"{{{SVG}}}defs")
    if defs is not None:
        for tag in ("color-profile", "metadata"):
            for el in defs.findall(f"{{{SVG}}}{tag}"):
                defs.remove(el)
    for el in root.findall(f"{{{SVG}}}metadata"):
        root.remove(el)
    ET.ElementTree(root).write(MASTER, encoding="utf-8", xml_declaration=True)
    print(f"[master] greena-master.svg: {s.count('<path')} paths (ICC/metadata stripped)")


# ── 3. split into variants ────────────────────────────────────────────────────

def _query_bboxes() -> dict[str, tuple[float, float, float, float]]:
    boxes = {}
    for line in inkscape(str(MASTER), "--query-all").splitlines():
        p = line.split(",")
        if len(p) == 5 and not p[0].startswith(("svg", "layer")):
            try:
                boxes[p[0]] = tuple(float(x) for x in p[1:])
            except ValueError:
                pass
    return boxes


def _hexes(el) -> list[str]:
    s = (el.get("style") or "") + " " + (el.get("fill") or "")
    return re.findall(r"#[0-9a-fA-F]{6}", s)


def _is_white_hex(h: str) -> bool:
    h = h.lstrip("#")
    return all(int(h[i:i + 2], 16) >= 240 for i in (0, 2, 4))


def split_variants() -> None:
    tree = ET.parse(MASTER)
    root = tree.getroot()
    defs = root.find(f"{{{SVG}}}defs")
    layer = root.find(f"{{{SVG}}}g")
    els = {c.get("id"): c for c in layer if c.tag == PATH}
    boxes = _query_bboxes()
    ids = [i for i in els if i in boxes]

    # union-find clustering by bbox proximity
    par = {i: i for i in ids}

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def near(a, b, gap=50.0):
        ax, ay, aw, ah = boxes[a]
        bx, by, bw, bh = boxes[b]
        return not (ax - gap > bx + bw or bx - gap > ax + aw
                    or ay - gap > by + bh or by - gap > ay + ah)

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if near(ids[i], ids[j]):
                par[find(ids[i])] = find(ids[j])

    clusters: dict[str, list[str]] = {}
    for i in ids:
        clusters.setdefault(find(i), []).append(i)

    def cbbox(idl):
        xs = [boxes[i][0] for i in idl]; ys = [boxes[i][1] for i in idl]
        xe = [boxes[i][0] + boxes[i][2] for i in idl]
        ye = [boxes[i][1] + boxes[i][3] for i in idl]
        return min(xs), min(ys), max(xe), max(ye)

    def has_grad(idl):
        return any("url(#" in ((els[i].get("style") or "") + (els[i].get("fill") or "")) for i in idl)

    def all_white(idl):
        for i in idl:
            hx = _hexes(els[i])
            if "url(#" in ((els[i].get("style") or "") + (els[i].get("fill") or "")):
                return False
            if not hx or not all(_is_white_hex(h) for h in hx):
                return False
        return True

    def width(idl):
        b = cbbox(idl); return b[2] - b[0]

    def aspect(idl):
        b = cbbox(idl); h = b[3] - b[1]; return (b[2] - b[0]) / h if h else 99

    color = [c for c in clusters.values() if not all_white(c)]
    grad = [c for c in color if has_grad(c)]

    emblem = min(grad, key=width)                                   # compact gradient mark
    wide_grad = [c for c in grad if aspect(c) > 2]
    lockup = max(wide_grad or grad, key=width)                      # horizontal lockup
    stacked = [c for c in grad if c is not emblem and aspect(c) < 1.6]
    stacked = max(stacked, key=width) if stacked else None
    out = {"greena-emblem": emblem, "greena-lockup": lockup}
    # wordmark-only: the widest single path in the horizontal lockup is the "Greena"
    # text (the standalone wordmark cluster in the artboard is the white/reverse one).
    out["greena-wordmark"] = [max(lockup, key=lambda i: boxes[i][2])]
    if stacked:
        out["greena-lockup-stacked"] = stacked

    for name, idl in out.items():
        x0, y0, x1, y1 = cbbox(idl)
        pad = 8
        new = ET.Element(f"{{{SVG}}}svg", {
            "viewBox": f"{x0-pad:.3f} {y0-pad:.3f} {x1-x0+2*pad:.3f} {y1-y0+2*pad:.3f}",
            "width": f"{x1-x0+2*pad:.3f}", "height": f"{y1-y0+2*pad:.3f}",
        })
        if defs is not None:
            new.append(copy.deepcopy(defs))
        g = ET.SubElement(new, f"{{{SVG}}}g")
        if layer.get("transform"):
            g.set("transform", layer.get("transform"))
        for i in idl:
            g.append(copy.deepcopy(els[i]))
        ET.ElementTree(new).write(VARIANTS / f"{name}.svg", encoding="utf-8", xml_declaration=True)
        print(f"[variant] {name}.svg ({len(idl)} paths)")

    for base in ("greena-emblem", "greena-lockup"):
        _recolor(base, "#111111", "mono")
        _recolor(base, "#ffffff", "white")


def _recolor(base: str, color: str, suffix: str) -> None:
    src = VARIANTS / f"{base}.svg"
    if not src.exists():
        return
    tree = ET.parse(src)
    root = tree.getroot()
    for d in root.findall(f"{{{SVG}}}defs"):
        root.remove(d)
    for el in root.iter():
        if el.tag in {PATH, f"{{{SVG}}}rect", f"{{{SVG}}}circle"}:
            el.set("fill", color)
            el.attrib.pop("stroke", None)
            if el.get("style"):
                el.set("style", re.sub(r"(fill|stroke)\s*:[^;]*;?", "", el.get("style")).strip())
    tree.write(VARIANTS / f"{base}-{suffix}.svg", encoding="utf-8", xml_declaration=True)


# ── 4. favicons / app icons / manifest / OG ───────────────────────────────────

def _square_svg(src: Path, out: Path, color: str | None = None) -> None:
    tree = ET.parse(src)
    root = tree.getroot()
    x, y, w, h = [float(v) for v in root.get("viewBox").split()]
    side = max(w, h) * 1.14
    cx, cy = x + w / 2, y + h / 2
    root.set("viewBox", f"{cx-side/2:.3f} {cy-side/2:.3f} {side:.3f} {side:.3f}")
    root.set("width", "512"); root.set("height", "512")
    if color:
        for d in root.findall(f"{{{SVG}}}defs"):
            root.remove(d)
        for el in root.iter():
            if el.tag == PATH:
                el.set("fill", color)
                if el.get("style"):
                    el.set("style", re.sub(r"fill\s*:[^;]*;?", "", el.get("style")).strip())
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)


def _png(svg: Path, out: Path, size: int) -> None:
    inkscape(str(svg), "--export-type=png", f"--export-filename={out}",
             f"--export-width={size}", f"--export-height={size}")


def build_icons() -> None:
    emblem = VARIANTS / "greena-emblem.svg"
    favsvg = PUBLIC / "favicon.svg"
    _square_svg(emblem, favsvg)
    _square_svg(VARIANTS / "greena-emblem-mono.svg", PUBLIC / "safari-pinned-tab.svg", color="#076524")

    for fname, sz in {"favicon-16.png": 16, "favicon-32.png": 32, "favicon-48.png": 48,
                      "apple-touch-icon.png": 180}.items():
        _png(favsvg, ICONS / fname, sz)
    for sz in (192, 512):
        _png(favsvg, ICONS / f"android-chrome-{sz}.png", sz)

    # maskable: emblem in the safe zone on a white plate
    mask = WORK / "maskable.svg"
    r = ET.parse(favsvg).getroot()
    vb = [float(v) for v in r.get("viewBox").split()]
    grow = vb[2] * 0.22
    r.set("viewBox", f"{vb[0]-grow:.3f} {vb[1]-grow:.3f} {vb[2]+2*grow:.3f} {vb[3]+2*grow:.3f}")
    r.insert(0, ET.Element(f"{{{SVG}}}rect", {"x": f"{vb[0]-grow}", "y": f"{vb[1]-grow}",
             "width": f"{vb[2]+2*grow}", "height": f"{vb[3]+2*grow}", "fill": "#ffffff"}))
    ET.ElementTree(r).write(mask, encoding="utf-8", xml_declaration=True)
    _png(mask, ICONS / "maskable-512.png", 512)

    imgs = [Image.open(ICONS / f"favicon-{s}.png").convert("RGBA") for s in (16, 32, 48)]
    imgs[0].save(PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

    # OG 1200x630 from the lockup on an off-white plate
    og = WORK / "og.svg"
    lr = ET.parse(VARIANTS / "greena-lockup.svg").getroot()
    lx, ly, lw, lh = [float(v) for v in lr.get("viewBox").split()]
    scale = min(820 / lw, 300 / lh)
    tx = (1200 - lw * scale) / 2 - lx * scale
    ty = (630 - lh * scale) / 2 - ly * scale
    o = ET.Element(f"{{{SVG}}}svg", {"viewBox": "0 0 1200 630", "width": "1200", "height": "630"})
    for d in lr.findall(f"{{{SVG}}}defs"):
        o.append(copy.deepcopy(d))
    ET.SubElement(o, f"{{{SVG}}}rect", {"width": "1200", "height": "630", "fill": "#f6f9f4"})
    wrap = ET.SubElement(o, f"{{{SVG}}}g", {"transform": f"translate({tx:.2f},{ty:.2f}) scale({scale:.4f})"})
    wrap.append(copy.deepcopy(next(g for g in lr if g.tag == f"{{{SVG}}}g")))
    ET.ElementTree(o).write(og, encoding="utf-8", xml_declaration=True)
    inkscape(str(og), "--export-type=png", f"--export-filename={PUBLIC / 'og-image.png'}",
             "--export-width=1200", "--export-height=630")
    print("[icons] favicon.svg/.ico, 16/32/48/180, android 192/512, maskable, safari, og-image")


def build_manifest() -> None:
    (PUBLIC / "manifest.webmanifest").write_text(json.dumps({
        "name": "Greena", "short_name": "Greena",
        "description": "Greena — the farm operating system.",
        "start_url": "/", "scope": "/", "display": "standalone",
        "background_color": "#0d0f12", "theme_color": "#076524",
        "icons": [
            {"src": "/icons/android-chrome-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icons/android-chrome-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }, indent=2), encoding="utf-8")
    print("[manifest] frontend/public/manifest.webmanifest")


if __name__ == "__main__":
    build_master()
    split_variants()
    build_icons()
    build_manifest()
    print("done.")
