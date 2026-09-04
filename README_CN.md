# medpaper - 具备硬性门禁的医学科研论文全流程自动化流水线

[English Documentation](README.md) | [中文文档 (Chinese)](README_CN.md)

通过 20 个严密设防的科研阶段，将一个粗略的医学研究设想完整转化为达到顶级医学期刊（NEJM, Lancet, JAMA 等）发表标准的投稿包，原生支持在各大主流 Agentic IDE（Google Antigravity、Claude Code、OpenAI Codex、Kiro）中无缝运行，彻底解决长提示词在模型上下文压缩时遗忘和衰退的顽疾。

---

## 解决的核心痛点

传统基于长 Prompt 或自由发挥的 AI 论文写作存在两大根本性缺陷：
1. **上下文压缩遗忘**：随着对话轮数增加，模型不可避免地对全局指令产生遗忘和漂移，跳步或遗漏关键科研步骤；
2. **学术幻觉与造假**：Prompt 本身没有任何代码校验能力，无法阻止 AI 编造假 PMID、伪造 p 统计值或臆造效应量。

本项目的解决方案是**架构级治理（Code carries enforcement）**，而非口头提示：

| 致命缺陷 | 本管线的机械化硬约束机制 |
|---|---|
| **执行步骤跑偏 / 丢失进度** | 真实运行状态持久化于磁盘（`project/.wf/state.json`）。运行 `wf status` 随时精准还原当前阶段。 |
| **规则被上下文压缩遗忘** | 模型每次仅获取当前单个 Stage 卡片，按需调用，无需在上下文中硬背 20 阶段规则。 |
| **伪造参考文献（幻觉 PMID/DOI）** | 文献必须由内置工具从 PubMed/Crossref API 真实检索，原始 API Payload 强制缓存入库；未在 `verified.json` 中标记为 `verified: true` 的文献视为不存在。 |
| **伪造统计数据与数值** | 论文正文、表格和摘要中出现的任何统计数据，必须能在 `03_analysis/results/*.json` 中精确溯源，门禁解析数值 Token，未匹配直接拦截报错。 |
| **越级跳步 / 偷跑结果** | `no_future_artifacts` 与 `single_section_written` 严格限制阶段产物，严禁单轮对话同时生成多个章节（如方法+结果混写）。 |
| **虚假图表质检** | 独立于绘图代码的确定性机器视觉 QC + 必须记录的人工/模型视觉审阅决策（Rationale >= 40 字符），严防未看图即确认。 |
| **临时文件混乱泛滥** | 每个阶段有严格声明的产物白名单，`wf clean` 自动扫描未申报文件，推进前强制清理草稿。 |

---

## 快速安装与配置

本项目驱动器（`tools/wf.py`）采用 Python 标准库构建，零第三方依赖，即使外部环境损坏也不影响门禁状态检测。图表与统计分析依赖常用科研库。

### 1. 创建虚拟环境与安装依赖

推荐使用现代 Python 包管理器 `uv`（亦可使用原生 `venv` + `pip`）：

```powershell
# 创建虚拟环境
uv venv .venv

# 安装统计与绘图依赖
uv pip install --python .venv\Scripts\python.exe matplotlib numpy openpyxl pandas scipy statsmodels lifelines pillow
```

### 2. 配置 NCBI API 环境变量（推荐）

配置个人免费的 NCBI API 凭据，可将 PubMed 请求频次从 3 次/秒提升至 10 次/秒，并启用 Unpaywall 开放获取全文下载支持：

```powershell
# Windows PowerShell / pwsh (当前会话):
$env:NCBI_API_KEY  = "你的NCBI_API_KEY"
$env:NCBI_API_EMAIL = "你的邮箱@example.com"

# 或者在 Windows 中永久持久化（推荐）:
[Environment]::SetEnvironmentVariable("NCBI_API_KEY", "你的NCBI_API_KEY", "User")
[Environment]::SetEnvironmentVariable("NCBI_API_EMAIL", "你的邮箱@example.com", "User")

# Linux / macOS:
export NCBI_API_KEY="你的NCBI_API_KEY"
export NCBI_API_EMAIL="你的邮箱@example.com"
```

### 3. 环境与安装自检

```powershell
# 验证环境与门禁完整性
python tools/wf.py doctor

# 运行自动化回归测试 (26 项离线测试，--online 可追加 3 项真实 API 校验)
.venv\Scripts\python tools/selftest.py
```

---

## 多 IDE 无缝复用指南 (Multi-IDE Support)

本项目遵循 [Agent Skills 开放标准](https://agentskills.io/specification)，一份核心技能定义（`.agents/skills/medpaper-pipeline/SKILL.md`）即可通过 `tools/install_adapters.py` 自动映射适配各大 AI 编程工具：

| 工具 / 环境 | 技能路径 | 指针与规则配置 |
|---|---|---|
| **OpenAI Codex** | `.agents/skills/medpaper-pipeline` | `AGENTS.md` |
| **Claude Code** | `.claude/skills/medpaper-pipeline` | `CLAUDE.md` |
| **Google Antigravity** | `.agents/skills/medpaper-pipeline` | `.agent/rules/`, `.agent/workflows/` |
| **Kiro** | `.kiro/skills/medpaper-pipeline` | `.kiro/steering/`, `.kiro/hooks/` |

### 1. 在 Claude Code 中使用
```bash
# 生成 Claude 专属适配文件 (生成 CLAUDE.md 和 .claude/skills/)
python tools/install_adapters.py --only claude

# 启动 Claude Code
claude
```
在 Claude Code 聊天框中直接输入：
> `Run python tools/wf.py status and start the pipeline.`

### 2. 在 OpenAI Codex 中使用
```bash
# 生成 Codex 适配文件 (生成 AGENTS.md 和 .agents/skills/)
python tools/install_adapters.py --only codex
```
将项目目录在 Codex 中打开，Codex 会自动读取根目录下的 `AGENTS.md` 作为项目规则约束。在对话框中提示：
> `Run python tools/wf.py status and follow the stage card.`

### 3. 在 Google Antigravity IDE 中使用
项目已默认挂载 Antigravity 适配器。在 Antigravity 聊天框中：
- 直接输入斜杠命令：`/medpaper-resume`
- 或自然语言唤醒：`运行 uv run python tools/wf.py status 开始论文流水线。`

### 一键同步所有 IDE 适配器：
```bash
python tools/install_adapters.py --all
```

---

## 核心使用闭环 (The Only Loop)

在任何 IDE 中，执行本工作流只需记住唯一的 4 步循环：

```powershell
# 1. 初始化项目状态机 (首次使用时运行一次)
python tools/wf.py init

# 2. 核心推进循环
python tools/wf.py status                     # 查询：当前在哪个阶段、门禁阻断项、完整 Stage Card
#   ... 按照当前 Stage Card 要求在对应目录下完成工作 ...
python tools/wf.py check                      # 检验：运行当前阶段的硬性门禁检测
python tools/wf.py advance --note "交接纪要"   # 推进：门禁全绿后记录纪要并进入下一阶段
```

> **注意**：若当前阶段的门禁为红灯（未达标），`wf advance` 会强制拒绝推进。严禁滥用 `--force`。

---

## 常用 CLI 控制命令

| 命令 | 用途 |
|---|---|
| `python tools/wf.py status` | 调取当前阶段卡片、不变量规则与门禁状态 |
| `python tools/wf.py tree -v` | 打印 20 个阶段的全景概览与期望产物树 |
| `python tools/wf.py card S11` | 随时调阅指定阶段（如 S11 绘图）的操作细则 |
| `python tools/wf.py check S09` | 单独预检指定阶段的门禁而无需切换当前进度 |
| `python tools/wf.py decide <KEY> <VALUE> --why "..."` | 记录重大方法学或质检决策（理由须 >= 40 字符） |
| `python tools/wf.py loop --to S05_analysis --why "..."` | 因修改数据而回退到之前阶段，后续阶段自动重置 |
| `python tools/wf.py note "..."` | 向 handoff 日志中追加交接纪要 |
| `python tools/wf.py clean [--apply]` | 检查/清理未在当前阶段声明的临时冗余文件 |
| `python tools/wf.py doctor` | 运行环境、依赖、外部工具（R/Pandoc/Git）健康自检 |

---

## 20 个科研阶段全图谱 (The 20 Stages)

| 阶段编号 | 阶段名称 | 核心产物与硬性门禁要求 |
|---|---|---|
| **S01** | Intake: 课题接收与标准化 | 结构化课题 `idea.json`，初始化科研备忘 `notes.md` |
| **S02** | Feasibility: 可行性评估与 Go/No-Go #1 | >= 3 次真实检索缓存，>= 20 篇文献，记录决策与通过理由 |
| **S03** | Protocol v1: 研究方案设计与数据规划 | 预设分析方案、文献检索可重复流程、变量字典草案 |
| **S04** | Data Acquisition: 数据获取与清洗 | 原始数据放入 `02_data/raw/`（只读不可改），数据字典 `codebook.md`，数据源溯源文档 |
| **S05** | Exploratory Analysis: 统计分析与计算 | 执行清洗与分析代码，统计指标精确导出为 JSON，**严禁在此阶段画图** |
| **S06** | Final Protocol: 最终研究方案与 Go/No-Go #2 | 记录对比 v1 的修改原因，形成最终执行标准 |
| **S07** | Artifacts: 图表清单规划与图注精炼 | 对标顶刊规划图表；图注严格执行四要素规范（80-150字，严禁堆砌方法学信度与小论文） |
| **S08** | Methods: 方法学章节撰写 | 正文遵循通用四步骨架并强制以 Statistical Analysis 收尾；详尽敏感性分析与技术细节分流至可选的 supplementary_methods.md |
| **S09** | Results: 结果章节撰写 | 每一个统计数值均可在 JSON 中追溯来源，严格对应规划的图表 |
| **S10** | Tables: 三线表制作与生成 | 纯正标准三线表（.xlsx），单元格数值 100% 数据代码溯源 |
| **S11** | Figures: 顶级医学期刊图表生成与质检 | 确定性 QC 代码检测，人工/视觉审阅留痕，严禁图面文字堆砌（移入图注） |
| **S12** | Reconcile: 图表与正文交叉一致性校对 | 文中引用的图表编号必须存在，文中所提数值与表格单元格 100% 严密吻合 |
| **S13** | Reference Library: 核心文献库构建 | ~50 篇真实文献，完整 Abstract，100% 经过二次复核验证，Bib/RIS 双格式同步 |
| **S14** | Introduction: 引言撰写 | 字数与文献引用量达标，科学假说与背景引文严密闭环 |
| **S15** | Deep-read: 精读核心代表作 | 5 篇核心全文精读，记录详细精读笔记并论证选取依据 |
| **S16** | Discussion: 讨论章节撰写 | 深入讨论机制、优缺点与临床意义，深度呼应 S15 精读文献 |
| **S17** | Front Matter & Audit: 标题、摘要、全文拼装与独立SCIE预审 | 标题依据 PICO 自动精选；作者信息暂留占位；自动组装全文.md；交付独立子 Agent 进行 SCIE 接受率审核并闭环修正，发文概率极低则触发熔断 |
| **S18** | Journal Selection: 目标期刊选择与指南抓取 | 基于预审报告推荐，锁定高接受概率 SCIE 期刊（低分亦可）；真实抓取并快照作者投稿须知（Author Guidelines） |
| **S19** | Language Polish: 事实保护性语言润色 | 执行快照 Diff 比对，**严禁润色篡改任何数值、引文或图表编号**，去除 AI 味 |
| **S20** | Submission Package: 完整投稿包封装 | 收集真实作者与基金信息；依据期刊指南动态适配字号行距；全篇纯黑 Times New Roman；正文文末自动集成图注；投稿信与正文全套 Word 化交付 |

---

## 仓库工程结构

```
pipeline/pipeline.toml       # 流水线唯一事实来源（定义阶段、产物、门禁与策略）
pipeline/stages/S01..S20.md  # 每个阶段的独立操作卡片
tools/wf.py                  # CLI 驱动入口 (标准库实现)
tools/wfcore/                # 核心状态机引擎、36 项门禁检验器、轻量 Excel 工具
tools/pubmed/                # PubMed E-utilities、Crossref、Unpaywall 客户端与文献验证器
tools/tables/threeline.py    # 顶级期刊标准三线表生成器
tools/figures/style.py       # 顶刊期刊绘图风格与 rcParams
tools/figures/qc.py          # 确定性自动化图表质检脚本
tools/text/polish.py         # 去 AI 味学术润色与数值事实保护 Diff 检查器
tools/install_adapters.py    # 多 IDE（Antigravity, Claude, Codex, Kiro）适配器同步脚本
reference/                   # 顶刊图表标准规范库与外部技能仲裁策略
project/                     # 正在撰写的论文工作区 (包含数据、分析结果、文献与稿件)
project/.wf/state.json       # 当前论文进度与状态
```

---

## 开源协议

本项目采用 MIT 许可证。