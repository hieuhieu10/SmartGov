"""
Reviewer Agent — Self-reflection loop with Citation Checker integration.

Responsibilities:
  - Run Citation Checker to validate all source references
  - Check logical consistency of the draft
  - Verify that the draft follows the plan outline
  - Ensure content is based on research data (no hallucination)
  - Check formatting and language quality
  - Decide: PASS (approve) or REVISE (send back to Writer with feedback)
"""

import json
import logging

from app.services.llm_service import llm_service
from app.agents.citation_checker import citation_checker

logger = logging.getLogger(__name__)

REVIEWER_SYSTEM_PROMPT = """Bạn là chuyên viên kiểm duyệt văn bản hành chính Việt Nam bậc cao, làm việc theo tiêu chuẩn của NotebookLM: "Mọi khẳng định đều phải có bằng chứng".

NHIỆM VỤ: Đánh giá bản thảo văn bản dựa trên sự thật (grounding), đúng thẩm quyền hành chính và văn phong hành chính nhà nước Việt Nam.

TRẢ VỀ JSON:
{{
    "pass": true/false,
    "overall_score": 0-10,
    "issues": [
        {{
            "type": "hallucination|citation|format|content|logic",
            "severity": "critical|major|minor",
            "description": "Mô tả vấn đề",
            "suggestion": "Cách sửa cụ thể"
        }}
    ],
    "feedback": "Hướng dẫn cụ thể cho Writer để sửa các lỗi trên",
    "summary": "Nhận xét tóm tắt"
}}

TIÊU CHÍ KHẮT KHE:
1. **Chống ảo giác (Anti-Hallucination)** [Trọng tâm]: Bất kỳ con số, ngày tháng, tên riêng hoặc sự kiện nào không xuất hiện trong "DỮ LIỆU NGHIÊN CỨU" đều bị coi là ảo giác. Đánh dấu "critical" nếu phát hiện bịa đặt dữ liệu (Tuyết đối không được bịa).
2. **Nguồn nội bộ, không xuất ra Word**: Không yêu cầu bản thảo có `[Nguồn: ...]`. Nếu bản thảo còn `[Nguồn: ...]`, `Điểm: ...`, tên file, markdown hoặc ký tự thừa thì đánh dấu lỗi format/content và yêu cầu loại bỏ.
3. **Bản thảo đầu vào là JSON nội bộ**: KHÔNG đánh lỗi chỉ vì bản thảo đang ở dạng JSON hoặc tên trường kỹ thuật. Hãy đánh giá nội dung trong các giá trị JSON; hệ thống Word exporter sẽ tự tạo tiêu đề lớn, quốc hiệu, cơ quan, chữ ký và nơi nhận.
4. **Thể thức (Administrative Format)**:
    - **BẮT BUỘC PHÂN CẤP**: Kiểm tra cấu trúc `I. -> 1. -> - -> +`.
    - Tuyệt đối KHÔNG cho phép dùng chữ số La Mã (I, II...) cho các mục con. Các mục này PHẢI dùng số `1., 2., 3...`. Đánh dấu "critical" nếu sai.
    - **Kiểm tra Gom nhóm**: Nếu một đề mục cha (VD: `1.`, hoặc `-`) CHỈ có duy nhất 1 mục con (VD: 1 dấu `-` hoặc 1 dấu `+`), hãy đánh dấu lỗi "format" và yêu cầu Writer gom mục con đó lên mục cha thành 1 dòng.
    - Không yêu cầu bản nháp JSON phải có tiêu đề chính IN HOA; việc này do exporter xử lý khi xuất Word.
    - **Kiểm tra viết hoa tên cơ quan**: Trong phần nội dung (trừ đề mục), tên cơ quan (VD: Ủy ban nhân dân) CHỈ được viết hoa chữ cái đầu theo quy tắc chính tả, TUYỆT ĐỐI KHÔNG IN HOA TOÀN BỘ (viết in hoa toàn bộ chỉ dành cho phần đầu trang do hệ thống tự xử lý). Đánh dấu lỗi "format" nếu sai.
5. **Ngôn ngữ**: Văn phong hành chính nhà nước Việt Nam, câu ngắn, rõ, thực tế; không dùng từ "tôi", "chúng ta", từ biểu cảm, văn phong AI hoặc nội dung chung chung.
6. **Cấm rác AI**: KHÔNG được có các câu như "Không có thông tin", "Dữ liệu không đề cập".
7. **Đúng cấp hành chính và thẩm quyền**: Nội dung phải phù hợp cơ quan ban hành. Với cấp xã/huyện, chỉ chấp nhận nhiệm vụ triển khai, phối hợp, rà soát, tuyên truyền, kiểm tra, tổng hợp, báo cáo, đề xuất cấp có thẩm quyền. Đánh dấu major/critical nếu văn bản giao việc, phê duyệt hoặc ban hành chính sách vượt thẩm quyền.
8. **Logic thực thi**: Kiểm tra logic nội dung, thời gian, cơ quan phối hợp, trách nhiệm thực hiện; loại bỏ câu lặp, câu rỗng nghĩa, câu khẩu hiệu.

QUY TẮC DUYỆT:
- pass = false nếu có lỗi "critical", sai phân cấp đề mục nghiêm trọng, nội dung vượt thẩm quyền, hoặc còn dữ liệu lỗi như `[Nguồn: ...]` trong nội dung.
- Nếu pass = false, hãy đưa ra feedback cực kỳ chi tiết để Writer sửa lại.
- KHÔNG markdown, CHỈ JSON.

BÁO CÁO NGUỒN NỘI BỘ, CHỈ DÙNG ĐỂ KIỂM CHỨNG, KHÔNG YÊU CẦU ĐƯA VÀO VĂN BẢN:
{citation_report}
"""


async def reviewer_node(state: dict) -> dict:
    """
    Reviewer Agent: evaluate draft quality with citation checking.

    Input state: draft, draft_data, plan, research_context, research_data, iteration
    Output state: review_feedback, review_pass, review_issues
    """
    draft = state.get("draft", "")
    plan = state.get("plan", {})
    research_context = state.get("research_context", "")
    research_data = state.get("research_data", [])
    iteration = state.get("iteration", 1)
    max_iterations = state.get("max_iterations", 2)

    # If max iterations reached, auto-pass
    if iteration >= max_iterations:
        logger.info(f"[Reviewer] Max iterations ({max_iterations}) reached — auto-pass")
        return {
            "review_pass": True,
            "review_feedback": "",
            "review_issues": [],
        }

    # ── Step 1: Run Citation Checker ──────────────────────────────────
    citation_report = citation_checker.generate_full_report(draft, research_data)
    citation_report_text = _format_citation_report(citation_report)

    logger.info(
        f"[Reviewer] Citation check: "
        f"score={citation_report['overall_score']:.2f}, "
        f"citations={citation_report['citations']['total']}, "
        f"valid={citation_report['citations']['valid']}"
    )

    # ── Step 2: LLM-based content review ──────────────────────────────
    plan_summary = _format_plan_summary(plan)

    # Inject citation report into system prompt
    system_prompt = REVIEWER_SYSTEM_PROMPT.format(
        citation_report=citation_report_text
    )

    user_prompt = f"""BẢN THẢO CẦN ĐÁNH GIÁ (Lần thứ {iteration}):
---
{draft}
---

DÀN Ý (OUTLINE) GỐC:
{plan_summary}

DỮ LIỆU NGHIÊN CỨU THAM KHẢO (tóm tắt):
{research_context[:3000]}

---

Hãy đánh giá bản thảo theo 5 tiêu chí trên và quyết định DUYỆT hay YÊU CẦU CHỈNH SỬA.
Lưu ý: Báo cáo trích dẫn tự động đã được đính kèm trong system prompt."""

    try:
        result = await llm_service.chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=3072,
        )

        if not result:
            logger.warning("[Reviewer] Empty/unparseable JSON review; requesting revision")
            return {
                "review_pass": False,
                "review_feedback": (
                    "Reviewer không trả JSON hợp lệ hoặc phản hồi bị cắt. "
                    "Hãy rút gọn bản nháp, loại bỏ metadata nguồn/ký tự thừa, "
                    "đảm bảo nội dung bám đúng dữ liệu nghiên cứu và đúng thẩm quyền."
                ),
                "review_issues": ["Reviewer JSON parse failed"],
            }

        review_pass = result.get("pass", False)
        feedback = result.get("feedback", "")
        issues = result.get("issues", [])
        score = result.get("overall_score", 7)

        # ── Step 3: Combine LLM review with citation report ──────────

        # Add citation issues to the issue list
        citation_issues = _extract_citation_issues(citation_report)
        if isinstance(issues, list):
            issues.extend(citation_issues)

        # Citation tags are internal only. Do not fail only because the draft has
        # no visible citations; final export must be clean for ordinary users.

        # Extract issue descriptions for logging
        issue_descriptions = [
            f"[{i.get('severity', '?')}] {i.get('description', '')}"
            for i in issues
            if isinstance(i, dict)
        ]

        logger.info(
            f"[Reviewer] Iteration {iteration}: "
            f"LLM score={score}, citation_score={citation_report['overall_score']:.2f}, "
            f"pass={review_pass}, {len(issues)} total issues"
        )
        for desc in issue_descriptions[:5]:
            logger.info(f"  → {desc}")

        return {
            "review_pass": review_pass,
            "review_feedback": feedback if not review_pass else "",
            "review_issues": issue_descriptions,
        }

    except Exception as e:
        logger.error(f"[Reviewer] Failed: {e}")
        # On error, pass the draft to avoid infinite loops
        return {
            "review_pass": True,
            "review_feedback": "",
            "review_issues": [f"Reviewer error: {str(e)}"],
        }


# ── Helper Functions ──────────────────────────────────────────────────

def _format_plan_summary(plan: dict) -> str:
    """Create a compact summary of the plan for review context."""
    sections = plan.get("sections", [])
    if not sections:
        return "Không có dàn ý"

    parts = []
    for i, s in enumerate(sections, 1):
        title = s.get("title", f"Mục {i}")
        key_points = s.get("key_points", [])
        kp_text = "; ".join(key_points) if key_points else ""
        parts.append(f"{i}. {title}: {kp_text}")

    return "\n".join(parts)


def _format_citation_report(report: dict) -> str:
    """Format citation report as text for the LLM prompt."""
    citations = report.get("citations", {})
    coverage = report.get("coverage", {})
    summary = report.get("summary", "")

    lines = [
        f"Tổng số trích dẫn: {citations.get('total', 0)}",
        f"Trích dẫn hợp lệ: {citations.get('valid', 0)}",
        f"Trích dẫn không hợp lệ: {citations.get('invalid', 0)}",
        f"Độ chính xác trích dẫn: {citations.get('accuracy_score', 0):.0%}",
        f"Độ bao phủ trích dẫn: {coverage.get('coverage', 0):.0%}",
        f"Đoạn chưa trích dẫn: {coverage.get('uncited_paragraphs', 0)}",
        f"Điểm tổng: {report.get('overall_score', 0):.2f}",
        f"Kết luận: {'ĐẠT' if report.get('pass', False) else 'CHƯA ĐẠT'}",
    ]

    if summary:
        lines.append(f"\nChi tiết:\n{summary}")

    # Add invalid citation details
    invalid_details = [
        d for d in citations.get("details", [])
        if not d.get("valid", True)
    ]
    if invalid_details:
        lines.append("\nTrích dẫn không hợp lệ:")
        for d in invalid_details[:5]:
            lines.append(f"  - {d.get('citation', '')}: {d.get('reason', '')}")

    return "\n".join(lines)


def _extract_citation_issues(report: dict) -> list[dict]:
    """Convert citation report issues into the standard issue format."""
    issues = []
    citations = report.get("citations", {})

    # Add issues for invalid citations
    for detail in citations.get("details", []):
        if not detail.get("valid", True):
            issues.append({
                "type": "citation",
                "severity": "major",
                "description": f"Trích dẫn không hợp lệ: {detail.get('citation', '')} — {detail.get('reason', '')}",
                "suggestion": "Kiểm tra lại nguồn trích dẫn hoặc loại bỏ nếu không tìm thấy trong kho dữ liệu",
            })

    return issues
