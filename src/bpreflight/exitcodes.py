"""退出码矩阵——全仓唯一实现点。

口径来源：`data/README.md` §8.5。代码与文档只引用，不复述第二份规则。

```
worst = max(severity of all findings)          # ok < info < warn < error
crossed(fail_on):
  none  -> never
  warn  -> worst >= warn
  error -> worst >= error

exit = 3  若用法错误 / 输入不可解析 / 内嵌字典缺失   # 优先，且不参与判定计数
exit = 2  若 crossed 且 worst == error
exit = 1  若 crossed 且 worst == warn
exit = 0  其余
```
"""

from bpreflight.severity import ERROR, WARN, rank

EXIT_OK = 0
EXIT_WARN_CROSSED = 1
EXIT_ERROR_CROSSED = 2
EXIT_USAGE = 3

FAIL_ON_CHOICES = ("none", "warn", "error")


def crossed(fail_on, worst_severity):
    """门槛是否被跨过。`none` 永不过门槛（默认只报告不拦）。"""
    if fail_on not in FAIL_ON_CHOICES:
        raise ValueError("unknown fail_on: {!r}".format(fail_on))
    if fail_on == "none":
        return False
    if fail_on == "warn":
        return rank(worst_severity) >= rank(WARN)
    return rank(worst_severity) >= rank(ERROR)


def exit_code(fail_on, worst_severity, usage_error=False):
    """按 §8.5 计算退出码。

    `usage_error=True` 覆盖一切：用法错误 / 输入不可解析 / 字典缺失都走 3，
    不参与判定计数（所以"0 个 finding + 用法错误"必须返回 3 而不是 0）。
    """
    if usage_error:
        return EXIT_USAGE
    if not crossed(fail_on, worst_severity):
        return EXIT_OK
    if worst_severity == ERROR:
        return EXIT_ERROR_CROSSED
    return EXIT_WARN_CROSSED
