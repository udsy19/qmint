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
        D1 (Schiansky 2023) is never certified: its Chernoff step is applied to a weighted variable outside the bound&apos;s
        hypothesis, and coherent attacks are reduced only by a qualitative de Finetti argument. The published p_d recomputes
        only with N = 4.2×10⁶.
      </li>
      <li>Kent et al.&apos;s experimental tuple lies outside their Theorem 1 domain, as the paper itself says.</li>
      <li>The certificate compiler (lane I) and the independent red-team audit (lane M) are in flight.</li>
    </UL>
  ),
  data: (
    <UL>
      <li>
        The Zenodo 7979319 archive reproduces both published QBERs, but loss, detector efficiency and multiphoton probability
        cannot be observed from it; they stay null, and the paper&apos;s values are kept separately as{" "}
        <C>PUBLISHED_AGGREGATE</C>.
      </li>
      <li>Runs are overdispersed and the D/A holdout differs between halves of the run sequence (p = 0.003): calibration is not stationary.</li>
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
