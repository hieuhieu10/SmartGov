"""
Writer Agent — Draft document content based on plan and research data.

Responsibilities:
  - Follow the Planner's outline structure
  - Use research data as evidence/sources
  - Generate content in the required document format (JSON)
  - Keep source references internal; exported content must not contain citations
  - Incorporate Reviewer feedback in revision iterations
"""

import json
import logging
import re

from app.services.llm_service import llm_service
from app.agents.prompt_policy import (
    ADMIN_DRAFTING_PROCESS_RULES,
    ADMIN_DRAFTING_ROLE_PROMPT,
    CHATBOT_PROHIBITIONS,
)

logger = logging.getLogger(__name__)

WRITER_SYSTEM_PROMPT = (
    ADMIN_DRAFTING_ROLE_PROMPT
    + "\n\n"
    + ADMIN_DRAFTING_PROCESS_RULES
    + "\n\n"
    + CHATBOT_PROHIBITIONS
    + """

NHIỆM VỤ: Viết nội dung văn bản {doc_type_label} dựa trên "DỮ LIỆU NGHIÊN CỨU" và yêu cầu của người dùng.

QUY TẮC CẤU TRÚC & PHÂN CẤP (QUAN TRỌNG):
1. **Phân cấp đề mục**: 
    - Các đề mục LỚN (I, II, III...) đã được hệ thống định nghĩa. Bạn KHÔNG tự ý viết lại các đề mục La Mã này trong nội dung.
    - TRONG MỖI PHẦN LỚN, các mục con PHẢI bắt đầu bằng số thứ tự: **1. , 2. , 3. ...** Tuyệt đối KHÔNG sử dụng chữ số La Mã (I, II, III...) cho các mục này.
    - Dưới mục số là các ý gạch đầu dòng: **-**
    - Dưới ý gạch đầu dòng là các dấu cộng: **+**
    *Ví dụ chuẩn (BẮT BUỘC TUÂN THỦ):* 
    II. NỘI DUNG (Hệ thống đã có)
    1. Cơ sở pháp lý và quy chuẩn liên quan
    - Luật X...
    + Nghị định Y...

2. **Gom ý cha - con (Merge single items)**: Nếu một đề mục (ví dụ mục 1. hoặc ý -) chỉ có DUY NHẤT một ý con nhỏ hơn, hãy GOM nội dung của ý con đó lên luôn mục cha. Tránh việc tạo phân cấp chỉ để chứa 1 dòng duy nhất. (Ví dụ: thay vì "- Nhiệm vụ\n  + Nhiệm vụ 1", hãy viết luôn "- Nhiệm vụ: Nhiệm vụ 1").

3. **Xử lý thiếu thông tin**: Nếu một mục hoặc ý chính không có dữ liệu trong phần nghiên cứu, hãy **BỎ QUA HOÀN TOÀN**. Tuyệt đối KHÔNG viết các câu như "[Không có thông tin]" hay "Chưa rõ thông tin".

QUY TẮC THỂ THỨC (Nghị định 30):
4. **Cơ quan chủ quản & Ban hành**: Trong nội dung văn bản, CHỈ viết hoa chữ cái đầu của các cụm từ theo đúng quy tắc chính tả tiếng Việt (Ví dụ: "Ủy ban nhân dân tỉnh Tây Ninh", "Sở Thông tin và Truyền thông"). TUYỆT ĐỐI KHÔNG VIẾT IN HOA TOÀN BỘ tên cơ quan trong phần nội dung (việc in hoa ở đầu trang đã do hệ thống tự động xử lý).
5. **Không sử dụng markdown stars**: Tuyệt đối KHÔNG sử dụng dấu ** trong văn bản.

QUY TẮC NỘI DUNG (TUYỆT ĐỐI TUÂN THỦ):
6. **CHỐNG BỊA ĐẶT DỮ LIỆU (ANTI-HALLUCINATION)**: TUYỆT ĐỐI KHÔNG ĐƯỢC BỊA DỮ LIỆU. Chỉ được lấy dữ liệu từ kho (DỮ LIỆU NGHIÊN CỨU) hoặc thông tin người dùng nhập. Mọi con số, tên người, cơ quan, ngày tháng không có trong dữ liệu gốc đều bị coi là vi phạm nghiêm trọng.
7. **Dựa trên bằng chứng**: Chỉ viết những gì có bằng chứng từ phần "TỔNG HỢP BẰNG CHỨNG THEN CHỐT".
8. **Không đưa metadata nguồn vào văn bản xuất**: KHÔNG ghi `[Nguồn: ...]`, `Điểm: ...`, tên file, heading nguồn, markdown, ký tự lạ hoặc chú thích nội bộ trong nội dung. Nguồn chỉ dùng để hiểu và kiểm chứng.
9. **Đúng thẩm quyền hành chính**: Nội dung phải phù hợp cấp cơ quan ban hành. Nếu cơ quan là cấp xã/huyện, chỉ viết các việc thuộc thẩm quyền như tổ chức thực hiện, phối hợp, rà soát, tuyên truyền, kiểm tra, tổng hợp, báo cáo, đề xuất cấp có thẩm quyền; không viết như thể cơ quan được ban hành chính sách cấp trên, phê duyệt ngân sách/quy hoạch vượt thẩm quyền.
10. **Văn phong hành chính thực tế**: Câu ngắn, rõ, trực tiếp; không dùng văn phong AI, không khẩu hiệu, không nói chung chung kiểu "đẩy mạnh toàn diện", "tối ưu hóa hiệu quả" nếu không có hành động cụ thể. Mỗi nhiệm vụ nên nêu được việc làm, đơn vị/phạm vi phối hợp, thời gian hoặc cách kiểm tra nếu có dữ liệu.
"""
)


async def writer_node(state: dict) -> dict:
    """
    Writer Agent: draft document content.

    Input state: plan, research_context, input_data, doc_type, doc_type_label,
                 review_feedback (on revision), iteration
    Output state: draft, draft_data, iteration
    """
    plan = state.get("plan", {})
    research_context = state.get("research_context", "")
    input_data = state.get("input_data", {})
    template_outline = state.get("template_outline", {})
    doc_type = state.get("doc_type", "khac")
    doc_type_label = state.get("doc_type_label", "Văn bản")
    trich_yeu = state.get("trich_yeu", "")
    review_feedback = state.get("review_feedback", "")
    iteration = state.get("iteration", 0) + 1

    try:
        section_drafts = await _write_sections(
            plan=plan,
            research_context=research_context,
            input_data=input_data,
            template_outline=template_outline,
            doc_type=doc_type,
            doc_type_label=doc_type_label,
            trich_yeu=trich_yeu,
            review_feedback=review_feedback,
            iteration=iteration,
        )

        draft_data = _assemble_draft_data(
            doc_type=doc_type,
            section_drafts=section_drafts,
            input_data=input_data,
        )
        raw_response = json.dumps(draft_data, ensure_ascii=False, indent=2)

        logger.info(
            f"[Writer] Iteration {iteration}: wrote {len(section_drafts)} sections, "
            f"{len(raw_response)} chars, {len(draft_data)} fields"
        )

        return {
            "draft": raw_response,
            "draft_data": draft_data,
            "section_drafts": section_drafts,
            "iteration": iteration,
        }

    except Exception as e:
        logger.error(f"[Writer] Failed at iteration {iteration}: {e}")
        return {
            "draft": "",
            "draft_data": {},
            "iteration": iteration,
            "error": f"Writer error: {str(e)}",
        }


SECTION_WRITER_SYSTEM_PROMPT = f"""{ADMIN_DRAFTING_ROLE_PROMPT}

{ADMIN_DRAFTING_PROCESS_RULES}

{CHATBOT_PROHIBITIONS}

NHIỆM VỤ: Chỉ viết MỘT MỤC trong dàn ý, không viết toàn bộ văn bản.

QUY TẮC:
1. Tổng hợp dữ liệu trong "DỮ LIỆU RIÊNG CHO MỤC" và thông tin người dùng; ưu tiên nguồn cùng lĩnh vực, cùng loại, mới hơn, giá trị pháp lý cao hơn.
2. Không bịa số liệu, ngày tháng, tên người, số hiệu văn bản, căn cứ pháp lý. Với nội dung nghiệp vụ chung còn thiếu chi tiết, tự viết phương án hành chính hợp lý theo ngữ cảnh.
3. Nếu thiếu dữ liệu cho một ý quá cụ thể, bỏ qua ý đó; không viết "[Không có thông tin]".
   Cũng không được viết các biến thể như "không có thông tin", "không tìm thấy dữ liệu", "dữ liệu không đề cập", "không đủ thông tin".
   Nếu toàn bộ mục không có dữ liệu liên quan trong kho và thông tin người dùng, trả về rỗng.
4. Viết bằng văn phong hành chính nhà nước Việt Nam, ngắn gọn, rõ việc, đúng thẩm quyền cơ quan ban hành.
5. Không dùng chữ số La Mã I, II, III trong nội dung mục.
6. Không dùng markdown table, không dùng dấu **.
7. KHÔNG đưa `[Nguồn: ...]`, `Điểm: ...`, tên file, heading nguồn, ký tự lạ hoặc metadata nội bộ vào nội dung.
8. Trả về văn bản thuần, KHÔNG JSON, KHÔNG markdown fence.
9. Nếu cơ quan ban hành là cấp xã/huyện, chỉ viết nhiệm vụ triển khai, phối hợp, rà soát, kiểm tra, tổng hợp, báo cáo, đề xuất; không viết nội dung vượt thẩm quyền như ban hành chính sách cấp tỉnh/trung ương hoặc phê duyệt nội dung ngoài thẩm quyền.
10. Loại bỏ văn phong AI/chung chung; tránh các cụm mơ hồ nếu không gắn với hành động cụ thể.

QUY TẮC RIÊNG KHI VIẾT MỤC CỦA VĂN BẢN "KẾ HOẠCH":
- Kế hoạch dùng khung cố định theo mẫu: phần mở đầu/căn cứ; I. Mục đích, yêu cầu; II. Nội dung thực hiện; III. Kinh phí; IV. Tổ chức thực hiện.
- Không tự viết chữ số La Mã trong nội dung; Word exporter tự đánh mục lớn I, II, III, IV.
- Nếu mục nào không có dữ liệu liên quan thì trả về rỗng để mục đó không xuất hiện khi xuất Word.
- Văn phong phải là hành chính nhà nước, giọng chỉ đạo, điều hành, quyết liệt, cụ thể; sát thực tế triển khai tại UBND/Sở/ngành.
- Không viết kiểu lý thuyết, giáo trình; không giải thích khái niệm.
- Mỗi nhiệm vụ phải nêu rõ việc phải làm, thời hạn thực hiện, cơ quan chủ trì và cơ quan phối hợp nếu có thông tin.
- Không tự đặt thêm quý/tháng/ngày/năm nếu dữ liệu nguồn không nêu rõ. Nếu nguồn chỉ có mốc năm hoặc giai đoạn thì dùng đúng mốc đó; nếu không có mốc thời gian thì dùng "Nhiệm vụ thường xuyên".
- Ưu tiên các cụm hành chính phù hợp ngữ cảnh: "khẩn trương", "chủ động rà soát", "tăng cường", "tiếp tục triển khai", "bảo đảm hiệu quả", "Nhiệm vụ thường xuyên".
- Trong từng mục, dùng phân cấp: 1. -> - -> + khi có đủ dữ liệu; không tạo phân cấp rỗng.
"""


async def _write_sections(
    plan: dict,
    research_context: str,
    input_data: dict,
    template_outline: dict,
    doc_type: str,
    doc_type_label: str,
    trich_yeu: str,
    review_feedback: str = "",
    iteration: int = 1,
) -> list[dict]:
    """Write each planned section with a bounded, focused LLM call."""
    sections = plan.get("sections", [])
    if not sections:
        sections = [{
            "title": "Nội dung chính",
            "key_points": [input_data.get("noi_dung_chinh", "") or trich_yeu],
            "instructions": f"Viết nội dung {doc_type_label} theo yêu cầu",
        }]

    section_drafts = []
    evidence_summary = _extract_evidence_summary(research_context)

    for index, section in enumerate(sections, 1):
        title = section.get("title", f"Mục {index}")
        key_points = section.get("key_points", [])
        instructions = section.get("instructions", "")
        section_context = _extract_section_context(research_context, title)
        if evidence_summary and evidence_summary not in section_context:
            section_context = f"{evidence_summary}\n\n--- DỮ LIỆU THEO MỤC ---\n\n{section_context}"

        if not section_context.strip():
            section_context = "Không tìm thấy dữ liệu riêng cho mục này."

        template_prompt = ""
        if template_outline:
            template_prompt = f"""
ĐẦU MỤC MẪU CÙNG LOẠI:
{_format_template_outline_for_writer(template_outline)}
"""
        section_format_prompt = _get_ke_hoach_section_format_prompt(doc_type, title)

        user_prompt = f"""LOẠI VĂN BẢN: {doc_type_label}
TRÍCH YẾU: {trich_yeu}
{template_prompt}

MỤC CẦN VIẾT ({index}/{len(sections)}): {title}

Ý CHÍNH CẦN XỬ LÝ:
{_format_list(key_points)}

HƯỚNG DẪN TỪ PLANNER:
{instructions or "Viết đúng trọng tâm mục này."}
{section_format_prompt}

THÔNG TIN NGƯỜI DÙNG:
{_format_input_data(input_data)}

DỮ LIỆU RIÊNG CHO MỤC:
{section_context[:9000]}
"""

        if review_feedback:
            user_prompt += f"""

PHẢN HỒI REVIEWER TỪ LẦN TRƯỚC:
{review_feedback}

Hãy sửa riêng mục này nếu phản hồi có liên quan.
"""

        user_prompt += """

YÊU CẦU ĐẦU RA:
- Viết nội dung hoàn chỉnh cho riêng mục này.
- Nếu mục này không có dữ liệu liên quan trong kho và thông tin người dùng, trả về rỗng.
- Nếu có nhiều ý, đánh số từ 1., 2., 3. hoặc dùng gạch đầu dòng hợp lý.
- Không viết tiêu đề mục lớn bằng chữ số La Mã.
- Không chèn nguồn trích dẫn, tên file, điểm similarity, markdown hoặc ký tự thừa.
- Nội dung phải ngắn gọn, thực tế, đúng thẩm quyền cấp cơ quan ban hành.
- Không viết JSON."""

        try:
            content = await llm_service.chat(
                system_prompt=SECTION_WRITER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=30000,
            )
        except Exception as e:
            logger.error(f"[Writer] Section '{title}' failed: {e}")
            content = ""

        content = _clean_section_draft(content)
        if content:
            section_drafts.append({
                "index": index,
                "title": title,
                "content": content,
                "key_points": key_points,
                "instructions": instructions,
            })
            logger.info(
                f"[Writer] Section {index}/{len(sections)} '{title}': "
                f"{len(content)} chars"
            )
        else:
            logger.info(f"[Writer] Section {index}/{len(sections)} '{title}' skipped (empty)")

    return section_drafts


def _assemble_draft_data(doc_type: str, section_drafts: list[dict], input_data: dict) -> dict:
    """Map section drafts into the JSON fields expected by WordExporter."""
    if not section_drafts:
        fallback = input_data.get("noi_dung_chinh", "")
        return {"noi_dung": fallback} if fallback else {}

    if doc_type == "cong_van":
        de_nghi_sections = _select_sections(section_drafts, ["đề nghị", "kiến nghị", "kính đề nghị"])
        main_sections = [s for s in section_drafts if s not in de_nghi_sections]
        return {
            "noi_dung": _join_sections(main_sections or section_drafts),
            "de_nghi": _join_sections(de_nghi_sections, include_titles=False),
        }

    if doc_type == "thong_bao":
        return {"noi_dung": _join_sections(section_drafts)}

    if doc_type == "ke_hoach":
        phan_mo_dau = _select_sections(
            section_drafts,
            ["phần mở đầu", "mở đầu", "căn cứ", "bối cảnh", "yêu cầu thực tiễn"],
        )
        muc_dich = _select_sections(
            [s for s in section_drafts if s not in phan_mo_dau],
            ["mục đích", "yêu cầu", "mục tiêu"],
        )
        noi_dung = _select_sections(
            [s for s in section_drafts if s not in phan_mo_dau and s not in muc_dich],
            ["nội dung thực hiện", "nội dung", "nhiệm vụ", "giải pháp", "triển khai", "tập huấn"],
        )
        kinh_phi = _select_sections(
            [s for s in section_drafts if s not in phan_mo_dau and s not in muc_dich and s not in noi_dung],
            ["kinh phí", "nguồn kinh phí", "thanh quyết toán"],
        )
        to_chuc = _select_sections(
            [s for s in section_drafts if s not in phan_mo_dau and s not in muc_dich and s not in noi_dung and s not in kinh_phi],
            ["tổ chức", "phân công", "thực hiện", "trách nhiệm", "báo cáo", "đôn đốc"],
        )
        phu_luc = _select_sections(section_drafts, ["phụ lục", "danh mục nhiệm vụ"])

        used = set(id(s) for s in phan_mo_dau + muc_dich + noi_dung + kinh_phi + to_chuc + phu_luc)
        remaining = [s for s in section_drafts if id(s) not in used]
        if remaining:
            noi_dung.extend(remaining)

        legacy_muc_dich = _join_sections(muc_dich)
        legacy_noi_dung = _join_sections(noi_dung or section_drafts)
        return {
            "custom_sections": [
                {"title": s.get("title", ""), "content": s.get("content", "")}
                for s in section_drafts
                if s.get("content") and "phần mở đầu" not in str(s.get("title", "")).lower()
            ],
            "phan_mo_dau": _join_sections(phan_mo_dau, include_titles=False),
            "muc_dich_yeu_cau": legacy_muc_dich,
            "noi_dung_thuc_hien": legacy_noi_dung,
            "kinh_phi": _join_sections(kinh_phi),
            "to_chuc_thuc_hien": _join_sections(to_chuc),
            "phu_luc_nhiem_vu": _join_sections(phu_luc, include_titles=False),
            # Backward-compatible fields for older exporters/clients.
            "noi_dung_ke_hoach": legacy_noi_dung,
        }

    if doc_type == "bao_cao":
        tinh_hinh = _select_sections(section_drafts, ["tình hình", "bối cảnh", "khái quát", "chung"])
        ket_qua = _select_sections(section_drafts, ["kết quả", "đạt được", "thực hiện"])
        han_che = _select_sections(section_drafts, ["hạn chế", "tồn tại", "khó khăn", "vướng mắc"])
        phuong_huong = _select_sections(section_drafts, ["phương hướng", "giải pháp", "kiến nghị", "đề xuất", "nhiệm vụ"])
        used = set(id(s) for s in tinh_hinh + ket_qua + han_che + phuong_huong)
        remaining = [s for s in section_drafts if id(s) not in used]
        if remaining:
            ket_qua.extend(remaining)
        return {
            "tinh_hinh_chung": _join_sections(tinh_hinh or section_drafts[:1]),
            "ket_qua": _join_sections(ket_qua),
            "han_che": _join_sections(han_che),
            "phuong_huong": _join_sections(phuong_huong),
        }

    if doc_type == "to_trinh":
        su_can_thiet = _select_sections(section_drafts, ["cần thiết", "lý do", "cơ sở", "thực tiễn", "pháp lý"])
        de_xuat = _select_sections(section_drafts, ["nội dung", "đề xuất", "phương án"])
        kien_nghi = _select_sections(section_drafts, ["kiến nghị", "đề nghị", "trình"])
        used = set(id(s) for s in su_can_thiet + de_xuat + kien_nghi)
        remaining = [s for s in section_drafts if id(s) not in used]
        if remaining:
            de_xuat.extend(remaining)
        return {
            "su_can_thiet": _join_sections(su_can_thiet or section_drafts[:1]),
            "noi_dung_de_xuat": _join_sections(de_xuat),
            "kien_nghi": _join_sections(kien_nghi),
        }

    if doc_type == "quyet_dinh":
        can_cu_sections = _select_sections(section_drafts, ["căn cứ", "cơ sở pháp lý", "pháp lý"])
        body_sections = [s for s in section_drafts if s not in can_cu_sections]
        can_cu = _build_can_cu_list(input_data, can_cu_sections)
        dieu_khoan = []
        for idx, section in enumerate(body_sections or section_drafts, 1):
            dieu_khoan.append({
                "so_dieu": f"Điều {idx}",
                "noi_dung": _with_title(section),
            })
        if not any("hiệu lực" in d.get("noi_dung", "").lower() for d in dieu_khoan):
            dieu_khoan.append({
                "so_dieu": f"Điều {len(dieu_khoan) + 1}",
                "noi_dung": "Quyết định này có hiệu lực kể từ ngày ký./.",
            })
        return {"can_cu": can_cu, "dieu_khoan": dieu_khoan}

    return {"noi_dung": _join_sections(section_drafts)}


def _format_plan(plan: dict) -> str:
    """Format plan dict into readable text for the Writer prompt."""
    sections = plan.get("sections", [])
    if not sections:
        return "Không có dàn ý"

    parts = []
    for i, section in enumerate(sections, 1):
        title = section.get("title", f"Mục {i}")
        key_points = section.get("key_points", [])
        instructions = section.get("instructions", "")

        part = f"{i}. {title}"
        if key_points:
            for j, kp in enumerate(key_points, 1):
                part += f"\n   {j}. {kp}"
        if instructions:
            part += f"\n   → Hướng dẫn: {instructions}"
        parts.append(part)

    return "\n\n".join(parts)


def _format_input_data(input_data: dict) -> str:
    """Format user input data for the prompt."""
    lines = []
    skip_keys = {"trich_yeu", "noi_dung_chinh", "_raw_response", "document_type"}
    for key, value in input_data.items():
        if key in skip_keys or not value:
            continue
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) if lines else ""


def _format_template_outline_for_writer(template_outline: dict) -> str:
    if not template_outline:
        return "Không có mẫu cùng loại; dùng dàn ý Planner."

    lines = []
    source = template_outline.get("source_filename", "")
    if source:
        lines.append(f"Nguồn mẫu: {source}")
    notes = template_outline.get("sample_notes", "")
    if notes:
        lines.append(f"Ghi chú mẫu: {notes}")
    headings = template_outline.get("headings", [])
    for heading in headings[:40]:
        level = heading.get("level", 1)
        marker = heading.get("marker", "")
        title = heading.get("title", "")
        indent = "  " * max(int(level or 1) - 1, 0)
        marker_text = f"{marker}. " if marker else ""
        lines.append(f"{indent}- level {level}: {marker_text}{title}")
    return "\n".join(lines) if lines else "Không có mẫu cùng loại; dùng dàn ý Planner."


def _format_list(items: list) -> str:
    if not items:
        return "- Không có ý chính riêng."
    return "\n".join(f"- {item}" for item in items if item)


def _extract_evidence_summary(research_context: str) -> str:
    marker = "--- CHI TIẾT NGUỒN TRÍCH DẪN ---"
    if marker in research_context:
        return research_context.split(marker, 1)[0].strip()
    return ""


def _extract_section_context(research_context: str, title: str) -> str:
    """Extract the context block matching a section title from Researcher output."""
    if not research_context:
        return ""

    detail = research_context
    has_sectioned_context = False
    marker = "--- CHI TIẾT NGUỒN TRÍCH DẪN ---"
    if marker in detail:
        detail = detail.split(marker, 1)[1]
        has_sectioned_context = True

    pattern = re.compile(rf"###\s+{re.escape(title)}\s*(.*?)(?=\n\n---\n\n###|\n###\s+QUAN HỆ TRI THỨC|\Z)", re.DOTALL)
    match = pattern.search(detail)
    if match:
        return match.group(0).strip()

    if has_sectioned_context:
        return ""

    # Fallback: return a bounded slice of full context so the section can still be written.
    return detail[:6000]


def _get_ke_hoach_section_format_prompt(doc_type: str, title: str) -> str:
    if doc_type != "ke_hoach":
        return ""

    normalized = (title or "").strip().lower()
    if "mục đích" in normalized or "yêu cầu" in normalized:
        return """

YÊU CẦU ĐỊNH DẠNG RIÊNG CHO MỤC NÀY:
- Bắt buộc trình bày đúng hai tiểu mục:
  1. Mục đích: ...
  2. Yêu cầu: ...
- Không viết riêng dòng "Mục đích" hoặc "Yêu cầu" nếu không có số thứ tự.
"""

    if "nội dung" in normalized:
        return """

YÊU CẦU ĐỊNH DẠNG RIÊNG CHO MỤC NÀY:
- Mỗi nhiệm vụ phải là một mục đánh số 1., 2., 3....
- Tên nhiệm vụ phải cụ thể, không đặt tên chung là "Nội dung".
- Mỗi nhiệm vụ bắt buộc nêu rõ các ý sau bằng gạch đầu dòng:
  - Nội dung:
  - Cơ quan chủ trì:
  - Cơ quan phối hợp:
  - Thời gian thực hiện:
- Nếu dữ liệu không nêu rõ cơ quan phối hợp hoặc thời gian, ghi nội dung hành chính phù hợp như "Các cơ quan, đơn vị liên quan" hoặc "Thường xuyên trong năm thực hiện"; không bỏ trống các ý này.
"""

    if "phụ lục" in normalized or "danh mục" in normalized:
        return """

YÊU CẦU ĐỊNH DẠNG RIÊNG CHO PHỤ LỤC:
- Liệt kê đầy đủ các nhiệm vụ cơ quan ban hành cần chủ trì hoặc tổ chức thực hiện theo đúng thẩm quyền nêu trong yêu cầu người dùng.
- Mỗi nhiệm vụ viết một dòng, dùng dấu chấm phẩy để tách trường theo đúng mẫu:
  STT: 1; Nội dung nhiệm vụ: ...; Văn bản giao nhiệm vụ: ...; Thời hạn hoàn thành: ...; Cơ quan chủ trì: ...; Cơ quan phối hợp: ...
- Không bỏ nhiệm vụ chỉ vì thiếu một trường; nếu thiếu văn bản giao nhiệm vụ thì ghi theo văn bản/kế hoạch đang triển khai.
"""

    return ""


def _clean_section_draft(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:\w+)?\s*", "", text).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\s*\[Nguồn:[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\[\s*Điểm\s*:[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\|\s*Điểm\s*:\s*[0-9.]+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?im)^\s*(?:I|II|III|IV|V|VI)\.\s+", "", text).strip()
    blocked = re.compile(
        r"không\s+có\s+thông\s+tin|"
        r"không\s+tìm\s+thấy\s+dữ\s+liệu|"
        r"dữ\s+liệu\s+không\s+đề\s+cập|"
        r"chưa\s+rõ\s+thông\s+tin|"
        r"không\s+đủ\s+thông\s+tin|"
        r"tôi\s+không\s+thể",
        re.IGNORECASE,
    )
    lines = [line for line in text.splitlines() if not blocked.search(line)]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _select_sections(section_drafts: list[dict], keywords: list[str]) -> list[dict]:
    selected = []
    lowered_keywords = [k.lower() for k in keywords]
    for section in section_drafts:
        title = section.get("title", "").lower()
        if any(keyword in title for keyword in lowered_keywords):
            selected.append(section)
    return selected


def _is_legal_basis_section(section: dict) -> bool:
    title = section.get("title", "").lower()
    content = section.get("content", "").lower()
    legal_keywords = ["cơ sở pháp lý", "căn cứ pháp lý", "căn cứ", "pháp lý"]
    return any(keyword in title for keyword in legal_keywords) or (
        title.strip() == "cơ sở" and "căn cứ" in content
    )


def _join_sections(sections: list[dict], include_titles: bool = True) -> str:
    parts = []
    for idx, section in enumerate(sections, 1):
        content = section.get("content", "").strip()
        if not content:
            continue
        if include_titles:
            parts.append(_with_title(section, idx))
        else:
            parts.append(content)
    return "\n".join(parts).strip()


def _with_title(section: dict, index: int | None = None) -> str:
    title = section.get("title", "").strip()
    content = section.get("content", "").strip()
    if not title:
        return content
    if re.match(r"^\d+[\.\)]\s", content):
        return content
    prefix = f"{index}. " if index else ""
    return f"{prefix}{title}: {content}"


def _build_can_cu_list(input_data: dict, can_cu_sections: list[dict]) -> list[str]:
    raw = input_data.get("can_cu", "")
    can_cu = []
    if isinstance(raw, list):
        can_cu.extend(str(item).strip() for item in raw if str(item).strip())
    elif raw:
        can_cu.extend(line.strip(" ;") for line in str(raw).split("\n") if line.strip())

    for section in can_cu_sections:
        for line in section.get("content", "").split("\n"):
            cleaned = line.strip(" -+;")
            if cleaned and len(cleaned) > 10:
                can_cu.append(cleaned)

    if not can_cu:
        can_cu.append("các văn bản pháp luật hiện hành có liên quan;")

    # Word exporter prepends "Căn cứ", so avoid duplicate leading words.
    normalized = []
    seen = set()
    for item in can_cu:
        item = re.sub(r"(?i)^căn cứ\s+", "", item).strip()
        if not item.endswith(";"):
            item += ";"
        key = item.lower()
        if key not in seen:
            seen.add(key)
            normalized.append(item)
    return normalized


def _get_output_format(doc_type: str) -> str:
    """Get the required JSON output format for a document type."""
    formats = {
        "cong_van": """\
Trả về JSON:
{"noi_dung": "Nội dung công văn với đánh số mục", "de_nghi": "Phần đề nghị cuối (nếu có)"}""",

        "quyet_dinh": """\
Trả về JSON:
{"can_cu": ["Căn cứ 1;", "Căn cứ 2;"], "dieu_khoan": [{"so_dieu": "Điều 1", "noi_dung": "Nội dung"}]}""",

        "ke_hoach": """\
Trả về JSON (KHÔNG tự viết số La Mã trong nội dung field):
{
    "phan_mo_dau": "Căn cứ ban hành và câu dẫn vào kế hoạch",
    "muc_dich_yeu_cau": "Nội dung mục I, bắt buộc tách 1. Mục đích và 2. Yêu cầu",
    "noi_dung_thuc_hien": "Nội dung mục II, mỗi nhiệm vụ có tên nhiệm vụ, nội dung, cơ quan chủ trì, cơ quan phối hợp và thời gian thực hiện",
    "kinh_phi": "Nội dung mục III, nguồn kinh phí và yêu cầu quản lý, thanh quyết toán nếu có",
    "to_chuc_thuc_hien": "Nội dung mục IV, phân công trách nhiệm, chế độ báo cáo, theo dõi, đôn đốc, kiểm tra",
    "phu_luc_nhiem_vu": "Nếu phù hợp: danh mục nhiệm vụ theo các cột STT, Nội dung, Văn bản giao nhiệm vụ, Thời hạn, Chủ trì, Phối hợp"
}""",

        "thong_bao": """\
Trả về JSON:
{"noi_dung": "Nội dung thông báo với đánh số mục"}""",

        "to_trinh": """\
Trả về JSON:
{"su_can_thiet": "Lý do, cơ sở", "noi_dung_de_xuat": "Chi tiết đề xuất", "kien_nghi": "Kiến nghị"}""",

        "bao_cao": """\
Trả về JSON:
{"tinh_hinh_chung": "Tình hình", "ket_qua": "Kết quả đạt được", "han_che": "Tồn tại", "phuong_huong": "Giải pháp đề xuất"}""",
    }

    return formats.get(doc_type, """\
Trả về JSON:
{"noi_dung": "Nội dung văn bản với đánh số mục"}""")


def _parse_writer_output(raw: str) -> dict:
    """Parse Writer's JSON output, with fallback."""
    import re

    text = raw.strip()

    # Remove markdown wrapping
    if text.startswith("```"):
        match = re.search(r'```(?:json)?\s*\n(.*?)\n\s*```', text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    # Try direct JSON parse
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Find first JSON object
    match = re.search(r'\{[\s\S]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback
    return {"noi_dung": raw}
