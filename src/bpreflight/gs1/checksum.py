"""GS1 check digit — **the only implementation in this repository**.

`data/README.md` §8.1 is the normative statement; this module is its single
executable form. `plan/00` K1 and `plan/01` §M1 both pin the count of
`gs1_check_digit` definitions under `src/` to exactly one, and
`tests/test_checksum.py` re-runs that scan (AST + text) so a second copy
cannot appear quietly in M2+.

The rule (transcribed from upstream `lint_csum.c`, see
`src/bpreflight/data/gs1-syntax-dictionary/NOTICE`):

    the weight of the leftmost data position is decided by the parity of the
    length *including* the check digit — 3 when that length is even, else 1 —
    then alternates left to right; only data positions are summed; the check
    digit is `(10 - sum % 10) % 10`.

Two mistakes are recorded history (`data/README.md` §4.1) and both are caught
by the four official vectors:

  1. alternating 3/1 *right-to-left* over the data only (gives ...79 / ...06);
  2. writing the alternate weight as six-minus-W instead of four-minus-W (with
     the first weight 3 that collapses into "all 3s").

So there is deliberately **no fallback branch**. Two algorithms in one file is
the same as no judgement at all.
"""

#: The alternating weights. The second one is `4 - W`, *not* `6 - W`.
_WEIGHTS = (3, 1)


def _weight_for(first_weight, index):
    return first_weight if index % 2 == 0 else 4 - first_weight


def gs1_check_digit(data_digits):
    """Return the check digit (a one-character string) for `data_digits`.

    `data_digits` is the digit string **without** the check digit. Raises
    `ValueError` for non-digit input: a check digit computed over garbage is a
    worse answer than a refusal.
    """
    text = _require_digits(data_digits)
    # Total length including the check digit decides the starting weight.
    total_length = len(text) + 1
    first_weight = _WEIGHTS[0] if total_length % 2 == 0 else _WEIGHTS[1]
    total = 0
    for index, char in enumerate(text):
        total += (ord(char) - ord("0")) * _weight_for(first_weight, index)
    return str((10 - total % 10) % 10)


def gs1_is_valid(full):
    """True when `full` (data + check digit) carries a correct check digit.

    A string shorter than two characters cannot be validated and is reported
    as invalid rather than raising — callers turn that into `invalid_length`
    before they ever ask about the check digit.
    """
    text = _require_digits(full)
    if len(text) < 2:
        return False
    return gs1_check_digit(text[:-1]) == text[-1]


def _require_digits(value):
    if not isinstance(value, str):
        raise ValueError("expected a string of digits, got {!r}".format(type(value).__name__))
    if not value:
        raise ValueError("expected a non-empty digit string")
    for char in value:
        if char < "0" or char > "9":
            raise ValueError("non-digit character {!r} in {!r}".format(char, value))
    return value
