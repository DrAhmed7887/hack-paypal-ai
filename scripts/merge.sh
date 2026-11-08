#!/bin/zsh
# merge.sh: squash-merge a PR whose CI is already green (one check, no polling).
# Usage: scripts/merge.sh <pr-number>
# Exit: 0 merged · 2 changes requested · 3 CI not green yet or failed · 1 other error.
set -euo pipefail
cd "$(dirname "$0")/.."
pr=${1:?usage: scripts/merge.sh <pr-number>}
[[ $(gh pr view "$pr" --json baseRefName -q .baseRefName) == main ]] || { print -u2 "merge: PR #$pr does not target main"; exit 1; }
head=$(gh pr view "$pr" --json headRefOid -q .headRefOid)
branch=$(gh pr view "$pr" --json headRefName -q .headRefName)
ci=$(gh run list --commit "$head" --workflow ci --json conclusion -q '.[0].conclusion' 2>/dev/null || true)
[[ $ci == success ]] || { print -u2 "merge: CI on ${head:0:10} is '${ci:-not finished}'"; exit 3; }
# Reviews: comments are checked by the conductor before this runs; a "changes requested" review always blocks.
decision=$(gh pr view "$pr" --json reviewDecision -q .reviewDecision)
[[ $decision != CHANGES_REQUESTED ]] || { print -u2 "merge: PR #$pr has changes requested"; exit 2; }
gh pr merge "$pr" --squash --match-head-commit "$head" >/dev/null
git push -q origin --delete "$branch" 2>/dev/null || true   # remote branch only: a worktree may hold the local one
print "merged PR #$pr (${head:0:10}) into main"
