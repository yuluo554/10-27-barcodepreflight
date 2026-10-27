"""Element string -> positional elements.

Two surface forms are accepted, because both appear in the wild and the
dictionary header describes both:

  bracketed   `(01)09501101530003(17)251200(10)BATCH`   — boundaries explicit
  raw FNC1    `0109501101530003\x1d17251200\x1dBATCH`   — GS1 carrier transport form

The bracketed form carries its own boundaries, so an unknown AI is contained
and parsing continues. In the raw form the AI length is what tells you where
the value ends, so an unknown AI makes the remainder unparseable — the parser
stops and hands back the leftover text instead of guessing.

Nothing here decides whether an element is *valid*; that is `validators.py`.
This module only answers "which AI, which characters, in which order".
"""

import re

from bpreflight.gs1.dictionary import FNC1

#: `(01)` .. `(9999)` — AI widths 2..4 are the only ones the table uses.
_BRACKETED = re.compile(r"\(([0-9]{2,4})\)")

#: Issue kinds. `unknown_ai` is a judgement (the id exists in the vocabulary);
#: `malformed` means "cannot even split this string", which is an input problem.
ISSUE_UNKNOWN_AI = "unknown_ai"
ISSUE_MALFORMED = "malformed"


class Element(object):
    """One (AI, value) pair at a known position in the element string."""

    __slots__ = ("ai", "value", "position", "aid")

    def __init__(self, ai, value, position, aid):
        self.ai = ai
        self.value = value
        self.position = position
        self.aid = aid

    @property
    def label(self):
        return "({}){}".format(self.ai, self.value)

    def __repr__(self):
        return "Element({!r})".format(self.label)


class Issue(object):
    """A parse problem: either an unknown AI or an unsplittable string."""

    __slots__ = ("kind", "position", "ai", "detail")

    def __init__(self, kind, position, ai=None, detail=""):
        self.kind = kind
        self.position = position
        self.ai = ai
        self.detail = detail

    def __repr__(self):
        return "Issue({}@{}{})".format(self.kind, self.position, " " + self.ai if self.ai else "")


def looks_bracketed(text):
    """`(` at the head means the bracketed HRI form. No character sniffing."""
    return text.startswith("(")


def parse(text, dictionary):
    """Parse `text` into `(elements, issues)`.

    Determinism: elements come back in string order and positions are the
    element ordinal, so two runs over the same input always produce the same
    findings and the same fingerprints.
    """
    if not isinstance(text, str):
        raise TypeError("element string must be a string")
    if not text:
        return [], [Issue(ISSUE_MALFORMED, 0, detail="empty element string")]
    if looks_bracketed(text):
        return _parse_bracketed(text, dictionary)
    return _parse_raw(text, dictionary)


def _parse_bracketed(text, dictionary):
    elements = []
    issues = []
    position = 0
    cursor = 0
    length = len(text)
    while cursor < length:
        match = _BRACKETED.match(text, cursor)
        if not match:
            issues.append(
                Issue(
                    ISSUE_MALFORMED,
                    position,
                    detail="expected an AI in parentheses at offset {}".format(cursor),
                )
            )
            return elements, issues
        ai = match.group(1)
        value_start = match.end()
        next_match = _BRACKETED.search(text, value_start)
        value_end = next_match.start() if next_match else length
        value = text[value_start:value_end]
        aid = dictionary.get(ai)
        if aid is None:
            issues.append(Issue(ISSUE_UNKNOWN_AI, position, ai=ai, detail="unknown AI"))
        else:
            elements.append(Element(ai, value, position, aid))
        position += 1
        cursor = value_end
    return elements, issues


def _parse_raw(text, dictionary):
    elements = []
    issues = []
    position = 0
    cursor = 0
    length = len(text)
    while cursor < length:
        char = text[cursor]
        if char == FNC1:
            # A separator with no field before it is not a legal element string.
            issues.append(
                Issue(ISSUE_MALFORMED, position, detail="stray FNC1 at offset {}".format(cursor))
            )
            return elements, issues
        match = dictionary.match_prefix(text[cursor:])
        if match is None:
            issues.append(
                Issue(
                    ISSUE_UNKNOWN_AI,
                    position,
                    ai=text[cursor:cursor + max(_AI_WIDTHS)],
                    detail="no AI in the dictionary matches the head of the data",
                )
            )
            return elements, issues
        ai, ai_width = match
        aid = dictionary.require(ai)
        value_start = cursor + ai_width
        fixed = aid.fixed_length
        if fixed is None:
            # Variable length: FNC1 terminates it, or the string ends.
            separator = text.find(FNC1, value_start)
            value_end = length if separator < 0 else separator
            if value_end == value_start:
                issues.append(
                    Issue(
                        ISSUE_MALFORMED,
                        position,
                        ai=ai,
                        detail="zero-length value for a variable-length AI",
                    )
                )
                return elements, issues
        else:
            value_end = value_start + fixed
            if value_end > length:
                issues.append(
                    Issue(
                        ISSUE_MALFORMED,
                        position,
                        ai=ai,
                        detail="field truncated: {} needs {} characters".format(ai, fixed),
                    )
                )
                return elements, issues
        elements.append(Element(ai, text[value_start:value_end], position, aid))
        position += 1
        cursor = value_end
        if cursor < length and text[cursor] == FNC1:
            cursor += 1
    return elements, issues


#: Widest AI in the table; only used to bound the "unknown AI" snippet.
_AI_WIDTHS = (2, 3, 4)
