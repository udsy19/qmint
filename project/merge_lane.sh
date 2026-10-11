#!/usr/bin/env bash
# Lead-only merge queue step: ownership check -> merge --no-ff -> full suite -> revert on regression.
set -euo pipefail
LANE="$1"; BRANCH="$2"
ROOT=/Users/udsy/PycharmProjects/Qollab-QMint; PY=$ROOT/.venv/bin/python
cd "$ROOT"
case "$LANE" in
  A) PAT='^(research/|licenses/|handoffs/A-|tests/unit/research/)' ;;
  B) PAT='^(qmint/protocols/|tests/unit/protocols/|handoffs/B-)' ;;
  C) PAT='^(qmint/attacks/|tests/unit/attacks/|audits/SDP_DERIVATION.md|handoffs/C-)' ;;
  D) PAT='^(qmint/proofs/|proofs/|tests/unit/proofs/|handoffs/D-)' ;;
  E) PAT='^(qmint/photonics/|datasets/manifests/|datasets/README.md|datasets/DATA_LICENSES.md|tests/unit/photonics/|reports/data_working/|handoffs/E-)' ;;
  F) PAT='^(qmint/quantum/(?!ionq\.py|qollab\.py)|tests/unit/quantum/|handoffs/F-)' ;;
  G) PAT='^(qmint/networks/|tests/unit/networks/|datasets/fixtures/ripe/|handoffs/G-)' ;;
  H) PAT='^(qmint/classical/|tests/unit/classical/|reports/classical_baseline_notes/|handoffs/H-)' ;;
  I) PAT='^(qmint/compiler/|tests/unit/compiler/|reports/optimizer_working/|benchmarks/|handoffs/I-)' ;;
  J) PAT='^(qmint/quantum/ionq\.py|qmint/quantum/qollab\.py|qollab/|tests/unit/ionq/|handoffs/J-)' ;;
  K) PAT='^(qmint/ui/|qmint/api/|app/|web/|docs/design/|tests/unit/ui/|tests/unit/api/|handoffs/K-)' ;;
  L) PAT='^(qmint/core/(?!contracts\.py|serialization\.py|interfaces\.py)|qmint/cli\.py|scripts/|\.github/|tests/integration/|tests/contracts/(?!test_contracts\.py)|docs/REPRODUCIBILITY\.md|pyproject\.toml|handoffs/L-)' ;;
  X) PAT='^(qmint/networks/|qmint/classical/|tests/unit/networks/|tests/unit/classical/|tests/integration/test_gh_|reports/classical_baseline_notes/|handoffs/GH-)' ;;
  M) PAT='^(audits/|tests/adversarial/|handoffs/M-)' ;;
  N) PAT='^(qmint/evaluation/|reports/|figures/|docs/|tests/unit/evaluation/|handoffs/N-)' ;;
  *) echo "unknown lane"; exit 1 ;;
esac
BASE=$(git merge-base main "$BRANCH")
BAD=$(git diff --name-only "$BASE" "$BRANCH" | python3 -c 'import re,sys; p=re.compile(sys.argv[1]); [print(l.strip()) for l in sys.stdin if not p.match(l.strip())]' "$PAT")
if [[ -n "$BAD" ]]; then echo "OWNERSHIP VIOLATION ($LANE):"; echo "$BAD"; exit 2; fi
PRE=$(git rev-parse HEAD)
git merge --no-ff -q -m "merge: lane $LANE ($BRANCH)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" "$BRANCH"
if ! "$PY" -m pytest -q -m "not network and not realdata and not slow" -p no:cacheprovider > /tmp/qmint_merge_$LANE.log 2>&1; then
  tail -30 /tmp/qmint_merge_$LANE.log; echo "REGRESSION after merging $LANE; reverting merge"; git revert -m 1 --no-edit HEAD >/dev/null; exit 3
fi
tail -2 /tmp/qmint_merge_$LANE.log; echo "MERGED $LANE at $(git rev-parse HEAD) (pre $PRE)"
