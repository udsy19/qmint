import { describe, expect, it } from "vitest";
import { DEFAULT_FILTERS, filterRows, networkLabel, sortRows, type Row } from "./model";

function row(p: Partial<Row> & { id: string }): Row {
  return {
    adversary: "",
    classical_bytes: null,
    code: "H1",
    comparability_pair: null,
    comparability_status: "QUALIFIED",
    cross_check: null,
    double_spend: { outcome: "PREVENTED", successful: 0, detail: "" },
    environment_lock: null,
    evidence_kind: "MODELLED_LATENCY",
    family: "classical",
    flexibility: "online_any_site",
    issuer_calls: null,
    label: "H1 online ledger",
    latency_basis: null,
    latency_unavailable_reason: null,
    local_validation: null,
    method: "",
    network_id: "net-h-synthetic-2site-10km",
    pre_distribution: "",
    pre_presentation_commit: null,
    privacy: "none",
    protocol_id: "classical_h1_online_ledger",
    record_git_sha: null,
    reproduce: "",
    site_count: 2,
    sources: [],
    trust_model: "",
    trusted_hardware: "",
    variant: null,
    ...p,
  } as Row;
}

const q = (v: number) => ({ id: "x", label: "x", value: v, unit: "ns", evidence_kind: "MODELLED_LATENCY", method: "event_simulation", source: "s" }) as Row["local_validation"];

describe("benchmark explorer model", () => {
  const rows = [
    row({ id: "a", local_validation: q(136_712) }),
    row({ id: "b", code: "H0", double_spend: { outcome: "SUCCEEDS", successful: 1, detail: "" }, comparability_status: "INCOMPARABLE", local_validation: q(10_000) }),
    row({ id: "s1", family: "quantum", code: "S1", network_id: null, comparability_status: "REFERENCE", double_spend: { outcome: "BOUNDED_BY_THEOREM", successful: null, detail: "" } }),
    row({ id: "c", network_id: "net-h-synthetic-3site-100km", local_validation: q(400_000) }),
  ];

  it("keeps the quantum reference row under every network filter", () => {
    const f = { ...DEFAULT_FILTERS, network: "net-h-synthetic-3site-100km" };
    expect(filterRows(rows, f).map((r) => r.id)).toEqual(["s1", "c"]);
  });

  it("filters by outcome and comparability", () => {
    expect(filterRows(rows, { ...DEFAULT_FILTERS, outcome: "SUCCEEDS" }).map((r) => r.id)).toEqual(["b"]);
    expect(filterRows(rows, { ...DEFAULT_FILTERS, comparability: "INCOMPARABLE" }).map((r) => r.id)).toEqual(["b"]);
  });

  it("sorts latency with missing values last in both directions", () => {
    expect(sortRows(rows, "local", "asc").map((r) => r.id)).toEqual(["b", "a", "c", "s1"]);
    expect(sortRows(rows, "local", "desc").map((r) => r.id)).toEqual(["c", "a", "b", "s1"]);
  });

  it("orders double-spend outcomes by meaning, not alphabetically", () => {
    expect(sortRows(rows, "outcome", "asc")[0]!.double_spend.outcome).toBe("PREVENTED");
    expect(sortRows(rows, "outcome", "asc").at(-1)!.double_spend.outcome).toBe("SUCCEEDS");
  });

  it("labels networks", () => {
    expect(networkLabel("net-h-synthetic-3site-100km")).toBe("3 sites · 100 km");
    expect(networkLabel(null)).toBe("any");
  });
});
