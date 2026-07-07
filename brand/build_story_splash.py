"""
Greena — signature storytelling splash.

Built from the master-derived stacked lockup (variants/greena-lockup-stacked.svg),
WITHOUT touching path geometry (final resting frame == the exact Greena lockup).

Story (dark stage): silence -> the sprout rises (life) -> the swoosh slides in
beneath (intelligent support) -> pause -> "Greena" is drawn into existence
(calm engineering) -> stillness. Honors prefers-reduced-motion.

Path roles in the stacked lockup: path2/path3 = leaves, path9/path14 = swoosh
(gradient), path1 = the "Greena" wordmark.
"""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "variants" / "greena-lockup-stacked.svg"
OUT = ROOT / "preview"
OUT.mkdir(exist_ok=True)
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)

LEAVES, SWOOSH, WORDMARK = ["path2", "path3"], ["path9", "path14"], "path1"

tree = ET.parse(SRC)
root = tree.getroot()
vb = root.get("viewBox")
defs = root.find(f"{{{SVG}}}defs")
if defs is not None:
    for cp in defs.findall(f"{{{SVG}}}color-profile"):
        defs.remove(cp)
layer = root.find(f"{{{SVG}}}g")
kids = {c.get("id"): c for c in list(layer) if c.tag == f"{{{SVG}}}path"}


def strip_style(el, props):
    style = el.get("style", "")
    for p in props:
        style = re.sub(rf"{p}\s*:[^;]*;?", "", style)
    el.set("style", style.strip())


# Wordmark draws on: normalise length + let CSS/animation own stroke + fill.
wm = kids[WORDMARK]
wm.set("pathLength", "1")
wm.set("class", "ag-draw ag-draw-green")
strip_style(wm, ["stroke", "fill-opacity", "stroke-opacity", "stroke-width"])


def wrap(ids, cls, style=None):
    g = ET.Element(f"{{{SVG}}}g", {"class": cls})
    if style:
        g.set("style", style)
    for i in ids:
        g.append(kids[i])
    return g


new_layer = ET.Element(f"{{{SVG}}}g")
if layer.get("transform"):
    new_layer.set("transform", layer.get("transform"))
new_layer.append(wrap(SWOOSH, "ag-swoosh"))
new_layer.append(wrap([LEAVES[0]], "ag-leaf", "--i:0"))
new_layer.append(wrap([LEAVES[1]], "ag-leaf", "--i:1"))
new_layer.append(wrap([WORDMARK], "ag-word"))

svg_markup = (f'<svg viewBox="{vb}" xmlns="{SVG}" role="img" aria-label="Greena">'
              + (ET.tostring(defs, encoding="unicode") if defs is not None else "")
              + ET.tostring(new_layer, encoding="unicode") + "</svg>")

STYLE = """<style>
.greena-story{
  --g-ease-emerge: cubic-bezier(.16,1,.3,1);
  --g-stage:#0d0f12;
  display:grid; place-items:center; min-height:min(70vh,560px);
  background:radial-gradient(120% 120% at 50% 40%, #14171c 0%, var(--g-stage) 70%);
  border-radius:20px;
}
.greena-story .wrap{ display:flex; flex-direction:column; align-items:center; gap:22px; }
.greena-story svg{ width:min(340px,58vw); height:auto; overflow:visible; }
.ag-leaf{ opacity:0; animation:g-rise .72s var(--g-ease-emerge) both;
          animation-delay:calc(.35s + var(--i) * .12s); }
.ag-swoosh{ opacity:0; animation:g-slide .82s var(--g-ease-emerge) both; animation-delay:.80s; }
.ag-draw{ stroke-width:1.1; stroke-linejoin:round; stroke-linecap:round;
          stroke-dasharray:1; fill-opacity:0; }
.ag-draw-green{ stroke:#66b701; }
.ag-word .ag-draw{ animation:g-draw 1.15s var(--g-ease-emerge) 1.95s both; }
@keyframes g-rise{ from{opacity:0; transform:translateY(9px)} to{opacity:1; transform:none} }
@keyframes g-slide{ from{opacity:0; transform:translateX(-16px)} to{opacity:1; transform:none} }
@keyframes g-draw{
  0%  { stroke-dashoffset:1; fill-opacity:0; stroke-opacity:1; }
  62% { stroke-dashoffset:0; fill-opacity:0; stroke-opacity:1; }
  100%{ stroke-dashoffset:0; fill-opacity:1; stroke-opacity:0; }
}
.g-replay{ font:500 12px/1 ui-sans-serif,system-ui,sans-serif; letter-spacing:.03em;
  color:#c7cdd6; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.12);
  border-radius:999px; padding:8px 16px; cursor:pointer; transition:background .18s ease; }
.g-replay:hover{ background:rgba(255,255,255,.11); }
@media (prefers-reduced-motion: reduce){
  .ag-leaf,.ag-swoosh{ opacity:1; animation:none; transform:none; }
  .ag-draw{ animation:none; fill-opacity:1; stroke-opacity:0; }
}
</style>"""

SCRIPT = """<script>
(function(){var r=document.querySelector('.greena-story');if(!r)return;
var b=r.querySelector('.g-replay');
if(b)b.addEventListener('click',function(){
  r.querySelectorAll('.ag-leaf,.ag-swoosh,.ag-draw').forEach(function(el){
    el.style.animation='none';void el.offsetWidth;el.style.animation='';});});})();
</script>"""

FRAG = (STYLE + '<div class="greena-story" data-greena-motion="story"><div class="wrap">'
        + svg_markup + '<button class="g-replay" type="button">Replay</button></div></div>'
        + SCRIPT)
(OUT / "story.fragment.html").write_text(FRAG, encoding="utf-8")
(OUT / "story.html").write_text(
    '<!doctype html><meta charset="utf-8"><title>Greena splash</title>'
    '<style>html,body{margin:0;height:100%;background:#07080a}'
    'body{display:grid;place-items:center}</style>' + FRAG, encoding="utf-8")
print("wrote", OUT / "story.html")
