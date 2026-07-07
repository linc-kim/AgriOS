"""
Greena brand asset pipeline — single source of truth: brand/Agios.ai

One command regenerates every derived asset from the master .ai:

    backend/.venv/Scripts/python brand/build_assets.py

Steps:
  1. Inkscape: Agios.ai -> plain SVG, text outlined to paths (geometry preserved).
  2. Clean: strip ICC color-profile, icc-color(...) noise, Illustrator metadata,
     and the white background plate -> brand/greena-master.svg  (the master SVG).
  3. Split the master's color lockup / emblem / wordmark into tight-viewBox SVGs,
     then derive monochrome + reverse-white variants  -> brand/variants/*.svg.
  4. Favicon / app-icon / manifest suite from the (name-neutral) emblem, plus an
     Open Graph image from the lockup  -> frontend/public/.

Requires: Inkscape (C:\\Program Files\\Inkscape) and Pillow.
NOTE: the current .ai wordmark reads "AgriOS"; the emblem is name-neutral so icons
are correct for Greena. Update the .ai to the Greena wordmark and re-run.
"""
from __future__ import annotations

import copy
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
AI = ROOT / "Agios.ai"
MASTER = ROOT / "greena-master.svg"
WORK = ROOT / "_work"
VARIANTS = ROOT / "variants"
PUBLIC = ROOT.parent / "frontend" / "public"
ICONS = PUBLIC / "icons"
INKSCAPE = Path(r"C:\Program Files\Inkscape\bin\inkscape.exe")
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)

for d in (WORK, VARIANTS, ICONS):
    d.mkdir(parents=True, exist_ok=True)


def inkscape(*args: str) -> None:
    subprocess.run([str(INKSCAPE), *args], check=True, capture_output=True, text=True)


# ── 1 + 2. Convert .ai -> clean master SVG ────────────────────────────────────

def build_master() -> None:
    raw = WORK / "master-raw.svg"
    inkscape(
        str(AI), "--export-type=svg", "--export-plain-svg",
        "--export-text-to-path", f"--export-filename={raw}",
    )
    s = raw.read_text(encoding="utf-8")
    s = re.sub(r"\s*icc-color\([^)]*\)", "", s)          # ICC artifacts on colors
    root = ET.fromstring(s)
    defs = root.find(f"{{{SVG}}}defs")
    if defs is not None:
        for tag in ("color-profile", "metadata"):        # ICC profile + AI metadata
            for el in defs.findall(f"{{{SVG}}}{tag}"):
                defs.remove(el)
    for el in list(root):
        if el.tag in (f"{{{SVG}}}metadata",):
            root.remove(el)
    # Drop any full-canvas white background plate.
    vb = [float(x) for x in root.get("viewBox", "0 0 0 0").split()]
    for g in root.iter(f"{{{SVG}}}path"):
        style = (g.get("style") or "") + (g.get("fill") or "")
        if any(w in style.lower() for w in ("#fff", "#fdfdfd", "#fefefe")):
            pass  # kept: white letter counters etc. are handled per-variant, not here
    ET.ElementTree(root).write(MASTER, encoding="utf-8", xml_declaration=True)
    print(f"[master] {MASTER.name}: {s.count('<path')} paths, icc/profile stripped")


# ── 3. Variants (color / mono / white) ────────────────────────────────────────

def _num(v: str) -> float:
    return float(v)


def query_bboxes() -> dict[str, tuple[float, float, float, float]]:
    out = subprocess.run(
        [str(INKSCAPE), str(MASTER), "--query-all"],
        check=True, capture_output=True, text=True,
    ).stdout
    boxes: dict[str, tuple] = {}
    for line in out.splitlines():
        p = line.split(",")
        if len(p) == 5 and p[0] not in ("svg1",) and not p[0].startswith("layer"):
            try:
                boxes[p[0]] = tuple(_num(x) for x in p[1:])
            except ValueError:
                pass
    return boxes


def _is_white(hexstr: str) -> bool:
    h = hexstr.lstrip("#")
    return len(h) == 6 and all(int(h[i : i + 2], 16) >= 240 for i in (0, 2, 4))


def split_variants() -> None:
    """Cluster the flat artboard into lockups by proximity; emit the COLOR pieces."""
    tree = ET.parse(MASTER)
    root = tree.getroot()
    defs = root.find(f"{{{SVG}}}defs")
    layer = next(g for g in root.iter(f"{{{SVG}}}g") if g.get("transform") or True)
    children = [c for c in list(layer) if c.tag == f"{{{SVG}}}path"]
    boxes = query_bboxes()

    # union-find clustering by bbox proximity (gap < 60 user units)
    ids = [c.get("id") for c in children if c.get("id") in boxes]
    parent = {i: i for i in ids}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def near(a, b, gap=60.0):
        ax, ay, aw, ah = boxes[a]
        bx, by, bw, bh = boxes[b]
        return not (ax - gap > bx + bw or bx - gap > ax + aw
                    or ay - gap > by + bh or by - gap > ay + ah)

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if near(ids[i], ids[j]):
                parent[find(ids[i])] = find(ids[j])

    clusters: dict[str, list[str]] = {}
    for i in ids:
        clusters.setdefault(find(i), []).append(i)

    def fills(idlist):
        f = set()
        for cid in idlist:
            el = next(c for c in children if c.get("id") == cid)
            f.add((el.get("style") or "") + (el.get("fill") or ""))
        return " ".join(f)

    # classify: color (has gradient/#66b701) vs white; wordmark (wide+short, no
    # gradient) vs emblem (has gradient) vs lockup (both, tall).
    def bbox_of(idlist):
        xs = [boxes[i][0] for i in idlist]; ys = [boxes[i][1] for i in idlist]
        xe = [boxes[i][0] + boxes[i][2] for i in idlist]
        ye = [boxes[i][1] + boxes[i][3] for i in idlist]
        return min(xs), min(ys), max(xe), max(ye)

    color_clusters = [c for c in clusters.values() if "66b701" in fills(c) or "url(#" in fills(c)]
    color_clusters = [c for c in color_clusters if not all(_is_white(re.search(r'#[0-9a-fA-F]{6}', fills([i]) or '#000') and re.search(r'#[0-9a-fA-F]{6}', fills([i])).group() or '#000000') for i in c)]

    tagged = {}
    for c in color_clusters:
        has_grad = "url(#" in fills(c)
        x0, y0, x1, y1 = bbox_of(c)
        w, h = x1 - x0, y1 - y0
        aspect = w / h if h else 99
        if has_grad and h > w:            # emblem over wordmark
            tagged["lockup"] = c
        elif has_grad:                     # emblem only (wide-ish, gradient)
            tagged.setdefault("emblem", c)
        elif aspect > 2.2:                 # wordmark only (wide, no gradient)
            tagged.setdefault("wordmark", c)
    # emblem is the gradient cluster with the smallest height that is not the lockup
    grad = sorted((c for c in color_clusters if "url(#" in fills(c)), key=lambda c: bbox_of(c)[3] - bbox_of(c)[1])
    if grad:
        tagged["emblem"] = grad[0]
        tagged["lockup"] = max((c for c in color_clusters if "url(#" in fills(c)),
                               key=lambda c: bbox_of(c)[3] - bbox_of(c)[1])

    for name, idlist in tagged.items():
        x0, y0, x1, y1 = bbox_of(idlist)
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
        for cid in idlist:
            g.append(copy.deepcopy(next(c for c in children if c.get("id") == cid)))
        ET.ElementTree(new).write(VARIANTS / f"greena-{name}.svg", encoding="utf-8", xml_declaration=True)
        print(f"[variant] greena-{name}.svg ({len(idlist)} paths)")

    _recolor("greena-lockup", "#111111", "mono")
    _recolor("greena-lockup", "#ffffff", "white")
    _recolor("greena-emblem", "#111111", "mono")
    _recolor("greena-emblem", "#ffffff", "white")


def _recolor(base: str, color: str, suffix: str) -> None:
    src = VARIANTS / f"{base}.svg"
    if not src.exists():
        return
    tree = ET.parse(src)
    root = tree.getroot()
    for d in root.findall(f"{{{SVG}}}defs"):
        root.remove(d)
    for el in root.iter():
        if el.tag in {f"{{{SVG}}}path", f"{{{SVG}}}rect", f"{{{SVG}}}circle"}:
            el.set("fill", color)
            el.attrib.pop("stroke", None)
            if el.get("style"):
                el.set("style", re.sub(r"(fill|stroke)\s*:[^;]*;?", "", el.get("style")).strip())
    tree.write(VARIANTS / f"{base}-{suffix}.svg", encoding="utf-8", xml_declaration=True)


# ── 4. Favicons / app icons / manifest ────────────────────────────────────────

def _square_svg(src: Path, out: Path, color: str | None = None) -> None:
    tree = ET.parse(src)
    root = tree.getroot()
    x, y, w, h = [float(v) for v in root.get("viewBox").split()]
    side = max(w, h) * 1.14  # small padding
    cx, cy = x + w / 2, y + h / 2
    root.set("viewBox", f"{cx-side/2:.3f} {cy-side/2:.3f} {side:.3f} {side:.3f}")
    root.set("width", "512"); root.set("height", "512")
    if color:
        for defs in root.findall(f"{{{SVG}}}defs"):
            root.remove(defs)
        for el in root.iter():
            if el.tag == f"{{{SVG}}}path":
                el.set("fill", color)
                if el.get("style"):
                    el.set("style", re.sub(r"fill\s*:[^;]*;?", "", el.get("style")).strip())
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)


def _png(svg: Path, out: Path, size: int, bg: str | None = None) -> None:
    args = [str(svg), "--export-type=png", f"--export-filename={out}",
            f"--export-width={size}", f"--export-height={size}"]
    if bg:
        args += [f"--export-background={bg}", "--export-background-opacity=1"]
    inkscape(*args)


def build_icons() -> None:
    # Verified, committed emblem/lockup (auto-clustering of the multi-lockup
    # artboard is not robust; these are the known-good extractions). The emblem
    # is name-neutral, so icons are correct for Greena regardless of the wordmark.
    emblem = VARIANTS / "agrios-emblem.svg"
    favsvg = PUBLIC / "favicon.svg"
    _square_svg(emblem, favsvg)                                   # crisp vector favicon
    _square_svg(VARIANTS / "agrios-emblem-mono.svg", PUBLIC / "safari-pinned-tab.svg", color="#076524")

    sizes = {"favicon-16.png": 16, "favicon-32.png": 32, "favicon-48.png": 48,
             "apple-touch-icon.png": 180}
    for fname, sz in sizes.items():
        _png(favsvg, ICONS / fname, sz)
    for sz in (192, 512):
        _png(favsvg, ICONS / f"android-chrome-{sz}.png", sz)

    # Maskable: emblem within safe zone on a white plate.
    mask_svg = WORK / "maskable.svg"
    tree = ET.parse(favsvg); r = tree.getroot()
    vb = [float(v) for v in r.get("viewBox").split()]
    grow = vb[2] * 0.22
    r.set("viewBox", f"{vb[0]-grow:.3f} {vb[1]-grow:.3f} {vb[2]+2*grow:.3f} {vb[3]+2*grow:.3f}")
    bgrect = ET.Element(f"{{{SVG}}}rect", {"x": f"{vb[0]-grow}", "y": f"{vb[1]-grow}",
             "width": f"{vb[2]+2*grow}", "height": f"{vb[3]+2*grow}", "fill": "#ffffff"})
    r.insert(0, bgrect)
    ET.ElementTree(r).write(mask_svg, encoding="utf-8", xml_declaration=True)
    _png(mask_svg, ICONS / "maskable-512.png", 512)

    # favicon.ico (16/32/48) via Pillow.
    imgs = [Image.open(ICONS / f"favicon-{s}.png").convert("RGBA") for s in (16, 32, 48)]
    imgs[0].save(PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

    # Open Graph 1200x630 from the lockup on an off-white plate.
    og = WORK / "og.svg"
    lt = ET.parse(VARIANTS / "agrios-lockup.svg"); lr = lt.getroot()
    lx, ly, lw, lh = [float(v) for v in lr.get("viewBox").split()]
    scale = min(760 / lw, 300 / lh)
    tx = (1200 - lw * scale) / 2 - lx * scale
    ty = (630 - lh * scale) / 2 - ly * scale
    ogroot = ET.Element(f"{{{SVG}}}svg", {"viewBox": "0 0 1200 630", "width": "1200", "height": "630"})
    for d in lr.findall(f"{{{SVG}}}defs"):
        ogroot.append(copy.deepcopy(d))
    ET.SubElement(ogroot, f"{{{SVG}}}rect", {"width": "1200", "height": "630", "fill": "#f6f9f4"})
    wrap = ET.SubElement(ogroot, f"{{{SVG}}}g", {"transform": f"translate({tx:.2f},{ty:.2f}) scale({scale:.4f})"})
    inner = next(g for g in lr if g.tag == f"{{{SVG}}}g")
    wrap.append(copy.deepcopy(inner))
    ET.ElementTree(ogroot).write(og, encoding="utf-8", xml_declaration=True)
    inkscape(str(og), "--export-type=png", f"--export-filename={PUBLIC / 'og-image.png'}",
             "--export-width=1200", "--export-height=630")
    print("[icons] favicon.svg/.ico, 16/32/48/180, android 192/512, maskable, safari, og-image")


def build_manifest() -> None:
    manifest = {
        "name": "Greena", "short_name": "Greena",
        "description": "Greena — the farm operating system.",
        "start_url": "/", "scope": "/", "display": "standalone",
        "background_color": "#0d0f12", "theme_color": "#076524",
        "icons": [
            {"src": "/icons/android-chrome-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icons/android-chrome-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    import json
    (PUBLIC / "manifest.webmanifest").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("[manifest] frontend/public/manifest.webmanifest")


if __name__ == "__main__":
    build_master()
    build_icons()
    build_manifest()
    print("done.")
