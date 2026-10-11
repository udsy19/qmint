# K-web-B: landing page and brand (route `/`)

Branch `feat/KB-web`, from `6a8053e`. Code commit `c9a4783`. Machine-readable record: `K-web-B.json`.

## Delivered
- **Identity.** The mark is a 2×2 plate of the four BB84 polarisation axes (`web/public/brand/qmint-mark.svg`, `Mark` in `components/marketing/wordmark.tsx`). The wordmark "QMint" is set in Geist Pixel Square. Pixel also sets the section numerals 01–06, and Pixel Grid sets the token id.
- **Nav.** The nav is sticky, 56px tall and opaque, and gets a hairline once you scroll. Links: Product → /app, Research, Benchmarks, Documentation, GitHub, and a white "Launch Lab" button. Below md the links move into a sheet that closes on Esc.
- **Footer.** It has mono column heads and shows "This effort is supported by Qollab & IonQ." exactly. It links the MIT License and DISCLOSURE.md, and shows the API version and git sha from `/meta`. When `/meta` is down it says "API offline".
- **Hero instrument** (`components/marketing/hero/`).
  - **Scenarios:** honest, measure–resend, phase-covariant (Bruß) cloner, MVW optimal channel, and the leaked-secret control, which is out of model. n can be 1, 2, 4 or 8.
  - **Aer sampling** can be switched on only where the API supports it: cloners with n ≤ 2.
  - **Diagram:** note glyphs from the seeded issuer view, then the channel, then V₁ and V₂, then the joint outcome.
  - **Readouts:** the headline both-pass value, per-qubit, one copy passes, and the W1 bound. The bound is crossed out with "does not apply" when out of model. A Monte Carlo row with a 99% CI appears when sampling is on, plus a log₁₀ scale of the value against the bound.
  - **Labels:** each value shows exactly one label: THEOREM, an exact model value (SIMULATOR-IDEAL, exact enumeration), a Monte Carlo CI, or OUT-OF-MODEL.
  - **States:** the API's DEMO_ADAPTER status and reason are shown, and there are loading and error/timeout states with a retry.
  - **Motion and accessibility:** branch strokes draw over 640 ms and are static under reduced motion. An aria-live sentence describes each result.
  - **Data:** the server renders the first reading through the API, and the client refetches whenever the selection changes.
- **Sections.**
  - **01 Problem:** two figures, copy vs double spend, plus a list of where lane H puts the trust.
  - **02 Primitive:** a plate of the four states, plus four limits of no-cloning, each labelled: the (3/4)ⁿ exponent with n = 73 for 10⁻⁹, the leaked secret (1, OUT-OF-MODEL), W2 loss, and the simulator caveat.
  - **03 Lab:** an index of /lab/mint, /lab/attack, /certificates and /benchmarks, with the endpoint and evidence kinds for each.
  - **04 Quantum vs classical:** lane H's finding, quoted. S-money needs the relayed Stage-II bit c, and a late-commit escrow with OT matches it under computational assumptions. A matched-requirement table follows, labelled MODELLED-LATENCY, with the counts 7 qualified, 4 incomparable, 0 comparable.
  - **05 Proof, not hype:** three columns.
    - THEOREM: (3/4)ⁿ, taken from `/games`.
    - CERTIFIED-NUMERIC: 3/4 ≤ OPT₁ ≤ 0.750000000003638 and 9/16 ≤ OPT₂ ≤ 0.562500000007276.
    - PHOTON-EXPERIMENT: QBER of 1.4491% and 3.2787% against the paper's 1.45% and 3.28%, with Zenodo DOI 10.5281/zenodo.7979319.
  - **06 Open research:** the repo, live lane status from `/meta`, real reproduce commands, primary sources P01/P03/P04/P05 with DOI or arXiv ids, and the two Zenodo DOIs.
  - **Closing:** a mint "Launch the Lab" button (the only mint CTA) and the disclaimer from `/meta`.

## Tests and QA
- Results: typecheck 0, lint 0, vitest 34/34 (18 of them new), build 0.
- `instrument-model.test.ts` checks that each scenario gets the right source and label. The leaked-secret case must be OUT-OF-MODEL with the bound not applying, honest must give null and never 0, and the Monte Carlo case must carry its CI.
- `instrument.test.tsx` uses a mocked fetch. It checks that the leaked-secret case calls `/lab/mint`, that sampling is gated, and that the error state renders.
- `footer.test.tsx` checks the exact support sentence and the licence and disclosure links.
- `research-values.test.ts` re-reads the lane C and lane E artefacts, so a quoted number fails the test if it drifts.
- Screenshots at 1440, 1920, 768 and 390, plus interaction, reduced-motion and mobile-menu captures, are listed in the JSON (in the scratchpad). There is no horizontal scroll and there are no console errors.
- With the API offline, `/` still returns 200 and shows explicit offline states.

## For other owners
- **KD:** the `/lab/attack` reason still says "lane C not merged". Please also add a `secret_leak_control` attack so the hero stops deriving that value from `/lab/mint`.
- **KC:** please add a `GET /evidence/highlights` endpoint for the SDP, QBER and comparability values. Then `research-values.ts` can be deleted.
- `StateGlyph` is a candidate primitive for /lab/mint.

## Update: re-targeted to the merged lab API (main @ 02aeab1)
- **Fast-forward.** `feat/KB-web` was fast-forwarded to main. Main's typecheck errors all came from the hero against KD's new `/lab` contract, and they are now fixed.
- **Scenario mapping** to KD's attack ids:

  | Scenario | Attack id |
  |---|---|
  | measure–resend | `A01_basis_guess_resend` |
  | phase-covariant cloner | `A03b_phase_covariant_xz` |
  | MVW optimal channel | `A04_mvw_optimal_channel` |
  | leaked secret | `CTRL_secret_leak` (taken straight from the API; no longer derived client-side) |
  | honest holder | `/lab/mint` honest acceptance |

- **Out-of-model** comes from the API's `proof_applicability`. When it is OUT_OF_MODEL, the W1 bound is the API's null "does not apply" quantity.
- **Monte Carlo** is now available for every attack, over 1,000 fresh notes, labelled MONTE-CARLO with its 95% CI.
- **SDP optimum.** For n ≤ 2 a CERTIFIED-NUMERIC "Optimum ≤" row shows the live SDP bracket at full precision.
- **Note states are hidden ("?")** because they are the bank's secret. They are revealed only in the leaked-secret control, through `/lab/mint` `teaching_reveal`, the API's out-of-model teaching view. In-model scenarios never request a reveal, and a test checks this.
- **`research-values.ts` is deleted, and so is its drift test.** Every landing-page number now comes from the API:
  - 05 QBER, reproduced vs published, plus the pair and run counts: `GET /benchmarks` → photon.
  - 05 SDP brackets: `POST /lab/attack` A04 at n = 1 and 2 → sdp.
  - 04 comparability counts: `/benchmarks` comparability.
  - 02 leak value: `CTRL_secret_leak`.
  - 02 n_min = 73: computed as ⌈−9 / log10 per_unit⌉ from the `/games` W1 per-unit value.
  - Links, the bibliography, the support line and the fallback disclaimer moved to `components/marketing/site.ts`.
- **Checks:** typecheck 0, lint 0, vitest 91/91, build 0. The visual check at 1440 and 390 showed no horizontal scroll and no console errors (scratchpad `shots2/`).
- **Superseded:** the KC/KD proposals made earlier in this handoff (evidence highlights endpoint, secret-leak attack) are no longer needed.
