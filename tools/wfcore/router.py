"""
router.py - Change routing engine for medpaper-pipeline.

Enforces the core pipeline discipline:
1. Classify modification requests into 6 canonical types.
2. Identify the earliest affected stage.
3. Prescribe the exact `wf loop` command.
4. Point to the single source of truth.
5. List required downstream dependencies to rebuild.
6. Strictly prohibit orphan edits to derived files (e.g. manuscript_assembled.md, bundle/*.docx).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class RouteDecision:
    change_type: str
    earliest_stage: str
    stage_title: str
    source_of_truth: str
    loop_command: Optional[str]
    downstream_rebuild: list[str]
    prohibited_actions: list[str]
    explanation: str


# Keyword patterns for rule-based matching (handling both English word boundaries and Chinese substrings)
PATTERNS = [
    # 1. Typography / Layout only (Exception - no loop needed)
    (
        "DOCX_TYPOGRAPHY_ONLY",
        r"(?i)(?:\b(?:font|font size|line space|line spacing|margin|margins|typography|csl|times new roman|double space|single space)\b|字号|行距|页边距|字体|排版样式)",
        RouteDecision(
            change_type="DOCX_TYPOGRAPHY_ONLY (纯排版样式修改 - 唯一例外)",
            earliest_stage="S20_package",
            stage_title="Assemble the submission bundle",
            source_of_truth="project/08_submission/guidelines_extract.md or docx compilation arguments",
            loop_command=None,
            downstream_rebuild=[
                "Re-run `uv run python tools/docx/render_package.py --project project` in S20",
                "Re-confirm with user, re-freeze, and re-audit",
            ],
            prohibited_actions=[
                "Do NOT edit prose text or scientific claims inside S20.",
                "Do NOT manually edit word/document.xml directly without code re-generation.",
            ],
            explanation="纯格式与排版参数微调可在 S20 内部闭环，通过重新渲染 docx 解决，无需回退工作流。",
        ),
    ),
    # 2. Design or Data / Statistics
    (
        "DESIGN_OR_DATA",
        r"(?i)(?:\b(?:data|sample size|subgroup|statistic|p-value|hazard ratio|odds ratio|cox|logistic|regression|baseline|primary outcome|cohort|results/\S+\.json)\b|数据|统计|样本量|亚组|风险比|[Pp]\s*值|效应量|重新分析|分析方法|纳入排除|变量)",
        RouteDecision(
            change_type="DESIGN_OR_DATA (设计、数据与统计分析改动)",
            earliest_stage="S05_analysis",
            stage_title="Analysis and results generation",
            source_of_truth="project/03_analysis/ scripts (Python/R) and raw data",
            loop_command='uv run python tools/wf.py loop --to S05_analysis --why "{why}"',
            downstream_rebuild=[
                "S05: Re-run analysis scripts to update project/03_analysis/results/*.json",
                "S06: Update SAP if methods altered",
                "S07: Update artifact specifications",
                "S08/S09: Update Methods and Results prose with provenance",
                "S10/S11: Re-render Tables and Figures with new data",
                "S17: Update Title Page / Abstract / Statements",
                "S20: Re-assemble and compile submission bundle",
            ],
            prohibited_actions=[
                "STRICTLY FORBIDDEN to directly modify numbers in markdown or DOCX prose without updated results/*.json.",
                "STRICTLY FORBIDDEN to fabricate or manually calculate statistics in text (violates no_orphan_numbers gate).",
            ],
            explanation="任何数据或统计结果的变动必须溯源自可执行代码。直接改文字会造成断链并触发 Red Gate 死锁。",
        ),
    ),
    # 3. Figures & Tables
    (
        "DISPLAY_ITEMS",
        r"(?i)(?:\b(?:figure|table|panel|legend|forest plot|kaplan-meier|heatmap|scatter|dpi|tiff|threeline)\b|图注|表格|插图|三线表|森林图|热图|散点图|配图|高清图)",
        RouteDecision(
            change_type="DISPLAY_ITEMS (图表与图注展示项修改)",
            earliest_stage="S10_tables",
            stage_title="Produce three-line tables & figures",
            source_of_truth="project/04_tables/ scripts, project/05_figures/ scripts & project/05_figures/legends.md",
            loop_command='uv run python tools/wf.py loop --to S10_tables --why "{why}"',
            downstream_rebuild=[
                "S10: Re-run table generation scripts (tools/tables/threeline.py)",
                "S11: Re-run figure plotting scripts (tools/figures/style.py) and deterministic QC (qc.py)",
                "Update project/05_figures/legends.md with 40-120 words concise visual guide",
                "S20: Re-run render_package.py to embed updated tables/figures into bundle",
            ],
            prohibited_actions=[
                "Do NOT manually paste modified images into bundle/ without source plotting script update.",
                "Do NOT put explanatory prose or results conclusions inside figure panels.",
            ],
            explanation="图表必须由确定性代码生成并经 QC 检验，图注必须在 05_figures/legends.md 统一维护。",
        ),
    ),
    # 4. References & Citations
    (
        "REFERENCES",
        r"(?i)(?:\b(?:reference|citation|cite|bib|pubmed|pmid|doi|unpaywall|crossref)\b|文献|引用|引文|参考文献|补引|漏引)",
        RouteDecision(
            change_type="REFERENCES (参考文献库与正文引文修改)",
            earliest_stage="S13_refs",
            stage_title="Verify and lock references",
            source_of_truth="project/06_refs/library.bib and verified.json via tools/pubmed/",
            loop_command='uv run python tools/wf.py loop --to S13_refs --why "{why}"',
            downstream_rebuild=[
                "S13: Retrieve real reference payload via tools/pubmed/client.py and verify via verify.py",
                "S14/S16: Update citation keys (@key) in relevant manuscript sections",
                "S20: Re-run render_package.py (auto-calibrates Title Page refcount and places refs before legends)",
            ],
            prohibited_actions=[
                "Do NOT write citations from memory or invent bib keys.",
                "Do NOT manually edit References section in docx without library.bib provenance.",
            ],
            explanation="文献必须来自真实的 PubMed API 检索和 verified.json 校验，杜绝虚假幻觉文献。",
        ),
    ),
    # 5. Section Prose & Narrative
    (
        "SECTION_PROSE",
        r"(?i)(?:\b(?:introduction|background|methods section|results section|discussion|limitation|mechanism|abstract|title page|statements|declarations)\b|引言|背景|方法部分|结果部分|讨论|局限性|机制|摘要|文题页|声明)",
        RouteDecision(
            change_type="SECTION_PROSE (分章节文本与学术论述修改)",
            earliest_stage="S14_intro",
            stage_title="Write specific manuscript section",
            source_of_truth="project/07_manuscript/<section>.md",
            loop_command='uv run python tools/wf.py loop --to {target_stage} --why "{why}"',
            downstream_rebuild=[
                "Update specific section source file (e.g. introduction.md, discussion.md, statements.md)",
                "Run `uv run python tools/wf.py check` to verify stage gates",
                "S19: Polish modified text if needed (preserving facts)",
                "S20: Re-run render_package.py to re-assemble unified manuscript",
            ],
            prohibited_actions=[
                "STRICTLY FORBIDDEN to edit manuscript_assembled.md directly (it will be overwritten on compile).",
                "STRICTLY FORBIDDEN to modify prose text inside manuscript.docx directly.",
            ],
            explanation="各章节源码独立存储在 07_manuscript/*.md。直接改汇编文件或 Word 属于孤立修改，会被瞬间覆盖。",
        ),
    ),
    # 6. Language Polish
    (
        "LANGUAGE_POLISH",
        r"(?i)(?:\b(?:polish|grammar|de-ai|academic tone|wording|flow)\b|润色|语法|去ai|学术化|措辞|行文流畅)",
        RouteDecision(
            change_type="LANGUAGE_POLISH (语言润色与去 AI 化)",
            earliest_stage="S19_polish",
            stage_title="Polish prose and verify facts intact",
            source_of_truth="project/07_manuscript/*.md via tools/text/polish.py",
            loop_command='uv run python tools/wf.py loop --to S19_polish --why "{why}"',
            downstream_rebuild=[
                "S19: Run `python tools/text/polish.py snapshot` -> edit wording -> verify with `wf check`",
                "S20: Re-run render_package.py",
            ],
            prohibited_actions=[
                "NEVER change a number, statistic, citation key, or figure/table reference during polish pass.",
            ],
            explanation="语言润色严格仅限文字润色，门禁会自动 diff 拦截任何改动数字或引用的破坏行为。",
        ),
    ),
]


def route_request(request_text: str, explicit_stage: Optional[str] = None) -> RouteDecision:
    """Analyze a modification request and determine the proper routing and earliest stage."""
    text = request_text.strip()
    
    # Check for specific section mentions first
    section_map = {
        r"(?i)(?:\b(?:intro|introduction)\b|背景|引言)": "S14_intro",
        r"(?i)(?:\b(?:methods|methodology)\b|方法)": "S08_methods",
        r"(?i)(?:\b(?:results|findings)\b|结果)": "S09_results",
        r"(?i)(?:\b(?:discussion|limitations)\b|讨论|局限性)": "S16_discussion",
        r"(?i)(?:\b(?:abstract|title|keywords|statements)\b|摘要|文题|关键词|声明)": "S17_frontmatter",
    }
    
    # Match patterns in order of precedence
    for ctype, pattern, decision in PATTERNS:
        if re.search(pattern, text):
            # Specialize SECTION_PROSE if specific section matched
            if ctype == "SECTION_PROSE":
                matched_stage = "S14_intro"
                for sec_pat, stg in section_map.items():
                    if re.search(sec_pat, text):
                        matched_stage = stg
                        break
                target_stage = explicit_stage or matched_stage
                cmd = decision.loop_command.format(target_stage=target_stage, why=text[:60])
                return RouteDecision(
                    change_type=decision.change_type,
                    earliest_stage=target_stage,
                    stage_title=f"Stage for {target_stage}",
                    source_of_truth=f"project/07_manuscript/ (specific section md file)",
                    loop_command=cmd,
                    downstream_rebuild=decision.downstream_rebuild,
                    prohibited_actions=decision.prohibited_actions,
                    explanation=decision.explanation,
                )
            
            cmd = decision.loop_command.format(why=text[:60]) if decision.loop_command else None
            return RouteDecision(
                change_type=decision.change_type,
                earliest_stage=decision.earliest_stage,
                stage_title=decision.stage_title,
                source_of_truth=decision.source_of_truth,
                loop_command=cmd,
                downstream_rebuild=decision.downstream_rebuild,
                prohibited_actions=decision.prohibited_actions,
                explanation=decision.explanation,
            )
            
    # Default fallback: Section Prose
    default_cmd = f'uv run python tools/wf.py loop --to S14_intro --why "{text[:60]}"'
    return RouteDecision(
        change_type="GENERAL_PROSE_REVISION (通用文本/学术修改)",
        earliest_stage="S14_intro",
        stage_title="Manuscript section editing",
        source_of_truth="project/07_manuscript/<section>.md",
        loop_command=default_cmd,
        downstream_rebuild=[
            "Identify the component section markdown file in project/07_manuscript/",
            "Edit the component section markdown file",
            "Pass stage gates with `uv run python tools/wf.py check`",
            "Re-run `tools/docx/render_package.py` to compile submission bundle",
        ],
        prohibited_actions=[
            "Do NOT edit manuscript_assembled.md directly.",
            "Do NOT edit manuscript.docx directly.",
        ],
        explanation="未匹配到特定数据或排版规则时，默认定位到正文源码分节。严禁孤立修改汇总或 Word 文件。",
    )


def format_route_report(decision: RouteDecision, request_text: str) -> str:
    """Format the routing decision as a clean, structured diagnostic report."""
    lines = [
        "=" * 70,
        " MEDPAPER-PIPELINE CHANGE ROUTER (修改路由诊断报告)",
        "=" * 70,
        f" 用户修改需求: {request_text}",
        f" 变更判定分类: {decision.change_type}",
        f" 最早受影响阶段: {decision.earliest_stage} ({decision.stage_title})",
        f" 唯一事实来源: {decision.source_of_truth}",
        "-" * 70,
    ]
    if decision.loop_command:
        lines.append(f" [推荐执行指令]:\n   {decision.loop_command}")
    else:
        lines.append(" [推荐执行指令]:\n   无需执行 wf loop (在当前 S20 内部直接重新渲染即可)")
        
    lines.append("\n [下游必须重建的依赖项]:")
    for d in decision.downstream_rebuild:
        lines.append(f"   * {d}")
        
    lines.append("\n [严禁事项 (Prohibited Actions)]:")
    for p in decision.prohibited_actions:
        lines.append(f"   ! {p}")
        
    lines.append(f"\n [底层逻辑解析]: {decision.explanation}")
    lines.append("=" * 70)
    return "\n".join(lines)
