"""Tổng hợp ý kiến góp ý thành Bảng tổng hợp tiếp thu/giải trình theo mẫu.

Luồng:
- Lấy phần đầu thể thức (cơ quan ban hành, địa danh, tên dự thảo) từ BẢN DỰ THẢO
  làm cơ sở cho metadata.
- Sinh phần MỞ ĐẦU (căn cứ + thống kê đơn vị góp ý/thống nhất) và BẢNG 4 cột từ
  các VĂN BẢN GÓP Ý.
- Dùng LLM tự lưu trữ (``llm_service``) sinh ra JSON đúng schema mẫu
  ``AI/sample_doc/mau_bang_tong_hop.json``. BE nhận JSON này để render .docx.
"""

from __future__ import annotations

import json
import logging
import re

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# Giới hạn ký tự để tránh vượt context window.
_MAX_CHARS_PER_FEEDBACK = 8000
# Phần metadata thể thức nằm ở đầu dự thảo -> chỉ cần vài nghìn ký tự đầu.
_MAX_CHARS_PER_DRAFT = 4000

# Các loại phản hồi cho phép ở cột "Nội dung tiếp thu, giải trình".
_RESPONSE_TYPES = [
    "Tiếp thu điều chỉnh",
    "Tiếp thu, bổ sung vào dự thảo",
    "Tiếp thu, thực hiện bổ sung",
    "Tiếp thu (thực hiện khi đủ điều kiện)",
    "Đề xuất giữ nguyên theo dự thảo (kèm Lý do giải trình)",
]

# Khung JSON bắt buộc model phải bám theo.
_SKELETON = {
    "metadata": {
        "co_quan_chu_quan": "",
        "co_quan_ban_hanh": "",
        "dia_danh": "",
        "ngay_ban_hanh": "",
        "ten_du_thao": "",
    },
    "mo_dau": {
        "can_cu": "",
        "don_vi_thong_nhat": [
            {"ten": "", "so_cong_van": "", "ngay": ""}
        ],
        "so_don_vi_co_y_kien": 0,
    },
    "sections": [
        {
            "tieu_de": "1. Đối với dự thảo Quyết định",
            "rows": [
                {
                    "nhom_van_de": "",
                    "chu_the_gop_y": "",
                    "noi_dung_gop_y": "",
                    "noi_dung_tiep_thu_giai_trinh": "",
                }
            ],
        },
        {"tieu_de": "2. Đối với dự thảo Quy chế", "rows": []},
    ],
}

_SYSTEM_PROMPT = (
    "Bạn là chuyên viên hành chính tổng hợp ý kiến góp ý dự thảo văn bản quy phạm "
    "pháp luật của cơ quan nhà nước. Chỉ dựa vào nội dung được cung cấp, TUYỆT ĐỐI "
    "không bịa thông tin; thông tin không có thì để chuỗi rỗng hoặc số 0. Trả lời "
    "DUY NHẤT bằng một object JSON hợp lệ đúng schema yêu cầu, KHÔNG kèm giải thích, "
    "KHÔNG dùng rào ```; không suy nghĩ thành tiếng, không dùng thẻ <think>. /no_think"
)

# Ví dụ few-shot ngắn để model học cách phân loại section + xưng chủ thể.
_FEWSHOT = """\
VÍ DỤ PHÂN LOẠI (chỉ để tham khảo cách xếp section, KHÔNG sao chép nội dung):
- "Đề nghị trình bày bố cục dự thảo theo mẫu Quyết định; sửa phần Nơi nhận; căn cứ
  ban hành" -> section 1 (Đối với dự thảo Quyết định).
- "Đề nghị sửa điểm a khoản 2 Điều 1 Quy chế; bổ sung lĩnh vực phản ánh tại khoản 6
  Điều 5; nêu rõ thời gian tại Điều 8" -> section 2 (Đối với dự thảo Quy chế)."""

_USER_PROMPT_TEMPLATE = """\
Hãy tạo BẢNG TỔNG HỢP TIẾP THU, GIẢI TRÌNH Ý KIẾN GÓP Ý ở dạng JSON, ĐÚNG theo schema.

SCHEMA (khung bắt buộc — điền dữ liệu vào, thêm nhiều dòng vào "rows" nếu cần):
{skeleton}

QUY TẮC CHUNG:
- Phần "metadata" LẤY TỪ BẢN DỰ THẢO ở mục A. Nếu dự thảo không nêu rõ thì để rỗng.
  + "co_quan_ban_hanh" là CƠ QUAN CHỦ TRÌ SOẠN THẢO dự thảo (thường là Sở/ban/ngành,
    ví dụ "Sở Khoa học và Công nghệ") — chính là đơn vị ban hành BẢNG TỔNG HỢP này.
  + "co_quan_chu_quan" là cơ quan cấp trên quản lý (thường "ỦY BAN NHÂN DÂN TỈNH ...").
  + LƯU Ý: dù dự thảo là Quyết định do UBND tỉnh ban hành, bảng tổng hợp vẫn do cơ
    quan chủ trì soạn thảo (Sở/ngành) ban hành — KHÔNG hoán đổi hai trường này.
- "chu_the_gop_y" là TÊN ĐƠN VỊ góp ý (ví dụ: "Sở Tư pháp", "UBND xã Bình Thành"),
  lấy từ tiêu đề/nội dung mỗi văn bản góp ý ở mục B.

QUY TẮC PHẦN "mo_dau":
- "can_cu": viết đúng câu: "Căn cứ Luật Ban hành văn bản quy phạm pháp luật, cơ quan
  chủ trì soạn thảo đã tổ chức lấy ý kiến đối với dự thảo <tên dự thảo>. Kết quả:".
- "don_vi_thong_nhat": liệt kê các đơn vị trong mục B mà THỐNG NHẤT HOÀN TOÀN với dự
  thảo (KHÔNG đề nghị sửa/bổ sung gì). Lấy tên cơ quan + số công văn + ngày từ chính
  văn bản đó. Đơn vị nào có ý kiến chỉnh sửa thì KHÔNG đưa vào đây (đưa vào bảng).
  Nếu không có đơn vị nào thống nhất hoàn toàn thì để mảng rỗng [].
- "so_don_vi_co_y_kien": số ĐƠN VỊ khác nhau có ý kiến góp ý cụ thể (xuất hiện trong bảng).

QUY TẮC PHÂN LOẠI SECTION (RẤT QUAN TRỌNG):
- section 1 "Đối với dự thảo Quyết định": ý kiến về THỂ THỨC bản Quyết định — bố cục,
  trình bày, căn cứ ban hành, phần "Nơi nhận", hiệu lực, và các Điều thuộc bản Quyết
  định (thường Điều 1, 2, 3 của Quyết định). Từ khóa: bố cục, căn cứ ban hành, nơi
  nhận, thể thức, mẫu Quyết định, hiệu lực.
- section 2 "Đối với dự thảo Quy chế": ý kiến về NỘI DUNG Quy chế đính kèm — các
  Điều/khoản nghiệp vụ (Điều 4, 5, 6, 7, 8, 9, 10, 12-15...), nội dung tiếp nhận, xử
  lý, phản ánh, kiến nghị, đối tượng áp dụng, giải thích từ ngữ.
- Nếu góp ý nêu rõ "Điều/khoản của Quy chế" hoặc nội dung nghiệp vụ -> LUÔN xếp
  section 2. Chỉ xếp section 1 khi nói về thể thức/bố cục/căn cứ/nơi nhận/hiệu lực
  của bản Quyết định. Nếu chỉ có một loại thì để section còn lại "rows" rỗng.
{fewshot}

QUY TẮC BẢNG:
- Mỗi ý kiến là một object trong "rows" đúng 4 trường: nhom_van_de (điều/khoản/vấn đề),
  chu_the_gop_y, noi_dung_gop_y (tóm tắt, giữ nguyên ý, không bịa), noi_dung_tiep_thu_giai_trinh.
- Gộp các ý kiến trùng/tương tự thành một dòng, ghi rõ các đơn vị cùng nêu.
- "noi_dung_tiep_thu_giai_trinh" chỉ dùng một trong các loại: {response_types}.
  Ý kiến đúng thể thức/pháp lý -> "Tiếp thu điều chỉnh" / "Tiếp thu, bổ sung vào dự
  thảo"; ý kiến đã được quy định trong dự thảo -> "Đề xuất giữ nguyên theo dự thảo"
  kèm lý do ngắn gọn.
- Chỉ xuất JSON, không thêm bất kỳ chữ nào khác.

===== A. BẢN DỰ THẢO (căn cứ lấy metadata) =====
{drafts}

===== B. CÁC VĂN BẢN GÓP Ý (nội dung điền vào bảng) =====
{feedback}
"""


def _extract_json(text: str) -> dict:
    """Cắt <think>, rào ```json và lấy object JSON từ phản hồi model."""
    text = text.strip()
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1].strip()
    elif "<think>" in text:
        raise ValueError("Model trả về phần suy luận nhưng không có kết quả")
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]
    return json.loads(text)


def _blocks(documents: list[dict], limit: int, label: str) -> list[str]:
    blocks: list[str] = []
    for index, doc in enumerate(documents, start=1):
        content = (doc.get("markdown_content") or "").strip()
        if not content:
            continue
        if len(content) > limit:
            content = content[:limit] + "\n...(đã lược bớt)"
        filename = doc.get("filename") or f"{label} {index}"
        blocks.append(f"### {label} {index}: {filename}\n{content}")
    return blocks


class SummaryService:
    async def consolidate_feedback(
        self,
        feedback_documents: list[dict],
        draft_documents: list[dict] | None = None,
    ) -> dict:
        """Sinh bảng tổng hợp (dict theo schema mẫu) từ dự thảo + văn bản góp ý.

        ``feedback_documents`` / ``draft_documents``: list dict có ``filename`` và
        ``markdown_content``. Trả về dict ``{"metadata", "mo_dau", "sections"}``.
        """
        feedback_blocks = _blocks(
            feedback_documents, _MAX_CHARS_PER_FEEDBACK, "Văn bản góp ý"
        )
        if not feedback_blocks:
            raise ValueError("Không có nội dung góp ý để tổng hợp")

        draft_blocks = _blocks(
            draft_documents or [], _MAX_CHARS_PER_DRAFT, "Bản dự thảo"
        )
        drafts_text = (
            "\n\n".join(draft_blocks)
            if draft_blocks
            else "(Không có bản dự thảo — để trống phần metadata cần lấy từ dự thảo.)"
        )

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            skeleton=json.dumps(_SKELETON, ensure_ascii=False, indent=2),
            response_types=json.dumps(_RESPONSE_TYPES, ensure_ascii=False),
            fewshot=_FEWSHOT,
            drafts=drafts_text,
            feedback="\n\n".join(feedback_blocks),
        )
        logger.info(
            "Consolidating %d feedback doc(s) with %d draft doc(s)",
            len(feedback_blocks),
            len(draft_blocks),
        )
        raw = await llm_service.chat(
            _SYSTEM_PROMPT, user_prompt, temperature=0.1, max_tokens=8192
        )
        try:
            result = _extract_json(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Không parse được JSON từ model: %s", exc)
            raise ValueError(
                "Model không trả về bảng tổng hợp hợp lệ. Vui lòng thử lại."
            ) from exc

        sections = result.get("sections")
        if not isinstance(sections, list) or not any(
            section.get("rows") for section in sections
        ):
            raise ValueError("Bảng tổng hợp không có nội dung góp ý nào")

        result.setdefault("metadata", {})
        result.setdefault("mo_dau", {})
        return result


summary_service = SummaryService()
