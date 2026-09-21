#!/usr/bin/env python3
"""Harvest real solar observational movies from the Helioviewer API (NASA/ESA, public domain).
Every frame carries the instrument name and UTC timestamp burned in by Helioviewer itself."""
import json, time, urllib.parse, urllib.request, os, sys

API = "https://api.helioviewer.org/v2/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "harvest")

def api(ep, **kw):
    u = API + ep + "/?" + urllib.parse.urlencode(kw)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(u, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 3: raise
            time.sleep(10)

JOBS = [
 dict(name="gannon-2024-cme",
      start="2024-05-08T18:00:00Z", end="2024-05-09T12:00:00Z",
      layers="[13,1,100],[4,1,100],[5,1,100]", scale=120,
      caption="SDO AIA 304 + SOHO LASCO C2/C3"),
 dict(name="gannon-2024-region",
      start="2024-05-08T00:00:00Z", end="2024-05-11T00:00:00Z",
      layers="[11,1,100]", scale=4.8,
      caption="SDO AIA 193"),
 dict(name="halloween-2003-cme",
      start="2003-10-28T09:00:00Z", end="2003-10-29T00:00:00Z",
      layers="[1,1,100],[4,1,100],[5,1,100]", scale=120,
      caption="SOHO EIT 195 + LASCO C2/C3"),
 dict(name="starlink-2022-sun",
      start="2022-01-29T00:00:00Z", end="2022-02-04T00:00:00Z",
      layers="[11,1,100]", scale=4.8,
      caption="SDO AIA 193"),
 # Bastille Day 2000. Same three instruments and the same scale as
 # halloween-2003-cme, because it is the same picture of the same kind of event
 # taken by the same observatory -- SDO did not exist in either year. The window
 # opens 84 minutes before the X5.7 peak at 10:24 UT so the pre-flare Sun is on
 # screen, and closes at the end of the UTC day. LASCO C2/C3 fill with proton
 # hits during it; that is the storm arriving at the spacecraft, not an artifact
 # of the harvest, and the caption says so.
 dict(name="bastille-2000-cme",
      start="2000-07-14T09:00:00Z", end="2000-07-15T00:00:00Z",
      layers="[1,1,100],[4,1,100],[5,1,100]", scale=120,
      caption="SOHO EIT 195 + LASCO C2/C3"),
 # St Patrick's Day 2015. The CME left the Sun on 15 March, two days before the
 # storm the replay draws; AIA 304 replaces EIT 195 because SDO was flying by
 # then and EIT was not the better instrument any more.
 dict(name="stpatricks-2015-cme",
      start="2015-03-15T00:00:00Z", end="2015-03-15T12:00:00Z",
      layers="[13,1,100],[4,1,100],[5,1,100]", scale=120,
      caption="SDO AIA 304 + SOHO LASCO C2/C3"),
]

def main():
    # Optional name filter, so a later session can re-harvest ONE clip without
    # re-queueing the four that are already in media/ and already cited.
    wanted = set(sys.argv[1:])
    jobs = [j for j in JOBS if not wanted or j["name"] in wanted]
    if wanted and len(jobs) != len(wanted):
        sys.exit(f"unknown job name(s): {sorted(wanted - {j[name] for j in jobs})}")
    os.makedirs(OUT, exist_ok=True)
    queued = []
    for j in jobs:
        try:
            r = api("queueMovie", startTime=j["start"], endTime=j["end"], layers=j["layers"],
                    events="", eventsLabels="false", imageScale=j["scale"],
                    x0=0, y0=0, width=512, height=512, format="mp4")
            j.update(id=r.get("id"), token=r.get("token"))
            print(f"QUEUED {j['name']} id={j['id']} eta={r.get('eta')}", flush=True)
            queued.append(j)
        except Exception as e:
            print(f"QUEUE-FAIL {j['name']}: {e}", flush=True)
        time.sleep(3)

    deadline = time.time() + 1800
    done = []
    while queued and time.time() < deadline:
        still = []
        for j in queued:
            try:
                s = api("getMovieStatus", id=j["id"], token=j["token"], format="mp4")
            except Exception as e:
                still.append(j); continue
            if s.get("status") == 2:
                url = s["url"]
                dest = os.path.join(OUT, j["name"] + ".mp4")
                urllib.request.urlretrieve(url, dest)
                j["frames"] = s.get("numFrames"); j["title"] = s.get("title")
                j["startDate"] = s.get("startDate"); j["endDate"] = s.get("endDate")
                j["bytes"] = os.path.getsize(dest); j["file"] = dest
                print(f"DONE {j['name']} frames={j['frames']} bytes={j['bytes']} title={j['title']}", flush=True)
                done.append(j)
            elif s.get("status") == 3:
                print(f"ERROR {j['name']}: {s}", flush=True)
            else:
                still.append(j)
        queued = still
        if queued: time.sleep(20)
    for j in queued:
        print(f"TIMEOUT {j['name']}", flush=True)
    json.dump(done, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
    print("HARVEST COMPLETE:", len(done), "movies", flush=True)

if __name__ == "__main__":
    main()
