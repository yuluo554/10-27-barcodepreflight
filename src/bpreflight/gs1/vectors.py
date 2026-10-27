"""Loader for `data/vectors/gs1_vectors.json`.

`gs1_vectors.json` is a **vector** file, not a threshold file, so it does not go
through `bpreflight/thresholds.py` (that module owns the print thresholds in
`quiet_zone.json` / `gen_spec.json`). It is loaded from exactly one place —
here — so the same "single reading point" property holds.

What the code takes from it, rather than hardcoding:

  `yymmd0.century_resolution`  the two-digit-year window that `lint_yymmd0.c`
                               expresses as a compile-time `CURRENT_YEAR`
  `identifier.lengths`         which bare identifier lengths are supported
  `checksum.vectors`           the official check-digit regression vectors

The cases themselves (`req` / `ex` / `yymmd0`) are read by the tests, which
re-derive every expectation instead of trusting a stored verdict.
"""

import io
import json

from bpreflight import paths

VECTOR_FILE = "gs1_vectors.json"


class VectorError(Exception):
    """The bundled vector file is missing or malformed (install problem, exit 3)."""


_CACHE = {}


def load():
    """Read and cache the vector document."""
    if VECTOR_FILE in _CACHE:
        return _CACHE[VECTOR_FILE]
    path = paths.vector_path(VECTOR_FILE)
    try:
        with io.open(path, "r", encoding="utf-8") as handle:
            doc = json.load(handle)
    except OSError as exc:
        raise VectorError(
            "cannot read bundled vector {!r}: {} (incomplete install?)".format(
                VECTOR_FILE, exc.strerror or exc
            )
        )
    except ValueError as exc:
        raise VectorError("bundled vector {!r} is not valid JSON: {}".format(VECTOR_FILE, exc))
    for key in ("checksum", "yymmd0", "req", "ex", "identifier"):
        if key not in doc:
            raise VectorError("{} misses top-level {!r}".format(VECTOR_FILE, key))
    _CACHE[VECTOR_FILE] = doc
    return doc


def load_century_resolution():
    """The YY -> CCYY window, as data (`yymmd0.century_resolution`)."""
    resolution = load()["yymmd0"]["century_resolution"]
    for key in ("reference_year_yy", "century_window", "centuries"):
        if key not in resolution:
            raise VectorError("gs1_vectors.json yymmd0.century_resolution misses {!r}".format(key))
    return resolution


def identifier_lengths():
    """`{length_as_str: family_label}` for bare identifiers."""
    lengths = load().get("identifier", {}).get("lengths")
    if not lengths:
        raise VectorError("gs1_vectors.json has no identifier.lengths (empty data is not a pass)")
    return lengths


def checksum_vectors():
    return load()["checksum"]["vectors"]
