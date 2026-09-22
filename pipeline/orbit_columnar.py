"""Persistent representation of element_set, never persistent analysis results.

See docs/orbit-columnar.md for the integrity/consumer and storage contracts.
The sweep uses certified generations and runs budgeted maintenance before reading.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
from dataclasses import dataclass
import fcntl
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import struct
import time
import uuid

import numpy as np

from pipeline import orbit_campaigns, orbit_history

FIELDS = ("epoch_ms", "mean_motion", "eccentricity", "inclination", "bstar", "raan", "arg_perigee")
SCALES = (None, 1e8, 1e8, 1e4, 1e12, 1e4, 1e4)
COLUMNS = "norad, epoch_ms, mean_motion_q, eccentricity_q, inclination_q, bstar_q, raan_q, arg_perigee_q"
INDEX_DTYPE = np.dtype([("norad", "<u4"), ("offset", "<u4"), ("length", "<u4")])
RAW_DTYPE = np.dtype([(n, "<i8") for n in FIELDS[:4]] + [("valid", "u1")] + [(n, "<i8") for n in FIELDS[4:]])
RAW_PACK = struct.Struct("<4qB3q")
OWNER = "orbit-columnar-v1"
MAX_ROWS = 2**32 - 1
BYTE_BUDGET = 30 * 1024**3  # current + replacement; refuses excess, never deletes source
FILE_BUDGET = 40
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "runtime" / "orbit-columnar"
_deadline = ContextVar("columnar_maintenance_deadline", default=None)


class BudgetExceeded(RuntimeError):
    """Maintenance stopped without certifying incomplete work."""


def _check_budget():
    deadline = _deadline.get()
    if deadline is not None and time.monotonic() >= deadline:
        raise BudgetExceeded("columnar maintenance time budget exhausted")


class IntegrityError(RuntimeError):
    """Source or representation is unproven. A consumer must abort its pass."""


class SourceChanged(IntegrityError):
    pass


def _stat(path):
    try:
        s = Path(path).stat()
        return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]
    except FileNotFoundError:
        return None


def _source_stamp(path):
    # ctime detects same-size writes even if mtime is restored. SHM is excluded:
    # readers alter it. WAL and rollback journal changes conservatively invalidate.
    return {suffix: _stat(str(path) + suffix) for suffix in ("", "-wal", "-journal")}


class _Source:
    def __init__(self, path=None):
        self.path = Path(path if path is not None else orbit_history.archive_db_path()).resolve()
        if not self.path.is_file():  # avoid the opener's absent-file writable fallback
            raise FileNotFoundError(self.path)
        self.db = orbit_campaigns.open_archive_for_reading(self.path)
        # Optional representation checks must never inherit the authoritative
        # reader's long writer-lock wait. A busy source falls back to SQLite.
        try:
            self.db.execute("PRAGMA busy_timeout=0")
            if _deadline.get() is not None:
                self.db.set_progress_handler(self._expired, 10000)
            self.version = self.db.execute("PRAGMA data_version").fetchone()[0]
            self.stamp = _source_stamp(self.path)
        except Exception:
            self.db.close()
            raise

    @staticmethod
    def _expired():
        return int(time.monotonic() >= _deadline.get())

    def check(self):
        _check_budget()
        version = self.db.execute("PRAGMA data_version").fetchone()[0]
        stamp = _source_stamp(self.path)
        if version != self.version or stamp != self.stamp:
            changed = [suffix or "database" for suffix in stamp if stamp[suffix] != self.stamp[suffix]]
            raise SourceChanged(f"Archive changed during this operation (data_version {self.version}->{version}, "
                                f"files {changed}); discard the pass and reconcile again")

    def close(self):
        self.db.close()


def _scope(only):
    if only is None:
        return None
    values = sorted(set(int(n) for n in only))
    if any(n < 0 or n > MAX_ROWS for n in values):
        raise ValueError("NORAD does not fit uint32")
    return values


def _raw_objects(source, only, page_rows=32768):
    if only == []:  # paged_element_sets interprets [] as ALL, so intercept it
        return
    rows = orbit_history.paged_element_sets(source.db, only=only, page_rows=page_rows, columns=COLUMNS)
    for norad, group in itertools.groupby(rows, key=lambda r: r[0]):
        raw = bytearray()
        for position, (_, epoch, mm, ecc, inc, bstar, raan, argp) in enumerate(group):
            if position % 1024 == 0:
                _check_budget()
            raw.extend(RAW_PACK.pack(epoch, mm, ecc, inc, bstar is not None,
                                     0 if bstar is None else bstar, raan, argp))
        source.check()
        yield int(norad), np.frombuffer(raw, dtype=RAW_DTYPE)
    source.check()


def _fingerprint(norad, raw):
    return {"norad": norad, "length": len(raw),
            "first_epoch_ms": int(raw["epoch_ms"][0]), "last_epoch_ms": int(raw["epoch_ms"][-1]),
            "raw_sha256": hashlib.sha256(struct.pack("<Q", norad) + raw.tobytes()).hexdigest()}


def _dequantise(raw):
    result = {"epoch_ms": raw["epoch_ms"].copy()}
    for name, scale in zip(FIELDS[1:], SCALES[1:]):
        q = raw[name]
        # float64 conversion must first preserve the integer; then division must
        # still allow exact recovery. Never silently accept an out-of-domain q.
        if np.any(q > 2**53 - 1) or np.any(q < -(2**53 - 1)):
            raise IntegrityError(f"{name}: quantised integer outside exact float64 domain")
        value = q.astype("<f8") / scale
        if not np.array_equal(np.rint(value * scale).astype("<i8"), q):
            raise IntegrityError(f"{name}: float64 does not round-trip the quantised value")
        if name == "bstar":
            value[raw["valid"] == 0] = np.nan
        result[name] = value
    return result


def _json(path, value):
    with open(path, "w") as f:
        json.dump(value, f, sort_keys=True, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024**2), b""):
            _check_budget()
            h.update(chunk)
    return h.hexdigest()


def _generation(root):
    pointer = json.loads((root / "CURRENT").read_text())
    name = pointer["generation"]
    if not name.startswith("gen-") or len(name) != 36 or any(c not in "0123456789abcdef" for c in name[4:]):
        raise IntegrityError("Invalid generation pointer")
    directory = root / name
    if directory.is_symlink():
        raise IntegrityError("Symlink generation refused")
    manifest_path = directory / "manifest.json"
    if _hash(manifest_path) != pointer["manifest_sha256"]:
        raise IntegrityError("Manifest hash differs")
    m = json.loads(manifest_path.read_text())
    if m["format"] != OWNER or m["generation"] != name:
        raise IntegrityError("Unknown store format")
    return directory, m


def _map(directory, m):
    arrays = {}
    for name in (*FIELDS, "index"):
        dtype = INDEX_DTYPE if name == "index" else np.dtype("<i8" if name == "epoch_ms" else "<f8")
        count = len(m["objects"]) if name == "index" else m["rows"]
        p = directory / (name + ".bin")
        if p.is_symlink() or p.stat().st_size != count * dtype.itemsize:
            raise IntegrityError(f"Wrong file size/type: {name}")
        arrays[name] = np.memmap(p, dtype=dtype, mode="r", shape=(count,)) if count else np.empty(0, dtype=dtype)
        arrays[name].flags.writeable = False
    expected = np.array([(o["norad"], o["offset"], o["length"]) for o in m["objects"]], dtype=INDEX_DTYPE)
    if not np.array_equal(arrays["index"], expected):
        raise IntegrityError("Object index differs from manifest")
    offset, last = 0, -1
    for obj in m["objects"]:
        if obj["offset"] != offset or obj["norad"] <= last or obj["length"] <= 0:
            raise IntegrityError("Invalid object segmentation")
        offset += obj["length"]
        last = obj["norad"]
    if offset != m["rows"] or offset > MAX_ROWS:
        raise IntegrityError("Row count/index overflow")
    return arrays


def _check_files(directory, m, *, hashes):
    for name in (*FIELDS, "index"):
        path = directory / (name + ".bin")
        if hashes:
            if _hash(path) != m["files"][name]["sha256"]:
                raise IntegrityError(f"Column content hash differs: {name}")
        elif _stat(path) != m["files"][name]["stat"]:
            raise IntegrityError(f"Column changed since certification: {name}")


def _halt(root, reason):
    # This receipt is deliberately sticky across source/file restoration.
    temp = root / ("halt-" + uuid.uuid4().hex)
    _json(temp, {"reason": str(reason), "time": time.time()})
    os.replace(temp, root / "HALTED.json")
    _fsync_dir(root)


@contextmanager
def _writer(root):
    root = Path(root).resolve()
    _check_budget()
    root.mkdir(parents=True, exist_ok=True)
    with open(root / ".writer", "a") as lock:
        # Single-flight maintenance, nonblocking; never waits on another writer.
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        marker = root / "OWNER"
        if marker.exists():
            if marker.read_text() != OWNER:
                raise IntegrityError("Not an owned columnar root")
        elif set(p.name for p in root.iterdir()) != {".writer"}:
            raise IntegrityError("Refusing to adopt a nonempty directory")
        else:
            marker.write_text(OWNER)
        yield root


def _inventory(root):
    files = list(root.rglob("*"))
    if any(p.is_symlink() for p in files):
        raise IntegrityError("Store must not contain symlinks")
    files = [p for p in files if p.is_file()]
    return sum(p.stat().st_size for p in files), len(files)


def _cleanup(root, apply):
    current, m = _generation(root)
    _check_files(current, m, hashes=True)
    candidates = []
    for p in root.iterdir():
        if p != current and p.is_dir() and p.name.startswith("gen-") and len(p.name) == 36:
            if p.is_symlink() or any(f.is_symlink() or not f.is_file() for f in p.iterdir()):
                raise IntegrityError("Unsafe cleanup candidate")
            allowed = {n + ".bin" for n in (*FIELDS, "index")} | {"manifest.json", "OWNER"}
            if (p / "OWNER").read_text() != OWNER or not {f.name for f in p.iterdir()} <= allowed:
                raise IntegrityError("Unowned cleanup candidate")
            candidates.append(p)
    result = {"apply": apply, "paths": [str(p) for p in candidates],
              "bytes": sum(f.stat().st_size for p in candidates for f in p.iterdir())}
    if apply:
        for p in candidates:
            shutil.rmtree(p)
        _check_files(current, m, hashes=True)
        _fsync_dir(root)
    return result


def cleanup(root, *, apply=False):
    """List (default) or delete only owned, superseded generations; keep CURRENT."""
    root = Path(root).resolve()
    if not (root / "OWNER").is_file() or (root / "OWNER").read_text() != OWNER:
        raise IntegrityError("Missing owned cleanup root")
    if not apply:
        return _cleanup(root, False)
    with _writer(root):
        return _cleanup(root, True)


def _write_generation(root, source, only, objects, *, budget_bytes, metadata):
    name = "gen-" + uuid.uuid4().hex
    directory = root / name
    used, files = _inventory(root)
    if files + 11 > FILE_BUDGET or used >= budget_bytes:
        raise IntegrityError("Storage budget exceeded; inspect cleanup dry run")
    directory.mkdir()
    (directory / "OWNER").write_text(OWNER)
    summaries, offset = [], 0
    try:
        with ExitStack() as stack:
            streams = {n: stack.enter_context(open(directory / (n + ".bin"), "wb")) for n in (*FIELDS, "index")}
            digests = {n: hashlib.sha256() for n in streams}
            for summary, arrays in objects:
                _check_budget()
                length = summary["length"]
                if not 0 <= summary["norad"] <= MAX_ROWS or offset + length > MAX_ROWS:
                    raise IntegrityError("uint32 index overflow; rebuild with a new format")
                if used + (offset + length) * 56 + (len(summaries) + 1) * 512 > budget_bytes:
                    raise IntegrityError("Atomic replacement would exceed byte budget")
                summary = dict(summary, offset=offset)
                summaries.append(summary)
                for n in FIELDS:
                    _check_budget()
                    data = np.ascontiguousarray(arrays[n], dtype="<i8" if n == "epoch_ms" else "<f8").tobytes()
                    streams[n].write(data)
                    digests[n].update(data)
                data = np.array([(summary["norad"], offset, length)], dtype=INDEX_DTYPE).tobytes()
                streams["index"].write(data)
                digests["index"].update(data)
                offset += length
            for f in streams.values():
                f.flush()
                os.fsync(f.fileno())
        source.check()
        m = {"format": OWNER, "generation": name, "source_path": str(source.path),
             "source_stamp": source.stamp, "only": only, "rows": offset,
             "objects": summaries, "created_at": time.time(), "maintenance": metadata,
             "files": {n: {"sha256": digests[n].hexdigest(), "stat": _stat(directory / (n + ".bin"))} for n in streams}}
        _json(directory / "manifest.json", m)
        _fsync_dir(directory)
        # Read back hashes before certification; flush alone is not integrity proof.
        _check_files(directory, m, hashes=True)
        _map(directory, m)
        source.check()
        _json(root / "CURRENT.next", {"generation": name, "manifest_sha256": _hash(directory / "manifest.json")})
        os.replace(root / "CURRENT.next", root / "CURRENT")
        _fsync_dir(root)
        (root / "HALTED.json").unlink(missing_ok=True)
        _cleanup(root, True)
        return m
    except Exception:
        # Keep an already-promoted generation; delete only our failed staging.
        try:
            promoted = json.loads((root / "CURRENT").read_text())["generation"] == name
        except (OSError, ValueError, KeyError, TypeError):
            promoted = False
        if not promoted:
            shutil.rmtree(directory)
        raise


def build(root, *, archive=None, only=None, budget_bytes=BYTE_BUDGET):
    """Full rebuild of the declared scope, paged reads, atomic generation switch."""
    only = _scope(only)
    with _writer(root) as root:
        source = _Source(archive)
        try:
            objects = ((_fingerprint(n, raw), _dequantise(raw)) for n, raw in _raw_objects(source, only))
            return _write_generation(root, source, only, objects, budget_bytes=budget_bytes,
                                     metadata={"operation": "build"})
        finally:
            source.close()


def _compare(source, m):
    old = {o["norad"]: o for o in m["objects"]}
    current, changed = [], []
    for n, raw in _raw_objects(source, m["only"]):
        item = _fingerprint(n, raw)
        current.append(item)
        previous = old.pop(n, None)
        if previous is None or any(previous[k] != item[k] for k in item):
            changed.append(n)
    return current, sorted(changed + list(old))


def verify(root, *, archive=None):
    """Scan/count/hash all raw projected rows plus all column bytes; raise and halt on mismatch.

    Never clears HALTED. A successful build/append is the only recovery path.
    Returns changed NORADs on the raised exception's ``changed_objects`` attribute.
    """
    root = Path(root).resolve()
    with _writer(root):
        source = _Source(archive)
        try:
            directory, m = _generation(root)
            if str(source.path) != m["source_path"]:
                raise IntegrityError("Wrong source archive")
            current, changed = _compare(source, m)
            if changed:
                error = IntegrityError(f"SQLite/store mismatch in {len(changed)} objects: {changed[:20]}")
                error.changed_objects = changed
                raise error
            _check_files(directory, m, hashes=True)
            _map(directory, m)
            source.check()
            return {"ok": True, "rows": sum(o["length"] for o in current), "objects": len(current),
                    "halted": (root / "HALTED.json").exists(),
                    "needs_recertification": source.stamp != m["source_stamp"] or any(
                        _stat(directory / (n + ".bin")) != m["files"][n]["stat"] for n in (*FIELDS, "index"))}
        except IntegrityError as error:
            _halt(root, error)
            raise
        finally:
            source.close()


def append(root, *, archive=None, budget_bytes=BYTE_BUDGET):
    """Reconcile arbitrary inserts/updates/deletes, including backfills and pruning.

    No timestamp watermark and no caller-provided 'changed' list is trusted.
    Scan every source object's raw hash; only changed objects are dequantised.
    Unchanged arrays are copied to retain one globally contiguous file per field.
    """
    with _writer(root) as root:
        directory, m = _generation(root)
        source = _Source(archive)
        try:
            if str(source.path) != m["source_path"]:
                raise IntegrityError("Wrong source archive")
            started = time.monotonic()
            current, changed = _compare(source, m)
            scan_seconds = time.monotonic() - started
            _check_files(directory, m, hashes=True)
            old_arrays = _map(directory, m)
            old = {o["norad"]: o for o in m["objects"]}
            changed_set = set(changed)
            def objects():
                for obj in current:
                    n = obj["norad"]
                    if n in changed_set:
                        found = list(_raw_objects(source, [n]))
                        if len(found) != 1 or _fingerprint(n, found[0][1]) != obj:
                            raise SourceChanged("Changed object differed on rebuild read")
                        arrays = _dequantise(found[0][1])
                    else:
                        previous = old[n]
                        sl = slice(previous["offset"], previous["offset"] + previous["length"])
                        arrays = {name: old_arrays[name][sl] for name in FIELDS}
                    yield obj, arrays
            return _write_generation(root, source, m["only"], objects(), budget_bytes=budget_bytes,
                                     metadata={"operation": "append", "changed_objects": changed,
                                               "source_scan_seconds": scan_seconds})
        except IntegrityError as error:
            _halt(root, error)
            raise
        finally:
            source.close()


@dataclass(frozen=True)
class ObjectArrays:
    norad: int
    columns: dict[str, np.ndarray]

    def rows(self):
        """Compatibility adapter; allocates Python tuples, forfeiting CPU savings."""
        for row in zip(*(self.columns[n] for n in FIELDS)):
            yield (int(row[0]), *[None if n == "bstar" and np.isnan(v) else float(v)
                                 for n, v in zip(FIELDS[1:], row[1:])])


class Store:
    """Use as a context manager; publish only AFTER successful context exit.

    Guards check the certified local source and generation before each yield and
    on exit. A concurrent source commit aborts the pass. Borrowed read-only views
    must not be reused outside this lifetime. Mathematics remains stateless.
    """
    def __init__(self, root, *, archive=None):
        self.root = Path(root).resolve()
        self.source = _Source(archive)
        self.closed = False
        try:
            self.directory, self.manifest = _generation(self.root)
            self.pointer_stamp = _stat(self.root / "CURRENT")
            self.manifest_stamp = _stat(self.directory / "manifest.json")
            self.assert_current()
            self.arrays = _map(self.directory, self.manifest)
            self.objects_by_norad = {o["norad"]: o for o in self.manifest["objects"]}
            self.assert_current()
        except Exception:
            self.close()
            raise

    def assert_current(self):
        if self.closed:
            raise IntegrityError("Store is closed")
        try:
            if (self.root / "HALTED.json").exists():
                raise IntegrityError("Store is HALTED; rebuild or reconcile before serving")
            self.source.check()
            if str(self.source.path) != self.manifest["source_path"] or self.source.stamp != self.manifest["source_stamp"]:
                raise SourceChanged("Archive changed since certification; run append/build before serving")
            if _stat(self.root / "CURRENT") != self.pointer_stamp or _stat(self.directory / "manifest.json") != self.manifest_stamp:
                raise IntegrityError("Generation changed during read")
            _check_files(self.directory, self.manifest, hashes=False)
        except IntegrityError:
            self.closed = True
            self.source.close()
            raise

    def iter_objects(self, *, only=None, since_ms=None, start_after=None):
        objects = (self.manifest["objects"] if only is None else
                   (self.objects_by_norad[n] for n in sorted(set(only)) if n in self.objects_by_norad))
        for obj in objects:
            if start_after is not None and obj["norad"] <= start_after:
                continue
            self.assert_current()
            start, end = obj["offset"], obj["offset"] + obj["length"]
            if since_ms is not None:
                start += int(np.searchsorted(self.arrays["epoch_ms"][start:end], since_ms))
            if start < end:
                yield ObjectArrays(obj["norad"], {n: self.arrays[n][start:end] for n in FIELDS})
        self.assert_current()

    def iter_chunks(self, *, objects_per_chunk=256):
        """Yield (uint32 index, columns) with offsets rebased to contiguous views."""
        if objects_per_chunk <= 0:
            raise ValueError("objects_per_chunk must be positive")
        index = self.arrays["index"]
        for i in range(0, len(index), objects_per_chunk):
            self.assert_current()
            chunk = index[i:i + objects_per_chunk].copy()
            start = int(chunk["offset"][0])
            end = int(chunk["offset"][-1]) + int(chunk["length"][-1])
            chunk["offset"] -= start
            chunk.flags.writeable = False
            yield chunk, {n: self.arrays[n][start:end] for n in FIELDS}
        self.assert_current()

    def close(self):
        if not self.closed:
            self.source.close()
            self.closed = True
        # NumPy owns mapped-view lifetimes; do not close an mmap under a view.
        # Release our references now; consumer-held borrowed views remain theirs.
        if hasattr(self, "arrays"):
            self.arrays.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.assert_current()
        finally:
            self.close()


def open_store(root, *, archive=None):
    return Store(root, archive=archive)


def require_scope(store, only):
    """A subset certificate can never silently truncate a broader sweep."""
    scope = store.manifest["only"]
    if scope is not None and (not only or not set(only).issubset(scope)):
        raise IntegrityError("Store scope does not cover the requested population")


def maintain(root, *, archive=None, only=None, seconds=60.0, budget_bytes=BYTE_BUDGET, dry_run=False):
    """Before-sweep maintenance, bounded in wall time and disk, never stale-serving.

    The default store covers the full archive. Explicit subset stores retain their
    scope. A failed certificate requires build; a changed source uses append.
    Checks are cooperative (1,024 rows / 4 MiB hash chunks); an OS filesystem
    operation can overrun. SQLite never waits on a writer during maintenance.
    """
    wall, cpu = time.monotonic(), time.process_time()
    # Opening an already certified store is a read, even with no maintenance
    # allowance left. The deadline applies only when a writer is needed.
    token = _deadline.set(None)
    operation = "current"
    try:
        try:
            with open_store(root, archive=archive) as store:
                require_scope(store, only)
            return {"operation": operation, "wall_seconds": time.monotonic() - wall,
                    "cpu_seconds": time.process_time() - cpu}
        except SourceChanged:
            operation = "append"
        except (IntegrityError, OSError, ValueError, KeyError, TypeError):
            operation = "build"
        if dry_run:
            return {"operation": operation, "dry_run": True, "budget_seconds": seconds,
                    "budget_bytes": budget_bytes, "budget_files": FILE_BUDGET}
        _deadline.set(wall + max(0.0, seconds))
        _check_budget()
        if operation == "append":
            try:
                append(root, archive=archive, budget_bytes=budget_bytes)
            except SourceChanged:
                raise  # a moving source is not a corrupt representation
            except BlockingIOError:
                raise  # another maintenance writer owns this root; never wait
            except (IntegrityError, OSError, ValueError, KeyError, TypeError):
                operation = "build"
        if operation == "build":
            # Full scope on automatic creation/recovery: bounded fixtures may
            # explicitly build subsets; a bad subset cannot become silent loss.
            build(root, archive=archive, budget_bytes=budget_bytes)
        with open_store(root, archive=archive) as store:
            require_scope(store, only)
        return {"operation": operation, "wall_seconds": time.monotonic() - wall,
                "cpu_seconds": time.process_time() - cpu}
    finally:
        _deadline.reset(token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("build", "verify", "append", "maintain", "cleanup", "status"))
    parser.add_argument("root", type=Path)
    parser.add_argument("--archive", type=Path, default=orbit_history.archive_db_path())
    parser.add_argument("--only", type=int, nargs="+")
    parser.add_argument("--apply", action="store_true", help="apply cleanup; default is dry run")
    parser.add_argument("--seconds", type=float, default=60.0, help="wall budget for maintain (default 60s)")
    parser.add_argument("--dry-run", action="store_true", help="preview maintenance without writing")
    args = parser.parse_args()
    if args.dry_run and args.operation != "maintain":
        parser.error("--dry-run is for maintain; cleanup is already a dry run unless --apply")
    if args.operation == "cleanup":
        result = cleanup(args.root, apply=args.apply)
    elif args.operation == "status":
        size, files = _inventory(args.root)
        with open_store(args.root, archive=args.archive) as store:
            result = {"ok": True, "rows": store.manifest["rows"], "bytes": size, "files": files,
                      "budget_bytes": BYTE_BUDGET, "budget_files": FILE_BUDGET,
                      "warning": size > 24 * 1024**3, "over_budget": size > BYTE_BUDGET or files > FILE_BUDGET}
    else:
        options = {"archive": args.archive}
        if args.only is not None and args.operation != "build":
            parser.error("--only declares build scope; append/verify always cover the entire stored scope")
        if args.operation == "build":
            options["only"] = args.only
        if args.operation == "maintain":
            if not 0 <= args.seconds <= 1800:
                parser.error("maintain requires a budget between 0 and 1800 seconds")
            options["seconds"] = args.seconds
            options["dry_run"] = args.dry_run
        result = globals()[args.operation](args.root, **options)
        if "objects" in result and isinstance(result["objects"], list):
            result = {k: v for k, v in result.items() if k not in ("objects", "files")}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
