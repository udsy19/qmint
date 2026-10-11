/**
 * Static site content for the marketing pages: links, the support line, the fallback disclaimer and
 * the bibliography. No research numbers live here: every number on the landing page comes from the API.
 */

export const REPO_URL = "https://github.com/udsy19/qmint";
export const LICENSE_URL = "https://github.com/udsy19/qmint/blob/main/LICENSE";
export const DISCLOSURE_URL = "https://github.com/udsy19/qmint/blob/main/DISCLOSURE.md";
export const SUPPORT_LINE = "This effort is supported by Qollab & IonQ.";
/** Shown when GET /api/v1/meta (which serves the canonical disclaimer) is unreachable. */
export const FALLBACK_DISCLAIMER =
  "QMint is an open-source research platform. Results are simulations, published analytic values or committed datasets, each labelled with its evidence kind. It is not money, not a payment service and not a deployable quantum currency.";

export interface Reference {
  id: string;
  cite: string;
  title: string;
  href: string;
  doi: string | null;
  role: string;
}

/** Ids from research/PRIOR_ART_MATRIX.csv (lane A); titles from proofs/OBLIGATIONS.yaml citations (lane D).
 *  P05 has no verified title in the repo, so it is described, not titled. */
export const REFERENCES: readonly Reference[] = [
  {
    id: "P01",
    cite: "Molina, Vidick & Watrous 2012",
    title: "Optimal counterfeiting attacks and generalizations for Wiesner's quantum money",
    href: "https://arxiv.org/abs/1202.4010",
    doi: null,
    role: "W1 bound (3/4)ⁿ, optimal channel",
  },
  {
    id: "P03",
    cite: "Kent, Lowndes, Pitalúa-García & Rarity 2022",
    title: "Practical quantum tokens without quantum memories and experimental tests",
    href: "https://doi.org/10.1038/s41534-022-00524-4",
    doi: "10.1038/s41534-022-00524-4",
    role: "S-money S1/S2, Lemma 1",
  },
  {
    id: "P04",
    cite: "Schiansky et al. 2023",
    title: "Demonstration of quantum-digital payments",
    href: "https://doi.org/10.1038/s41467-023-39519-w",
    doi: "10.1038/s41467-023-39519-w",
    role: "photon dataset, QBER reproduced",
  },
  {
    id: "P05",
    cite: "Jiang et al. 2024",
    title: "S-token experiment over 2.766 km and 60.54 km fibre links (arXiv preprint, v2)",
    href: "https://arxiv.org/abs/2408.13063",
    doi: null,
    role: "S-token latency 15.34 / 304.20 µs",
  },
] as const;

export const DATASETS = [
  {
    id: "Zenodo 7979319",
    doi: "10.5281/zenodo.7979319",
    href: "https://doi.org/10.5281/zenodo.7979319",
    note: "Schiansky 2023 coincidence data, v1 (cited by the paper)",
  },
  {
    id: "Zenodo 7997998",
    doi: "10.5281/zenodo.7997998",
    href: "https://doi.org/10.5281/zenodo.7997998",
    note: "v2, adds raw TTM8000 time tags",
  },
] as const;
