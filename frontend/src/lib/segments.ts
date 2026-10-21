import type { Segment } from "./types";

// Top-to-bottom dashboard order (drawing NP-ARCH-001). L2 and below are in scope but handled
// with care (CLAUDE.md rule 13): their cards carry an OT badge and stricter confirms.
export const SEGMENTS: Segment[] = ["L5", "L4", "DMZ", "L3", "Plantbus", "L2", "L1", "Mgmt"];

export const SEG_LABEL: Record<Segment, string> = {
  L5: "L5 · WAN",
  L4: "L4 · Enterprise",
  DMZ: "DMZ",
  L3: "L3 · Ops Mgmt",
  Plantbus: "Plantbus",
  L2: "L2 · System / Terminal",
  L1: "L1 · Control cells",
  Mgmt: "Host management",
};

export const SEG_VAR: Record<Segment, string> = {
  L5: "var(--seg-l5)",
  L4: "var(--seg-l4)",
  DMZ: "var(--seg-dmz)",
  L3: "var(--seg-l3)",
  Plantbus: "var(--seg-plantbus)",
  L2: "var(--seg-l2)",
  L1: "var(--seg-l1)",
  Mgmt: "var(--seg-mgmt)",
};
