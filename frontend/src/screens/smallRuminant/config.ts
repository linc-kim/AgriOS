/**
 * Per-species UI vocabulary for the Small Ruminant workspaces — the frontend
 * mirror of the backend `small_ruminant_species_config`. One shared screen set is
 * parameterised by this config so goat and sheep render from the same components.
 */
import type { Species } from "@/api/smallRuminant";

export interface SpeciesUi {
  species: Species;
  title: string;          // workspace title
  collective: string;     // herd | flock
  offspring: string;      // kid | lamb
  sexes: string[];        // valid sex tokens
  productionLabel: string; // Dairy | Wool
  productionPath: string;  // dairy | wool
  producesMilk: boolean;
  producesWool: boolean;
}

const PURPOSES_COMMON = [
  "meat", "dairy", "fiber", "wool", "breeding", "show", "pet",
  "replacement", "genetic_improvement", "conservation", "educational", "mixed", "unknown",
];

export const PURPOSES = PURPOSES_COMMON;

export const STATUSES = ["active", "sold", "transferred", "deceased", "culled", "archived"];

export const SPECIES_UI: Record<Species, SpeciesUi> = {
  goat: {
    species: "goat",
    title: "Goats",
    collective: "herd",
    offspring: "kid",
    sexes: ["buck", "doe", "wether", "unknown"],
    productionLabel: "Dairy",
    productionPath: "dairy",
    producesMilk: true,
    producesWool: false,
  },
  sheep: {
    species: "sheep",
    title: "Sheep",
    collective: "flock",
    offspring: "lamb",
    sexes: ["ram", "ewe", "wether", "unknown"],
    productionLabel: "Wool",
    productionPath: "wool",
    producesMilk: true,
    producesWool: true,
  },
};
