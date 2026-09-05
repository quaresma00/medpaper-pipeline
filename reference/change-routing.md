# Change Routing & Single Source of Truth Specification
# 医学论文修改路由与唯一事实来源规范

## 1. 核心设计原则 (Core Principles)

在 `medpaper-pipeline` 科学研究管线中，学术论文是**代码、数据与分段源码的确定性派生产物**，而不是一个脱离上下文的独立文本文件。

> **铁律**：
> **“正文由数据派生，Word 由 Markdown 编译，所有状态由 `tools/wf.py` 追踪。”**
> 任何抛弃工作流、绕过门禁的“私自改文件”，均属于高危破坏行为，会导致事实断链、门禁爆红死锁及手改内容被重新编译覆盖清空。

---

## 2. 修改路由判定表 (Change Routing Decision Matrix)

当用户或审稿人在任何阶段提出修改需求时，必须先使用路由判定机制：
```bash
uv run python tools/wf.py route "<用户修改需求描述>"
```
根据返回的诊断报告，判定变更类型与最早受影响阶段：

| 修改类型 (Change Type) | 典型触发场景 | 最早受影响阶段 | 唯一事实来源 (Single Source of Truth) | 必须重建的下游依赖 (Downstream Rebuild) | 严禁事项 (Prohibited) |
|---|---|---|---|---|---|
| **1. 纯排版样式 (唯一例外)**<br>`DOCX_TYPOGRAPHY_ONLY` | 修改字号 (11pt/12pt)、行距 (Double/1.5)、页边距、标题字体颜色 | **S20_package**<br>(无需回退) | `08_submission/guidelines_extract.md` 与编译参数 | 重新运行 `tools/docx/render_package.py` 重新渲染 DOCX -> 重新人工确认与冻结 | 严禁在 S20 修改实质性正文文本；严禁手改 Word XML |
| **2. 研究设计/数据/统计**<br>`DESIGN_OR_DATA` | 调整纳入排除标准、重算样本量、增加亚组分析、调整 Cox/Logistic 模型、更新效应量与 P 值 | **S03_protocol** (改设计)<br>或 **S05_analysis** (改统计) | `03_analysis/` 下的 Python/R 脚本及原始数据 | S05 重跑更新 `results/*.json` -> S06/S07 规格 -> S08/S09 正文更新 -> S10/S11 表格与图片重建 -> S20 重新渲染 | **绝对严禁直接在 Markdown 或 Word 中手改数字**（`no_orphan_numbers` 门禁直接拦截阻断） |
| **3. 表格与插图展示项**<br>`DISPLAY_ITEMS` | 调整三线表列、重新绘制森林图/K-M图/热图、调整 DPI 或尺寸、修改图注说明 | **S10_tables** (表格)<br>或 **S11_figures** (插图) | `04_tables/`、`05_figures/` 源码脚本及 `05_figures/legends.md` | 重跑出图/制表脚本 -> 运行 `qc.py` 质检 -> 更新 `legends.md` 图注 -> S20 重新渲染 | 严禁直接拷贝未经验证的外来图片进 bundle；严禁在图内写大段解释文本 |
| **4. 参考文献与正文引文**<br>`REFERENCES` | 补引最新指南/重要试验、纠正引文错误、更新 DOI | **S13_refs** | `06_refs/cache/scan_manifest.json`、`verified.json` 及 `library.bib` | S13 经 PubMed API 真实检索 -> 更新 `library.bib` -> S14/S16 更新正文 `@key` -> S20 自动校准文献数与位置 | **严禁凭记忆手写 PMID/DOI**；严禁在 docx 文末手写参考文献条目 |
| **5. 分章节文本与学术论述**<br>`SECTION_PROSE` | 修改背景假说、深化讨论机制推测、补充局限性、精简摘要、更新文题页作者信息 | 对应分节阶段：<br>S08 (Methods)<br>S09 (Results)<br>S14 (Intro)<br>S16 (Discussion)<br>S17 (Frontmatter) | `project/07_manuscript/<section>.md` | 修改对应分节 md -> 运行 `uv run python tools/wf.py check` 通过门禁 -> S19 润色 -> S20 重新编译 | **绝对严禁直接修改 `manuscript_assembled.md` 或 `full_manuscript.md`**（属于汇编产物，会被覆盖）；严禁直接改 docx |
| **6. 语言学术润色**<br>`LANGUAGE_POLISH` | 去除 AI 口气、增强学术严谨度、改进长难句流畅度 | **S19_polish** | `07_manuscript/*.md` (由 `tools/text/polish.py` 监控) | 快照比对 -> 修改表述 -> 运行 `wf check` 校验（diff 确保零数字变动） -> S20 重新编译 | **严禁改动任何数字、统计量、引用键或图表序号**（违者门禁爆红） |

---

## 3. 为什么严禁“孤立修改（Orphan Edits）”？

### 3.1 严禁修改 `manuscript_assembled.md`（汇编产物）
- `07_manuscript/manuscript_assembled.md` 是由 `render_package.py` 在编译时自动从 `title_page.md`、`abstract.md`、`introduction.md`、`methods.md`、`results.md`、`discussion.md`、`statements.md`、`legends.md` 动态拼接而成的**临时汇编产物**。
- 如果直接在 `manuscript_assembled.md` 上修改，**当下一次执行 `render_package.py` 时，该文件会被重新拼接并瞬间覆盖，所有手动修改瞬间归零**！

### 3.2 严禁脱离工作流直接修改 `bundle/*.docx`（最终成品）
- `bundle/manuscript.docx` 是从 Markdown 源码经由 Pandoc 编译生成的**最终交付物**。
- 直接改动 DOCX 会导致：
  1. **源码与成品事实性脱节**：底层的 Markdown 还是旧的，版本不可追溯；
  2. **SHA-256 包哈希冻结报警**：S20 的 `tools/package_review.py verify` 会立即捕获未受控的改动并抛出篡改警告；
  3. **重新编译覆灭**：一旦后续重新打包，手改的 Word 将被完全覆盖。

---

## 4. 标准修改执行 SOP (Standard Operating Procedure)

1. **第 1 步：运行路由诊断**：
   ```bash
   uv run python tools/wf.py route "<用户的具体修改诉求>"
   ```
2. **第 2 步：执行阶段回退**（除纯排版样式外）：
   ```bash
   uv run python tools/wf.py loop --to <最早受影响阶段> --why "<修改原因>"
   ```
3. **第 3 步：定位唯一事实源修改**：
   - 数据/统计：修改 `03_analysis/` 脚本并重新运行生成 `results/*.json`；
   - 图表：修改 `04_tables/` 或 `05_figures/` 脚本重新出图；
   - 文献：通过 `tools/pubmed/` 重新检索并更新 `library.bib`；
   - 文本：修改 `07_manuscript/` 下的具体章节 `.md`。
4. **第 4 步：门禁校验与重新推进**：
   ```bash
   uv run python tools/wf.py check
   uv run python tools/wf.py advance --note "已完成针对 XX 的修改与重算"
   ```
5. **第 5 步：在 S20 重新生成投稿包并重新冻结终审**：
   ```bash
   uv run python tools/docx/render_package.py --project project
   # 交付用户人工复查 -> 用户确认 OK -> 重新冻结与三重终审
   ```
