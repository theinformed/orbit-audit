#!/usr/bin/env bash
set -euo pipefail

project_root=/home/sdegan/space-teaching-aid
remote_host="${ORBIT_PUBLISH_SSH_HOST:-root@publisher.example.invalid}"
remote_data=/root/space-teaching-aid/runtime/data
stage_root=$(mktemp -d /tmp/space-explorer-data.XXXXXX)
cleanup() {
  rm -rf -- "$stage_root"
}
trap cleanup EXIT

cd "$project_root"

# ---------------------------------------------------------------------------
# Bandwidth accounting. Every rsync below is asked for --stats, and the output
# is handed to ops/bandwidth.py, which is the only thing on this stack that
# knows how many bytes this site moves.
#
# It has to be measured HERE, at the transfer, because neither machine's
# interface totals are about this site: bigmem also runs ComfyUI, local
# language models and other agents, and the VPS runs Bob's whole OpenClaw
# stack. Reading /proc/net/dev on either and calling it "the site" would be a
# number nobody could stand behind.
#
# --out-format='XFER|%l|%b|%n' gives one line per transferred file: the file's
# length, the bytes rsync actually put on the socket for it, and its name. %b
# is the COMPRESSED figure under -z, which is what the connection is billed
# for; %l is what it would have been without compression. Both are recorded,
# on separate bases, and ops/bandwidth.py will not add them together.
#
# Recording never fails the publish. `|| true` on every accounting line: an
# unmeasured cycle shows on the page as unmeasured, which is survivable, and a
# publish that died counting its own bytes is not.
# ---------------------------------------------------------------------------
bandwidth_log=$stage_root/rsync.log

# Pull the CelesTrak mirror down from the VPS over the private link. The VPS is
# the only machine in this installation that talks to celestrak.org: it runs
# under the LLC, and Sean's home IP should not appear on the public internet for
# this project. This is also exactly the caching proxy CelesTrak's own usage
# policy asks organisations to build. A failed pull is NOT fatal - the previous
# mirror keeps the catalog building.
install -d -m 755 "$project_root/runtime/celestrak-mirror"
# This one is bigmem INGRESS, not egress: it comes DOWN the same private link.
# Counting it as egress would inflate the one number Sean is watching.
if ! rsync -az --stats --timeout=60 --delete \
      "$remote_host:/root/space-teaching-aid/ingest/cache/" \
      "$project_root/runtime/celestrak-mirror/" > "$bandwidth_log" 2>&1; then
  cat "$bandwidth_log"
  echo "WARNING: could not pull the CelesTrak mirror from the VPS; using the copy already on disk"
else
  python3 -m ops.bandwidth rsync-pull --run publish --family celestrak-mirror-pull \
    --file "$bandwidth_log" || true
fi

# The cadence the operations page has asked for, if any. Only the FILE NAMES
# matter and only ops/cadence.py may act on them: this pull moves a REQUEST,
# never a command, and nothing on the VPS runs anything here.
#
# Guarded on the directory existing, so this stays silent until the VPS-side
# endpoint is installed rather than logging a failure every five minutes -- the
# watchdog reads these journals, and a permanent harmless error teaches an
# operator to ignore the one line that matters.
#
# A failed pull leaves the last request in place, which is the right failure: a
# dropped link must not silently revert Sean's chosen cadence.
install -d -m 755 "$project_root/runtime/cadence-requests"
if ssh -o BatchMode=yes "$remote_host" \
     "test -d /root/space-teaching-aid/runtime/cadence-requests" 2>/dev/null; then
  rsync -az --timeout=60 --delete \
    "$remote_host:/root/space-teaching-aid/runtime/cadence-requests/" \
    "$project_root/runtime/cadence-requests/" \
    || echo "NOTE: could not pull the cadence request from the VPS; keeping the last one"
fi

# The operator's country, from Jonathan McDowell's GCAT. Called on every cycle
# and fetches at most WEEKLY -- the throttle lives in the script, not in a timer,
# so the lane is exercised 288 times a day and cannot rot unnoticed between
# refreshes. Two files, ~20 MB, once a week. NEVER fatal: without the mirror the
# catalog publishes no operator country and says so in `operatorStateEvidence`,
# which is a labelled gap rather than a wrong answer.
python3 -m ingest.gcat_mirror || echo "WARNING: GCAT mirror refresh declined; using the copy already on disk"

python3 -m pipeline.build_release
python3 deploy/publish_data.py public/data "$stage_root/data"

ssh -o BatchMode=yes "$remote_host" "install -d -m 755 '$remote_data/artifacts'"
# --exclude='orbit-history-*': THE ORBIT ARCHIVE NO LONGER GOES TO THE VPS.
#
# Sean, 2026-08-27: "the orbit histories should reside on bigmem-pc. It has the
# space. I don't want the VPS storing huge files... Bigmem-pc should be the
# repository that the VPS reaches out to."
#
# One release is 256 shards / 4.1 GB and orbit-release rewrites all of them
# hourly, against ~15 GB free on a 91%-full VPS disk that also carries Bob and
# the gateway. So the shards stay here and the VPS reverse-proxies the ONE a
# reader opened: Caddy's `handle /space/data/artifacts/orbit-history-*` routes
# that path over the private link to `space-orbit-archive`, at whatever
# address deploy/orbit-archive.compose.yaml binds (ORBIT_ARCHIVE_BIND there).
#
# THE MANIFEST STILL NAMES ALL 256, AND MUST. It is what tells the browser the
# shard count and the content-addressed filenames, and those URLs resolve --
# just not on this machine's disk. A publish that dropped them from the
# manifest would blank the archive instead of moving it.
#
# The exclusion is HERE rather than in deploy/publish_data.py on purpose: that
# script is also the gate that checks every manifest-referenced artifact exists
# and hashes to what the manifest claims, and the shards should keep being
# checked. This line is only about which of the checked files cross the wire.
rsync -az --stats --out-format='XFER|%l|%b|%n' --chmod=D755,F644 \
  --exclude='orbit-history-*' \
  "$stage_root/data/artifacts/" "$remote_host:$remote_data/artifacts/" > "$bandwidth_log"
python3 -m ops.bandwidth rsync-push --run publish --file "$bandwidth_log" || true
scp -q "$stage_root/data/manifest.json" "$remote_host:$remote_data/.manifest.next"
# scp reports nothing about what it moved, so the manifest is recorded from its
# length on disk and on the RAW basis -- it crossed the wire compressed by ssh
# and therefore smaller. About 44 kB against tens of gigabytes a day, so the
# gap is negligible; it is labelled anyway rather than rounded into the wire
# total, because the moment a raw number is allowed into a wire column nobody
# can tell which of them are which.
python3 -m ops.bandwidth file-size --path "$stage_root/data/manifest.json" \
  --leg bigmem-egress --family manifest --run publish \
  --source "manifest length on disk (scp reports no transferred byte count)" || true

# Operations pages. Deliberately NOT part of the manifest and NOT under
# artifacts/, so the publish gate and the pruner both leave them alone. They
# reach the VPS only here, and Caddy serves them only behind forward_auth.
# AUTHORED operator pages ride the same review push as the GENERATED ones.
# The container mounts runtime/review at /ops, which shadows anything the
# image carries -- a page committed at public/ops/ is invisible until it is
# copied into the review tree. Found the hard way on 2026-09-12: the
# computation-methods page deployed into the image, and /ops served the SPA
# shell in its place. Canonical copies stay in git under public/ops/.
if [ -d public/ops ]; then
  cp -f public/ops/*.html public/data/review/ 2>/dev/null || true
fi
if [ -d public/data/review ]; then
  ssh -o BatchMode=yes "$remote_host" "install -d -m 755 /root/space-teaching-aid/runtime/review"
  rsync -az --stats --out-format='XFER|%l|%b|%n' --chmod=D755,F644 \
    public/data/review/ "$remote_host:/root/space-teaching-aid/runtime/review/" \
    > "$bandwidth_log"
  # Forced to their own family: these filenames carry no artifact prefix, so
  # without this they would pile into "other", where a genuinely new layer
  # appearing unannounced would be indistinguishable from the watchdog page.
  python3 -m ops.bandwidth rsync-push --run publish-ops-pages --force-family ops-pages \
    --file "$bandwidth_log" || true
fi
ssh -o BatchMode=yes "$remote_host" "chmod 644 '$remote_data/.manifest.next' && mv -f '$remote_data/.manifest.next' '$remote_data/manifest.json'"
# The VPS holds 150 GB total and shares it with Bob's backups and recovery
# archives. Files the CURRENT manifest references are never pruned regardless
# of age -- see the `keep` set in deploy/prune_data.py -- so this window only
# governs SUPERSEDED artifacts, and its only job is to be a grace period for a
# browser that read the manifest a moment ago and is still fetching what it
# named. That is a matter of seconds. Any window longer than that is not
# safety, it is just stored garbage.
#
# 72 h needed ~29 GB and took the disk to 97% on 2026-08-08. Cutting it to 18 h
# did NOT help, and the reason is worth keeping: the window is measured against
# how long a superseded file has existed, not how much is produced. On
# 2026-08-08 the tree held 33.3 GB, of which the live site needed 2.4 GB across
# 267 files -- the other 30.9 GB was 7,153 superseded files, every one of them
# under 18 h old and therefore untouchable. orbit-release rewrites all 256
# catalogue shards hourly and aurora frames are ~36 MB apiece, so the tree
# gains thousands of dead files a day without any of them ageing out. A window
# sized for retention cannot bound a directory whose churn is the problem.
#
# Three hours is a thousandfold more grace than a page load needs and reclaimed
# 22.9 GB the first time it ran. On bigmem, the canonical environmental and
# orbit histories live under /mnt/d; public/data is only the hot publish
# workspace. Keep one day of superseded local artifacts for debugging and
# republishing, then let the same manifest-aware pruner rotate them off the SSD.
# A seven-day grace grew this directory to 127 GB even though the live manifest
# referenced only 270 files. Files named by the current manifest remain protected
# regardless of age, so shortening this window cannot remove the live release.
# PUSH THE PRUNER BEFORE RUNNING IT. This machine's copy is the source of
# record and is in git; the VPS copy is a deployment artifact and nothing ever
# refreshed it. On 2026-08-27 the two had been diverged for weeks and it was
# destroying live data: the VPS copy predated the `referenced()` helper, so it
# walked only TOP-LEVEL manifest records and treated every nested shard record
# as garbage. All 256 orbit-history shards were 404 on the live site, and so
# were 9 of the 20 thermosphere-msis shards -- a second layer nobody had
# noticed, quietly losing a file every time one aged past the window.
#
# One rsync closes the class, not just the instance. Running remote code that
# no local step ever updates is the actual defect; the missing helper was only
# how it showed. Keep this line immediately above the invocation so the copy
# that runs is always the copy that was just shipped.
rsync -az --chmod=F755 deploy/prune_data.py \
  "$remote_host:/root/space-teaching-aid/deploy/prune_data.py"
ssh -o BatchMode=yes "$remote_host" "python3 /root/space-teaching-aid/deploy/prune_data.py '$remote_data' --max-age-hours 3"
python3 deploy/prune_data.py public/data --max-age-hours 24
python3 -m pipeline.prune_swmf_cache /mnt/d/space-explorer/swmf-cache --max-age-hours 96
