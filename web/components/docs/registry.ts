/**
 * Documentation table of contents — metadata only (no content), so the shell's ⌘K palette and
 * breadcrumbs can import it cheaply. Content lives in components/docs/content/*.tsx keyed by the
 * same section ids; docs.test.tsx asserts every section here has content and vice versa.
 */
export interface DocSectionMeta {
  id: string;
  title: string;
}

export interface DocPageMeta {
  slug: string;
  title: string;
  group: "Start" | "Reference" | "Science";
  description: string;
  sections: DocSectionMeta[];
}

/** OpenAPI tags in display order; the API reference renders one section per tag (checked against openapi.json in tests). */
export const API_TAGS = ["meta", "protocols", "lab", "benchmarks", "certificates", "research", "evidence"] as const;

export const DOCS: DocPageMeta[] = [
  {
    slug: "getting-started",
    title: "Getting started",
    group: "Start",
    description: "Install the Python environment and the web app, run the API, run the tests.",
    sections: [
      { id: "what-qmint-is", title: "What QMint is" },
      { id: "prerequisites", title: "Prerequisites" },
      { id: "python", title: "Python environment" },
      { id: "api", title: "Run the research API" },
      { id: "web", title: "Run the web app" },
      { id: "tests", title: "Run the tests" },
      { id: "support-license", title: "Support, license and disclosure" },
    ],
  },
  {
    slug: "architecture",
    title: "Architecture",
    group: "Start",
    description: "Research lanes, frozen contracts C0–C7, security games and how evidence reaches the UI.",
    sections: [
      { id: "lanes", title: "Research lanes" },
      { id: "contracts", title: "Frozen contracts C0–C7" },
      { id: "games", title: "Security games" },
      { id: "evidence-flow", title: "From lane to screen" },
      { id: "web", title: "Web application" },
    ],
  },
  {
    slug: "examples",
    title: "Example experiments",
    group: "Start",
    description: "Commands that were run and checked on this checkout, with what they write.",
    sections: [
      { id: "doctor", title: "Check the environment" },
      { id: "reproduce-bounds", title: "Reproduce published bounds" },
      { id: "attack-report", title: "Attack suite and SDP certificates" },
      { id: "classical", title: "Classical baselines" },
      { id: "core-run", title: "Offline core run" },
      { id: "api-calls", title: "Call the API" },
    ],
  },
  {
    slug: "api",
    title: "API reference",
    group: "Reference",
    description: "Every endpoint of the FastAPI research API, generated from openapi.json.",
    sections: [
      { id: "conventions", title: "Conventions" },
      ...API_TAGS.map((t) => ({ id: `tag-${t}`, title: t.charAt(0).toUpperCase() + t.slice(1) })),
      { id: "errors", title: "Errors" },
    ],
  },
  {
    slug: "cli",
    title: "CLI",
    group: "Reference",
    description: "The `qmint` command, its subcommands, exit codes and module entrypoints.",
    sections: [
      { id: "usage", title: "Usage" },
      { id: "builtin", title: "Built-in commands" },
      { id: "lane-commands", title: "Lane commands" },
      { id: "exit-codes", title: "Exit codes" },
      { id: "modules", title: "Module entrypoints" },
    ],
  },
  {
    slug: "reproducibility",
    title: "Reproducibility",
    group: "Science",
    description: "Pinned environments, seeds, records and manifests.",
    sections: [
      { id: "environment", title: "Environment" },
      { id: "configuration", title: "Configuration" },
      { id: "runs", title: "Runs" },
      { id: "records", title: "Records" },
      { id: "entrypoints", title: "Lane entrypoint convention" },
    ],
  },
  {
    slug: "methodology",
    title: "Methodology and evidence",
    group: "Science",
    description: "Evidence kinds, response statuses, computation methods and the rules every number follows.",
    sections: [
      { id: "principles", title: "Principles" },
      { id: "evidence-kinds", title: "Evidence kinds" },
      { id: "certificate-statuses", title: "Certificate statuses" },
      { id: "api-statuses", title: "Response statuses" },
      { id: "methods", title: "Computation methods" },
      { id: "verification", title: "Research verification statuses" },
    ],
  },
  {
    slug: "limitations",
    title: "Limitations",
    group: "Science",
    description: "What QMint does not show, and why.",
    sections: [
      { id: "scope", title: "Scope" },
      { id: "hardware", title: "Hardware" },
      { id: "proofs", title: "Proofs and certificates" },
      { id: "data", title: "Data" },
      { id: "comparisons", title: "Quantum vs classical" },
      { id: "platform", title: "Platform" },
    ],
  },
];

export const DOC_GROUPS = ["Start", "Reference", "Science"] as const;

export function docBySlug(slug: string): DocPageMeta | undefined {
  return DOCS.find((d) => d.slug === slug);
}

export function docNeighbours(slug: string): { prev?: DocPageMeta; next?: DocPageMeta } {
  const i = DOCS.findIndex((d) => d.slug === slug);
  return { prev: i > 0 ? DOCS[i - 1] : undefined, next: i >= 0 && i < DOCS.length - 1 ? DOCS[i + 1] : undefined };
}
