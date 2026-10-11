# Security policy

QMint is a **research simulator**. It is not a payment system, holds no funds, and must not be used to protect real
value. "Security" in this repository means *mathematical security claims about modelled games*, each tied to a named
theorem or certified computation with explicit assumptions.

## Reporting

- **Scientific errors** (a wrong bound, a misapplied theorem, an evidence label that overstates its source): open a
  GitHub issue with the label `claim-audit`. These are welcome and are treated as first-class findings; see `audits/`
  for how earlier findings were handled (failing regression test first, then fix).
- **Software vulnerabilities** (e.g. secret material leaking through an API response, the record store accepting
  forged records): please use GitHub's private vulnerability reporting ("Report a vulnerability" on the Security tab)
  rather than a public issue.

## Secrets

The repository needs no secrets. `IONQ_API_KEY` is optional, read from the environment or a git-ignored `.env`, never
logged, and paid hardware jobs are refused in code (`QMINT_ALLOW_PAID_HARDWARE`). Never commit keys; `.env` is ignored.
