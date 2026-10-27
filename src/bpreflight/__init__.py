"""bpreflight — 条码印前可扫描性审计器。

纯本地、零网络、参数驱动：从生成参数（符号类型、X-dimension、静区、目标 DPI、
条/空颜色、条高、放大率）判定"这个条码印出来会扫不出"，并给出可执行修复项。

版本号是**唯一来源**：`pyproject.toml` 通过 `dynamic = ["version"]` 读这里。
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
