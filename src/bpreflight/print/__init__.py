"""M3 · 印刷层：五项检查（静区 / 放大率 / DPI 混叠 / 条高 / 颜色）。

**输入全是参数，不是图片**（`plan/01` §M3）：从生成参数推风险，不做图像采集，
也不做 ISO/IEC 15416 ⚠️ 分级（`plan/00` D6）。

三条结构纪律（与 M1/M2 同款，`plan/HANDOFF-M3` §二）：

1. **判定模块不读文件**：`ThresholdBook` 由 `pipeline` 装载后传入；`print/` 下任何
   `open()` 都会被 `tests/test_print_audit.py` 的 AST 判据抓红。这也正是
   `tools/check_thresholds.py`（阈值零硬编码）能成立的前提。
2. **未核降级只作用于 gen-spec 项**：`status == "unverified"` 的项派生的 `error`
   默认降为 `warn`，`--strict-thresholds` 恢复；`basis: "engineering-heuristic"`
   的项（DPI 每模块点数、颜色两项）没有 `status`，`threshold_status` 恒
   `"not-applicable"`、`severity` 恒定（`data/README.md` §8.2 末条）。
3. **缺参即拒判**（§8.9 G3）：缺 `x_dimension_mm` / `target_dpi` / `quiet_zone_mm`
   时只产一条 `input_incomplete`，**不产**任何 `quiet_zone_*` / `magnification_*` /
   `raster_*` 结论——不静默补默认值。
"""
