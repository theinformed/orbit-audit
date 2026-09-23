"""Reader for the public Starlink ephemeris file format.

Pure parsing. This module opens no socket, reads no database, and holds no
policy: it turns bytes that are already on disk into records, and refuses
anything it does not recognise rather than guessing.

The published format, as the operator writes it:

    created:YYYY-MM-DD HH:MM:SS UTC
    ephemeris_start:YYYY-MM-DD HH:MM:SS UTC ephemeris_stop:... step_size:60
    ephemeris_source:blend
    UVW
    <epoch> <x> <y> <z> <vx> <vy> <vz>
    <7 covariance values>
    <7 covariance values>
    <7 covariance values>
    ... the four-line record repeats ...

States are kilometres and kilometres per second in the mean-equator,
mean-equinox frame of J2000.  The epoch token is ``YYYYDDDHHMMSS.sss`` --
four-digit year, three-digit day of year, then hours, minutes and seconds.

The 21 covariance values are the lower triangle of a six by six
position/velocity covariance, row by row::

    C11
    C21 C22
    C31 C32 C33
    C41 C42 C43 C44
    C51 C52 C53 C54 C55
    C61 C62 C63 C64 C65 C66

The frame those axes are expressed in is whatever the fourth header line
names -- carried through verbatim as ``covariance_frame``.  This module does
not assert which index is radial, in-track or cross-track: that is a property
of the operator's convention, and an unverified convention is recorded, not
asserted.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import gzip
import math
from pathlib import Path
from typing import Iterator, Sequence

COVARIANCE_TERMS = 21
COVARIANCE_LINES = 3
TERMS_PER_LINE = 7
STATE_FIELDS = 7  # epoch plus three position and three velocity components

# Index of each diagonal entry inside the 21-term lower triangle.
DIAGONAL_INDEX = (0, 2, 5, 9, 14, 20)


class EphemerisFormatError(ValueError):
    """The bytes are not a Starlink ephemeris file we recognise."""


@dataclasses.dataclass(frozen=True)
class EphemerisHeader:
    created: dt.datetime
    start: dt.datetime
    stop: dt.datetime
    step_seconds: int
    source: str
    covariance_frame: str


@dataclasses.dataclass(frozen=True)
class EphemerisRecord:
    epoch: dt.datetime
    position_km: tuple[float, float, float]
    velocity_km_s: tuple[float, float, float]
    covariance: tuple[float, ...]  # 21 lower-triangular terms, or empty

    @property
    def position_sigma_km(self) -> tuple[float, float, float] | None:
        """One-sigma position on each covariance axis, in the file's frame.

        Returns ``None`` when the record carried no covariance.  A negative
        diagonal term is not silently square-rooted; it raises, because a
        negative variance means the file is not what we think it is.
        """
        if not self.covariance:
            return None
        out = []
        for index in DIAGONAL_INDEX[:3]:
            value = self.covariance[index]
            if value < 0.0:
                raise EphemerisFormatError(
                    f"negative variance {value!r} at lower-triangle index {index}"
                )
            out.append(math.sqrt(value))
        return (out[0], out[1], out[2])


@dataclasses.dataclass(frozen=True)
class Ephemeris:
    header: EphemerisHeader
    records: tuple[EphemerisRecord, ...]


def _parse_utc(text: str) -> dt.datetime:
    cleaned = text.strip()
    if cleaned.endswith("UTC"):
        cleaned = cleaned[: -len("UTC")].strip()
    try:
        stamp = dt.datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
    except ValueError as error:
        raise EphemerisFormatError(f"unreadable timestamp {text!r}") from error
    return stamp.replace(tzinfo=dt.timezone.utc)


def parse_epoch_token(token: str) -> dt.datetime:
    """``YYYYDDDHHMMSS.sss`` to an aware UTC datetime.

    The day-of-year form has no month, so a wrong split is silent rather than
    loud; the field widths are therefore fixed and checked, not inferred.
    """
    text = token.strip()
    whole, _, fraction = text.partition(".")
    if len(whole) != 13 or not whole.isdigit():
        raise EphemerisFormatError(f"unreadable epoch token {token!r}")
    year = int(whole[0:4])
    day_of_year = int(whole[4:7])
    hour = int(whole[7:9])
    minute = int(whole[9:11])
    second = int(whole[11:13])
    if not 1 <= day_of_year <= 366:
        raise EphemerisFormatError(f"day of year {day_of_year} out of range in {token!r}")
    if hour > 23 or minute > 59 or second > 60:
        raise EphemerisFormatError(f"clock field out of range in {token!r}")
    microsecond = 0
    if fraction:
        microsecond = int(round(float("0." + fraction) * 1_000_000))
    base = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
    stamp = base + dt.timedelta(
        days=day_of_year - 1, hours=hour, minutes=minute, seconds=second
    )
    return stamp + dt.timedelta(microseconds=microsecond)


def parse_header(lines: Sequence[str]) -> EphemerisHeader:
    if len(lines) < 4:
        raise EphemerisFormatError("header is shorter than four lines")
    first = lines[0].strip()
    if not first.startswith("created:"):
        raise EphemerisFormatError(f"first line is not a creation stamp: {first!r}")
    created = _parse_utc(first[len("created:") :])

    second = lines[1].strip()
    start_key, stop_key, step_key = "ephemeris_start:", "ephemeris_stop:", "step_size:"
    if start_key not in second or stop_key not in second or step_key not in second:
        raise EphemerisFormatError(f"second line is not a span declaration: {second!r}")
    start_text = second[second.index(start_key) + len(start_key) : second.index(stop_key)]
    stop_text = second[second.index(stop_key) + len(stop_key) : second.index(step_key)]
    step_text = second[second.index(step_key) + len(step_key) :]
    start = _parse_utc(start_text)
    stop = _parse_utc(stop_text)
    try:
        step_seconds = int(float(step_text.strip()))
    except ValueError as error:
        raise EphemerisFormatError(f"unreadable step size {step_text!r}") from error
    if stop <= start:
        raise EphemerisFormatError("ephemeris stop is not after ephemeris start")

    third = lines[2].strip()
    if not third.startswith("ephemeris_source:"):
        raise EphemerisFormatError(f"third line is not a source declaration: {third!r}")
    source = third[len("ephemeris_source:") :].strip()

    frame = lines[3].strip()
    if not frame or any(character.isspace() for character in frame):
        raise EphemerisFormatError(f"fourth line is not a frame name: {frame!r}")

    return EphemerisHeader(
        created=created,
        start=start,
        stop=stop,
        step_seconds=step_seconds,
        source=source,
        covariance_frame=frame,
    )


def _open_text(path: Path) -> Iterator[str]:
    if path.suffix == ".gz":
        handle = gzip.open(path, "rt", encoding="ascii", errors="strict")
    else:
        handle = open(path, "rt", encoding="ascii", errors="strict")
    with handle:
        for line in handle:
            yield line


def read(path: Path, *, max_records: int | None = None) -> Ephemeris:
    """Read a whole file.

    ``max_records`` stops after that many state records; the header is still
    parsed in full.  Nothing is skipped silently -- a line that does not fit
    the four-line pattern raises.
    """
    lines = _open_text(Path(path))
    header_lines: list[str] = []
    for line in lines:
        header_lines.append(line)
        if len(header_lines) == 4:
            break
    header = parse_header(header_lines)

    records: list[EphemerisRecord] = []
    pending: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        pending.append(line)
        if len(pending) < 4:
            continue
        records.append(_record_from_block(pending))
        pending = []
        if max_records is not None and len(records) >= max_records:
            return Ephemeris(header=header, records=tuple(records))
    if pending:
        raise EphemerisFormatError(
            f"file ends with {len(pending)} orphaned line(s); records are four lines"
        )
    if not records:
        raise EphemerisFormatError("file carries a header but no state records")
    return Ephemeris(header=header, records=tuple(records))


def _record_from_block(block: Sequence[str]) -> EphemerisRecord:
    state = block[0].split()
    if len(state) != STATE_FIELDS:
        raise EphemerisFormatError(
            f"state line carries {len(state)} fields, expected {STATE_FIELDS}"
        )
    epoch = parse_epoch_token(state[0])
    try:
        numbers = [float(value) for value in state[1:]]
    except ValueError as error:
        raise EphemerisFormatError(f"unreadable state line {block[0]!r}") from error

    covariance: list[float] = []
    for index in range(1, 1 + COVARIANCE_LINES):
        terms = block[index].split()
        if len(terms) != TERMS_PER_LINE:
            raise EphemerisFormatError(
                f"covariance line carries {len(terms)} terms, expected {TERMS_PER_LINE}"
            )
        try:
            covariance.extend(float(value) for value in terms)
        except ValueError as error:
            raise EphemerisFormatError(
                f"unreadable covariance line {block[index]!r}"
            ) from error
    if len(covariance) != COVARIANCE_TERMS:
        raise EphemerisFormatError(
            f"covariance carries {len(covariance)} terms, expected {COVARIANCE_TERMS}"
        )

    return EphemerisRecord(
        epoch=epoch,
        position_km=(numbers[0], numbers[1], numbers[2]),
        velocity_km_s=(numbers[3], numbers[4], numbers[5]),
        covariance=tuple(covariance),
    )


def spacecraft_name(filename: str) -> str | None:
    """The spacecraft name a manifest filename carries, or ``None``.

    The filename carries no catalogue number, so this name is the only join to
    the catalogue there is, and it is a name join: fallible, and counted rather
    than trusted.
    """
    stem = filename.split("/")[-1]
    parts = stem.split("_")
    for part in parts:
        if part.upper().startswith("STARLINK-"):
            return part.upper()
    return None
