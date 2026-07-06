"""
AGRIOS — Signature storytelling splash.

Builds the brand's signature motion from the isolated color lockup, WITHOUT
touching path geometry (final resting frame == master lockup, pixel-exact).

Story (dark stage, silence -> life -> intelligence -> word -> stillness):
  1. silence
  2. sprout rises (two leaves, staggered)            = life beginning
  3. swoosh slides in beneath                         = intelligent support
  4. brief pause                                      = the emblem is remembered
  5. "Agri" is drawn into existence (outline -> fill) = calm engineering
  6. "OS" arrives, drawn faster + crisper easing      = precise, technical
  7. stillness (no loop, no shimmer)

Each animated element is wrapped so CSS transforms COMPOSE with the element's own
SVG transform attribute (a CSS `transform` on the element itself would replace it).
Honors prefers-reduced-motion. Motion tokens mirror brand/MOTION-TOKENS.
"""
from __future__ import annotations
import copy
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "variants" / "agrios-lockup.svg"
OUT = ROOT / "preview"
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)

tree = ET.parse(SRC)
root = tree.getroot()
vb = root.get("viewBox")
defs = root.find(f"{{{SVG}}}defs")
# Drop the unused embedded ICC color-profile blob (~12 KB of base64).
if defs is not None:
    for cp in defs.findall(f"{{{SVG}}}color-profile"):
        defs.remove(cp)
layer = root.find(f"{{{SVG}}}g")
kids = {c.get("id"): c for c in list(layer)}

def strip_style(el, props):
    """Remove given CSS props from an element's inline style so classes/animations win."""
    style = el.get("style", "")
    for p in props:
        style = re.sub(rf"{p}\s*:[^;]*;?", "", style)
    el.set("style", style.strip())

def wrap(ids, cls, style=None):
    g = ET.Element(f"{{{SVG}}}g")
    g.set("class", cls)
    if style:
        g.set("style", style)
    for i in ids:
        g.append(kids[i])
    return g

# Prepare draw paths (normalized length + draw class on the actual path).
# Strip inline stroke / fill-opacity so the draw CSS + animation control them.
for pid, cls in (("path1", "ag-draw ag-draw-green"), ("text1", "ag-draw ag-draw-blue")):
    kids[pid].set("pathLength", "1")
    kids[pid].set("class", cls)
    strip_style(kids[pid], ["stroke", "fill-opacity", "stroke-opacity", "stroke-width"])

# Rebuild the layer children in the right order (defs stays in <defs>).
new_layer = ET.Element(f"{{{SVG}}}g")
if layer.get("transform"):
    new_layer.set("transform", layer.get("transform"))
new_layer.append(wrap(["path14", "path9"], "ag-swoosh"))         # swoosh under
new_layer.append(wrap(["path2"], "ag-leaf", "--i:0"))            # leaf 1
new_layer.append(wrap(["path3"], "ag-leaf", "--i:1"))            # leaf 2
new_layer.append(wrap(["path1"], "ag-agri"))                     # Agri
new_layer.append(wrap(["text1"], "ag-os"))                       # OS

svg_open = f'<svg viewBox="{vb}" xmlns="{SVG}" role="img" aria-label="AGRIOS">'
inner_defs = ET.tostring(defs, encoding="unicode") if defs is not None else ""
inner_layer = ET.tostring(new_layer, encoding="unicode")
svg_markup = f"{svg_open}{inner_defs}{inner_layer}</svg>"

STYLE = """<style>
.agrios-story{
  /* ── AGRIOS motion tokens ─────────────────────────────── */
  --ag-ease-emerge: cubic-bezier(.16,1,.3,1);   /* calm, organic          */
  --ag-ease-precise: cubic-bezier(.2,.8,.2,1);  /* crisp, technical (OS)  */
  --ag-stage:#0d0f12;                            /* charcoal, never #000   */
  display:grid; place-items:center; min-height:min(70vh,560px);
  background:radial-gradient(120% 120% at 50% 40%, #14171c 0%, var(--ag-stage) 70%);
  border-radius:20px;
}
.agrios-story .wrap{ display:flex; flex-direction:column; align-items:center; gap:22px; }
.agrios-story svg{ width:min(360px,60vw); height:auto; overflow:visible; }

/* leaves rise (staggered), swoosh slides in, wordmark draws on */
.ag-leaf{ opacity:0; animation:ag-rise .72s var(--ag-ease-emerge) both;
          animation-delay:calc(.35s + var(--i) * .12s); }
.ag-swoosh{ opacity:0; animation:ag-slide .82s var(--ag-ease-emerge) both; animation-delay:.80s; }
.ag-draw{ stroke-width:1.3; stroke-linejoin:round; stroke-linecap:round;
          stroke-dasharray:1; fill-opacity:0; }
.ag-draw-green{ stroke:#66b701; }
.ag-draw-blue{ stroke:#0359b4; }
.ag-agri .ag-draw{ animation:ag-draw 1.0s var(--ag-ease-emerge) 2.00s both; }
.ag-os   .ag-draw{ animation:ag-draw .70s var(--ag-ease-precise) 2.78s both; }

@keyframes ag-rise{ from{opacity:0; transform:translateY(9px)} to{opacity:1; transform:none} }
@keyframes ag-slide{ from{opacity:0; transform:translateX(-16px)} to{opacity:1; transform:none} }
@keyframes ag-draw{
  0%  { stroke-dashoffset:1; fill-opacity:0; stroke-opacity:1; }
  58% { stroke-dashoffset:0; fill-opacity:0; stroke-opacity:1; }
  100%{ stroke-dashoffset:0; fill-opacity:1; stroke-opacity:0; }
}

.ag-replay{ font:500 12px/1 ui-sans-serif,system-ui,sans-serif; letter-spacing:.03em;
  color:#c7cdd6; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.12);
  border-radius:999px; padding:8px 16px; cursor:pointer; transition:background .18s ease; }
.ag-replay:hover{ background:rgba(255,255,255,.11); }

@media (prefers-reduced-motion: reduce){
  .ag-leaf,.ag-swoosh{ opacity:1; animation:none; transform:none; }
  .ag-draw{ animation:none; fill-opacity:1; stroke-opacity:0; }
}
</style>"""

SCRIPT = """<script>
(function(){
  var r=document.querySelector('.agrios-story'); if(!r)return;
  var b=r.querySelector('.ag-replay');
  if(b)b.addEventListener('click',function(){
    r.querySelectorAll('.ag-leaf,.ag-swoosh,.ag-draw').forEach(function(el){
      el.style.animation='none'; void el.offsetWidth; el.style.animation='';
    });
  });
})();
</script>"""

FRAG = (STYLE +
        '<div class="agrios-story" data-agrios-motion="story"><div class="wrap">' +
        svg_markup +
        '<button class="ag-replay" type="button">Replay</button></div></div>' +
        SCRIPT)

(OUT / "story.fragment.html").write_text(FRAG, encoding="utf-8")
(OUT / "story.html").write_text(
    '<!doctype html><meta charset="utf-8"><title>AGRIOS splash</title>'
    '<style>html,body{margin:0;height:100%;background:#07080a}'
    'body{display:grid;place-items:center}</style>' + FRAG, encoding="utf-8")
print("wrote", OUT / "story.html")
print("wrote", OUT / "story.fragment.html")
