import Link from "next/link";
import { C, P, UL } from "../prose";

const link = "text-foreground underline decoration-border-strong underline-offset-4";

/** Drawn from project/TRACKER.yaml, the lane handoffs (handoffs/*.md) and research/NOVELTY_HYPOTHESES.md. */
export const content = {
  scope: (
    <>
      <P>
        QMint is a research platform. It is not money, not a payment service and not a deployable quantum currency. It
        reproduces and checks published results; it does not claim to have invented quantum tokens, S-money or quantum
        payments. The statements QMint must never make are listed in{" "}
        <Link href="/research/NOV-DISALLOWED" className={link}>
          NOV-DISALLOWED
        </Link>
        .
      </P>
    </>
  ),
  hardware: (
    <UL>
      <li>No quantum hardware result exists in this build. Gate G6 (optional authorised IonQ run) is <C>SKIPPED</C>: no API key and no paid approval.</li>
      <li>The IonQ path is a dry-run cost and approval plan; submission is disabled. The Qollab integration has no public API and is blocked.</li>
      <li>Circuits are simulated with Qiskit Aer (ideal or with declared noise). Declared noise is hypothetical, not a device model.</li>
    </UL>
  ),
  proofs: (
    <UL>
      <li>
        Ideal bounds (W1, W1_CV, S1) are published theorems reproduced in code. Lane C&apos;s SDPs are certified only for n = 1
        and n = 2; larger n is refused by a size guard.
      </li>
      <li>
        W2 (noisy/threshold Wiesner) has no bound. MVW Sec. 3.5&apos;s binomial tail covers a joint-success game, not per-copy
        thresholds.
      </li>
      <li>
        D1 (Schiansky 2023) is not certified by QMint. This is an unresolved reproducibility finding, not an invalidation of the
        original work: the published p_d = 5.9×10⁻⁴⁵ recomputes only with N = 4.2×10⁶ (the SI table lists 4,482,440), and we
        could not confirm that the Chernoff step applied to the weighted error-plus-loss sum meets that bound&apos;s stated
        hypothesis (a conservatively rescaled version gives 3.3×10⁻⁷). Coherent attacks are reduced by a de Finetti argument we
        did not formalise. These questions are open for review by the authors and independent experts.
      </li>
      <li>Kent et al.&apos;s experimental tuple lies outside their Theorem 1 domain, as the paper itself says.</li>
      <li>
        Certificate compiler (lane I): it matches the exhaustive oracle on all small grids and every released certificate passes
        the independent checker, but its apparent photon savings (1.8–10.6× vs naive sizing on Kent Fig. 5 point devices) do not
        survive calibration uncertainty: under the uncertainty boxes every selector is infeasible. Only hypothetical devices
        clear the pre-registered bar, and the method is standard parameter optimisation, not a new technique.
      </li>
      <li>
        An independent red-team audit (lane M) found five high-severity defects in our own code; all are fixed with regression
        tests. Lower-severity items remain open and are tracked as strict expected-failure tests.
      </li>
      <li>
        Not done: no physical quantum hardware run (free IonQ noise-model simulators only), no S-money double-spend simulation
        in the network model, no more-than-two-site scenarios, no third-party reproduction, no manuscript yet.
      </li>
    </UL>
  ),
  data: (
    <UL>
      <li>
        The Zenodo 7979319 archive reproduces both published QBERs, but loss, detector efficiency and multiphoton probability
        cannot be observed from it; they stay null, and the paper&apos;s values are kept separately as{" "}
        <C>PUBLISHED_AGGREGATE</C>.
      </li>
      <li>Photon runs are overdispersed (χ²/dof ≈ 10): run-to-run heterogeneity driven by a few outlier runs, not temporal drift. A run-level Welch test of first vs second half finds no difference (p = 0.334 D/A, 0.587 H/V; an earlier pooled-iid p = 0.003 was invalid and was corrected after red-team review). Calibration intervals are widened accordingly.</li>
      <li>RIPE Atlas one-way delays are RTT/2, an assumption that is flagged wherever they appear.</li>
      <li>Several research entries were checked at abstract or metadata level only; their status says so.</li>
    </UL>
  ),
  comparisons: (
    <UL>
      <li>
        The S-money network model covers timing only and says nothing about security. RIPE-based numbers are not a matched
        benchmark: trust model, privacy and processing differ.
      </li>
      <li>
        Classical baselines show that coordination alone is not S1&apos;s distinction; what differs is information-theoretic vs
        computational security. Rows that are not comparable are marked so in the comparability matrix.
      </li>
      <li>A measured quantum transaction-time advantage is Jiang et al. 2024&apos;s result, not QMint&apos;s.</li>
    </UL>
  ),
  platform: (
    <UL>
      <li>Where a lane is not wired into the API yet, the response says <C>DEMO_ADAPTER</C> or <C>NOT_AVAILABLE</C> with the reason, instead of a number.</li>
      <li>The uniform lane entrypoints are not merged yet, so <C>qmint simulate</C> and similar commands exit 3.</li>
      <li>The site is dark-only; LaTeX in research records is shown as source, not typeset.</li>
    </UL>
  ),
};
