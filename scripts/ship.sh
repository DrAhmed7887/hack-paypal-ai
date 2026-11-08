#!/bin/zsh
# ship.sh: the /loop's publish step for the current build/* branch.
#   local checks → base check → rules gate → push → PR to main → ask Copilot (Lite) to review.
# CI is NOT watched here: the conductor binds the PR in the desktop app, which wakes it on CI events.
# Then scripts/merge.sh squash-merges once CI is green.
# Usage: scripts/ship.sh "PR title" [body-file]
# Exit: 0 PR open · 4 rules/data files changed (needs Ahmed's sign-off) · 1 other error.
set -euo pipefail
cd "$(dirname "$0")/.."
title=${1:?usage: scripts/ship.sh "PR title" [body-file]}
branch=$(git rev-parse --abbrev-ref HEAD)
[[ $branch == build/* ]] || { print -u2 "ship: run from a build/* branch (now on $branch)"; exit 1; }
[[ -z $(git status --porcelain) ]] || { print -u2 "ship: commit your changes first"; exit 1; }

print "== local checks"
PY=python3; [[ -x .venv/bin/python ]] && PY=.venv/bin/python
$PY -m pytest -q >/dev/null || { print -u2 "ship: tests failed"; exit 1; }
# Same patterns as CI, over the files git tracks (what CI checks out). git grep: 0 = match, 1 = none, else error.
set +e
hits=$(git grep -l -i -E -f .github/secret-patterns.txt -- . ':(exclude).github/secret-patterns.txt')
rc=$?
set -e
if (( rc == 0 )); then print -u2 "ship: secret-like content (same scan as CI):"; print -u2 "$hits"; exit 1; fi
if (( rc != 1 )); then print -u2 "ship: secret scan failed (git grep exit $rc)"; exit 1; fi

git fetch -q origin main
base=$(git rev-parse origin/main)
head=$(git rev-parse HEAD)
git merge-base --is-ancestor "$base" "$head" || { print -u2 "ship: main has moved; rebase on origin/main and rerun"; exit 1; }

# Hard gate: benchmark rules, thresholds and test data are Ahmed's to sign.
# SHIP_SIGNED=<head SHA> is set only after Ahmed says yes in chat for this exact commit (CLAUDE.md).
gated=$(git diff --name-only "$base...$head" -- data src/billcheck/benchmarks.json docs/EVIDENCE.md)
if [[ -n $gated && ${SHIP_SIGNED:-} != "$head" ]]; then
  print -u2 "ship: rules/data files changed; needs Ahmed's sign-off for $head (then rerun with SHIP_SIGNED=$head):"; print -u2 "$gated"; exit 4
fi

print "== push $branch"
git push -q -u origin "$branch"

pr=$(gh pr list -H "$branch" --state open --json number -q '.[0].number' 2>/dev/null || true)
if [[ -z $pr ]]; then
  if [[ -n ${2:-} ]]; then gh pr create -B main -H "$branch" -t "$title" -F "$2" >/dev/null
  else gh pr create -B main -H "$branch" -t "$title" -b "Autonomous /loop build step (see docs/LOOP.md)." >/dev/null; fi
  pr=$(gh pr list -H "$branch" --state open --json number -q '.[0].number')
fi
gh pr edit "$pr" --add-reviewer "@copilot" >/dev/null 2>&1 || print "   (Copilot review not requested; continue without it)"
print "PR #$pr open for ${head:0:10}. Bind it in the app; run scripts/merge.sh $pr when CI is green."
