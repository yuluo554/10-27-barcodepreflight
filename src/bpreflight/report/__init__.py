"""报告子包：数据结构 + 两种纯排版渲染器。

**零判定**：本子包只消费 `pipeline` 产出的 `Report`；不得 import
`bpreflight.gs1` / `bpreflight.symbols` / `bpreflight.print`（由
`tests/test_report_render.py::test_render_layer_has_no_judgement` 走 AST 守门）。
"""

from bpreflight.report.model import Report, Finding  # noqa: F401

__all__ = ["Report", "Finding"]
