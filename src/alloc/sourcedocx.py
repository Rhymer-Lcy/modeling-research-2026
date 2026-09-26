"""Structure-preserving value verification against the canonical Q3 DOCX.

The problem statement expresses most Q3 constants in Office Math (OMML).  A
flattened text dump turns ``10^{24}`` into ``1024`` and ``2 x 10^{-4}`` into
``2x10-4``, so neither formula-name anchors nor flattened strings can attribute
an individual numeric value.  This module linearizes each math zone with its
superscript, subscript, fraction and delimiter structure intact, addresses every
body paragraph by a stable locator, and verifies each load-bearing value at the
exact paragraph and math zone where the organizer states it.

Locators are ``w:body/w:p[i]`` (1-based among the body's direct paragraph
children, empty paragraphs included) and, within a paragraph, ``m:oMath[j]``
(1-based in document order).  Table cells are
``w:body/w:tbl[t]/w:tr[r]/w:tc[c]/w:p[k]``.  In a paragraph's text, each math
zone appears in place as ``⟦linear form⟧`` so that wording checks also pin the
surrounding structure.  The quoted fragments below are the organizer's own
wording, kept verbatim so that a reviewer can compare them with the source.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from xml.etree import ElementTree as ET

from .receipts import (
    DOCX_PATH,
    reject_forbidden_q3_input,
    require_authorized_q3_input,
    sha256_authorized_q3_input,
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

#: Whole-file identity of the canonical DOCX, carried forward from the reviewed
#: T-010 checkpoint receipt and re-verified before any value is extracted.
ACCEPTED_DOCX_SHA256 = "89f1b27c497c03ebf03335f5c9a738fa8a7f3525409bceb1ff8676794cf3b6a7"


class SourceVerificationError(ValueError):
    """A load-bearing value could not be verified at its canonical source span."""


def _w(tag: str) -> str:
    return "{" + W_NS + "}" + tag


def _m(tag: str) -> str:
    return "{" + M_NS + "}" + tag


def _math_children(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(_math(child) for child in node if not child.tag.endswith("Pr"))


def _math(node: ET.Element) -> str:
    """Linearize one OMML element with its exponent/subscript structure kept."""
    tag = node.tag
    if tag == _m("r"):
        return "".join(text.text or "" for text in node.iter(_m("t")))
    if tag == _m("sSup"):
        return "{" + _math_children(node.find(_m("e"))) + "}^{" + _math_children(node.find(_m("sup"))) + "}"
    if tag == _m("sSub"):
        return "{" + _math_children(node.find(_m("e"))) + "}_{" + _math_children(node.find(_m("sub"))) + "}"
    if tag == _m("sSubSup"):
        return (
            "{" + _math_children(node.find(_m("e"))) + "}_{" + _math_children(node.find(_m("sub")))
            + "}^{" + _math_children(node.find(_m("sup"))) + "}"
        )
    if tag == _m("f"):
        return "\\frac{" + _math_children(node.find(_m("num"))) + "}{" + _math_children(node.find(_m("den"))) + "}"
    if tag == _m("d"):
        properties = node.find(_m("dPr"))
        begin, end = "(", ")"
        if properties is not None:
            begin_node = properties.find(_m("begChr"))
            end_node = properties.find(_m("endChr"))
            if begin_node is not None:
                begin = begin_node.get(_m("val"), "")
            if end_node is not None:
                end = end_node.get(_m("val"), "")
        return begin + ",".join(_math_children(item) for item in node.findall(_m("e"))) + end
    if tag == _m("func"):
        return _math_children(node.find(_m("fName"))) + "(" + _math_children(node.find(_m("e"))) + ")"
    if tag == _m("nary"):
        properties = node.find(_m("naryPr"))
        character = "∑"
        if properties is not None and properties.find(_m("chr")) is not None:
            character = properties.find(_m("chr")).get(_m("val"), character)
        return (
            character + "_{" + _math_children(node.find(_m("sub"))) + "}^{"
            + _math_children(node.find(_m("sup"))) + "}" + _math_children(node.find(_m("e")))
        )
    if tag == _m("rad"):
        return "sqrt[" + _math_children(node.find(_m("deg"))) + "]{" + _math_children(node.find(_m("e"))) + "}"
    return _math_children(node)


@dataclass(frozen=True)
class SourceBlock:
    """One addressed body paragraph or table-cell paragraph of the DOCX."""

    locator: str
    text: str
    math: tuple[str, ...]


def _paragraph(node: ET.Element, locator: str) -> SourceBlock:
    parts: list[str] = []
    zones: list[str] = []

    def walk(element: ET.Element) -> None:
        for child in element:
            if child.tag == _w("r"):
                for item in child:
                    if item.tag == _w("t"):
                        parts.append(item.text or "")
                    elif item.tag == _w("tab"):
                        parts.append("\t")
            elif child.tag == _m("oMath"):
                zone = _math_children(child)
                zones.append(zone)
                parts.append("⟦" + zone + "⟧")
            elif child.tag == _m("oMathPara"):
                for math in child.findall(_m("oMath")):
                    zone = _math_children(math)
                    zones.append(zone)
                    parts.append("⟦" + zone + "⟧")
            else:
                walk(child)

    walk(node)
    return SourceBlock(locator, "".join(parts), tuple(zones))


def read_docx_blocks(path: Path | None = None) -> Mapping[str, SourceBlock]:
    """Return every addressed paragraph of the DOCX, keyed by locator.

    Without ``path`` the allowlisted canonical DOCX is read; an explicit path is
    for mutation fixtures only.
    """
    source = require_authorized_q3_input(DOCX_PATH) if path is None else reject_forbidden_q3_input(path)
    with zipfile.ZipFile(source) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(_w("body"))
    if body is None:
        raise SourceVerificationError("DOCX has no document body")
    blocks: dict[str, SourceBlock] = {}
    paragraph_index = 0
    table_index = 0
    for child in body:
        if child.tag == _w("p"):
            paragraph_index += 1
            locator = "w:body/w:p[" + str(paragraph_index) + "]"
            blocks[locator] = _paragraph(child, locator)
        elif child.tag == _w("tbl"):
            table_index += 1
            for row_index, row in enumerate(child.findall(_w("tr")), 1):
                for cell_index, cell in enumerate(row.findall(_w("tc")), 1):
                    for inner_index, inner in enumerate(cell.findall(_w("p")), 1):
                        locator = (
                            "w:body/w:tbl[" + str(table_index) + "]/w:tr[" + str(row_index)
                            + "]/w:tc[" + str(cell_index) + "]/w:p[" + str(inner_index) + "]"
                        )
                        blocks[locator] = _paragraph(inner, locator)
    return blocks


_POWER_OF_TEN = re.compile(r"^(?:(?P<mantissa>\d+(?:\.\d+)?)×)?\{10\}\^\{(?P<exponent>[−-]?\d+)\}$")


def parse_power_of_ten(expression: str) -> float:
    """Parse a structured ``m×{10}^{e}`` or ``{10}^{e}`` value exactly."""
    match = _POWER_OF_TEN.match(expression)
    if match is None:
        raise SourceVerificationError("not a structured power-of-ten value: " + repr(expression))
    mantissa = match.group("mantissa") or "1"
    exponent = match.group("exponent").replace("−", "-")
    return float(mantissa + "e" + exponent)


def parse_decimal(expression: str) -> float:
    """Parse a plain decimal literal such as ``6.0``."""
    if re.fullmatch(r"\d+(?:\.\d+)?", expression) is None:
        raise SourceVerificationError("not a plain decimal value: " + repr(expression))
    return float(expression)


def _rhs(parser: Callable[[str], Any]) -> Callable[[str], Any]:
    def parse(zone: str) -> Any:
        return parser(zone.split("=", 1)[1])
    return parse


def _budget(zone: str) -> float:
    return parse_power_of_ten(zone[2:] if zone.startswith("C=") else zone)


def _training_coefficient(zone: str) -> int:
    match = re.fullmatch(r"\{C\}_\{train\}=(\d+)ND", zone)
    if match is None:
        raise SourceVerificationError("training compute is not of the form {C}_{train}=kND")
    return int(match.group(1))


def _interval(zone: str) -> dict[str, Any]:
    match = re.fullmatch(r"Q∈([(\[])(\d+(?:\.\d+)?),(\d+(?:\.\d+)?)([)\]])", zone)
    if match is None:
        raise SourceVerificationError("quality domain is not a structured interval")
    return {
        "lower": float(match.group(2)),
        "lower_inclusive": match.group(1) == "[",
        "upper": float(match.group(3)),
        "upper_inclusive": match.group(4) == "]",
    }


@dataclass(frozen=True)
class SourceCheck:
    """One load-bearing statement and the exact source span that must carry it."""

    key: str
    locator: str
    description: str
    fragments: tuple[str, ...] = ()
    math: str | None = None
    parse: Callable[[str], Any] | None = None
    expected: Any = None


#: The organizer's C_Q formula separates ``D`` and ``[`` with U+2009 THIN SPACE.
THIN_SPACE = "\u2009"

P = "w:body/w:p["
SOURCE_CHECKS: tuple[SourceCheck, ...] = (
    SourceCheck(
        "q3_title_structural_transfer", P + "27]",
        "Question 3 is joint multi-resource optimization under compute constraint and structural transfer",
        ("问题三：算力约束下的多维资源联合优化与结构性转移",),
    ),
    SourceCheck(
        "budget_inequality", P + "35]",
        "the allocation is solved with total cost not exceeding C, i.e. C_total <= C",
        ("在总成本不超过 ⟦C⟧ 的条件下求解资源配置",),
        expected="C_total <= C",
    ),
    SourceCheck(
        "total_budget_three_parts", P + "29]",
        "the total compute budget is C and consumption consists of three parts",
        ("设总算力预算为 ⟦C⟧", "算力消耗由以下三部分组成"),
    ),
    SourceCheck(
        "representative_budget_low", P + "29]",
        "suggested low representative budget in FLOPs",
        ("建议考察低、中、高三档典型预算",),
        "C={10}^{19}", _budget, 1e19,
    ),
    SourceCheck(
        "representative_budget_medium", P + "29]",
        "suggested medium representative budget in FLOPs",
        ("⟦{10}^{22}⟧",),
        "{10}^{22}", _budget, 1e22,
    ),
    SourceCheck(
        "representative_budget_high", P + "29]",
        "suggested high representative budget in FLOPs; other levels allowed, at least three magnitudes required",
        ("⟦{10}^{24}⟧ FLOPs", "可自行选取其他档位，但须至少考察三个不同量级的预算"),
        "{10}^{24}", _budget, 1e24,
    ),
    SourceCheck(
        "base_training_coefficient", P + "30]",
        "base training compute C_train = 6 N D (Chinchilla approximation), N parameter count, D training tokens",
        ("基础训练开销：", "（Chinchilla 近似）", "为参数个数", "为训练 Token 数"),
        "{C}_{train}=6ND", _training_coefficient, 6,
    ),
    SourceCheck(
        "flops_unit_definition", "w:body/w:tbl[1]/w:tr[6]/w:tc[2]/w:p[1]",
        "FLOPs are floating-point operation counts, commonly approximated by C = 6 N D",
        ("浮点运算次数，常用近似",),
        "C≈6ND",
    ),
    SourceCheck(
        "attention_compute_form", P + "34]",
        "long-context attention compute C_attn = eta N D L_ctx with exogenous L_ctx taken from C7",
        ("长文本注意力开销：", "（外生给定，取值依据 C7）"),
        "{C}_{attn}=ηND{L}_{ctx}",
    ),
    SourceCheck(
        "attention_eta", P + "34]",
        "attention coefficient eta = 2 x 10^-4",
        (),
        "η=2×{10}^{−4}", _rhs(parse_power_of_ten), 2e-4,
    ),
    SourceCheck(
        "quality_cost_optional_form", P + "31]",
        "the incremental quality cost is stated conditionally: if the incremental form is adopted",
        ("若采用增量成本形式，可按下式计算",),
    ),
    SourceCheck(
        "quality_cost_increment", P + "32]",
        "incremental quality cost C_Q = D [g(Q) - g(Q0)]_+ with a positive part",
        (),
        "{C}_{Q}=D" + THIN_SPACE + "[g(Q)−g({Q}_{0}){]}_{+},",
    ),
    SourceCheck(
        "q0_source_semantics", P + "31]",
        "Q0 is the baseline quality, given by Attachment A quality scores or by a reasonable assumption",
        ("设基线质量为 ⟦{Q}_{0}⟧（可由附件 A 的质量评分或合理假设给出）",),
        expected=["Attachment A quality scoring", "a reasonable declared assumption"],
    ),
    SourceCheck(
        "quality_domain", P + "31]",
        "quality is raised to Q in (0, 1]; the lower endpoint is excluded and the upper included",
        ("提升至 ⟦Q∈(0,1]⟧ 需要额外算力",),
        "Q∈(0,1]", _interval,
        {"lower": 0.0, "lower_inclusive": False, "upper": 1.0, "upper_inclusive": True},
    ),
    SourceCheck(
        "quality_family_choice", P + "33]",
        "g(Q) is chosen or improved from the exponential, power and logarithmic-asymptotic families of Appendix B",
        ("可从指数型、幂函数型、对数渐进型三类中选取或改进", "具体形式与参数见附录 B"),
    ),
    SourceCheck(
        "appendix_b_quality_cost", P + "48]",
        "Appendix B.1 restates C_Q = D [g(Q) - g(Q0)]_+ for Question 3",
        ("B.1数据质量成本函数（供问题三选取、比较或改进；",),
        "{C}_{Q}=D" + THIN_SPACE + "[g(Q)−g({Q}_{0}){]}_{+}",
    ),
    SourceCheck(
        "g_exponential_form", P + "49]", "exponential family g(Q) = gamma e^(lambda Q)",
        ("指数型：",), "g(Q)=γ{e}^{λQ}",
    ),
    SourceCheck(
        "g_exponential_gamma", P + "49]", "exponential gamma = 10^7 FLOPs per token",
        (), "γ={10}^{7}", _rhs(parse_power_of_ten), 1e7,
    ),
    SourceCheck(
        "g_exponential_lambda", P + "49]", "exponential lambda = 6.0",
        (), "λ=6.0", _rhs(parse_decimal), 6.0,
    ),
    SourceCheck(
        "g_power_form", P + "50]", "power family g(Q) = gamma Q^lambda",
        ("幂函数型：",), "g(Q)=γ{Q}^{λ}",
    ),
    SourceCheck(
        "g_power_gamma", P + "50]", "power gamma = 5 x 10^9 FLOPs per token",
        (), "γ=5×{10}^{9}", _rhs(parse_power_of_ten), 5e9,
    ),
    SourceCheck(
        "g_power_lambda", P + "50]", "power lambda = 4.0",
        (), "λ=4.0", _rhs(parse_decimal), 4.0,
    ),
    SourceCheck(
        "g_logarithmic_form", P + "51]", "logarithmic-asymptotic family g(Q) = gamma ln(1 + lambda Q)",
        ("对数渐进型：",), "g(Q)=γln(1+λQ)",
    ),
    SourceCheck(
        "g_logarithmic_gamma", P + "51]", "logarithmic gamma = 2 x 10^9 FLOPs per token",
        (), "γ=2×{10}^{9}", _rhs(parse_power_of_ten), 2e9,
    ),
    SourceCheck(
        "g_logarithmic_lambda", P + "51]", "logarithmic lambda = 10.0",
        (), "λ=10.0", _rhs(parse_decimal), 10.0,
    ),
    SourceCheck(
        "exogenous_context", P + "29]",
        "L_ctx is exogenous, its feasible values follow C7, and it is not an interior optimization variable",
        ("由模型架构与任务需求外生给定（其可行取值须依据 C7）", "而不将其作为内点寻优变量"),
    ),
    SourceCheck(
        "exogenous_context_appendix", P + "45]",
        "Appendix A: L_ctx exogenous (not optimized), feasible values from C7, with sensitivity analysis",
        ("外生给定（非寻优变量），其可行取值须依据 C7 并做敏感性分析",),
    ),
    SourceCheck(
        "structural_transition_requirement", P + "35]",
        "decide whether allocation shows a structural transfer (a qualitative change of the optimal "
        "strategy) as C spans magnitudes, and give an explicit mathematical definition and identification method",
        ("当预算 ⟦C⟧ 跨越上述不同量级时，资源分配是否出现结构性转移（即最优策略发生质的变化），"
         "并给出明确的数学定义与识别方法",),
    ),
    SourceCheck(
        "critical_context_identity", P + "35]",
        "derive analytically the critical context at which attention equals training cost, "
        "L_ctx^crit = 6/eta, and run sensitivity over the feasible C7 values",
        ("须解析给出使注意力开销与训练开销相当的临界值", "并在其可行取值上完成敏感性分析"),
        "{L}_{ctx}^{crit}=6/η",
    ),
    SourceCheck(
        "same_d_rule", P + "35]",
        "training, quality processing and attention use the same D by default",
        ("默认训练、质量处理与注意力计算使用同一 ⟦D⟧",),
    ),
)


def _record(check: SourceCheck, blocks: Mapping[str, SourceBlock]) -> dict[str, Any]:
    block = blocks.get(check.locator)
    if block is None:
        raise SourceVerificationError(check.key + ": locator " + check.locator + " is absent")
    for fragment in check.fragments:
        if fragment not in block.text:
            raise SourceVerificationError(
                check.key + ": expected organizer wording is absent at " + check.locator
            )
    record: dict[str, Any] = {
        "key": check.key,
        "locator": check.locator,
        "description": check.description,
        "verified_fragments": list(check.fragments),
    }
    if check.math is not None:
        matches = [index for index, zone in enumerate(block.math, 1) if zone == check.math]
        if len(matches) != 1:
            raise SourceVerificationError(
                check.key + ": structured math " + repr(check.math) + " occurs " + str(len(matches))
                + " times at " + check.locator + "; exactly one is required"
            )
        record["math_locator"] = check.locator + "/m:oMath[" + str(matches[0]) + "]"
        record["structured_math"] = check.math
    if check.parse is not None:
        extracted = check.parse(check.math)
        if extracted != check.expected:
            raise SourceVerificationError(
                check.key + ": extracted value " + repr(extracted)
                + " differs from the audit expectation " + repr(check.expected)
            )
        record["verified_value"] = extracted
        record["verification_mode"] = "value parsed from structured OMML at the math locator"
    elif check.expected is not None:
        record["verified_value"] = check.expected
        record["verification_mode"] = "semantics fixed by the verified organizer wording"
    else:
        record["verification_mode"] = "organizer wording and structured math present at the locator"
    record["status"] = "VERIFIED"
    return record


def verify_source_values(path: Path | None = None) -> dict[str, Any]:
    """Verify every load-bearing Q3 statement at its canonical DOCX span.

    Production (no ``path``) verifies the allowlisted canonical DOCX and first
    requires its accepted whole-file SHA-256.  An explicit ``path`` is only for
    mutation fixtures that prove a changed source value is detected.
    """
    digest: str | None = None
    if path is None:
        digest = sha256_authorized_q3_input(DOCX_PATH)
        if digest != ACCEPTED_DOCX_SHA256:
            raise SourceVerificationError("canonical DOCX SHA-256 differs from the accepted receipt: " + digest)
    blocks = read_docx_blocks(path)
    return {"docx_sha256": digest, "records": [_record(check, blocks) for check in SOURCE_CHECKS]}


def verified_values(verification: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return ``key -> verified value`` for every VERIFIED record that carries one."""
    return {
        record["key"]: record["verified_value"]
        for record in verification["records"]
        if "verified_value" in record and record.get("status") == "VERIFIED"
    }


__all__ = [
    "ACCEPTED_DOCX_SHA256",
    "SOURCE_CHECKS",
    "SourceBlock",
    "SourceCheck",
    "SourceVerificationError",
    "parse_decimal",
    "parse_power_of_ten",
    "read_docx_blocks",
    "verified_values",
    "verify_source_values",
]
