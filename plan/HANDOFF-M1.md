# HANDOFF-M1 · 第 1 棒交接单（数据先行）

> 上一棒：**M0 计划与骨架**（✅ 2026-10-27）
> 本棒目标：**M1 数据层**——内嵌官方 AI 字典 + 校验位 + 四个语义解释器。
> 读法：**先跑布局门**（`AGENTS.md` 里的命令），绿了再读本文件。

## 一、当前进度与证据

M0 已完成并验证（**本地等价校验，未接远端，CI 待首推验证**）：

| 交付 | 证据（命令 + 结果） |
| --- | --- |
| 计划套件 `plan/00`–`06` | `py -3.12 tools/check_sprint_layout.py` → `LAYOUT.SECTIONS 8 份文档小节齐备` |
| 装订三件 | `LAYOUT.FILES 11 份齐备` + `LAYOUT.BINDING_HEAD` PASS |
| 四道常驻门 + 自检 | `py -3.12 tools/verify_gates.py` → `23 组变异：符合预期 23 / 不符合 0` |
| 可运行骨架 | `py -3.12 -m bpreflight check --input examples/spec-ean13.json` → 首屏三段 + `VERDICT: fail`（骨架期诚实） |
| 测试 | `py -3.12 -m pytest -q` → **72 passed**；`py -3.8 -m pytest -q` → **72 passed** |
| 阈值三态 | `tests/test_package_data.py` + `tests/test_pipeline_skeleton.py` 断言 `source/status/verified_at/basis` 齐 |

**M0 的 DoD 在 `plan/05` §三（全部打勾）**。

## 二、当前事实·状态不变量（下一棒动手前必须知道）

1. **`implementation_pending` 必须与 M1 落地同提交退役**。
   它现在在 `src/bpreflight/pipeline.py` 的 `_pending_finding()` 里，是 `error` 级。
   `tests/test_pipeline_skeleton.py::test_skeleton_never_reports_pass` 与
   `test_pending_finding_is_an_error_with_actionable_fix` 依赖它——**退役时两条测试要一起改**，
   改成"该 id 不再出现 + 有真实判定时 verdict 才可能 pass"。
2. **校验位只准有一个实现**：`src/bpreflight/gs1/checksum.py::gs1_check_digit`。
   `plan/00` 台账与 `plan/01` §M1 都写死了"`grep -rc` == 1"。**M2 不许复制第二份**，
   只能 import。加这个文件时顺手把这条 grep 判据写进 `tests/test_checksum.py`（扫 `src/`）。
3. **阈值只能从 `bpreflight.json` 装载器读**：`src/bpreflight/thresholds.py` 是唯一读
   `data/vectors/*.json` 的地方。判定模块**接收装载好的对象**，不自己 `open()`。
   `tools/check_thresholds.py` 会拦 `src/` 里的裸数值常量——写 `0.330` 进去立刻红。
   允许集在 `tools/check_thresholds.py:ALLOWED_NUMBERS`（结构性常量，如 `0/1/2/16`）；
   确实需要例外就往 `REGISTERED` 里逐条登记并写理由。
4. **`finding` 构造即校验**：`report/model.py` 的 `Finding.__init__` 会拒绝
   warn/error 无 `fix`、`evidence.kind` 非法、`threshold_status` 非法。
   **不要绕过它去拼 dict**——那会让契约在渲染期才崩。
5. **状态副本是 3 处**：`plan/00` 里程碑表、`plan/05` 状态表、`README.md` 状态表。
   翻 M1 ✅ 时**三处同提交改**，否则布局门 `LAYOUT.STATUS` 红。
6. **`src/bpreflight/data/` 是运行期数据目录**（决策 D15）；仓库根 `data/` 只放人读台账。
   新增数据文件必须同步改 `pyproject.toml` 的 `[tool.setuptools.package-data]`（glob **不递归**）。
7. **本轮没跑过 CI**。任何"绿"都只能写**本地等价校验**，并注明"未接远端，CI 待首推验证"。
   `plan/05` 与 `README` 已经这么写，别改成"CI 绿"。

## 三、下一棒待办（M1）

按顺序做，每步都有可跑红的判据：

1. **取官方字典并入库**：`gs1/gs1-syntax-dictionary`（Apache-2.0）→
   `src/bpreflight/data/gs1-syntax-dictionary/`，同时落 `NOTICE`（上游许可 + 来源 URL + 快照日期）。
   取不到就**停下来问**，不要手抄 AI 表（`plan/00` D1 写死）。
2. **落 `dict_manifest.json`**：`{path, sha256, dict_version, fetched_at}`。
3. **实现 `gs1/checksum.py`**：严格按 `data/README.md` §8.1（起始权重按**含校验位的全长**奇偶；
   自左交替；另一权重 = `4 - W`，不是 `6 - W`）。**先写向量，后写实现**。
4. **实现 `gs1/dictionary.py`**：把字典行解析成 `AIDef`，**不实现语义规则**。
   整表解析行数必须进测试结论（非空跑自证）。
5. **实现 `gs1/validators.py` 的四个解释器**：`req`（OR/AND）、`ex`、`yymmd0`、`csum`。
   `yymmd0` 用 `calendar.monthrange`，DD=00 → 当月最后一天。
6. **落 `data/vectors/gs1_vectors.json`**：四官方向量 + `yymmd0` 两条 + `req` OR/AND + `ex`。
7. **接进 pipeline**：M1 findings 进报告；退役 `implementation_pending`。
8. **回写状态**：`plan/00` 台账 + 里程碑表、`plan/05` 状态表、`README` 状态表（3 处同提交）。
9. **写 `plan/HANDOFF-M2.md`**（七节），然后 commit。

## 四、既定口径清单（K 编号 —— 动了会打挂测试）

| K | 约定 | 位置 |
| --- | --- | --- |
| K1 | 校验位算法唯一实现，`4 - W` 不是 `6 - W` | `data/README.md` §8.1；`gs1/checksum.py` |
| K2 | 四向量必须全 PASS，且向量只存"数据位 + 期望校验位"（期望由数据独立复算） | `data/vectors/gs1_vectors.json` |
| K3 | `verdict` 只有 `pass/warn/fail` 三值；"不可判"走 `threshold_status`/`skipped`/降级 | `data/README.md` §8.8；`severity.py` |
| K4 | `Finding.fingerprint = sha256(id \\x1f module \\x1f target)[:16]`，**不含 severity** | `report/model.py` |
| K5 | `findings` 排序键 = `(module, ai_position, id)`，不是严重级别 | `report/model.py` |
| K6 | 退出码只在 `exitcodes.py` 定义；`3` 优先且不参与判定计数 | `data/README.md` §8.5 |
| K7 | 数值一律定点字符串（如 `"1.559"`），不从 JSON 读 float 再格式化 | `data/README.md` §8；`plan/03` §五 |
| K8 | `basis: engineering-heuristic` 项**没有** `status`，不参与未核降级 | `data/README.md` §8.2 末条 |
| K9 | 首屏三段字面固定（`VERDICT:` / `FINDINGS:` / `TOP FIX:`） | `report/render_md.py`；`tests/test_report_render.py` |
| K10 | 报告默认不读时钟；`--with-timestamp` 才标 `deterministic: false` | `pipeline.py` |
| K11 | 运行期零第三方依赖、零网络；`tests/test_no_network.py` AST 守 | `tests/test_no_network.py` |
| K12 | `requires-python >= 3.8`：3.10 的 `match`、3.9 的 `list[int]` 注解一律禁 | `tools/check_python_floor.py` |

## 五、本机环境坑（实测过的）

- **`python` / `python3` 是 Windows Store 占位符，执行即 exit 49**。一律 `py -3.12`
  （或 `py -3.8`）；输出中文加 `-X utf8`。
- `py -3.8` = 3.8.8，`py -3.12` = 3.12.10，两者都装了 pytest。
- Git Bash 下 heredoc 与 `cd` 复合命令容易被环境包装截断——**写临时脚本文件再执行**比
  `python - <<EOF` 稳。
- `pytest` 通过 `pyproject.toml` 的 `pythonpath = ["src"]` 直接跑源码树，**不需要先安装**；
  但"安装后仍能读到数据"这条另外由 `tests/test_package_data.py` + CI 的 pip install 覆盖。

## 六、DoD 逐项 checklist（M1 完成时须全部打勾）

- [ ] 四官方向量全 PASS（`02345673` / `416000336108` / `09501101530003` / `4006381333931`）
- [ ] `grep -rc "def gs1_check_digit" src/` == 1
- [ ] `(17)251200` → 不报 `invalid_date`，报 `dd00_last_day_of_month`（info），归一 `2025-12-31`
- [ ] `(17)251301` → `invalid_date`
- [ ] `req` OR：`(10)` 单独 → `missing_required_ai`；`(01)…(10)…` → 不报
- [ ] `req` AND：`(250)` 单独 → 报；`(01)(21)(250)` → 不报；`(01)(250)` → 报
- [ ] `ex`：`(01)`+`(255)` → `mutually_exclusive_ai`；`(01)` 单独 → 不报
- [ ] 字典整表可解析，解析行数进测试结论
- [ ] `dict_version` / `dict_sha256` 进报告头且可独立复算
- [ ] `implementation_pending` 已退役（测试同步改）
- [ ] 三处状态副本同提交翻 ✅
- [ ] `plan/HANDOFF-M2.md` 七节齐
- [ ] 四道门 + `verify_gates.py` 仍全绿；`pytest` 3.8 / 3.12 双绿

## 七、关键命令速查

```bash
py -3.12 tools/check_sprint_layout.py     # 布局门（第一件事）
py -3.12 tools/check_desensitized.py      # 脱敏门
py -3.12 tools/check_thresholds.py        # 阈值零硬编码门
py -3.12 tools/check_python_floor.py      # Python 下限门
py -3.12 tools/verify_gates.py            # 门自检（23 组变异）
py -3.12 -m pytest -q                     # 全量测试
py -3.8  -m pytest -q                     # 3.8 通道（语法回归）
py -3.12 -m bpreflight check --input examples/spec-ean13.json
grep -rc "def gs1_check_digit" src/       # 必须 == 1
```

> 官方单测向量与校验位手算留痕见 `data/README.md` §4.2。四类日期的 `yymmd0` 逐条适用性
> 仍标 ⚠️（`data/README.md` §9 第 5 项）—— M1 落地时以 linter 源码逐条核。
