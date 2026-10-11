import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Schemas } from "@/lib/api/client";
import { matches, ResearchIndex, type Filters } from "./research-index";

const e = (o: Partial<Schemas["ResearchEntry"]>): Schemas["ResearchEntry"] => ({
  id: "X",
  kind: "paper",
  title: "t",
  games: [],
  status: "FULL_TEXT_READ",
  verification: "FULL_TEXT_READ",
  summary: "",
  urls: [],
  dois: [],
  source_file: "research/PRIOR_ART_MATRIX.csv",
  related: [],
  ...o,
});

const ENTRIES = [
  e({ id: "P01", title: "Optimal counterfeiting attacks", games: ["W1", "W1_CV"], dois: ["10.1/abc"] }),
  e({ id: "T-MVW12-THM1", kind: "theorem", title: "MVW Theorem 1", games: ["W1"], status: "VERIFIED_FROM_SOURCE" }),
  e({ id: "T-GAV25", kind: "theorem", title: "Gavinsky construction", games: ["A1"], status: "NOT_VERIFIED" }),
];
const ALL: Filters = { q: "", kind: "all", game: "", tone: "all" };

describe("research index", () => {
  it("filters by text (all terms), kind, game and verification tone", () => {
    expect(ENTRIES.filter((x) => matches(x, { ...ALL, q: "counterfeiting W1_CV" })).map((x) => x.id)).toEqual(["P01"]);
    expect(ENTRIES.filter((x) => matches(x, { ...ALL, q: "10.1/abc" })).map((x) => x.id)).toEqual(["P01"]);
    expect(ENTRIES.filter((x) => matches(x, { ...ALL, kind: "theorem" }))).toHaveLength(2);
    expect(ENTRIES.filter((x) => matches(x, { ...ALL, game: "W1" }))).toHaveLength(2);
    expect(ENTRIES.filter((x) => matches(x, { ...ALL, tone: "open" })).map((x) => x.id)).toEqual(["T-GAV25"]);
  });

  it("renders grouped rows, narrows on search and offers to clear", async () => {
    render(<ResearchIndex entries={ENTRIES} initial={ALL} />);
    expect(screen.getByRole("heading", { name: /Papers/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /P01/ })).toHaveAttribute("href", "/research/P01");
    await userEvent.type(screen.getByRole("searchbox"), "gavinsky");
    expect(screen.queryByRole("link", { name: /P01/ })).not.toBeInTheDocument();
    expect(screen.getByText("Gavinsky construction")).toBeInTheDocument();
    expect(window.location.search).toContain("q=gavinsky");
    await userEvent.click(screen.getAllByRole("button", { name: /Clear filters/ })[0]!);
    expect(screen.getByRole("link", { name: /P01/ })).toBeInTheDocument();
  });

  it("shows an explicit empty result", async () => {
    render(<ResearchIndex entries={ENTRIES} initial={{ ...ALL, q: "zzz-nothing" }} />);
    expect(within(screen.getByRole("status")).getByText(/No entry matches/)).toBeInTheDocument();
  });
});
