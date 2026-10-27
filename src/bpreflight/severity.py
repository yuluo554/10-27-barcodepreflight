"""严重级别与 verdict 派生。

口径来源：`data/README.md` §8.5（级别）与 §8.8（verdict 三值）。
本模块是全仓唯一的级别序实现——不要在别处再写一遍 `{"error": 3, ...}`。
"""

OK = "ok"
INFO = "info"
WARN = "warn"
ERROR = "error"

#: 级别从低到高的固定序。排序、门槛比较都只认这一处。
_SEVERITY_ORDER = (OK, INFO, WARN, ERROR)
_SEVERITY_RANK = {name: index for index, name in enumerate(_SEVERITY_ORDER)}

VERDICT_PASS = "pass"
VERDICT_WARN = "warn"
VERDICT_FAIL = "fail"

#: verdict 只有三个值（§8.8）。"不可判"走 threshold_status / skipped / severity 降级。
VERDICTS = (VERDICT_PASS, VERDICT_WARN, VERDICT_FAIL)


def rank(severity):
    """返回级别的序（0=ok .. 3=error）。未知级别报 ValueError，不静默当 ok。"""
    try:
        return _SEVERITY_RANK[severity]
    except KeyError:
        raise ValueError("unknown severity: {!r}".format(severity))


def worst(severities):
    """取最严重级别；空序列返回 ok（"没有 finding" 的语义由调用方负责区分）。"""
    worst_name = OK
    for name in severities:
        if rank(name) > rank(worst_name):
            worst_name = name
    return worst_name


def verdict_for(severities):
    """由 findings 的最严重级别派生 verdict（§8.8）。

    **不设 unknown**：verdict 必须只由 findings 决定，否则同一输入会因"是否装了 oracle"
    而产出不同 verdict，破坏确定性。
    """
    top = worst(severities)
    if top == ERROR:
        return VERDICT_FAIL
    if top == WARN:
        return VERDICT_WARN
    return VERDICT_PASS
