# Reference audit: third-party sources and licences (lane A, A1)

Snapshot 2026-10-11. Branch `feat/A-research`. This is the record of every external artefact lane A inspected, with its exact identifier and declared licence. **No third-party code or data was copied into the repository by lane A.** Downloads were made to a scratch directory outside the repo and only metadata/hashes are recorded here. Details: `research/DATASOURCE_REGISTER.yaml`, `research/LICENSE_AND_PATENT_RISKS.md`.

## Papers (text read; equations transcribed with attribution)

| ID | Identifier | Version inspected | Declared licence | sha256 of file read |
|---|---|---|---|---|
| P01 | arXiv:1202.4010 | v1 PDF | arXiv non-exclusive distrib. 1.0 | a95b64d9fc03c8286171694006ed6219374a75360152d27a6ab63a0f338eb2a6 |
| P02 | doi:10.1098/rspa.2019.0170 (PMC6545040) | PMC HTML | © Authors, Royal Society, all rights reserved | (HTML, not hashed) |
| P03 | doi:10.1038/s41534-022-00524-4 | journal PDF + HTML + Tables 1–6 + SI | CC BY 4.0 | PDF 8980aeabba8ff2c0dca6f2bafae31357b503baa4e3a0d254010dd109ff36df3a; SI 7b49b60c8acbd3d2785fb7f6b227dae56ab1c78b6f4b8b57598e1d21bb833b66 |
| P04 | doi:10.1038/s41467-023-39519-w | corrected journal PDF + HTML + SI | CC BY 4.0 | PDF 7689e53d6116999db070812a92f82d4a7e19e79329622aef1a28d160efdae596; SI 26e50b759192559e58e05a48a93d6ad70dd744da8ba975ee973266a46591a223 |
| P04-corr | doi:10.1038/s41467-023-40866-x | PDF + HTML | CC BY 4.0 | 5018ada3a27042d8549d35f83e11be120effee9f6fad6eb08f4050f2d8df237c |
| P05 | arXiv:2408.13063 | v2 PDF | CC BY 4.0 | a5a4242882c4a265738dbcf84a58f41acd345dfa51eb0dcf40537df7dec5deb4 |
| P06 | arXiv:2510.06212 | v2 PDF | CC BY 4.0 | 84b5087ed0b9897c036a104f3820aefdebe7a9b71c059b42ea8aebd3d54e5b11 |
| P07 | arXiv:2602.10621 | v1 PDF (abstract read) | arXiv non-exclusive | 94d5d38ac012ea399eb18cde1e43faf8951fc2932a1973168f644c70a8589f83 |
| P08 | arXiv:2307.12120 | v5 PDF (abstract read) | CC BY 4.0 | 58fa00537d505dcfeae7b854e122fbf875a7f0dc5b7360306597996de6f5a936 |
| P09 | arXiv:2205.10488 | v2 (abstract read) | CC BY 4.0 | 8034e1cffbff295fd23e77da5d16410684916f6ed163362f67c0d40036134643 |
| P10 | arXiv:2411.04482 | v1 (abstract read) | CC BY 4.0 | fbc001c1bce63eb8198cd6df70692f3239765f17871014ed17bfa828f09820b3 |
| P11 | arXiv:2407.06463 | v2 (abstract read) | CC BY-SA 4.0 | 5f2b932155e3045fb684dd91d09143518cc69d45ef56b25d2eafffc4cade6e3b |
| P12 | arXiv:2503.18890 | v4 (abstract read) | CC BY 4.0 | 206cf0bd5fbf6c648694c0fa4f7ff38e466ddf2a2cc30db162bbea4142940943 |

Hashes are sha256 of the files as downloaded on 2026-10-11 (`shasum -a 256`). Publisher PDFs can be regenerated, so a mismatch later doesn't necessarily mean the content changed.

## Data and code

| Item | Identifier | Declared licence | Inspection | Adopted into QMint? |
|---|---|---|---|---|
| Schiansky timetags v1 | doi:10.5281/zenodo.7979319, Archive.zip md5 fd708578a613b63f57c31f986a56bf94 | CC BY 4.0 | zip directory listed by range requests | No (lane E downloads at runtime) |
| Schiansky timetags v2 | doi:10.5281/zenodo.7997998, Archive.zip md5 544ed5cff8db0598b04dfecb6a5072be | CC BY 4.0 | zip directory listed | No |
| Schiansky code | doi:10.5281/zenodo.8020667, Archiv.zip md5 efae565eeb2cd3d5c1bb49266800c482, sha256 e3f80ccb8d559df8fc14e3d1109402da569257fe3d593aa5b5fb61953363d714 | **Conflict: metadata CC BY 4.0, file LICENSE_AGPLv3** | downloaded, unzipped, read (README, headers) | **No. Must not be copied.** |
| QMoney | github.com/runeape-sats/qmoney @ 017502ea815314af8f200648473c741534df1a8c | MIT | README read via GitHub API | No (comparison only) |
| openQKDsecurity | github.com/Optical-Quantum-Communication-Theory/openQKDsecurity | MIT | licence via API only | No |
| numerical_qkd | github.com/dbunandar/numerical_qkd | MIT | licence via API only | No |

## Libraries already pinned in `requirements.lock` (licence check only)

qiskit 2.5.2 (Apache-2.0), qiskit-aer 0.17.2 (Apache-2.0), qutip 5.3.1 (BSD-3-Clause), cvxpy 1.9.3 (Apache-2.0), scs 3.3.1 (MIT), clarabel 0.11.1 (Apache-2.0, repo-level), dilithium-py 1.4.0 (MIT). All are compatible with Apache-2.0 distribution with attribution. Licences are from GitHub API / PyPI metadata, not from the installed wheels' METADATA files (not re-checked).

## Unadopted references (listed so nobody assumes they were vetted)

SeQUeNCe (custom licence), SimQN (GPL-3.0), QuNetSim (MIT, stale), liboqs / liboqs-python (MIT + third-party), qiskit-ionq (Apache-2.0), ripe-atlas-bigquery (no licence), otm_billz (not checked).
