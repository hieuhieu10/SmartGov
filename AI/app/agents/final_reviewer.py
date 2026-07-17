"""Final deterministic + LLM gate before exporting self-hosted drafts to Word."""

import json
import logging
import re
from typing import Any

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

DOC_CODE_PATTERN = r"\b\d{1,5}\s*(?:/|-)\s*[A-ZĐ-]+(?:\s*(?:[-–]|/)\s*[A-ZĐ-]+)*\b"


REQUIRED_CONTENT_FIELDS = {
    "cong_van": ["noi_dung"],
    "thong_bao": ["noi_dung"],
    "ke_hoach": ["phan_mo_dau", "muc_dich_yeu_cau", "noi_dung_thuc_hien", "kinh_phi", "to_chuc_thuc_hien"],
    "bao_cao": ["tinh_hinh_chung", "ket_qua", "han_che", "phuong_huong"],
    "to_trinh": ["su_can_thiet", "noi_dung_de_xuat", "kien_nghi"],
    "quyet_dinh": ["can_cu", "dieu_khoan"],
}

SCHEMA_DESCRIPTIONS = {
    "cong_van": "noi_dung, de_nghi",
    "thong_bao": "noi_dung",
    "ke_hoach": "custom_sections, phan_mo_dau, muc_dich_yeu_cau, noi_dung_thuc_hien, kinh_phi, to_chuc_thuc_hien, phu_luc_nhiem_vu",
    "bao_cao": "tinh_hinh_chung, ket_qua, han_che, phuong_huong",
    "to_trinh": "su_can_thiet, noi_dung_de_xuat, kien_nghi",
    "quyet_dinh": "can_cu, dieu_khoan",
}

MIN_FIELD_CHARS = {
    "noi_dung": 120,
    "muc_dich_yeu_cau": 80,
    "noi_dung_ke_hoach": 160,
    "phan_mo_dau": 120,
    "noi_dung_thuc_hien": 200,
    "kinh_phi": 40,
    "dinh_huong_chi_dao": 120,
    "nhiem_vu_trong_tam": 200,
    "to_chuc_thuc_hien": 80,
    "tinh_hinh_chung": 80,
    "ket_qua": 160,
    "han_che": 60,
    "phuong_huong": 80,
    "su_can_thiet": 100,
    "noi_dung_de_xuat": 120,
    "kien_nghi": 60,
}

BLOCKED_PHRASES = [
    "không có thông tin",
    "không tìm thấy dữ liệu",
    "dữ liệu không đề cập",
    "chưa rõ thông tin",
    "không đủ thông tin",
    "tôi không thể",
    "as an ai",
]


FINAL_REVIEWER_SYSTEM_PROMPT = """Bạn là kiểm duyệt viên cuối cùng trước khi xuất văn bản hành chính ra Word.

NHIỆM VỤ:
Đánh giá bản nháp đã merge JSON sau khi Writer viết từng mục. Kiểm tra toàn cục:
1. Văn bản có trả lời đúng yêu cầu/trích yếu không.
2. Các mục có liền mạch, không trùng lặp quá mức, không mâu thuẫn.
3. Không có dấu hiệu bịa dữ liệu ngoài context.
4. Không còn câu rác như "không có thông tin", "chưa rõ", "tôi không thể".
5. Nội dung phù hợp loại văn bản và văn phong hành chính nhà nước Việt Nam.
6. Đúng cấp hành chính, đúng thẩm quyền cơ quan ban hành; cấp xã/huyện không được viết như cơ quan cấp tỉnh/trung ương.
7. Không còn dữ liệu lỗi trong nội dung xuất Word: `[Nguồn: ...]`, `Điểm: ...`, tên file nguồn, markdown, ký tự thừa, đoạn lặp.

TIÊU CHÍ VĂN PHONG/THẨM QUYỀN:
- Câu ngắn gọn, rõ việc, thực tế; tránh văn phong AI, khẩu hiệu, câu chung chung.
- Với cơ quan cấp xã/huyện, chỉ dùng các hành động thuộc thẩm quyền như triển khai, phối hợp, rà soát, tuyên truyền, kiểm tra, tổng hợp, báo cáo, đề xuất cấp có thẩm quyền.
- Không cho phép nội dung vượt thẩm quyền như tự phê duyệt quy hoạch, phân bổ ngân sách vượt cấp, ban hành chính sách cấp tỉnh/trung ương, giao nhiệm vụ cho cơ quan không thuộc phạm vi phối hợp.
- Kiểm tra logic thời gian, trách nhiệm chủ trì/phối hợp và trình tự thực hiện.

LƯU Ý VỀ SCHEMA:
- Kiểm tra schema theo "SCHEMA HỢP LỆ" trong prompt người dùng.
- KHÔNG tự yêu cầu các trường generic như "summary" hoặc "sections" nếu schema hợp lệ không liệt kê các trường đó.
- Nếu kiểm tra deterministic đã pass, chỉ báo lỗi schema khi BẢN NHÁP thực sự thiếu trường trong SCHEMA HỢP LỆ.

LƯU Ý VỀ SỐ/KÝ HIỆU VĂN BẢN:
- Mẫu `số/ký-hiệu` như `123/KH-UBND`, `2023/KH-UBND`, `01-KH/BCĐ`, `45/QĐ-UBND` là SỐ/KÝ HIỆU văn bản.
- Phần số trong số/ký hiệu văn bản KHÔNG mặc nhiên là năm, kể cả khi có 4 chữ số.
- Chỉ coi có ràng buộc năm nếu người dùng ghi năm độc lập ngoài số/ký hiệu, ví dụ `năm ...`, `trong năm ...`, `giai đoạn ...`, hoặc ngày/tháng/năm cụ thể.
- Khi nhắc văn bản có số/ký hiệu, phải gọi đầy đủ là `Kế hoạch số ...`, `Quyết định số ...`; không rút gọn thành `kế hoạch <phần số>`.
- Nếu nguồn tham chiếu có năm khác nhưng đang dẫn căn cứ/triển khai cho một văn bản theo số/ký hiệu, không tự kết luận là bịa/mâu thuẫn chỉ vì năm khác. Chỉ báo lỗi khi có explicit_years độc lập và nội dung thật sự trái với explicit_years.
- Trích dẫn [Nguồn: ... | Điểm: ...] là metadata nội bộ. Nếu còn trong nội dung cuối thì phải yêu cầu loại bỏ hoặc làm sạch trước khi xuất Word.

TRẢ VỀ JSON DUY NHẤT:
{
  "pass": true,
  "score": 0-10,
  "issues": [
    {
      "type": "schema|content|grounding|style|logic",
      "severity": "critical|major|minor",
      "description": "...",
      "suggestion": "..."
    }
  ],
  "summary": "Nhận xét ngắn"
}

QUY TẮC DUYỆT:
- pass=false nếu có issue critical.
- pass=false nếu văn bản thiếu phần chính, trả lời lệch yêu cầu, vượt thẩm quyền, còn dữ liệu lỗi `[Nguồn: ...]`, hoặc có dấu hiệu bịa số liệu/ngày tháng/tên riêng.
- pass=true nếu chỉ còn lỗi minor không ảnh hưởng nội dung xuất Word.
- Không markdown, chỉ JSON."""


async def final_review_document(
    doc_type: str,
    doc_type_label: str,
    draft_data: dict,
    input_data: dict,
    agent_result: dict,
) -> dict:
    """
    Run deterministic checks and an LLM final review.

    Returns:
        {
          pass: bool,
          deterministic: {...},
          llm: {...},
          issues: list[dict],
          summary: str
        }
    """
    deterministic = deterministic_review(doc_type, draft_data)
    if not deterministic["pass"]:
        logger.warning(
            f"[FinalReviewer] deterministic failed: "
            f"{len(deterministic['issues'])} issues"
        )
        return {
            "pass": False,
            "deterministic": deterministic,
            "llm": None,
            "issues": deterministic["issues"],
            "summary": "Không đạt kiểm tra cấu trúc/nội dung bắt buộc trước khi xuất Word.",
        }

    llm_review = await llm_final_review(
        doc_type=doc_type,
        doc_type_label=doc_type_label,
        draft_data=draft_data,
        input_data=input_data,
        agent_result=agent_result,
    )
    llm_review["issues"] = _filter_invalid_schema_issues(
        doc_type,
        llm_review.get("issues", []),
    )

    issues = deterministic["issues"] + [
        issue for issue in llm_review.get("issues", [])
        if isinstance(issue, dict)
    ]
    has_blocking_issue = has_blocking_final_issues(issues)
    llm_pass = bool(llm_review.get("pass", False))
    try:
        score = float(llm_review.get("score", 0) or 0)
    except (TypeError, ValueError):
        score = 0
    only_minor_issues = bool(issues) and all(
        isinstance(issue, dict) and issue.get("severity") == "minor"
        for issue in issues
    )
    passed = not has_blocking_issue and (llm_pass and score >= 6 or only_minor_issues)

    logger.info(
        f"[FinalReviewer] deterministic=pass, llm_pass={llm_review.get('pass')}, "
        f"score={llm_review.get('score')}, final_pass={passed}"
    )

    return {
        "pass": passed,
        "deterministic": deterministic,
        "llm": llm_review,
        "issues": issues,
        "summary": llm_review.get("summary", ""),
    }


def deterministic_review(doc_type: str, draft_data: dict) -> dict:
    """Fast schema/content gate that does not call the LLM."""
    issues = []
    draft_data = sanitize_for_review(draft_data)

    if not isinstance(draft_data, dict) or not draft_data:
        issues.append(_issue("schema", "critical", "Bản nháp rỗng hoặc không phải JSON object."))
        return {"pass": False, "issues": issues}

    if doc_type == "ke_hoach" and _has_valid_custom_sections(draft_data):
        required = []
    else:
        required = REQUIRED_CONTENT_FIELDS.get(doc_type, ["noi_dung"])
    for field in required:
        if field not in draft_data:
            issues.append(_issue("schema", "critical", f"Thiếu trường bắt buộc `{field}`."))
            continue
        if _is_empty_value(draft_data.get(field)):
            issues.append(_issue("content", "critical", f"Trường `{field}` đang rỗng."))

    if doc_type == "quyet_dinh":
        can_cu = draft_data.get("can_cu", [])
        dieu_khoan = draft_data.get("dieu_khoan", [])
        if not isinstance(can_cu, list) or not can_cu:
            issues.append(_issue("schema", "critical", "`can_cu` phải là danh sách không rỗng."))
        if not isinstance(dieu_khoan, list) or not dieu_khoan:
            issues.append(_issue("schema", "critical", "`dieu_khoan` phải là danh sách không rỗng."))
        else:
            for idx, dieu in enumerate(dieu_khoan, 1):
                if not isinstance(dieu, dict):
                    issues.append(_issue("schema", "critical", f"Điều khoản {idx} không phải object."))
                    continue
                if not dieu.get("so_dieu") or not dieu.get("noi_dung"):
                    issues.append(_issue("schema", "critical", f"Điều khoản {idx} thiếu `so_dieu` hoặc `noi_dung`."))

    for field, min_chars in MIN_FIELD_CHARS.items():
        if field not in draft_data:
            continue
        value = draft_data.get(field)
        if isinstance(value, str) and value.strip() and len(value.strip()) < min_chars:
            issues.append(_issue("content", "minor", f"Trường `{field}` hơi ngắn ({len(value.strip())}/{min_chars} ký tự)."))

    full_text = _flatten_text(draft_data)
    lower_text = full_text.lower()
    for phrase in BLOCKED_PHRASES:
        if phrase in lower_text:
            issues.append(_issue("content", "minor", f"Còn câu rác/thiếu dữ liệu đã được lọc trước xuất: `{phrase}`."))

    if re.search(r"\[Nguồn:[^\]]*\]|\[\s*Điểm\s*:[^\]]*\]|\|\s*Điểm\s*:\s*[0-9.]+", full_text, re.IGNORECASE):
        issues.append(_issue("format", "major", "Nội dung còn metadata nguồn/ký hiệu nội bộ như `[Nguồn: ...]` hoặc `Điểm: ...`."))

    if re.search(r"(?m)^\s*(?:I|II|III|IV|V|VI)\.\s+", full_text):
        issues.append(_issue("format", "minor", "Nội dung field còn tự viết mục La Mã; hệ thống sẽ làm sạch trước khi xuất."))

    if "**" in full_text or "|" in full_text and re.search(r"\|.+\|", full_text):
        issues.append(_issue("format", "minor", "Nội dung còn dấu markdown/table, cần làm sạch trước khi xuất."))

    blocking = any(issue["severity"] in {"critical", "major"} for issue in issues)
    return {"pass": not blocking, "issues": issues}


def _has_valid_custom_sections(draft_data: dict) -> bool:
    sections = draft_data.get("custom_sections") if isinstance(draft_data, dict) else None
    if not isinstance(sections, list):
        return False
    valid = [
        section for section in sections
        if isinstance(section, dict)
        and str(section.get("title", "")).strip()
        and len(str(section.get("content", "")).strip()) >= 40
    ]
    return len(valid) >= 1


def sanitize_for_review(data: dict) -> dict:
    """Light cleanup for review-only checks; export cleanup happens in drafting_service."""
    if not isinstance(data, dict):
        return data
    return {key: _sanitize_review_value(value) for key, value in data.items()}


def _sanitize_review_value(value):
    if isinstance(value, str):
        text = value
        for phrase in BLOCKED_PHRASES:
            text = re.sub(rf"(?im)^.*{re.escape(phrase)}.*$", "", text)
        text = re.sub(r"\s*\[Nguồn:[^\]]*\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*\[\s*Điểm\s*:[^\]]*\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*\|\s*Điểm\s*:\s*[0-9.]+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"(?m)^\s*(?:I|II|III|IV|V|VI)\.\s+", "", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()
    if isinstance(value, list):
        return [_sanitize_review_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_review_value(item) for key, item in value.items()}
    return value


def has_blocking_final_issues(issues: list[dict]) -> bool:
    return any(
        isinstance(issue, dict)
        and issue.get("severity") in {"critical", "major"}
        for issue in issues
    )


def has_critical_final_issues(issues: list[dict]) -> bool:
    return any(
        isinstance(issue, dict)
        and issue.get("severity") == "critical"
        for issue in issues
    )


def has_unrecoverable_schema_issues(issues: list[dict]) -> bool:
    """Issues that still cannot be exported after the LLM cleanup attempt."""
    for issue in issues:
        if not isinstance(issue, dict) or issue.get("severity") != "critical":
            continue
        issue_type = issue.get("type")
        description = str(issue.get("description", "") or "").lower()
        if issue_type == "schema":
            return True
        if issue_type == "content" and ("rỗng" in description or "trống" in description):
            return True
    return False


async def final_fix_draft(
    doc_type: str,
    doc_type_label: str,
    draft_data: dict,
    input_data: dict,
    issues: list[dict],
) -> dict:
    """Use the LLM once to fix review issues while preserving exporter schema."""
    schema = SCHEMA_DESCRIPTIONS.get(
        doc_type,
        ", ".join(REQUIRED_CONTENT_FIELDS.get(doc_type, ["noi_dung"])),
    )
    system_prompt = f"""Bạn là biên tập viên cuối văn bản hành chính.

NHIỆM VỤ:
Sửa JSON bản nháp để khắc phục các lỗi review, giữ đúng schema exporter.

QUY TẮC:
- Trả về JSON object duy nhất, không markdown.
- Giữ đúng các field hợp lệ: {schema}
- Không thêm field ngoài schema.
- Không bịa số liệu/ngày tháng/tên văn bản mới.
- Loại bỏ hoàn toàn `[Nguồn: ...]`, `Điểm: ...`, tên file nguồn, markdown, ký tự thừa và nội dung lặp.
- Viết lại theo văn phong hành chính nhà nước Việt Nam: ngắn, rõ, thực tế, không văn phong AI/chung chung.
- Bảo đảm đúng cấp hành chính và đúng thẩm quyền cơ quan ban hành. Với cấp xã/huyện, chỉ dùng nhiệm vụ triển khai, phối hợp, rà soát, kiểm tra, tổng hợp, báo cáo, đề xuất; không viết nội dung vượt thẩm quyền.
- Nếu các field lặp nhau, tách vai trò:
  + phan_mo_dau: căn cứ ban hành, bối cảnh, yêu cầu thực tiễn và câu dẫn vào kế hoạch.
  + muc_dich_yeu_cau: mục I, tách mục đích và yêu cầu nếu phù hợp.
  + noi_dung_thuc_hien: mục II, nhiệm vụ/hoạt động triển khai; mỗi nhiệm vụ có chủ trì/phối hợp/thời gian nếu có dữ liệu.
  + kinh_phi: mục III, nguồn kinh phí, quản lý và thanh quyết toán nếu có.
  + to_chuc_thuc_hien: mục IV, phân công, trách nhiệm, chế độ báo cáo, theo dõi, đôn đốc, kiểm tra.
  + phu_luc_nhiem_vu: phụ lục nhiệm vụ nếu phù hợp.
  + custom_sections: danh sách mục kế hoạch cố định, mỗi mục gồm title và content; giữ nếu có, bỏ mục content rỗng.
- Nếu có nhận xét về khác biệt số/ký hiệu văn bản và tài liệu tham chiếu, viết lại cho rõ đó là tài liệu tham chiếu/căn cứ nếu có trong bản nháp; không tự kết luận sai.
"""
    user_prompt = f"""LOẠI VĂN BẢN: {doc_type_label} ({doc_type})

SCHEMA HỢP LỆ:
{schema}

THÔNG TIN NGƯỜI DÙNG:
{json.dumps(input_data, ensure_ascii=False, indent=2)}

BẢN NHÁP JSON CẦN SỬA:
{json.dumps(draft_data, ensure_ascii=False, indent=2)}

LỖI REVIEW CẦN KHẮC PHỤC:
{json.dumps(issues, ensure_ascii=False, indent=2)}
"""

    try:
        fixed = await llm_service.chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=12000,
        )
    except Exception as exc:
        logger.warning("[FinalFixer] LLM fix failed: %s", exc)
        return {}

    if not isinstance(fixed, dict):
        return {}

    allowed = set(REQUIRED_CONTENT_FIELDS.get(doc_type, ["noi_dung"]))
    if doc_type == "cong_van":
        allowed.add("de_nghi")
    if doc_type == "ke_hoach":
        allowed.update({
            "custom_sections",
            "phu_luc_nhiem_vu",
            "muc_dich_yeu_cau",
            "noi_dung_thuc_hien",
            "kinh_phi",
            "noi_dung_ke_hoach",
            "dinh_huong_chi_dao",
            "nhiem_vu_trong_tam",
        })
    fixed = {key: value for key, value in fixed.items() if key in allowed}

    logger.info("[FinalFixer] produced fields=%d", len(fixed))
    return fixed


async def final_grounding_edit_draft(
    doc_type: str,
    doc_type_label: str,
    draft_data: dict,
    input_data: dict,
    issues: list[dict],
    agent_result: dict | None = None,
) -> dict:
    """
    User-friendly final editor: remove unsupported/hallucinated content and
    replace missing details with administrative notes so Word export can proceed.
    """
    agent_result = agent_result or {}
    schema = SCHEMA_DESCRIPTIONS.get(
        doc_type,
        ", ".join(REQUIRED_CONTENT_FIELDS.get(doc_type, ["noi_dung"])),
    )
    research_context = str(agent_result.get("research_context", "") or "")[:6000]
    evidence_issues = agent_result.get("evidence_issues") or []

    system_prompt = f"""Bạn là biên tập viên kiểm chứng cuối trước khi xuất Word.

MỤC TIÊU:
Tạo JSON văn bản hành chính sạch, dễ dùng cho người phổ thông. Khi phát hiện
nội dung nghi bịa hoặc không có căn cứ, KHÔNG báo lỗi kỹ thuật cho người dùng;
hãy loại bỏ/viết lại nội dung đó và ghi chú ngắn để người dùng bổ sung.

QUY TẮC BẮT BUỘC:
- Trả về JSON object duy nhất, không markdown.
- Giữ đúng các field hợp lệ: {schema}
- Không thêm field ngoài schema.
- Không bịa số liệu, ngày tháng, số hiệu văn bản, tên người, tên cơ quan, căn cứ pháp lý, chỉ tiêu cụ thể.
- Chỉ giữ thông tin có trong THÔNG TIN NGƯỜI DÙNG, BẢN NHÁP, hoặc DỮ LIỆU NGHIÊN CỨU.
- Nếu thiếu dữ liệu chi tiết, viết ghi chú hành chính trong đúng field, ví dụ:
  "Ghi chú cần bổ sung: ...".
- Không dùng các câu rác như "không có thông tin", "không tìm thấy dữ liệu", "tôi không thể".
- Loại bỏ toàn bộ `[Nguồn: ...]`, `Điểm: ...`, tên file nguồn, heading nguồn, markdown, ký tự lạ, đoạn lặp.
- Văn phong phải là hành chính nhà nước Việt Nam: ngắn gọn, rõ việc, thực tế, phù hợp cấp xã/huyện khi cơ quan ban hành là cấp xã/huyện.
- Không viết nội dung vượt thẩm quyền; chỉ ghi nhiệm vụ triển khai/phối hợp/rà soát/kiểm tra/tổng hợp/báo cáo/đề xuất nếu là cấp xã/huyện.
- Số/ký hiệu như `123/KH-UBND`, `2023/KH-UBND`, `01-KH/BCĐ`, `45/QĐ-UBND`
  là mã văn bản; không tự coi phần số là năm nếu người dùng không ghi năm độc lập.
- Với kế hoạch:
  + phan_mo_dau: căn cứ ban hành, bối cảnh, yêu cầu thực tiễn và câu dẫn vào kế hoạch.
  + muc_dich_yeu_cau: mục đích và yêu cầu; thiếu mục tiêu/yêu cầu thì ghi chú cần bổ sung.
  + noi_dung_thuc_hien: nội dung thực hiện; thiếu chỉ tiêu/thời hạn/đầu mối thì ghi chú cần bổ sung.
  + kinh_phi: nguồn kinh phí; thiếu nguồn kinh phí thì ghi chú cần bổ sung.
  + to_chuc_thuc_hien: tổ chức thực hiện, phân công, trách nhiệm, kiểm tra; thiếu đầu mối/thời hạn thì ghi chú cần bổ sung.
  + phu_luc_nhiem_vu: phụ lục nhiệm vụ nếu phù hợp, trình bày theo các cột yêu cầu bằng văn bản thuần.
  + custom_sections: nếu bản nháp có danh sách mục kế hoạch cố định thì giữ lại mục có content, làm sạch từng content, không tự thêm mục rỗng.
"""
    user_prompt = f"""LOẠI VĂN BẢN: {doc_type_label} ({doc_type})

SCHEMA HỢP LỆ:
{schema}

THÔNG TIN NGƯỜI DÙNG:
{json.dumps(input_data, ensure_ascii=False, indent=2)}

BẢN NHÁP JSON CẦN LÀM SẠCH:
{json.dumps(draft_data or {}, ensure_ascii=False, indent=2)}

LỖI/EVIDENCE CẦN XỬ LÝ:
{json.dumps({"review_issues": issues, "evidence_issues": evidence_issues}, ensure_ascii=False, indent=2)}

DỮ LIỆU NGHIÊN CỨU TÓM TẮT:
{research_context}
"""

    try:
        cleaned = await llm_service.chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=16000,
        )
    except Exception as exc:
        logger.warning("[GroundingEditor] LLM cleanup failed: %s", exc)
        cleaned = {}

    cleaned = _coerce_export_schema(doc_type, cleaned if isinstance(cleaned, dict) else {})
    if not cleaned:
        cleaned = build_user_friendly_fallback_draft(doc_type, input_data, issues + evidence_issues)

    logger.info("[GroundingEditor] produced fields=%d", len(cleaned))
    return cleaned


def build_user_friendly_fallback_draft(
    doc_type: str,
    input_data: dict,
    issues: list | None = None,
) -> dict:
    """Deterministic fallback when LLM cleanup cannot produce JSON."""
    issues = issues or []
    requirement = _first_non_empty(
        input_data.get("noi_dung_chinh"),
        input_data.get("trich_yeu"),
        input_data.get("ten_van_ban"),
        "nội dung theo yêu cầu",
    )
    note = _fallback_note(issues)

    if doc_type == "ke_hoach":
        return {
            "phan_mo_dau": (
                f"Căn cứ yêu cầu triển khai {requirement}, cơ quan ban hành xây dựng kế hoạch "
                f"nhằm tổ chức thực hiện thống nhất, kịp thời và phù hợp điều kiện thực tế. {note}"
            ),
            "muc_dich_yeu_cau": (
                f"1. Mục đích: Tổ chức triển khai {requirement} thống nhất, kịp thời, phù hợp điều kiện thực tế. {note}\n"
                "2. Yêu cầu: Nội dung thực hiện phải rõ trách nhiệm, đúng tiến độ, tiết kiệm, hiệu quả và bảo đảm phối hợp giữa các đơn vị liên quan."
            ),
            "noi_dung_thuc_hien": (
                f"Khẩn trương rà soát hiện trạng, xác định nhiệm vụ trọng tâm, phân công cơ quan "
                f"chủ trì, cơ quan phối hợp và thời hạn thực hiện đối với {requirement}. {note}"
            ),
            "kinh_phi": (
                f"Kinh phí thực hiện từ nguồn kinh phí được giao và các nguồn hợp pháp khác theo quy định. {note}"
            ),
            "to_chuc_thuc_hien": (
                "Các bộ phận, đơn vị liên quan căn cứ chức năng, nhiệm vụ được giao "
                f"để phối hợp triển khai, tổng hợp kết quả và báo cáo theo quy định. {note}"
            ),
        }
    if doc_type == "bao_cao":
        return {
            "tinh_hinh_chung": f"Tổng hợp tình hình chung liên quan đến {requirement}. {note}",
            "ket_qua": f"Trình bày kết quả thực hiện theo các nội dung đã có căn cứ. {note}",
            "han_che": f"Nêu các tồn tại, khó khăn trong quá trình thực hiện. {note}",
            "phuong_huong": f"Đề xuất phương hướng, nhiệm vụ tiếp tục thực hiện. {note}",
        }
    if doc_type == "to_trinh":
        return {
            "su_can_thiet": f"Nêu sự cần thiết của nội dung đề xuất: {requirement}. {note}",
            "noi_dung_de_xuat": f"Trình bày nội dung đề xuất theo thông tin đã được cung cấp. {note}",
            "kien_nghi": f"Kính đề nghị cấp có thẩm quyền xem xét, cho ý kiến chỉ đạo. {note}",
        }
    if doc_type == "quyet_dinh":
        return {
            "can_cu": [f"Căn cứ các văn bản, thông tin do người dùng cung cấp. {note}"],
            "dieu_khoan": [
                {"so_dieu": "Điều 1", "noi_dung": f"Quyết định nội dung liên quan đến {requirement}. {note}"},
                {"so_dieu": "Điều 2", "noi_dung": "Tổ chức thực hiện theo chức năng, nhiệm vụ được giao."},
            ],
        }
    return {
        "noi_dung": (
            f"Trình bày nội dung theo yêu cầu: {requirement}. Các nội dung chưa có "
            f"căn cứ đầy đủ được để lại dưới dạng ghi chú để người dùng bổ sung. {note}"
        ),
        **({"de_nghi": f"Kính đề nghị xem xét, bổ sung thông tin còn thiếu trước khi ban hành. {note}"} if doc_type == "cong_van" else {}),
    }


def _coerce_export_schema(doc_type: str, data: dict) -> dict:
    if not isinstance(data, dict):
        return {}

    allowed = set(REQUIRED_CONTENT_FIELDS.get(doc_type, ["noi_dung"]))
    if doc_type == "cong_van":
        allowed.add("de_nghi")
    if doc_type == "ke_hoach":
        allowed.update({
            "custom_sections",
            "phu_luc_nhiem_vu",
            "muc_dich_yeu_cau",
            "noi_dung_thuc_hien",
            "kinh_phi",
            "noi_dung_ke_hoach",
            "dinh_huong_chi_dao",
            "nhiem_vu_trong_tam",
        })
    coerced = {key: value for key, value in data.items() if key in allowed}

    if doc_type == "quyet_dinh":
        if "can_cu" in coerced and isinstance(coerced["can_cu"], str):
            coerced["can_cu"] = [coerced["can_cu"]]
        if "dieu_khoan" in coerced and isinstance(coerced["dieu_khoan"], str):
            coerced["dieu_khoan"] = [{"so_dieu": "Điều 1", "noi_dung": coerced["dieu_khoan"]}]

    return coerced


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _fallback_note(issues: list) -> str:
    descriptions = []
    for issue in issues:
        if isinstance(issue, dict):
            text = str(issue.get("description", "") or issue.get("suggestion", "") or "").strip()
        else:
            text = str(issue or "").strip()
        if text:
            descriptions.append(text)

    if not descriptions:
        return "Ghi chú cần bổ sung: rà soát và cập nhật thông tin chi tiết trước khi ban hành."

    summary = "; ".join(descriptions[:2])
    summary = re.sub(r"\s+", " ", summary).strip()
    replacements = {
        "Không tìm thấy dữ liệu": "Cần bổ sung căn cứ",
        "không tìm thấy dữ liệu": "cần bổ sung căn cứ",
        "Không có thông tin": "Cần bổ sung thông tin",
        "không có thông tin": "cần bổ sung thông tin",
        "Không đủ thông tin": "Cần bổ sung thông tin",
        "không đủ thông tin": "cần bổ sung thông tin",
    }
    for old, new in replacements.items():
        summary = summary.replace(old, new)
    return f"Ghi chú cần bổ sung: {summary[:280]}."


async def llm_final_review(
    doc_type: str,
    doc_type_label: str,
    draft_data: dict,
    input_data: dict,
    agent_result: dict,
) -> dict:
    """LLM reviewer for global coherence after section merge."""
    plan = agent_result.get("plan", {})
    research_context = agent_result.get("research_context", "")
    review_issues = agent_result.get("review_issues", [])
    expected_schema = SCHEMA_DESCRIPTIONS.get(
        doc_type,
        ", ".join(REQUIRED_CONTENT_FIELDS.get(doc_type, ["noi_dung"])),
    )
    constraints = _extract_request_constraints(input_data)

    user_prompt = f"""LOẠI VĂN BẢN: {doc_type_label} ({doc_type})

SCHEMA HỢP LỆ CHO BẢN NHÁP:
{expected_schema}

RÀNG BUỘC HIỂU TRÍCH YẾU:
{json.dumps(constraints, ensure_ascii=False, indent=2)}

YÊU CẦU/TRÍCH YẾU NGƯỜI DÙNG:
{json.dumps(input_data, ensure_ascii=False, indent=2)}

DÀN Ý PLANNER:
{json.dumps(plan, ensure_ascii=False, indent=2)[:4000]}

BẢN NHÁP ĐÃ MERGE JSON:
{json.dumps(draft_data, ensure_ascii=False, indent=2)[:9000]}

DỮ LIỆU NGHIÊN CỨU TÓM TẮT:
{research_context[:5000]}

ISSUES TỪ REVIEWER TRƯỚC ĐÓ:
{json.dumps(review_issues, ensure_ascii=False, indent=2)}

Hãy kiểm tra lần cuối trước khi xuất Word."""

    try:
        result = await llm_service.chat_json(
            system_prompt=FINAL_REVIEWER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=2400,
        )
    except Exception as e:
        logger.error(f"[FinalReviewer] LLM review failed: {e}")
        return {
            "pass": False,
            "score": 0,
            "issues": [_issue("system", "critical", f"LLM final reviewer lỗi: {e}")],
            "summary": "Không thể kiểm tra lần cuối bằng LLM.",
        }

    if not result:
        logger.warning("[FinalReviewer] Empty/unparseable LLM review; allowing deterministic result")
        return {
            "pass": True,
            "score": 7,
            "issues": [],
            "summary": "LLM reviewer không trả JSON hợp lệ; đã dùng kiểm tra deterministic.",
        }

    issues = result.get("issues") if isinstance(result.get("issues"), list) else []
    issues = _filter_false_temporal_and_citation_issues(issues, constraints)
    return {
        "pass": bool(result.get("pass", False)),
        "score": result.get("score", 0),
        "issues": issues,
        "summary": str(result.get("summary", "") or ""),
    }


def _filter_invalid_schema_issues(doc_type: str, issues: list) -> list[dict]:
    """Drop schema complaints about fields that are not part of this exporter."""
    required_fields = set(REQUIRED_CONTENT_FIELDS.get(doc_type, ["noi_dung"]))
    allowed_fields = set(required_fields)
    if doc_type == "cong_van":
        allowed_fields.add("de_nghi")
    if doc_type == "ke_hoach":
        allowed_fields.update({
            "custom_sections",
            "phu_luc_nhiem_vu",
            "muc_dich_yeu_cau",
            "noi_dung_thuc_hien",
            "kinh_phi",
            "noi_dung_ke_hoach",
            "dinh_huong_chi_dao",
            "nhiem_vu_trong_tam",
        })

    filtered = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue

        description = str(issue.get("description", "") or "")
        issue_type = str(issue.get("type", "") or "")
        lowered = description.lower()

        if issue_type == "schema":
            if any(field in lowered for field in ("summary", "sections")):
                continue

            mentioned_fields = set(re.findall(r'"([^"]+)"|`([^`]+)`', description))
            flattened_mentions = {item for pair in mentioned_fields for item in pair if item}
            unknown_mentions = {
                field for field in flattened_mentions
                if re.match(r"^[a-z_]+$", field) and field not in allowed_fields
            }
            if unknown_mentions:
                continue

            optional_mentions = {
                field for field in flattened_mentions
                if field in allowed_fields and field not in required_fields
            }
            if (
                optional_mentions
                and any(term in lowered for term in ("thiếu", "missing", "bắt buộc", "required"))
            ):
                continue

        if doc_type == "ke_hoach" and any(
            term in lowered
            for term in (
                "trình bày dưới dạng json",
                "dạng json",
                "các trường",
                "không có đánh số i",
                "không có đánh số i.",
                "không được viết in hoa",
            )
        ):
            # The final reviewer sees exporter JSON, not the rendered DOCX. Word export
            # adds the uppercase headings and Roman numerals for kế hoạch.
            continue

        filtered.append(issue)

    return filtered


def _extract_request_constraints(input_data: dict) -> dict:
    text = json.dumps(input_data or {}, ensure_ascii=False)
    doc_codes = [
        re.sub(r"\s+", "", match).upper().replace("–", "-")
        for match in re.findall(
            DOC_CODE_PATTERN,
            text,
            re.IGNORECASE,
        )
    ]
    text_without_doc_codes = re.sub(
        DOC_CODE_PATTERN,
        "",
        text,
        flags=re.IGNORECASE,
    )
    explicit_years = sorted(set(re.findall(r"\b20\d{2}\b", text_without_doc_codes)))
    return {
        "document_codes": doc_codes,
        "explicit_years": explicit_years,
        "note": (
            "Các số trong document_codes là số/ký hiệu văn bản, không phải ràng buộc năm. "
            "Chỉ explicit_years mới là năm bắt buộc."
        ),
    }


def _filter_false_temporal_and_citation_issues(issues: list, constraints: dict) -> list[dict]:
    explicit_years = set(constraints.get("explicit_years") or [])
    doc_code_numbers = {
        number
        for code in constraints.get("document_codes") or []
        for number in re.findall(r"\b\d{1,5}\b", code)
    }

    filtered = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue

        description = str(issue.get("description", "") or "")
        lowered = description.lower()

        if (
            "điểm:" in lowered
            or "metadata" in lowered
            or "ký hiệu không chuẩn" in lowered
            or "[nguồn:" in lowered and "trích dẫn" in lowered
        ):
            continue

        if not explicit_years and doc_code_numbers:
            if _is_doc_code_number_confusion(description, lowered, doc_code_numbers):
                continue

        filtered.append(issue)

    return filtered


def _is_doc_code_number_confusion(description: str, lowered: str, doc_code_numbers: set[str]) -> bool:
    """Detect generic LLM mistakes that treat number in document code as a standalone year/number."""
    if not any(number in description for number in doc_code_numbers):
        return False

    temporal_or_grounding_terms = (
        "mâu thuẫn thời gian",
        "yêu cầu năm",
        "trong khi yêu cầu",
        "không có bằng chứng",
        "không có nguồn hỗ trợ",
        "tài liệu tham khảo",
        "nguồn tham khảo",
        "không nhất quán",
        "năm khác",
        "bịa dữ liệu",
        "ngoài ngữ cảnh",
    )
    if any(term in lowered for term in temporal_or_grounding_terms):
        return True

    for number in doc_code_numbers:
        generic_patterns = (
            rf"\bnăm\s+{re.escape(number)}\b",
            rf"\bkế hoạch\s+{re.escape(number)}\b",
            rf"\bquyết định\s+{re.escape(number)}\b",
            rf"\bcông văn\s+{re.escape(number)}\b",
            rf"\bvăn bản\s+{re.escape(number)}\b",
            rf"\byêu cầu\s+{re.escape(number)}\b",
        )
        if any(re.search(pattern, lowered) for pattern in generic_patterns):
            return True

    return False


def format_final_review_errors(review: dict) -> str:
    """Convert final review issues to a compact error message for task status."""
    issues = review.get("issues", [])
    if not issues:
        return review.get("summary") or "Văn bản chưa đạt kiểm tra cuối."
    lines = []
    for issue in issues[:6]:
        if not isinstance(issue, dict):
            continue
        lines.append(
            f"- [{issue.get('severity', '?')}] {issue.get('description', '')}"
        )
    return "Văn bản chưa đạt kiểm tra cuối trước khi xuất Word:\n" + "\n".join(lines)


def _issue(issue_type: str, severity: str, description: str, suggestion: str = "") -> dict:
    return {
        "type": issue_type,
        "severity": severity,
        "description": description,
        "suggestion": suggestion,
    }


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_flatten_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(_flatten_text(v) for v in value)
    return str(value) if value is not None else ""
