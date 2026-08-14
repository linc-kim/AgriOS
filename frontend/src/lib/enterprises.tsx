/**
 * Greena — the farming enterprises Greena actually supports (single source).
 *
 * These are the SHIPPED modules only, grounded in real backend endpoints and
 * frontend routes: poultry (flocks), ornamental birds (aviculture), black
 * soldier fly, rabbits, goats, sheep, pigs. **Fish/aquaculture is NOT included**
 * — it is not implemented. Both the homepage showcase and the per-enterprise
 * pages read from this list, so marketing can never claim more than the product.
 *
 * Emoji marks avoid an icon dependency and read clearly at every size.
 */

export interface Enterprise {
  slug: string;
  name: string;
  emoji: string;
  /** One-line positioning. */
  tagline: string;
  /** Short paragraph for the enterprise page hero + showcase. */
  summary: string;
  /** Real, shipped capabilities — nothing aspirational. */
  capabilities: string[];
  /** The in-app area this maps to (for signed-in users). */
  appPath: string;
}

export const ENTERPRISES: Enterprise[] = [
  {
    slug: "poultry",
    name: "Poultry",
    emoji: "🐔",
    tagline: "Broilers, layers and everything in between.",
    summary:
      "Run every flock from placement to sale with live bird counts, mortality, weights and vaccinations — and know the feed conversion and profit per batch without waiting for the cycle to end.",
    capabilities: [
      "Flock lifecycle: placement → sale with live counts",
      "Daily egg collection and lay-rate tracking",
      "Feed conversion (FCR) calculated per batch",
      "Vaccinations, treatments and disease alerts",
      "Feed cost per bird and profit per flock",
    ],
    appPath: "/livestock",
  },
  {
    slug: "ornamental-birds",
    name: "Ornamental Birds",
    emoji: "🦜",
    tagline: "Aviaries, breeding pairs and hatch results.",
    summary:
      "Purpose-built for aviculture: manage aviaries and individual birds, track breeding pairs and incubation, and keep health records that follow each line over long cycles.",
    capabilities: [
      "Aviaries and individual bird profiles",
      "Breeding pairs and lineage",
      "Incubation and hatch tracking",
      "Health records per bird",
      "Collection dashboards and reports",
    ],
    appPath: "/aviculture",
  },
  {
    slug: "black-soldier-fly",
    name: "Black Soldier Fly",
    emoji: "🪰",
    tagline: "Insect protein, batch by batch.",
    summary:
      "Manage the full BSF lifecycle — feedstock in, batches through growth stages, environment conditions, and harvest out — with the finances of each batch tracked alongside.",
    capabilities: [
      "Batches through each growth stage",
      "Feedstock intake and consumption",
      "Environment (temperature, humidity) tracking",
      "Harvest yields and quality",
      "Finance per batch",
    ],
    appPath: "/bsf",
  },
  {
    slug: "rabbit",
    name: "Rabbits",
    emoji: "🐇",
    tagline: "Does, bucks, kits and cages.",
    summary:
      "Track breeding does and bucks, kindling and weaning, hutch and cage housing, growth to market and health — with a profile for every animal.",
    capabilities: [
      "Breeding: mating, kindling, weaning",
      "Housing across hutches and cages",
      "Growth to market weight",
      "Health and treatments",
      "Per-animal profiles and reports",
    ],
    appPath: "/rabbit",
  },
  {
    slug: "goat",
    name: "Goats",
    emoji: "🐐",
    tagline: "Dairy and meat herds.",
    summary:
      "Manage the herd with breeding, health and growth records, daily milk yield per animal for dairy goats, and reports across the whole operation.",
    capabilities: [
      "Herd and per-animal records",
      "Daily milk yield per animal (dairy)",
      "Breeding and kidding",
      "Health and growth tracking",
      "Herd reports",
    ],
    appPath: "/goat",
  },
  {
    slug: "sheep",
    name: "Sheep",
    emoji: "🐑",
    tagline: "Flocks, wool and lambs.",
    summary:
      "Run the flock with breeding, health and growth records, wool production tracking, and per-animal history from lamb to sale.",
    capabilities: [
      "Flock and per-animal records",
      "Wool production tracking",
      "Breeding and lambing",
      "Health and growth tracking",
      "Flock reports",
    ],
    appPath: "/sheep",
  },
  {
    slug: "swine",
    name: "Pigs",
    emoji: "🐖",
    tagline: "Farrow to finish.",
    summary:
      "Cover the pig operation end to end — sows and boars, pregnancy and farrowing, feed and growth, housing and biosecurity — with health records throughout.",
    capabilities: [
      "Breeding: sows, boars, pregnancy, farrowing",
      "Feed and growth to finish",
      "Housing and biosecurity",
      "Health records",
      "Herd reports",
    ],
    appPath: "/swine",
  },
];

export const enterpriseBySlug = (slug: string): Enterprise | undefined =>
  ENTERPRISES.find((e) => e.slug === slug);
