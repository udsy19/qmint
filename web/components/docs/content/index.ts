import type * as React from "react";
import { content as api } from "./api";
import { content as architecture } from "./architecture";
import { content as cli } from "./cli";
import { content as examples } from "./examples";
import { content as gettingStarted } from "./getting-started";
import { content as limitations } from "./limitations";
import { content as methodology } from "./methodology";
import { content as reproducibility } from "./reproducibility";

/** slug → section id → content. Keys must match components/docs/registry.ts (asserted in docs.test.tsx). */
export const DOC_CONTENT: Record<string, Record<string, React.ReactNode>> = {
  "getting-started": gettingStarted,
  architecture,
  examples,
  api,
  cli,
  reproducibility,
  methodology,
  limitations,
};
