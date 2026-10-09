#!/bin/sh
# Check every commit in <base>..<head> against CLAUDE.md, "Git rules".
# Usage: sh .github/scripts/check-history.sh [base] [head]   (defaults: main HEAD)

base=${1:-main}
head=${2:-HEAD}
root=$(git rev-parse --show-toplevel) || exit 2
git rev-parse --quiet --verify "$base^{commit}" >/dev/null || { echo "unknown base: $base" >&2; exit 2; }

fail=0
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

for sha in $(git rev-list --reverse "$base..$head"); do
  short=$(git rev-parse --short "$sha")
  subject=$(git log -1 --format=%s "$sha")
  bad=0

  if [ "$(git rev-list --parents -n 1 "$sha" | wc -w)" -gt 2 ]; then
    echo "$short: merge commit in the branch; rebase onto main instead of merging it in" >&2
    bad=1
  fi

  case $subject in
    "fixup! "* | "squash! "* | "amend! "*)
      echo "$short: unsquashed commit; run git rebase --autosquash" >&2
      bad=1
      ;;
  esac
  if printf '%s\n' "$subject" | grep -qiE '^wip([^a-z]|$)'; then
    echo "$short: work-in-progress commit; fold it into a real commit" >&2
    bad=1
  fi

  git log -1 --format=%B "$sha" >"$tmp"
  sh "$root/.githooks/commit-msg" "$tmp" || bad=1

  if [ "$bad" -eq 1 ]; then
    echo "  in $short $subject" >&2
    fail=1
  fi
done

[ "$fail" -eq 0 ] && echo "history ok: $base..$head"
exit $fail
