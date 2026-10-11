"""Frozen core: contracts C0-C7, canonical serialization, secret boundary.

`contracts.py`, `serialization.py` and `interfaces.py` are FROZEN at the bootstrap
SHA (lead-owned). Changes require a versioned schema migration approved by the lead.
Lane L may add new modules under `qmint/core/` (doctor, manifest, config, logging).
"""
