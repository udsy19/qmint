# K-web-D: quantum lab (/lab/mint, /lab/attack)

Branch `feat/KD-web`. Starting commit `6a8053e`, code commit `528e0b3`. Machine-readable record: `K-web-D.json`.

## What changed
- **API (`qmint/api/routes/lab.py`).** Both endpoints now return `status: OK` on real merged code. `DEMO_ADAPTER` has been removed, along with the superseded helpers `measure_resend_per_qubit` and `cloner_single_copy_pass`.
  - **/lab/mint.** The lane-B `WiesnerChallenger` mints, verifies, redeems, refuses replay and remints. The issuer secret stays on the server. The public response carries the `TokenRecord`, the flow and statistics, and nothing else secret.
    - It contains no bases, bits, gates, QASM, gate counts or circuit hash. A hash of a circuit with 8 or fewer qubits can be brute-forced, so it is withheld too.
    - The only exception is `teaching_reveal: true`. This adds a `teaching` block (`TEST_ONLY_TEACHING_REVEAL`, `OUT_OF_MODEL`) that comes from `leak_secret_TEST_ONLY`.
    - Acceptance is checked several ways, kept separate:
      - bank exact value, cross-checked at runtime against the lane-F Poisson-binomial closed form;
      - closed-form mean over notes;
      - Aer shots with a Clopper–Pearson 95% interval;
      - fresh-note Monte Carlo.
    - Also returned: the error-count histogram, the W1 theorem from lane D (W2 gets `null` plus the reason) and QPU "not run".
  - **/lab/attack.** Covers A01, A01b, A02, A02b, A03, A03b, A04, A06, A08 and CTRL.
    - Exact per-qubit both-pass and single-copy values come from `qmint.attacks.heuristic.joint_outcome_probs`.
    - Monte Carlo runs over fresh notes. The W1 attacks use lane-C Kraus maps against the **lane-B** bank, an implementation independent of lane C's own challenger. A06 and A08 use lane C's toy challengers. CTRL uses lane B's `unsafe_secret_leak_control`.
    - Theorem `(3/4)^n` comes from `qmint.proofs.ideal_bounds` with registry anchors. It is `null` for A06 (W2, NO_THEOREM) and for A08 and CTRL (OUT_OF_MODEL).
    - For n ≤ 2 an SDP bracket is computed live and cached, in four parts:
      - exact rational lower end from the MVW channel;
      - lane-C `certify_w1_dual` applied to a fresh SCS dual;
      - lane-D `sdp_exact.w1_independent_upper_bound`;
      - the SCS numerical value.
    - For n = 3 the bracket is `UNSUPPORTED`, with the reason.
  - **Limits.**
    - n ≤ 8, shots ≤ 20 000, trials ≤ 5 000 (A08 ≤ 400), probes ≤ 16. Anything larger is rejected with a 422.
    - Each request has a cooperative 20 s compute deadline plus 25 s of queue grace. Exceeding it returns **HTTP 504 with `error.code = "timeout"`**.
    - The single quantum worker thread guard is kept.
- **Web (`web/components/lab/**`, `web/app/(platform)/lab/**`).**
  - A run state machine (`run-state.ts`): idle → queued → running → done/error/timeout/cancelled. It ignores stale runs, keeps the last result dimmed during a re-run, and supports cancel through AbortController.
  - Config rails with client-side validation that mirrors the API caps.
  - The token strip shows the serial in Pixel Grid and opaque per-qubit glyphs. In teaching mode, after a confirm dialog, the glyphs become Bloch arrows.
  - A circuit SVG: hatched secret boxes by default, X/H gates in teaching mode.
  - The lane-B verification flow, the error-count histogram (exact bars, Aer ticks, a threshold rule) and readouts with evidence labels, method and CI.
  - An attack comparison dot plot, grouped Analytic / Simulated / Hardware, with the dashed theorem rule and CI whiskers. It switches to a log axis when values span decades.
  - The certified SDP bracket.
  - Plain-language explanations, plus collapsible math typeset without dependencies (`math.tsx`), sources for every number, provenance with a curl reproduce command, and the C3 `AttackResult` JSON.

## Results
- **python:** `test_d_lab.py` 34 passed. With the test_api patch below, `tests/unit/api` + `tests/contracts` give 82 passed. ruff is clean.
- **web:** typecheck 0, lint 0, vitest 36/36 (6 files; 20 of them new in `components/lab`), build 0.
- **Timings** (local, single worker): mint at n=8 with 20k shots and 5k trials takes 4.4 s. The worst attack (n=8, 5k trials) takes 7 s; A08 at n=8 with 400 trials takes 3.9 s. The live SDP takes 0.02 s at n=1 and 0.3 s at n=2.

## Needed by the lead
1. **`tests/unit/api/test_api.py`** imports `measure_resend_per_qubit` and `cloner_single_copy_pass` (now deleted) and asserts the old DEMO_ADAPTER shape. As committed, it **fails at collection**. Apply `handoffs/K-web-D.test_api.patch`, which removes those 3 lab tests and the 2 imports. The behaviour they covered is re-tested in `test_d_lab.py`. With the patch applied, the suite gives 82 passed.
2. **`schemas.Method`:** please add `"monte_carlo"` and `"numerical_sdp"`. Until then lab.py uses a route-local `LabQuantity(Quantity)` that widens `method`.
3. **Primitive fixes (frozen `components/ui`):**
   - `Slider` forwards `aria-label` to the Radix Root, not to the focusable thumb (`role=slider`), so the thumbs are unnamed. `controls.tsx` patches the thumb's name locally (`ThumbLabel`). The proposal is for `ui/slider` to forward `aria-label` and `aria-valuetext` to each `Thumb`.
   - `ReadoutGroup` keeps its left divider and `px-6` on wrapped items, which leaves an orphan indent. The lab uses a local `ReadoutGrid` instead. Promote it, or fix wrapping in `ReadoutGroup`.
4. Agent C's shell: pages render their own `<main id="main">` and one `<h1>`, per WEB_OWNERSHIP. Results rails are sticky at `--header-h + 1.5rem`.

## Mobbin (extra searches, recorded here instead of MOBBIN_RESEARCH.md)
- Run-detail and progress patterns: [Browserbase run detail](https://mobbin.com/screens/b5e81a85-c4ac-4fae-8ee3-ef1f8ad5652b) gave the status, duration and step-timeline header that RunStatus and the verification flow follow. [AirOps step logs](https://mobbin.com/screens/6dadd86c-1a15-47ea-b654-a45132bb45d1) showed per-step durations. [Replit logs](https://mobbin.com/screens/463065cc-fddc-437c-bc42-fe5c6b8994eb) was reviewed as an anti-pattern (log wall).
- Value comparison: [AirOps analytics bar list](https://mobbin.com/screens/a0c8e522-9ff7-4787-a203-648575e28504) gave the label / bar / right-aligned value rows used by the comparison chart and the histogram. [Gumloop dashboard](https://mobbin.com/screens/60ec82f0-afbf-4a61-b57a-0c56f540f9b6) and [Klaviyo metrics](https://mobbin.com/screens/83dd22ed-ad2c-48a8-92df-1a15d9617008) were rejected: KPI cards and heavy chart chrome.

## Visual QA
Screenshots are in `/private/tmp/claude-501/-Users-udsy-PycharmProjects-Qollab-QMint/634384d6-a062-4a24-8650-bcd5800df2da/scratchpad/final`, not committed (KF owns the committed ones):
- `lab-mint-{390,768,1440,1920}.png`, `lab-attack-{390,768,1440,1920}.png`
- `lab-mint-teaching-1440.png`, `lab-mint-w2-amplitude-1440.png`, `lab-attack-a01-n8-1440.png`, `lab-attack-cancelled-1440.png`

No horizontal overflow and no console errors at any width.

Fixed after review:
- The StrictMode double-mount aborted the first run, which left the page stuck in "queued".
- Math subscripts were split by flex gaps.
- The SDP bracket text wrapped.
- Readout rows wrapped with an orphan indent.
- The log axis threshold was moved to 0.05 so the n=8 counterfeit values are legible.
- The token caption now says "minted ideal" when the channel is noisy.

## Limitations
- The queued → running hand-off is a client-side estimate (250 ms): the API has no progress channel. The copy says "waiting for the quantum worker".
- Cancel aborts the HTTP request. Server work on the single worker runs until its own 20 s deadline.
- Readout error is not offered in the lab. The lane-B register verifier has no readout stage, and a readout flip in the secret basis cannot be expressed without the secret.
- Per-note bank-side statistics (exact per-note acceptance, Aer shots of the same note) are labelled as bank analysis. A holder could never obtain them.
- No QPU numbers anywhere; every hardware readout is "not run". No paid jobs were run.
