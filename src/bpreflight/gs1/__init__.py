"""GS1 data-layer checks (M1): check digit, dictionary, element strings, validators.

Boundary (`plan/00` D1): this package does **not** attempt to be a GS1 AI
parser product — the official `gs1/gs1-syntax-engine` already owns that slot.
What lives here is exactly what the auditor needs: the vendored official AI
dictionary read as data, plus four semantic interpreters (`req` / `ex` /
`yymmd0` / `csum`) and the structural checks (charset / length / date).

Layout:

  checksum.py    the only `gs1_check_digit()` in the repository (K1)
  dictionary.py  reads the vendored AI table into `AIDef` objects; no rules
  elements.py    element string -> positional elements (bracketed / FNC1 raw)
  validators.py  the four semantic interpreters + charset/length/date checks
"""
