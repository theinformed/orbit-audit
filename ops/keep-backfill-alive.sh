#!/bin/bash
# Keep the bulk-TLE backfill running until the archive's own ledger says the
# held bundles are in, and stop with a non-zero status the moment it stalls.
#
# Why this exists in the repository rather than as a shell one-liner: the first
# version of this keeper decided the import was finished by counting the words
# "already imported" in the log. A crash loop prints those words too - the
# importer re-announces every finished year on each relaunch - so two crashes
# in one log file cleared the threshold and the keeper wrote "import complete"
# over a backfill that had died at 2005 and never reached 2004. A completion
# test a failure can satisfy is not a completion test.
#
# What replaced it: the importer's own ledger, read through `--status`, which
# reports per bundle whether it imported and how many rows it holds. Progress
# is measured, not inferred, and a launch that ends with no bundle finished and
# nothing pending removed is reported as a stall rather than a success.
#
# The import itself is safe to restart blindly: it reads bundles already on
# disk, deduplicates on (norad, epoch_ms), and skips bundles the ledger marks
# done, so a restart resumes rather than repeats. It makes no network request.
set -u

REPO=/home/sdegan/space-teaching-aid
LOGDIR=${LOGDIR:-/mnt/d/space-orbit-history/bulk}
KEEPER_LOG="$LOGDIR/keeper.log"
YEARS=${YEARS:-2024,2025,2023,2022,2021,2020,2019,2018,2017,2016,2015,2014,2013,2012,2011,2010,2009,2008,2007,2006,2005,2004}
MAX_STALLS=${MAX_STALLS:-2}

cd "$REPO" || exit 1

say() { echo "$(date -u +%FT%TZ) $*" >> "$KEEPER_LOG"; }

# Bundles the ledger still has no import row for. Empty output means done.
pending() {
  python3 -m pipeline.orbit_history_backfill --status 2>/dev/null | python3 -c '
import json, sys
try:
    held = json.load(sys.stdin)["held"]
except Exception:
    # A status we cannot read is not an empty pending list. Say so loudly by
    # emitting a sentinel the caller counts as "still work to do".
    print("status-unreadable")
    sys.exit(0)
for name in sorted(held):
    if not held[name].get("imported"):
        print(name)
'
}

stalls=0
while true; do
  remaining=$(pending)
  if [ -z "$remaining" ]; then
    say "backfill complete; every held bundle has a ledger row"
    exit 0
  fi
  count=$(printf '%s\n' "$remaining" | grep -c .)

  if pgrep -f "pipeline.orbit_history_backfill --import-held" > /dev/null; then
    sleep 300
    continue
  fi

  # One file per launch, named for when it started. Counting existing files
  # and adding one reused the log of a run that had already crashed, which put
  # a fresh run's output underneath a stale traceback.
  log="$LOGDIR/import-$(date -u +%Y%m%dT%H%M%SZ).log"
  say "importer not running; $count bundle(s) pending; launching -> $log"
  nice -n 19 ionice -c 3 python3 -u -m pipeline.orbit_history_backfill \
    --import-held --years "$YEARS" >> "$log" 2>&1
  status=$?

  after=$(pending)
  after_count=$(printf '%s\n' "$after" | grep -c .)
  if [ -z "$after" ]; then
    say "backfill complete; last launch exited $status"
    exit 0
  fi
  if [ "$after_count" -lt "$count" ]; then
    stalls=0
    say "progress: $count -> $after_count pending (exit $status)"
  else
    stalls=$((stalls + 1))
    say "NO PROGRESS: still $after_count pending after exit $status (stall $stalls/$MAX_STALLS); tail: $(tail -1 "$log")"
    if [ "$stalls" -ge "$MAX_STALLS" ]; then
      say "giving up; the import is failing on the same bundle every time - read $log"
      exit 1
    fi
  fi
  sleep 60
done
