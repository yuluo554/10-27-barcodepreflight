"""Read the vendored official AI table into `AIDef` objects.

**This module implements no GS1 semantics.** It turns each dictionary line into
data and stops there: the specification components (`N14,csum,gcppos2`,
`X..20`, `[X..16]`), the `req` / `ex` attributes, the flags and the title all
become fields. The interpreters live in `validators.py` (`plan/00` D1: the
official `gs1/gs1-syntax-engine` already owns "be a GS1 parser"; we only need
the table plus four interpreters).

Dictionaries are never hand-transcribed (`plan/01` §M1): the table is read from
`src/bpreflight/data/gs1-syntax-dictionary/` and its digest is checked against
`data/vectors/dict_manifest.json` on every load. A digest mismatch is an
installation error (`DictionaryError` → exit 3), **not** a judgement.

Structural notes drawn from the table's own header:

  `AI    Flags  Specification  Attributes...  [# Title]`
  `*` pre-defined length AI not requiring an FNC1 separator
  `?` AI permitted as a GS1 Digital Link data attribute
  component `Type[,linter...]`; `N..20` is 1..20; `[...]` marks an optional
  component; only the final component may have variable length
  `req=a+b,c` mandatory association: OR over comma groups, AND within `+`
  `ex=a,b` invalid to pair with any listed AI; an AI is not exclusive of itself
"""

import io
import json
import os
import re

from bpreflight import canonical, paths

#: Attribute keys the M1 interpreters consume. `dlpkey` is recognised so it is
#: not mistaken for a component, but it belongs to Digital Link (out of scope).
ATTRIBUTE_KEYS = ("req", "ex", "dlpkey")

#: `*` and `?` plus the rest of the allocated flag characters.
_FLAG_CHARS = frozenset('*!?"$%&\'()+,-./:;<=>@[\\]^_`{|}~')

#: AI surface forms: a solitary AI or an inclusive range of equal width.
_AI_SOLITARY = re.compile(r"^[0-9]+$")
_AI_RANGE = re.compile(r"^([0-9]+)-([0-9]+)$")

#: AI lengths present in the table, longest first (deterministic prefix scan).
AI_LENGTHS = (4, 3, 2)

_COMPONENT_CORE = re.compile(r"^([NXZY])(\.\.)?([0-9]+)$")
_TITLE_MARK = "#"

#: GS1 separates variable-length fields with FNC1 (ASCII 29 in transport).
FNC1 = "\x1d"


class DictionaryError(Exception):
    """The bundled dictionary is missing, altered, or does not parse.

    The CLI maps this to exit 3 ("bundled dictionary missing") — `data/README.md`
    §8.5 keeps `3` outside the judgement counts.
    """


class Component(object):
    """One specification component, e.g. `N6,yymmd0` or `[X..16]`."""

    __slots__ = ("type", "min_length", "max_length", "linters", "optional")

    def __init__(self, type_, min_length, max_length, linters, optional):
        self.type = type_
        self.min_length = min_length
        self.max_length = max_length
        self.linters = tuple(linters)
        self.optional = optional

    @property
    def is_fixed(self):
        return self.min_length == self.max_length

    def __repr__(self):
        return "Component({}{}{}{})".format(
            "[" if self.optional else "",
            self.type,
            "" if self.is_fixed else "..",
            self.max_length,
        )


class AIDef(object):
    """One concrete AI (range entries are expanded, so 3100-3105 is six of these)."""

    __slots__ = (
        "ai",
        "entry_ai",
        "title",
        "flags",
        "components",
        "req_groups",
        "ex_patterns",
        "source_line",
        "source_text",
    )

    def __init__(
        self,
        ai,
        entry_ai,
        title,
        flags,
        components,
        req_groups,
        ex_patterns,
        source_line,
        source_text,
    ):
        self.ai = ai
        self.entry_ai = entry_ai
        self.title = title
        self.flags = flags
        self.components = tuple(components)
        self.req_groups = tuple(tuple(group) for group in req_groups)
        self.ex_patterns = tuple(ex_patterns)
        self.source_line = source_line
        self.source_text = source_text

    # ---- flags ----

    @property
    def starred(self):
        """`*` — pre-defined length, no FNC1 separator required."""
        return "*" in self.flags

    @property
    def dl_attribute(self):
        """`?` — permitted as a GS1 Digital Link data attribute."""
        return "?" in self.flags

    # ---- lengths ----

    @property
    def fixed_length(self):
        """Total length when every component is mandatory and fixed, else None."""
        total = 0
        for component in self.components:
            if component.optional or not component.is_fixed:
                return None
            total += component.min_length
        return total

    @property
    def min_length(self):
        return sum(
            component.min_length
            for component in self.components
            if not component.optional
        )

    @property
    def max_length(self):
        return sum(component.max_length for component in self.components)

    @property
    def linters(self):
        seen = []
        for component in self.components:
            for name in component.linters:
                if name not in seen:
                    seen.append(name)
        return tuple(seen)

    def __repr__(self):
        return "AIDef({}{})".format(self.ai, " " + self.title if self.title else "")


class Dictionary(object):
    """The parsed table: AI -> `AIDef`, plus the identity of the bytes read."""

    def __init__(self, entries, dict_version, sha256, source_path, stats):
        self.entries = entries
        self.dict_version = dict_version
        self.sha256 = sha256
        self.source_path = source_path
        self.stats = stats

    def __len__(self):
        return len(self.entries)

    def __contains__(self, ai):
        return ai in self.entries

    def get(self, ai):
        return self.entries.get(ai)

    def require(self, ai):
        try:
            return self.entries[ai]
        except KeyError:
            raise DictionaryError(
                "AI {!r} is not in the bundled dictionary ({})".format(
                    ai, self.dict_version
                )
            )

    def match_prefix(self, text):
        """Longest AI at the head of `text` (deterministic longest-first scan).

        Returns `(ai, value_position)` or `None`. Used by the unbracketed
        element-string reader; the bracketed form carries its own boundaries.
        """
        for length in AI_LENGTHS:
            if len(text) < length:
                continue
            candidate = text[:length]
            if candidate in self.entries:
                return candidate, length
        return None


def _parse_component(token):
    """`N6,yymmd0` / `[N3],iso3166` / `X..20` -> Component."""
    optional = token.startswith("[")
    body = token
    linters = []
    if optional:
        close = body.find("]")
        if close < 0:
            raise DictionaryError("unterminated optional component {!r}".format(token))
        core = body[1:close]
        tail = body[close + 1:]
        if tail:
            if not tail.startswith(","):
                raise DictionaryError("garbled component {!r}".format(token))
            linters = [name for name in tail[1:].split(",") if name]
    else:
        parts = body.split(",")
        core = parts[0]
        linters = [name for name in parts[1:] if name]

    match = _COMPONENT_CORE.match(core)
    if not match:
        raise DictionaryError("unrecognised component core {!r} in {!r}".format(core, token))
    type_, variable, digits = match.groups()
    limit = int(digits)
    if variable:
        return Component(type_, 1, limit, linters, optional)
    return Component(type_, limit, limit, linters, optional)


def _parse_ai_list(value):
    """`01+21,03+21` -> (("01","21"), ("03","21"))."""
    groups = []
    for chunk in value.split(","):
        if not chunk:
            continue
        members = tuple(part for part in chunk.split("+") if part)
        if members:
            groups.append(members)
    return groups


def _split_flags(tokens):
    """Peel the optional flags token off the front of `tokens`."""
    if tokens and tokens[0] and all(char in _FLAG_CHARS for char in tokens[0]):
        return tokens[0], tokens[1:]
    return "", tokens


def parse_dictionary_text(text, source_line_offset=0):
    """Parse the whole table.

    Returns `(entries, stats)`. Every non-comment, non-blank line after the
    `# AI    Flags` header must become at least one `AIDef`; an unparsable line
    raises instead of being skipped, because a silently-skipped line would make
    the AI table quietly smaller (`plan/04` §二 truth-discipline #3).
    """
    entries = {}
    stats = {
        "lines_total": 0,
        "lines_comment": 0,
        "entries": 0,
        "concrete_ais": 0,
        "components": 0,
        "with_req": 0,
        "with_ex": 0,
    }
    started = False
    for index, raw_line in enumerate(text.splitlines()):
        stats["lines_total"] += 1
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(_TITLE_MARK):
            stats["lines_comment"] += 1
            if stripped.startswith("# AI") and "Flags" in stripped:
                started = True
            continue
        if not started:
            raise DictionaryError(
                "line {} appears before the '# AI    Flags' header".format(
                    index + 1 + source_line_offset
                )
            )

        tokens = stripped.split()
        ai_token = tokens[0]
        flags, rest = _split_flags(tokens[1:])

        # Title: from the first '#' token to end of line.
        title = None
        for position, token in enumerate(rest):
            if token.startswith(_TITLE_MARK):
                title = " ".join(rest[position:])[1:].strip()
                rest = rest[:position]
                break

        components = []
        req_groups = []
        ex_patterns = []
        for token in rest:
            if "=" in token:
                key, _, value = token.partition("=")
                if key == "req":
                    req_groups.extend(_parse_ai_list(value))
                elif key == "ex":
                    ex_patterns.extend(part for part in value.split(",") if part)
                elif key not in ATTRIBUTE_KEYS:
                    raise DictionaryError(
                        "unknown attribute {!r} on AI {}".format(key, ai_token)
                    )
                continue
            if token in ATTRIBUTE_KEYS:
                continue
            components.append(_parse_component(token))

        if not components:
            raise DictionaryError("AI {} has no specification components".format(ai_token))

        concrete = _expand_ai(ai_token)
        stats["entries"] += 1
        stats["components"] += len(components)
        if req_groups:
            stats["with_req"] += 1
        if ex_patterns:
            stats["with_ex"] += 1
        for ai in concrete:
            if ai in entries:
                raise DictionaryError(
                    "AI {!r} is defined twice (entry {})".format(ai, ai_token)
                )
            entries[ai] = AIDef(
                ai=ai,
                entry_ai=ai_token,
                title=title,
                flags=flags,
                components=components,
                req_groups=req_groups,
                ex_patterns=ex_patterns,
                source_line=index + 1 + source_line_offset,
                source_text=line,
            )
            stats["concrete_ais"] += 1

    if not started:
        raise DictionaryError("dictionary has no '# AI    Flags' header line")
    if not entries:
        raise DictionaryError("dictionary parsed to zero AIs (empty data is not a pass)")
    return entries, stats


def _expand_ai(ai_token):
    match = _AI_SOLITARY.match(ai_token)
    if match:
        return [ai_token]
    match = _AI_RANGE.match(ai_token)
    if not match:
        raise DictionaryError("unrecognised AI {!r}".format(ai_token))
    low, high = match.group(1), match.group(2)
    if len(low) != len(high):
        raise DictionaryError("AI range {!r} mixes widths".format(ai_token))
    if int(low) > int(high):
        raise DictionaryError("AI range {!r} is descending".format(ai_token))
    return [str(value).zfill(len(low)) for value in range(int(low), int(high) + 1)]


def ai_pattern_matches(pattern, ai):
    """`310n` matches 3100..3109; plain digits match exactly.

    Digit wildcards only (`n`), which is the whole of the table's pattern
    language (`plan/01` §M1 keeps the surface deliberately small).
    """
    if len(pattern) != len(ai):
        return False
    for expected, actual in zip(pattern, ai):
        if expected == "n":
            if actual < "0" or actual > "9":
                return False
        elif expected != actual:
            return False
    return True


def load_manifest(path=None):
    """Read `data/vectors/dict_manifest.json`."""
    target = path or paths.vector_path("dict_manifest.json")
    try:
        with io.open(target, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except OSError as exc:
        raise DictionaryError(
            "cannot read dictionary manifest {!r}: {}".format(target, exc.strerror or exc)
        )
    except ValueError as exc:
        raise DictionaryError("dictionary manifest is not valid JSON: {}".format(exc))
    for field in ("path", "sha256", "dict_version"):
        if not manifest.get(field):
            raise DictionaryError("dictionary manifest misses {!r}".format(field))
    return manifest


def dictionary_path(manifest=None):
    """Resolve `manifest["path"]` (relative to the package `data/` dir)."""
    manifest = manifest or load_manifest()
    return os.path.join(paths.DATA_DIR, *manifest["path"].split("/"))


def load(manifest=None):
    """Load + verify + parse the vendored dictionary.

    Verification is per run, not per install: the digest is the only thing that
    says "the table the report names is the table that was read"
    (`plan/00` ledger row "AI 表来自官方字典").
    """
    manifest = manifest or load_manifest()
    path = dictionary_path(manifest)
    try:
        with io.open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise DictionaryError(
            "cannot read bundled dictionary {!r}: {} (incomplete install?)".format(
                manifest["path"], exc.strerror or exc
            )
        )
    # 摘要面 = **行尾归一后**的字节（`canonical.py`）：CRLF 检出与 LF 检出必须同一摘要，
    # 否则"换个平台克隆"就会 exit 3（M6 实测：git archive 按 autocrlf 导出 CRLF）。
    digest = canonical.sha256_of_bytes(raw)
    if digest != manifest["sha256"]:
        raise DictionaryError(
            "bundled dictionary digest mismatch: manifest says {}, file is {}".format(
                manifest["sha256"], digest
            )
        )
    try:
        text = canonical.normalize_newlines(raw).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DictionaryError("bundled dictionary is not valid UTF-8: {}".format(exc))
    entries, stats = parse_dictionary_text(text)
    return Dictionary(
        entries=entries,
        dict_version=manifest["dict_version"],
        sha256=digest,
        source_path=manifest["path"],
        stats=stats,
    )
