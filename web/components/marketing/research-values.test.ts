import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { LANE_C_LEAK_CONTROL, SDP_W1, ZENODO_QBER } from "./research-values";

// Re-read the committed lane artefacts so a quoted number cannot drift from its source.
// vitest runs from web/; the artefacts live at the repository root.
const repo = (p: string) => resolve(process.cwd(), "..", p);
const json = (p: string) => JSON.parse(readFileSync(repo(p), "utf8"));

describe("landing-page research values match their artefacts", () => {
  it("QBER (lane E summary.json, paper estimator)", () => {
    const b = json("reports/data_working/schiansky2023/summary.json").basis_summaries;
    for (const row of ZENODO_QBER.rows) {
      const s = b[row.key];
      expect(Number((s.qber_state_avg * 100).toFixed(4))).toBe(row.ours);
      expect(Number((s.qber_state_avg_se * 100).toFixed(4))).toBe(row.oursSe);
    }
    expect(b.Z.n_pairs + b.X.n_pairs).toBe(ZENODO_QBER.pairs);
    expect(b.Z.n_runs + b.X.n_runs).toBe(ZENODO_QBER.runs);
  });

  it("W1 SDP certified brackets (lane C evidence, SCS certified dual)", () => {
    const sdp = json("handoffs/C-C1-evidence.json").w1_sdp;
    const cert = (k: string) =>
      sdp[k].attack_results.find((r: { evidence_kind: string }) => r.evidence_kind === "CERTIFIED_NUMERIC");
    expect(cert("n1_SCS").sdp_dual).toBe(SDP_W1.n1.upper);
    expect(cert("n1_SCS").sdp_primal).toBe(0.75);
    expect(cert("n2_SCS").sdp_dual).toBe(SDP_W1.n2.upper);
    expect(cert("n2_SCS").sdp_primal).toBe(0.5625);
  });

  it("leaked-secret control (lane C, out of model)", () => {
    const c = json("handoffs/C-C1-evidence.json").ctrl_secret_leak;
    expect(c.record.proof_applicability).toBe(LANE_C_LEAK_CONTROL.label);
    expect(c.record.success_rate_ci.point).toBe(LANE_C_LEAK_CONTROL.value);
  });
});
