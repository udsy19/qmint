# QMint — proof-carrying quantum payment security research platform

This effort is supported by Qollab & IonQ.

**Status: research simulator and evaluation harness (claim level L0 until a record says otherwise).**
Not a payment system, not physical quantum money, not a security certification.

- Spec: `QMINT_MASTER_RESEARCH_PLAN.md` · Work orders: `AGENT_WORK_PACKAGES.md`
- Contracts: `project/CONTRACTS.md` · Tracker: `project/TRACKER.yaml` · Agent rules: `project/AGENT_RULES.md`

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.lock
.venv/bin/python -m pytest -q
```

License: MIT (`LICENSE`). Disclosure of starting material and AI assistance: `DISCLOSURE.md`.
