# RELEASE-M7 · 发布留档（`bpreflight` v0.1.1 / M6.1）

> **两栏纪律**（`references/release.md`「tag 树内的留档」）：本文件随 tag 进发布树。
> **§一 只写"tag 前事实"**（改前基线、改了什么、验收命令与输出）；**§二 只写"对 tag 树
> 本身的派生量"**——tag 对象 OID、tag 指向的 commit、产物 `sha256`、CI run id 都会因
> "再写一次"而失效，因此**字面值一律不进 tag 树**，只在 tag 之后的追加提交里落。
> 本文件在 tag 树内的 §二 是**占位骨架**（列名 + 取证命令），不是漏填。
>
> 口径：凡写"实测"= 本机真跑并贴了输出；"源码直读"= 读了文件但没跑；"推断"= 两者都不是。

## 一、tag 前事实

### 1.1 本版性质（为什么出这一版）

**v0.1.0 的发布物里带着 5 处错误的「299 passed」**（同包 `plan/RELEASE-M6.md` 写的是 303
⇒ 发布物内部自相矛盾），另有两道门的扫描面漏了 `tools/` 与 `update/`，以及元数据的
弃用倒计时（`license` TOML table 表 + License classifier，硬截止 2027-02-18）。

因此本版**只改文档数字 / 门扫描面 / 元数据**：**判定逻辑一行未改**。可核对的口径：

| 面 | 是否改动 | 核对命令 |
| --- | --- | --- |
| 判定层 `src/bpreflight/{print,symbols,gs1,oracle,report}/`、`pipeline.py`、`exitcodes.py`、`severity.py`、`input.py`、`paths.py`、`canonical.py`、`thresholds.py` | **未改** | `git diff --stat <v0.1.0>..<tag>` 里不应出现这些路径 |
| 阈值/向量数据 `src/bpreflight/data/vectors/*.json` 的 `status` / `verified_at` / `value` | **未改**（仍全部 `unverified`） | `git diff <v0.1.0>..<tag> -- src/bpreflight/data/` |
| 退出码矩阵（9 格 + 3 类 `3`） | **未改** | `py -3.12 -m pytest tests/test_exit_codes.py -q` |
| 报告落点契约（`out/report.json` / `out/report.md` / `out/oracle-report.*`） | **未改** | `py -3.12 -m pytest tests/test_cli_contract.py -q` |
| 唯一改动的产品面 | `src/bpreflight/__init__.py` 的 `__version__`（`0.1.0` → `0.1.1`，单源） | `grep -n __version__ src/bpreflight/__init__.py` |

### 1.2 改前基线（v0.1.0，实测）

| 项 | 值 |
| --- | --- |
| HEAD | `33cbdace6d23ac616c3e058013f807c28d7e070c`（`main`，与 `origin/main` 同 sha） |
| annotated tag `v0.1.0` | OID `0d603db3f034bef843dcc4c3fdbec1994ff7daa8` → commit `7deb5aa358b8025a48bb29c7ba3ccb5c3e07eb2a` |
| 测试 | `py -3.12 -m pytest -q` → **303 passed**；`py -3.8 -m pytest -q` → **303 passed** |
| 门 | 7 道全 exit 0；`verify_gates.py` **32 组变异 / 7 组阴性对照** |
| 文档自称 | `plan/05`（3 处）与 `plan/HANDOFF-M6`（5 处）写 **299 passed**；无任何门守着这个数字 |

### 1.3 本版做了什么（按批）

**B0 · 门扫描面收编**（无功能改动，后面所有门禁依赖它）

| 动作 | 内容 |
| --- | --- |
| B0-1 | `tools/check_python_floor.py`：`SCAN_ROOTS` 追加 `tools/`（52 → 59 份 `.py`）；并把 `MIN_VERSION` 从"只印在标题上的字"变成**判据本身**（`ast.parse(feature_version=(3, 12))`）。三类历史判据（`match` / 注解 `X \| Y` / 内建泛型注解）**保留**作为"比下限更严"的保守禁用清单——它们在 3.12 下合法，本代码库零使用，保留使 `verify_gates` 的 P1/P2 阳性变异仍咬得住东西 |
| B0-2 | `tools/check_desensitized.py`：`SKIP_DIRS` 加 `update` 与 `.scratch`（与 `.gitignore` 成对） |
| B0-3 | `.gitignore`：「临时工作目录」段加 `update/` 与 `.scratch/`，并写明"与 `SKIP_DIRS` 成对维护"的两条失效路径（只 ignore 不 SKIP → 做一次诊断就打红门；只 SKIP 不 ignore → 交接物被推上远端） |
| B0-4 | `tools/verify_gates.py`：新增 **3 组**变异 —— `P4`（`tools/` 里写内建泛型注解 → **期望红**，D2 的回归锁）、`P5`（`tools/` 里写普通合法代码 → 期望绿，防"新判定面过度报警"）、`D6`（`update/` 里写盘符路径 → **期望绿**，证明收编是定向的而非把判定面缩到零）。**32 → 35 组，阴性对照 7 → 9 组** |

> **与路线 B0-4 的偏差（如实登记）**：路线写"新增两组（P4 期望红 / D6 期望红）、32 → 34 组、
> 阴性对照 7 → 9 组"，这三个数**自相矛盾**——若两组都是阳性，阴性对照只能 7 组（7+0=7）；
> 若 34 组且 9 组阴性，则新增的两组必须都是阴性，那 `P4` 就不是"期望红"。
> 根因：`update/` 一旦进 `SKIP_DIRS`，往它里面写盘符路径**必然放行**，`D6` 只能是阴性对照。
> 故按语义落成 3 组（2 阴 + 1 阳），并在 `P4` 配了 `P5` 阴性对照 —— 否则"把所有 `tools/`
> 文件一律判红"也能通过该变异。**方向是加严**（变异组数与阴性对照数都上升）。

**B1 · 自述数字收口**

| 动作 | 内容 |
| --- | --- |
| B1-1 | `plan/05`：M5 状态行与 DoD 行改为 **306 passed**；M4 行的 269 保留原值并加「M4 时点；当前值见 §四 第 7 行」；§四 第 7 行由「Python 3.8 实跑」改写为「Python 下限实跑」（登记 3.8 EOL + 与 `setuptools>=77` 互斥 + 当前值）。`plan/HANDOFF-M6`：5 处 299 全改（第 6 棒的"当前事实"必须与此刻一致） |
| B1-2 | 新增 `tests/test_reported_counts.py`，**正好 3 条**：`test_documented_counts_match_collected`（`subprocess` 收集 → 断言 `plan/05` / `plan/HANDOFF-M6` / `README.md` 里每个「数字 + passed/tests」都等于真实条数）、`test_no_stale_299_string`（两个"当前事实"文档不得出现 `299 passed`）、`test_count_gate_finds_the_docs`（阴性对照：目标文档读不到时必须失败） |
| 历史值处理 | `plan/HANDOFF-M4`（253）/ `HANDOFF-M5`（269）/ `plan/06` R6（269）/ `data/README.md` §依据查证第 10 项 —— 这些都是**那一棒当时的真值**，改动等于篡改历史。统一改为「N 条」形态并注明时点，既不触发自指守门的「数字 + passed」判据，也不伪造当前值 |

**B2 · 元数据与生态**

| 动作 | 内容 |
| --- | --- |
| B2-1 | `requires-python = ">=3.12"`（原 `>=3.8`）；`build-system.requires = ["setuptools>=77"]`（原 `>=61`）；classifier 删 `3.8` |
| B2-2 | `license = "Apache-2.0"` + `license-files = ["LICENSE"]`（原 `license = { file = "LICENSE" }`）；删 `License :: OSI Approved :: Apache Software License` classifier。`LICENSE` 文件与 `MANIFEST.in` 的 `include LICENSE` **保留** |
| B2-3 | CI `actions/checkout@v4 → @v7`、`actions/setup-python@v5 → @v7` |
| B2-4 | CI 矩阵删 3.8 腿（剩 `ubuntu-3.12` + `windows-3.12`）。**连带三处判据同步**：`check_ci_workflow.py` 的 `REQUIRED_PYTHONS` 改为从 `pyproject.toml` 的 `requires-python` **算出下限**（不写死），`verify_gates` 的 `C4` 变异靶子改为"两条 3.12 腿全换掉"，`check_python_floor.MIN_VERSION = "3.12"` |
| B2-5 | GitHub topics 由空数组填 7 项：`barcode` / `cli` / `ean13` / `gs1` / `preflight` / `python` / `quality-assurance`（PUT 是替换语义，一次给全） |

**B3 · 文档面**（DEC6=丙：不动产品契约，只改 README）

| 动作 | 内容 |
| --- | --- |
| B3-1 | README「用法」加一段**不依赖仓库文件**的最小 spec：`{"schema":"bpreflight/spec/1","mode":"params","identifier":"4006381333931"}`；`--input examples/spec-ean13.json` 的示例保留但**移到"要印刷层判定"之下**，并注明照仓内该文件的字段写全 |
| B3-2 | README「不装也能跑」补 `PYTHONPATH=src` 前缀，并明说 `pythonpath = ["src"]` **只对 `pytest` 生效** |
| B3-3 | README 明说「`examples/` 随 **sdist**、不随 wheel」 |

**B4 · 发布**

| 动作 | 内容 |
| --- | --- |
| B4-1 | `src/bpreflight/__init__.py` `__version__` `0.1.0` → `0.1.1`（单源）；README 3 处 `bpreflight-0.1.0-*` 附件名同步为 `0.1.1` |
| B4-2 | `python -m build` 重出 `dist/`（clean venv，非开发环境）；`SHA256SUMS` 形态 `<hex>  <name>`（两空格、无 `*`，与 v0.1.0 同形态） |
| B4-4 | 本文件 |
| B4-5 | `plan/06` 的 **D16 已修订**（下限 3.8 → 3.12，含理由与判据同步）；**D14 已登记前提失效**——它的立论「`tomllib` 是 3.11+ 而本项目 `>=3.8`」在抬到 3.12 后不成立，但**本轮不改产品行为**（DEC6=丙 的口径），"是否收 TOML"留待下一轮重新决策 |

### 1.4 门与测试（tag 前那棵树，实测）

| 检查 | 结果 | 期望（路线） |
| --- | --- | --- |
| `tools/check_sprint_layout.py` | 全绿（`LAYOUT.RELEASE` 两栏 + 覆盖对账 + 三态行 53） | 全绿 |
| `tools/check_desensitized.py` | PASS **126 份**，0 处命中 | B1 之后 125 + 1 = 126 ✔ |
| `tools/check_thresholds.py` | PASS 37 份 `.py` / 192 个数值常量，0 处未登记 | 不变 ✔ |
| `tools/check_python_floor.py` | PASS **60 份** `.py`，0 处越过 3.12 | 59 + `test_reported_counts.py` = 60 ✔ |
| `tools/check_ci_workflow.py` | PASS 1 份 / 96 行 / 19 step / 7 门独立 step / 矩阵含 3.12（下限 3.12） | exit 0 ✔ |
| `tools/gen_fixtures.py --check` | PASS 31 件位级一致 | 不变 ✔ |
| `tools/verify_gates.py` | **35 组：符合预期 35 / 不符合 0（阴性对照 9 组）** | 见 §1.3 的偏差说明 |
| `py -3.12 -m pytest -q` | **306 passed** | 303 + 3 = 306 ✔ |
| `py -3.12 -m pytest --collect-only -q` | **306 tests collected** | 306 ✔ |

**B1 负控（真跑过一次）**：把 `plan/05` 的 `306 passed` 改成 `307 passed` →
`test_documented_counts_match_collected` 变红且精确指名
`plan/05-里程碑与发布.md: 写 '307 passed'，真实收集 306 条` → 还原后 3 passed。

**B2 专项**：clean venv 里 `python -m build --sdist --wheel` 的 stderr **`WARNING` 计数 = 0**
（改前每个产物各打两条：`project.license as a TOML table is deprecated` + `License classifiers are deprecated`）。

**B3 专项**（wheel-only + 中立目录，不复用开发环境）：新 venv 装 `bpreflight-0.1.1-py3-none-any.whl`
→ `printf` 最小 spec → `bpreflight check --input spec.json` → **`VERDICT: pass` / exit 0**；
`PYTHONPATH=src py -3.12 -m bpreflight --help` → exit 0，而**不带** `PYTHONPATH` 时 exit 1
（README 现在把这两态都写对了）。

### 1.5 遗留与不做

| 项 | 状态 |
| --- | --- |
| 真解码引擎路径 | **仍未验证**（本机 `zxing-cpp` / `ZXingReader` / `zbarimg` 全无，`oracle` 一律 `skipped: oracle_absent`）。本轮不装引擎 |
| 3.9–3.11 行为 | 本轮起**不在契约内**（下限 3.12）；未测 |
| 阈值真值 | 仍全部 `unverified`（未取到 GenSpec 原表）。**不许**为了"消灭降级"改成 `verified` |
| `plan/01-题目文档.md` 的 CRLF（D8） | **未动**（工作树 CRLF 435 个而 blob 是 LF、`git status` 干净、sdist 里是 LF；动它只增 diff） |
| sdist 带 `src/bpreflight.egg-info/`（D14 原登记） | **未修**，登记即可 |
| 首次 push 时的 CI 结果 | **待 push 后回填**（见 §二） |

## 二、tag 后追加事实

> **本节在 tag 树里是占位骨架**（列名 + 取证命令在位，值写"见 tag 后追加提交"）。
> 下面的字面值都在 **tag 之后**的追加提交里落：tag 树不变 → 附件字节不变 → 值不会失效。

### 2.1 tag 与提交

| 项 | 值 | 取证命令 |
| --- | --- | --- |
| tag 名 | `v0.1.1` | `git tag -l 'v0.1.1'` |
| tag 类型 | annotated | `git cat-file -t v0.1.1` |
| tag 对象 OID | `d070a5f503e6b3ca24147346dcdc60c58ee19582` | `git rev-parse v0.1.1` |
| tag 指向的 commit | `67204d0a2b960f602c2afe2e98cf8474e1057805` | `git rev-parse v0.1.1^{commit}` |
| tagger | 与 v0.1.0 同一身份（noreply 邮箱） | `git for-each-ref --format='%(taggername) %(taggeremail)' refs/tags/v0.1.1` |
| 本文件在 tag 树里 | 在（`git cat-file -e` 通过） | `git cat-file -e v0.1.1:plan/RELEASE-M7.md` |

### 2.2 CI run

| 事实 | 值 |
| --- | --- |
| `push main`（tag 前的提交） | RUN_MAIN `40687175968` — 3 个 job 全 `success`；注解 2 条（均为 `ubuntu-latest` 迁移平台公告，非弃用注解） |
| `push tag v0.1.1` | RUN_TAG `40687930173` — 3 个 job 全 `success`；注解 2 条（同上） |
| 对账规则 | 每个 push 事件对应一条 run；同 sha 的 branch run 与 tag run 是**合法两条**，两条都要绿。本表**不写"共 N 轮"**（会随每次回填自己变） |
| 期望形态 | 实测 3 个 job：`gates`、`tests (py3.12 ubuntu)`、`tests (py3.12 windows)`；`Node.js 20 is deprecated` 注解已清零（`checkout@v7` / `setup-python@v7`）。仍余 2 条 `notice` 级平台公告：`ubuntu-latest` 将于 2026-10-19 迁移 Ubuntu 26（runner-images#14748），与本次改动无关，改动 workflow 才能消除 |

### 2.3 产物 `sha256` 与真下载复核

| 产物 | `sha256` | 复核 |
| --- | --- | --- |
| `bpreflight-0.1.1-py3-none-any.whl` | `ca2a29739292b82ff4ce27bcdee57afbd4a2bbec7a78b8d4ecea1225485a0e77` | 真下载 → `sha256sum -c SHA256SUMS` → OK；与本地 `dist/` 件 `cmp` 逐字节一致（`WHEEL_IDENTICAL`） |
| `bpreflight-0.1.1.tar.gz` | `d9509ae5a6f6f2fee1ee42ab874a4e292066b11afa7e14af1f5118cb136cb6f3` | 同上（`SDIST_IDENTICAL`） |
| `SHA256SUMS` | （清单本身不入校验清单） | 真下载后与 Release 正文的 digest 行逐条比 |

### 2.4 tag 之后的改动面

| 项 | 值 / 命令 |
| --- | --- |
| 声明 | tag 之后只有**追加类**提交，且都在 `plan/` 与本文件（留档回填 / 状态对账 / 复核记录）；**无功能代码、无 `README.md`、无 `src/`** 改动 |
| 核对 | `git -c core.quotepath=false diff --name-only v0.1.1..HEAD` → 只应出现 `plan/*` |
| 交付面零差异 | `git -c core.quotepath=false diff --name-only v0.1.1..HEAD -- src/ MANIFEST.in pyproject.toml .github/ README.md` **必须为空** |
| 不重打 tag 的理由 | 若首推即绿且附件真下载复核通过，则无缺陷落在已发布物上，重打只改变发布件身份 |
