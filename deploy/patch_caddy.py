#!/usr/bin/env python3
"""Insert the /space route without replacing Caddy's bind-mounted inode."""

from __future__ import annotations

import shutil
import sys
import re
from datetime import datetime, timezone
from pathlib import Path


LEGACY_ROUTE = """\tredir /space /space/ 308
\thandle_path /space/* {
\t\treverse_proxy space-web:8080
\t}

"""
HEADER_ROUTE = """\tredir /space /space/ 308
\thandle_path /space/* {
\t\treverse_proxy space-web:8080 {
\t\t\theader_up Accept-Encoding {http.request.header.Accept-Encoding}
\t\t}
\t}

"""
TRANSPORT_ROUTE = """\tredir /space /space/ 308
\thandle_path /space/* {
\t\treverse_proxy space-web:8080 {
\t\t\theader_up Accept-Encoding {http.request.header.Accept-Encoding}
\t\t\ttransport http {
\t\t\t\tcompression off
\t\t\t}
\t\t}
\t}

"""
ROUTE = """\tredir /space /space/ 308
\thandle_path /space/* {
\t\tencode zstd gzip
\t\treverse_proxy space-web:8080 {
\t\t\theader_up -Accept-Encoding
\t\t\ttransport http {
\t\t\t\tcompression off
\t\t\t}
\t\t}
\t}

"""
LEGACY_SPACED_ROUTE = LEGACY_ROUTE.replace("\t\t", "        ").replace("\t", "    ")


def truncate_write(path: Path, text: str) -> None:
    # Caddyfile is a single-file bind mount. Preserve its inode by writing and
    # truncating the existing file rather than replacing it with rename(2).
    with path.open("r+") as handle:
        handle.seek(0)
        handle.write(text)
        handle.truncate()
        handle.flush()


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "/root/apps/openclaw/Caddyfile")
    text = path.read_text()
    if "handle_path /space/*" in text:
        updated = text
        if LEGACY_SPACED_ROUTE in text:
            updated = text.replace(LEGACY_SPACED_ROUTE, LEGACY_ROUTE, 1)
        if LEGACY_ROUTE in updated:
            updated = updated.replace(LEGACY_ROUTE, ROUTE, 1)
        elif HEADER_ROUTE in updated:
            updated = updated.replace(HEADER_ROUTE, ROUTE, 1)
        elif TRANSPORT_ROUTE in updated:
            updated = updated.replace(TRANSPORT_ROUTE, ROUTE, 1)
        if updated != text:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = path.with_name(f"{path.name}.bak-space-upgrade-{timestamp}")
            shutil.copy2(path, backup)
            truncate_write(path, updated)
            print(f"upgraded existing /space route; backup: {backup}")
            return 0
        print("/space route already present")
        return 0

    site_start = text.find("sean.theinformed.org {")
    if site_start < 0:
        raise RuntimeError("sean.theinformed.org site block not found")
    site_end = text.find("\n}", site_start)
    if site_end < 0:
        raise RuntimeError("site block terminator not found")
    site_text = text[site_start:site_end]
    anchors = list(re.finditer(r"(?m)^[ \t]+respond[ \t]+404[ \t]*$", site_text))
    if not anchors:
        raise RuntimeError("site block's final respond 404 anchor not found")
    anchor = site_start + anchors[-1].start()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.bak-space-{timestamp}")
    shutil.copy2(path, backup)
    updated = text[:anchor] + ROUTE + text[anchor:]

    truncate_write(path, updated)
    print(f"inserted /space route; backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
