/**
 * UI vocabulary for the Swine workspace — the frontend mirror of the backend
 * `swine_config`. Single species, so one screen set (no discriminator).
 */
export const SEXES = ["boar", "sow", "gilt", "barrow", "unknown"];
export const PURPOSES = [
  "meat", "breeding", "replacement", "show", "genetic_improvement", "mixed", "unknown",
];
export const PRODUCTION_STAGES = [
  "piglet", "weaner", "nursery", "grower", "finisher", "breeding",
  "replacement", "cull", "retired", "unknown",
];
export const STATUSES = ["active", "sold", "transferred", "deceased", "culled", "archived"];
