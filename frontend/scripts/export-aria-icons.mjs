/**
 * Rasterise the ARIA SVG sources to PNG.
 *
 * Run: node scripts/export-aria-icons.mjs
 *
 * The SVGs in public/brand/aria are the source of truth; these exports are
 * derived, so regenerating is always safe. Kept as a script rather than
 * checked-in-only binaries so the PNGs can never silently drift from the mark.
 *
 * Size choices: the primary keeps its venation down to 32px, below which the
 * veins turn to mush and the simplified variant takes over. Simplified is only
 * exported small, because that is the only place it should ever be used.
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const here = dirname(fileURLToPath(import.meta.url));
const SRC = join(here, "..", "public", "brand", "aria");
const OUT = join(SRC, "png");

const JOBS = [
  { file: "aria-primary", sizes: [512, 256, 128, 64, 32] },
  { file: "aria-simplified", sizes: [64, 32, 16] },
  { file: "aria-monochrome", sizes: [512, 256, 128, 64, 32] },
  { file: "aria-light", sizes: [512, 256, 128, 64] },
  { file: "aria-dark", sizes: [512, 256, 128, 64] },
];

await mkdir(OUT, { recursive: true });

let count = 0;
for (const job of JOBS) {
  let svg = await readFile(join(SRC, `${job.file}.svg`), "utf-8");

  // currentColor has no meaning outside a DOM; bake it so the file stands alone.
  svg = svg.replaceAll("currentColor", "#076524");

  for (const size of job.sizes) {
    const target = join(OUT, `${job.file}-${size}.png`);
    await sharp(Buffer.from(svg), { density: 384 })
      .resize(size, size, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
      .png({ compressionLevel: 9 })
      .toFile(target);
    count++;
  }
}

console.log(`Exported ${count} PNGs to ${OUT}`);
