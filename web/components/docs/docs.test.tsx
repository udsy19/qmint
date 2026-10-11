import { describe, expect, it } from "vitest";
import openapi from "@/lib/api/openapi.json";
import { allTags } from "./api-reference";
import { DOC_CONTENT } from "./content";
import { API_TAGS, DOCS, docNeighbours } from "./registry";

describe("docs registry", () => {
  it("has content for every section and no orphan content", () => {
    expect(Object.keys(DOC_CONTENT).sort()).toEqual(DOCS.map((d) => d.slug).sort());
    for (const d of DOCS) {
      expect(Object.keys(DOC_CONTENT[d.slug]!).sort(), d.slug).toEqual(d.sections.map((s) => s.id).sort());
    }
  });

  it("has unique slugs and section ids per page", () => {
    expect(new Set(DOCS.map((d) => d.slug)).size).toBe(DOCS.length);
    for (const d of DOCS) expect(new Set(d.sections.map((s) => s.id)).size, d.slug).toBe(d.sections.length);
  });

  it("documents every OpenAPI tag", () => {
    expect([...API_TAGS].sort()).toEqual(allTags().sort());
    expect(Object.keys((openapi as { paths: object }).paths).length).toBeGreaterThan(10);
  });

  it("links pages in order", () => {
    expect(docNeighbours(DOCS[0]!.slug).prev).toBeUndefined();
    expect(docNeighbours(DOCS[0]!.slug).next?.slug).toBe(DOCS[1]!.slug);
  });
});
