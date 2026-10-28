# RELEASE-M6 · 发布留档（`bpreflight` v0.1.0）

> **两栏纪律**（`references/release.md`「tag 树内的留档」）：本文件随 tag 进发布树。
> **§一 只写"已发生的历史"与"复验方法"**；**§二 只写"对 tag 树本身的派生量"**——
> tag 对象 OID、tag 指向的 commit、产物 `sha256`、CI run id 都会因"再写一次"而失效，
> 因此**字面值一律不进 tag 树**，只在 tag 之后的追加提交里落。
> 本文件在 tag 树内的 §二 是**占位骨架**（列名 + 取证命令），不是漏填。
>
> 口径：凡本节说"本地等价校验"，指的是**本机真跑**；凡说"待首推"，指的是**只有远端能证**。

## 一、tag 前事实

### 1.1 发布身份与 D13 重名核对

| 项 | 值 |
| --- | --- |
| 仓库 | `yuluo554/10-27-barcodepreflight`（GitHub **公开**仓库） |
| 分发包名 | `bpreflight`（`pyproject.toml` `[project] name`） |
| CLI 入口 | `bpreflight`（`[project.scripts]`） |
| 版本 | `0.1.0`，**单一来源** `src/bpreflight/__init__.py:__version__`（`dynamic = ["version"]`） |
| 许可 | Apache-2.0（`LICENSE`；内嵌字典随附上游 `LICENSE` + `NOTICE`） |
| 提交身份 | 作者与提交者统一 `282769740+yuluo554@users.noreply.github.com`；tagger 同 |

**D13 重名核对（2026-10-28，本机真连，非限流）**：

| 名字 | PyPI | GitHub 仓库检索 | 结论 |
| --- | --- | --- | --- |
| `bpreflight` | `GET https://pypi.org/pypi/bpreflight/json` → **HTTP 404**（未占用） | `search/repositories q='bpreflight in:name'` → `total_count = 0` | **保留** |
| `10-27-barcodepreflight` | `GET https://pypi.org/pypi/10-27-barcodepreflight/json` → **HTTP 404**（未占用） | `q='10-27-barcodepreflight'` → `total_count = 0` | **保留**（仓库名） |

> 与 D5 的分工：**404 是"未找到"的正面答复**（请求成功）；`total_count = 0` 也来自成功响应。
> 本轮没有触发 403 二级限流，因此这两个 0 不是"限流假 0"。不需要改名，也没有 old→new 映射。

### 1.2 干净环境验证（发布物本体）

**两条独立通道，都在仓库外的新 venv 里跑**（中立目录用 `<临时目录>` 占位；报告产物生成在那里，用完即弃）：

| 通道 | 做法 | 结果 |
| --- | --- | --- |
| A · 源码树 | 新 venv（Python 3.12.10）→ `pip install <repo>`（build 依赖**真下载**，HTTP 200） | `bpreflight` 0.1.0 可执行 |
| B · 发布物本体 | 另一只新 venv → `pip install <repo>/dist/bpreflight-0.1.0.tar.gz` | `bpreflight --version` → `bpreflight 0.1.0` |

**README 逐条真敲**（在通道 A 的中立目录，`examples/` 只复制示例输入）：

| README 命令 | 实测 | 退出码 |
| --- | --- | --- |
| `bpreflight --help` | 打出三段子命令（`check` / `report` / `oracle`） | 0 |
| `bpreflight check --input examples/spec-ean13.json` | `VERDICT: warn`，`FINDINGS: ok=0 info=0 warn=2 error=0`（两条 `quiet_zone_marginal`，`unverified` 降级）；首屏 `THRESHOLDS:` / `SKIPPED:` 各一行 | 0 |
| `mkdir -p out && … --json --md` | `out/` 只多 `report.json` + `report.md` 两个文件 | 0 |
| `bpreflight report --input … --format json` | 合法 JSON，`deterministic: true` | 0 |
| `bpreflight check --input … --fail-on=error` | 干净 spec 不跨门槛 | 0 |
| `… --fail-on=error` 配 `spec-zero-quiet-zone.json` | 零静区恒 `error` → 跨门槛 | **2** |
| `… --fail-on=error` 配 `spec-red-ink-red-light.json` | 波长塌陷 → 跨门槛 | **2** |
| `mkdir -p out && bpreflight oracle --input …` | `ORACLE: skipped` / `SKIPPED: oracle_absent` / `ORACLE RESULT: n/a (this layer did not run)` | 0 |
| `… --with-timestamp` | 报告头 `deterministic: false` + `timestamp: 2026-10-28T02:12:06Z`（UTC，句尾 `Z`，无时区名/主机名） | 0 |
| `--json` 但 `out/` 不存在 | exit 3 且**零副作用**（不静默建目录） | **3** |

**通道 B（发布物本体）复跑同三条输入**：`check` → 0；零静区 → 2；`oracle` → 0（`oracle_absent`）。与通道 A 一致。

> **本轮的实质发现**（不是"跑一遍确认没问题"）：解包 sdist 实测发现**三处缺件**——
> `examples/*.json`、`fixtures/manifest.json`、`.github/workflows/*.yml` 都不在包里，
> 于是解包树里 README 的"用法"一节首条命令、`gen_fixtures.py --check`、
> `check_ci_workflow.py` 三条全红，`pytest` 也 **12 failed**。
> 处置 = `MANIFEST.in` 补三条白名单（见 §1.4），**不是**在文档里加"先怎么怎么样"的免责句。
>
> **第二处（更贵，发布阻塞级）**：按纪律"在 `git archive` 导出的干净目录里构建"之后，
> 装出来的 wheel **跑不起来**——`dictionary.load()` 抛 `DictionaryError`：
> 清单 `1ea02f4e…`，文件 `84359ef1…`；`thresholds.load_book()` 的 `vectors_sha256`
> 也从 `17ead62a…` 变成 `04d515df…`，`gen_fixtures --check` 与解包树 `pytest` 大面积红
> （72 failed / 48 errors）。根因：本机 `core.autocrlf=true`（Git for Windows 默认），
> **`git archive` 会按它把 blob 的 LF 转成 CRLF**（实测：blob 4983 字节 / 0 个 CRLF，
> 导出树 5103 字节 / 120 个 CRLF；字典正文同理 344 处）。而字典与阈值册的摘要算的是
> **原始字节** ⇒ 同一份数据两个摘要，运行期判据又是"不符即 exit 3"。
> 处置 = **摘要面改为"归一后字节"**（新增 `src/bpreflight/canonical.py`：
> `\r\n`→`\n` 后算 sha256；`data/README.md` §8.11 定义）+ **`.gitattributes` 钉
> `* text=auto eol=lf`**；三条单测钉住"CRLF 副本仍验得过""LF/CRLF 摘要相等""改内容摘要必须变"。
> 同一根因下，Windows 上 `git clone`（autocrlf=true ⇒ CRLF 检出）后直接跑会命中**同一条
> exit 3**——本轮实测的是 archive 那条链，clone 那条是同一条摘要链的必然结果。

### 1.3 脱敏四步 + 产物扫描

| 步 | 动作 | 实测 |
| --- | --- | --- |
| ① 改（元数据面） | `git log --format="%ae\|%ce" --all \| sort -u` | 12 个提交、**单一值** `282769740+yuluo554@users.noreply.github.com`（作者与提交者两字段都查）→ **无需 `filter-branch`** |
| ② 扫（文本面） | `py -3.12 tools/check_desensitized.py` | 扫描 **122 份**入库文本，豁免 2 份（门自身），**0 处命中**（盘符 / MSYS 用户路径 / 本机用户名 / 回环代理四规则） |
| ③ 复核（产物面） | `git ls-files \| grep -E '\.(png\|jpg\|bmp\|tif)$\|^(out\|dist\|build\|reports\|runs)/\|\.(whl\|tar\.gz)$\|^fixtures/[^/]+\.json$'` | **只命中 `fixtures/manifest.json`**（设计如此：清单入仓、产物不入仓）；`out/`、`dist/`、`*.png`、`*.tar.gz` **零入库** |
| ④ 重建历史 | `refs/original` 清理 / `gc --prune=now` | **不适用**：历史本来就只有一个 noreply 值，本轮没有改写动作，也就没有悬空对象要清 |

`.gitignore` 是"白名单之外的反向清单"：`fixtures/*.json` 默认忽略、只放行清单；`*.png` 等一律忽略。

### 1.4 交付面定稿 → 构建 → 装态验证（顺序是硬纪律）

实测顺序（每一步的产物都会进包，所以构建必须排在所有文档/清单改动**之后**）：

1. 交付面定稿：`README.md`（状态行 + 附件名）、`plan/*`（状态副本翻 ✅ + 本文件）、
   `MANIFEST.in`（**本轮唯一的功能性修正**：补 `examples/*.json` / `fixtures/manifest.json` /
   `.github/*.yml`）、`.github/workflows/ci.yml`（tests job 加 job 级 `PYTHONUTF8` / `PYTHONIOENCODING`）
2. 六道门 + `gen_fixtures.py --check` + `verify_gates.py` + `pytest` 双通道（见 §1.6）
3. `rm -rf dist build src/*.egg-info` → 在 **`git archive HEAD` 导出的干净目录**里 `python -m build`
   （不在工作目录 build：`MANIFEST.in` 的 glob 会把未入库的临时文件打进包）。
   **导出前必须确认导出树里的字节与 blob 一致**：`.gitattributes` 的 `* text=auto eol=lf`
   就是为此而加（`core.autocrlf=true` 时 `git archive` 默认会把 LF 转 CRLF，见 §1.2 第二处）
4. `twine check` 两件 → 双装态验证（源码树装 / sdist 装）
5. `SHA256SUMS`（两件产物各一行）→ commit → tag → Release

> 解包树回归（**解包即用**）：`tar xzf` 后在新目录里跑六道门 + `gen_fixtures.py --check` + `pytest`
> 必须全绿。补 `MANIFEST.in` 之前这里 **2 门红 + 12 failed**；补之后见 §1.6 的数字
> （`pytest` 为 302 passed + 1 skipped：那条 `skip` 是"解包树没有 `.gitignore`"的显式两态判定）。

### 1.5 构建产物

| 产物 | 说明 |
| --- | --- |
| `bpreflight-0.1.0-py3-none-any.whl` | 52 个成员；`bpreflight/data/` 下字典（正文 + `LICENSE` + `NOTICE`）、六个向量文件、`sampler_patterns.json` 全在 |
| `bpreflight-0.1.0.tar.gz` | 含 `LICENSE` / `README.md` / `AGENTS.md` / `pyproject.toml` / `MANIFEST.in` / `plan/`（14 份）/ `data/README.md` / `examples/` / `fixtures/manifest.json` / `.github/` / `src/` / `tests/` / `tools/`（8 份） |
| `SHA256SUMS` | 形态 `<hex>  <name>`（两空格；`sha256sum -c` 认的两种合法形态之一），随附件同批上传 |

`twine check` **两件均 PASSED**。

> **产物 `sha256` 只写在 §二 与 Release 正文，不写进本文件的 §一**：本文件在 tag 树里，
> 写死的摘要会因"写它这个动作"立刻失效（`references/release.md`「附件 sha256 的两个不动点」）。

### 1.6 门与测试（tag 前那棵树）

| 检查 | 结果 |
| --- | --- |
| `tools/check_sprint_layout.py` | 全绿；9 条判据全 PASS（含 `LAYOUT.RELEASE` 的两栏 + 覆盖对账 + 三态行 ≥3） |
| `tools/check_desensitized.py` | 122 份 / 0 命中 |
| `tools/check_thresholds.py` | 37 份 `.py` / 192 个数值常量 / 0 处未登记字面量 |
| `tools/check_python_floor.py` | 52 份 `.py` / 0 处越过 3.8 的语法 |
| `tools/check_ci_workflow.py` | 1 份工作流 / 98 行 / 20 个 step；7 个门各自独立 step；矩阵含 3.8 + 3.12 |
| `tools/gen_fixtures.py --check` | 31 件 fixture 位级一致，期望无漂移 |
| `tools/verify_gates.py` | **32 组变异：符合预期 32 / 不符合 0**（阴性对照 7 组） |
| `py -3.12 -m pytest -q` | **303 passed**（仓库树） |
| `py -3.8 -m pytest -q` | **303 passed**（仓库树，与 3.12 同数） |
| 解包树（无 `.git`）`pytest` | **302 passed + 1 skipped**——skip 的是 `test_manifest_is_committed_and_fixtures_are_not`（解包树没有 `.gitignore`，忽略规则在树里不成立；**显式 SKIP，不冒充 PASS**） |

> 这些数字是 **tag 前那棵树**上的实测；tag 之后再跑会因"追加提交只动文档/清单"而不变。
>
> **本轮的四处实修**（顺序即发现顺序）：
> ① **`MANIFEST.in` 补三条白名单**——解包树缺 `examples/` / `fixtures/manifest.json` /
> `.github/`，README 的"用法"首条命令与两道门在解包树里红；
> ② **摘要面行尾归一**（`src/bpreflight/canonical.py` + `.gitattributes`）——见 §1.2 第二处，
> 发布阻塞级：从 `git archive` 树构建的 wheel 装好后 `dictionary.load()` 直接失败；
> ③ **`verify_gates.py` 的靶子算法**——M6 翻 ✅ 之后 L4 / L9 两组变异静默变绿，根因是靶子把
> `plan/05` §四"已知未验证项"里**表尾引用 `M6` + 状态格 `⬜`** 误当成状态行（"行里含 M6"）——
> 改成**首格必须是 `M<k>`**（与布局门 `STATUS_LINE` 同口径），并给 L4 / L5 / L9 补
> "全部 ✅ 之后"的第二态（把已 ✅ 的里程碑只在单副本退回 ⬜ / 删掉已收尾里程碑的交接单 /
> 删掉发布留档）。**没有删测试、没有放宽断言**；
> ④ **一条判据改两态**——`test_manifest_is_committed_and_fixtures_are_not` 读 `.gitignore`
> 才能断言"产物不入仓"，而 sdist 不带 `.gitignore`。解包树里**显式 SKIP 并写明理由**，
> 不删测试、不写成 PASS（`references/release.md`「无 `.git` 是发布包的常态」）。

### 1.7 覆盖对账（阶段 7 出口门逐条）

三态口径：**实现** = 有门/有实测，贴证据 · **不适用** = 写具体理由（本项目形态为什么不涉及）·
**待首推** = 只有远端能证，首推后回填 §二。**不留空**。

#### A · 干净环境与本体复核

| 出口门 | 状态 | 证据 / 不适用理由 |
| --- | --- | --- |
| 发布物本体已验（真下载 + 中立目录） | 实现 | §1.2 两通道：源码树装（build 依赖真下载）+ sdist/wheel 装；README 逐条真敲，退出码 0/0/0/0/0/2/2/0/0/3。**装态冒烟抓到过一次"装不起来"**（CRLF 摘要 → `DictionaryError`），修完复验 |
| 发布物能证伪里程碑自述 | 实现 | 解包树 + 装态冒烟**证伪了三处自述**：① examples / fixtures 清单 / CI 工作流缺件；② 摘要面随检出形态漂移（archive 导出 CRLF → 装好即 exit 3）；③ 两组门变异在 M6 翻 ✅ 后静默变绿。三处都已修并复验 |
| 随包数据的摘要与检出/打包形态无关（`data/README.md` §8.11） | 实现 | 摘要面 = `\r\n`→`\n` 后的字节（`canonical.py`）；三条单测（LF/CRLF 摘要相等 + CRLF 字典副本仍验得过 + 改内容摘要必变）；`.gitattributes` 钉 `* text=auto eol=lf` |
| 入仓工具在无 `.git` 树里也要能跑 | 实现 | 解包树（无 `.git`）跑六道门 + `gen_fixtures.py --check` + `pytest` 全绿；`tools/` 无一读 git 元数据（布局门注释即声明） |
| 发布包实测 = README 每条命令在解包树里真敲（含前置条件） | 实现 | §1.2 + §1.4；"前置条件"= `out/` 必须已存在（缺则 exit 3 且零副作用），README 已写明 |
| 干净环境要连"真实输入"一起验 | 实现 | 三条真实 spec：干净样本（warn）、零静区（error→2）、红条+红光（error→2）。**不是**只喂"测试夹具" |
| "干净环境"的第一分支 = 无本地数据缓存 | 不适用 | 运行期数据（字典 + 向量 + 图案表）全部随包安装，仓库里没有"下载件缓存"这类分叉；干净 venv 本身就是无缓存态 |
| tag 树内留档与 tag 自身事实是自指关系 | 实现 | §一 只写方法与历史；OID / commit / run id / `sha256` 全在 §二 骨架里，tag 后回填 |
| 附件与 tag 树逐字节同源 | 实现 | 构建在 `git archive HEAD` 导出树里做；复核 = 归一化后共有文件逐个 `sha256` 相等 + 两侧独有集合逐项点名（`PKG-INFO`/`setup.cfg` 属 sdist 构建元数据；`.gitignore` 属不入包文件） |
| 源码包要自足（`MANIFEST.in` 白名单） | 实现 | 解包 → 装 → **从解包目录之外**跑 CLI（通道 B）；解包树内六门 + pytest 全绿 |
| 构建必须排在交付面定稿之后 | 实现 | §1.4 的五步顺序；`README.md` 在包内，先定稿后构建 |
| README 提到的附件名必须真在 Release 里 | 实现 | README「下载即用」写的是 `bpreflight-0.1.0-py3-none-any.whl` / `.tar.gz` / `SHA256SUMS`，与 `dist/` 实名逐字一致（`pyproject` 名 + 版本无下划线规范化问题） |
| 对外样例产物在中立示意目录生成 | 实现 | `out/report.*` 在**仓库外**的中立目录生成，用完即弃；仓库内 `out/` 不入库 |
| CI 无网络 job 的容器模型 | 不适用 | 本工作流不用 `container:`，也没有"无网络 job"；零网络由 `tests/test_no_network.py`（AST）+ 运行时零第三方依赖证明 |
| 首推第四色：配置面（`src` 布局 / 控制台编码 / 零依赖断言 / 离线镜像） | 实现 | `src` 布局 → CI 用 `pip install -e .`（不靠 `PYTHONPATH`）；**控制台编码**本轮补 tests job 级 `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8`；零依赖 = AST 门而非"查几个包名"；无离线镜像 → 该项不涉及 |

#### B · 附件与校验和

| 出口门 | 状态 | 证据 / 不适用理由 |
| --- | --- | --- |
| 附件口径四选一且留档写明 | 实现 | 选 **sdist + wheel**（构建产物本身）；不用 GitHub 自动生成的 Source code 包（其 `sha256` 本地复算不出来） |
| `diff -r` 零差异是错形态 | 实现 | 判据写成"共有文件非空自证 + 共有文件逐个相等 + 两侧独有集合逐项点名" |
| 附件 `sha256` 的两个不动点 | 实现 | 只写 Release 正文与 §二；**不写进包内文档** |
| 判据扫描面限定到 tag 树那一半 | 实现 | §一 **零** `sha256` 字面值（本节即证据）；§二 允许登记 |
| `SHA256SUMS` 的三形态 | 实现 | 本清单用 `<hex>  <name>`；`sha256sum -c` 复验两件均 OK（`*` 前缀形态同样合法，本项目未采用） |
| 真下载复核（`sha256sum -c` + `cmp`） | 待首推 | 需要 Release 已上传；首推后按 §2.3 逐条回填 |

#### C · tag 与留档时序

| 出口门 | 状态 | 证据 / 不适用理由 |
| --- | --- | --- |
| 版本号"单一来源 + 机器断言" | 实现 | `__init__.__version__` 唯一真源；`pyproject` `dynamic` 读它；`bpreflight --version` 输出 `bpreflight 0.1.0`；`tests/test_cli_contract.py` 断言该属性存在 |
| DoD 打勾只能在事实落地后 | 实现 | tag 树里 §二 是空骨架；M6 的"首推后回填 run id"在 `plan/05` §四 如实写"待首推" |
| 随包 README 的状态行不承载"发布到哪一步" | 实现 | README 状态行只写**版本 + 能力**（v0.1.0 / 五层），"已发布 / CI 绿"交给 Release 页与本文件 |
| `POST_TAG` 处置 = 声明 + 可核对 | 实现 | §2.4 写明"tag 之后只有追加类提交" + 一条可逐条核对的命令；不重打 tag |
| annotated tag 两端一致（对象哈希） | 实现 | 本机建 annotated tag；tagger 与作者一致为 noreply；对象 OID 记在 §二（不写进 tag 树） |
| tag 之后只许非交付面提交（`POST_TAG_SCOPE` / `DELIVERABLE_UNCHANGED`） | 实现 | 判据拆两条：改动集合 ⊆ `plan/` `README.md` `AGENTS.md`；交付面前缀（`src/` `MANIFEST.in` `pyproject.toml` `.github/`）**零差异**。核对命令见 §2.4 |
| 定版改变"参与摘要的指纹字段"→ 样例同轮重生成 | 实现 | 版本号本轮不变（`0.1.0` 自 M0 起固定）；`fixtures/manifest.json` 与阈值册身份一致（`gen_fixtures.py --check` 31 件位级一致）。报告里的 `version` 字段不参与任何入仓摘要 |
| 发布门报红先看它读的是 tag 树还是工作树 | 实现 | 本项目的门只读工作树文件（不读 git 元数据）；§二 的核对命令显式区分 `git rev-parse` / `git show <tag>:…` |

#### D · CI 与对账

| 出口门 | 状态 | 证据 / 不适用理由 |
| --- | --- | --- |
| 推送前本地解析 workflow 并断言 job/step 数 | 实现 | `check_ci_workflow.py`：1 份 / 98 行 / **20 个 step**；门自带的 fail-closed 子集判据抓得住"未加引号的 `: `"这类会让 `jobs=0` 的形状 |
| 每条已交付命令都有一条离线 CI 冒烟 | 实现 | CI 的 `Smoke (installed CLI: help + example run)` step 跑 `--help` 与 `check`；README 的其余命令在 §1.2 的净环境里逐条真敲（CI 不重复跑全部，差集如实登记在此） |
| "能力缺失"的降级冒烟不许用 PATH 隔离伪造缺失 | 实现 | `oracle` 缺引擎走 `skipped: oracle_absent`（`probe` 用 `shutil.which`，测试断言"检测不到即跳过"）；三样本的"解出"用**可注入替身**，不靠清空 PATH |
| push 数 = run 数对账（sha 台账，不写会自追的总数） | 待首推 | 首推后按 §2.2 逐行登记 `<sha> event=<…> conclusion=<…>`，并写"此后文档提交恒 1 push = 1 run"的规则 |
| 四矩阵同点全红 = 接线缺陷非平台差异 | 待首推 | 判读规则先定死：**同一点全红 → 查接线（import 期 / 打印期 / 断言词表）；只红一格 → 查触发条件**。本地三条等价形态（3.12 / 3.8 / 无 `.git` 解包树）全绿 |
| tag push 与 branch push 各一条 run（同 sha 两条合法） | 待首推 | 首推后逐条配对，两条都必须绿 |
| CI 检出形态会让"标注 tag 对象"整类不存在 | 不适用 | 本项目的 CI 不校验 tag 对象（不读 `git tag` / tagger）；tagger 的 noreply 在**本地**验（§1.3 ①），如实标注"本地验的" |

#### E · 门自身的纪律

| 出口门 | 状态 | 证据 / 不适用理由 |
| --- | --- | --- |
| 门要自己数"这轮扫到了几个" | 实现 | 每道门都打印扫描量：122 份文本 / 36 份 `.py` + 192 常量 / 51 份 `.py` / 1 份工作流 + 20 step / 31 件 fixture / 32 组变异。**0 命中即空跑**在 CI 工作流门里是 FAIL |
| 门对"被检查对象不存在"报 FAIL 不崩 | 实现 | 解包树里 `check_ci_workflow.py` 扫到 0 份工作流 → `FAIL 判据空跑`（不是静默 PASS）；`gen_fixtures --check` 缺清单 → FAIL |
| 发出去的那道门要能在它自己的 tag 树上跑通 | 实现 | 六道门随 sdist 发布（`tools/*.py` 入包），在解包树里全绿；本轮**先**在解包树发现门红、**再**修 `MANIFEST.in`、**最后**才构建 —— 缺陷没有落到已发布的包里 |
| 发布终态自检门可复跑（离线 / `--online` / `--pre-tag` 三模） | 不适用 | 本项目没有独立的发布终态门脚本：发布物 = `sdist` + `wheel`，其可核对性由 `twine check` + 装态冒烟 + 本文件的复验命令承担；再造一个"只在发布期有意义的门"会让它自己成为又一个"随包发布、必须在 tag 树上正确"的面 |
| 离线模式报 SKIP 不报 PASS | 不适用 | 没有离线模式开关（运行期本来就零网络，"离线"不是一种模式） |
| 发布门三处输入校验（tag 名 / 清单文件名 / 归档成员） | 不适用 | 没有独立发布门脚本，不读 tag 名、不解析 `SHA256SUMS` 文件名、不解包归档 |
| "发布未达成"与"环境缺失"两个退出码语义 | 不适用 | 同上（无独立发布门）。发布动作的失败面由 `gh` 自己的退出码 + §2 的逐条核对承担 |
| 门的结果会被"为满足它而写入的产物"改变 | 实现 | 本文件写完后**重跑一遍布局门**（`LAYOUT.RELEASE` 从"不适用"变"判两栏 + 覆盖对账"）；本文件登记的是**重跑之后**的形态，不写"写之前"的预期数字 |
| 门读"人写的文档"时，样例行会被当成真值 | 实现 | §一 不写任何可被正则当登记的 `<hex>  <name>` 行；摘要行只出现在 §二（tag 后），且 `SHA256SUMS` 是**独立文件**而非本文件的代码块 |
| 常驻测试要能"构造缺件态"（不测瞬态） | 实现 | `LAYOUT.RELEASE` 按"M6 是否 ✅"解锁两态；`verify_gates.py` 的 L5 变异正是"先删交接单再标 ✅"的两态探测（本轮**未删除**该探测） |
| 会话转回归：门缺件不崩 / 判据按面分层 / 常驻测试只测运行时形态 | 实现 | 布局门的 `guarded` 包装：任一判据抛异常报 FAIL 并继续；`verify_gates` 32 组含 7 组阴性对照 |

### 1.8 本文件的适用面（写给下一棒）

- 本文件**只**覆盖阶段 7 出口门。里程碑 DoD 在 `plan/05` §三，风险在 `plan/06` §二。
- **不要**为了"让 §二 看起来完整"而把 OID / `sha256` / run id 抄回 §一：那会让它们立刻失效。
- §二 的字面值只允许在 **tag 之后**的追加提交里改；追加提交只碰非交付面。

---

## 二、tag 后追加事实

> **本节在 tag 树里是占位骨架**（列名 + 取证命令在位，值写"见 tag 后追加提交"）。
> 下面的字面值都在 **tag 之后**的追加提交里落：tag 树不变 → 附件字节不变 → 值不会失效。
> 本文件在 tag 树内的版本仍保留本节标题与空表结构（布局门要读它）。

### 2.1 tag 与提交

| 项 | 值 | 取证命令 |
| --- | --- | --- |
| tag 名 | `v0.1.0` | `git tag -l` |
| tag 类型 | annotated | `git cat-file -t v0.1.0` |
| tag 对象 OID | `0d603db3f034bef843dcc4c3fdbec1994ff7daa8` | `git rev-parse v0.1.0` |
| tag 指向的 commit | `7deb5aa358b8025a48bb29c7ba3ccb5c3e07eb2a` | `git rev-parse v0.1.0^{commit}` |
| tagger | `yuluo554 <282769740+yuluo554@users.noreply.github.com>` | `git for-each-ref --format='%(taggername) %(taggeremail)' refs/tags/v0.1.0` |
| 本文件在 tag 树里 | 在（`git cat-file -e` 通过） | `git cat-file -e v0.1.0:plan/RELEASE-M6.md` |

### 2.2 CI 首跑与 push 台账

| 事实 | 值 |
| --- | --- |
| 首推形态 | **private 建仓 → 推 `main` + `v0.1.0` → CI 双绿 → 切 public → 建 Release**（没有公开过红的 run） |
| `push main`（`7deb5aa`） | run `40622681587`，结论 **success**；4 个 job 全绿：`gates`、`tests (py3.8 ubuntu)`、`tests (py3.12 ubuntu)`、`tests (py3.12 windows)` |
| `push tag v0.1.0`（同 `7deb5aa`） | run `40622697610`，结论 **success**；同样 4 个 job 全绿 |
| 对账规则 | **每个 push 事件对应一条 run**；同 sha 的 branch run 与 tag run 是**合法两条**，两条都要绿。此后 `plan/` 文档追加提交各产生一条 run，均绿；**本表不写"共 N 轮"**（会随每次回填自己变） |
| 传输通道 | `git` over HTTPS 到 `github.com:443` 本机**不可达**（`Connection was reset` / 20s 超时，`curl` 返回 000）；`api.github.com` 与 `gh` 正常、SSH（`git@github.com`）认证成功 ⇒ **remote 改用 SSH**。这条只影响推送通道，不影响上面的 run 事实 |

### 2.3 产物 `sha256` 与真下载复核

| 产物 | `sha256` | 复核 |
| --- | --- | --- |
| `bpreflight-0.1.0-py3-none-any.whl` | `b284e717bb79f2d43d40cf0e3fc0661e5fb281f5bb2cb047e86cd5c65772fd6a` | 真下载 → `sha256sum -c SHA256SUMS` **OK** → 与本机构建件 `cmp` **逐字节一致** |
| `bpreflight-0.1.0.tar.gz` | `2199200b721da33d85c59f549cbc8a99b207621d524c85600b0f0f16a6824ba4` | 同上 |
| `SHA256SUMS` | （清单本身不入校验清单） | 真下载后与 Release 正文的 digest 行逐条比 |

Release：`https://github.com/yuluo554/10-27-barcodepreflight/releases/tag/v0.1.0`，
`isDraft: false`、`isPrerelease: false`，三件附件齐（`SHA256SUMS` 190 B / wheel 134528 B / sdist 326552 B）。

**附件与 tag 树逐字节同源**（归一化后比对，`references/release.md`「共有文件」条）：
sdist vs `git archive v0.1.0` 解包树 **共有 100 个文件、0 处字节不一致**（sdist 独有 `PKG-INFO` /
`setup.cfg`；树独有 `.gitattributes` / `.gitignore`）；wheel 补 `src/` 前缀后**共有 47 个、0 处不一致**，
wheel 无"树里没有"的文件。

### 2.4 tag 之后的改动面

| 项 | 值 / 命令 |
| --- | --- |
| 声明 | tag 之后只有**追加类**提交，且都在 `plan/`（留档回填 / 状态对账 / 复核记录）；**无功能代码、无 `README.md`、无 `src/`** 改动 |
| 核对 | `git -c core.quotepath=false diff --name-only v0.1.0..HEAD` → 只应出现 `plan/*` |
| 交付面零差异 | `git -c core.quotepath=false diff --name-only v0.1.0..HEAD -- src/ MANIFEST.in pyproject.toml .github/ README.md` **必须为空** |
| 附件字节不变 | 三件附件在 tag 时点已定稿；`plan/` 的这次回填**不进**已发布的 `sdist`/`wheel`（包内 `plan/` 是 tag 树快照）——§二 的事实按设计只能活在仓库里 |
| 不重打 tag 的理由 | 首推即双绿、附件真下载复核通过、无缺陷落在已发布物上；此后只做 `plan/` 追加 —— 重打只会改变发布件身份，没有收益 |
