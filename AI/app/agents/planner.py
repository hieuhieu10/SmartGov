"""
Planner Agent — Analyze user request and create a structured outline.

Responsibilities:
  - Parse the document type and user requirements
  - Create a section-by-section outline
  - Generate specific search queries for each section
  - Identify key points that need supporting data
"""

import json
import logging

from app.services.llm_service import llm_service
from app.agents.prompt_policy import (
    ADMIN_DRAFTING_PROCESS_RULES,
    ADMIN_DRAFTING_ROLE_PROMPT,
    CHATBOT_PROHIBITIONS,
)

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = f"""{ADMIN_DRAFTING_ROLE_PROMPT}

Bạn đang làm bước phân tích yêu cầu và lập khung văn bản trước khi soạn thảo.

{ADMIN_DRAFTING_PROCESS_RULES}

{CHATBOT_PROHIBITIONS}

NHIỆM VỤ: Phân tích yêu cầu và tạo DÀN Ý CHI TIẾT cùng các CÂU TRUY VẤN để tìm kiếm bằng chứng trong kho dữ liệu.

TRẢ VỀ JSON:
{{
    "summary": "Tóm tắt mục tiêu văn bản",
    "sections": [
        {{
            "title": "Tên mục (VD: Tình hình kết quả thực hiện)",
            "key_points": ["Điểm chính cần làm rõ (VD: Con số tăng trưởng)", "Điểm chính 2"],
            "search_queries": [
                "Câu truy vấn tìm số liệu cụ thể...",
                "Câu truy vấn tìm căn cứ pháp lý liên quan...",
                "Câu truy vấn tìm các tồn tại, hạn chế..."
            ],
            "instructions": "Hướng dẫn cho Writer: Cần nhấn mạnh bằng chứng nào?"
        }}
    ],
    "tone": "Văn phong (Hành chính / Báo cáo / Kế hoạch)",
    "total_sections": 5
}}

QUY TẮC CHIẾN LƯỢC:
1. **KHÔNG sử dụng chữ số La Mã**: Tuyệt đối không viết I, II, III... vào `title`. Hệ thống sẽ tự động thêm các số này khi xuất bản. Chỉ viết tên mục (VD: "Cơ sở pháp lý" thay vì "I. Cơ sở pháp lý").
2. **Tư duy dựa trên bằng chứng**: Với mỗi mục, hãy đặt câu hỏi: "Cần những con số hay sự thật nào để mục này thuyết phục?". Tạo `search_queries` để trả lời các câu hỏi đó.
3. **Tối ưu hóa truy vấn**: Mỗi mục tạo TỐI ĐA 2 câu truy vấn cốt lõi nhất (1 câu về số liệu/thực trạng, 1 câu về căn cứ pháp lý/hướng dẫn). Không tạo quá nhiều truy vấn thừa.
4. **Cấu trúc Nghị định 30**: Dàn ý phải tuân thủ logic của văn bản hành chính Việt Nam (Đặt vấn đề -> Giải quyết vấn đề -> Kết luận/Kiến nghị).
5. **Sát thực tế**: Tránh các câu truy vấn chung chung như "tìm thông tin". Hãy dùng "báo cáo kết quả năm 2023 về...", "quy định về mức chi...".
6. **Đúng cấp hành chính và thẩm quyền**: Dàn ý phải phù hợp cơ quan ban hành. Cấp xã/huyện chỉ dùng các động từ như triển khai, phối hợp, rà soát, tuyên truyền, tổng hợp, báo cáo, đề xuất; không dùng các nội dung vượt thẩm quyền như ban hành chính sách cấp tỉnh/trung ương, phê duyệt quy hoạch, phân bổ ngân sách vượt cấp.
7. **Văn phong thực tế**: Ưu tiên các mục ngắn, rõ, có thể thực hiện ở cấp xã/huyện; tránh các mục chung chung, khẩu hiệu, hoặc văn phong giống AI.

QUY TẮC RIÊNG KHI LOẠI VĂN BẢN LÀ "KẾ HOẠCH":
- Kế hoạch dùng dàn ý cố định theo mẫu: phần mở đầu/căn cứ; Mục đích, yêu cầu; Nội dung thực hiện; Kinh phí; Tổ chức thực hiện.
- Các `title` KHÔNG ghi số La Mã; hệ thống xuất Word sẽ tự đánh mục lớn bằng chữ La Mã.
- Chỉ lập `search_queries` dựa trên "YÊU CẦU NỘI DUNG" người dùng nhập và thông tin bổ sung.
- Nếu một phần không có dữ liệu liên quan từ kho hoặc thông tin người dùng, Writer phải để rỗng để không xuất hiện trong Word.
"""


async def planner_node(state: dict) -> dict:
    """
    Planner Agent: analyze request and create outline.

    Input state: user_request, doc_type, doc_type_label, input_data, trich_yeu
    Output state: plan
    """
    doc_type_label = state.get("doc_type_label", "Văn bản")
    doc_type = state.get("doc_type", "")
    trich_yeu = state.get("trich_yeu", "")
    user_request = state.get("user_request", "")
    input_data = state.get("input_data", {})

    if doc_type == "ke_hoach":
        result = _build_fixed_ke_hoach_plan(user_request, trich_yeu, input_data)
        logger.info("[Planner] Created fixed ke_hoach plan: %d sections", len(result["sections"]))
        return {"plan": result}

    template_outline = state.get("template_outline", {})
    template_text = _format_template_outline(template_outline)

    # Build user prompt
    user_prompt = f"""LOẠI VĂN BẢN: {doc_type_label}
TRÍCH YẾU: {trich_yeu}
YÊU CẦU NỘI DUNG: {user_request}

ĐẦU MỤC MẪU CÙNG LOẠI TRÍCH XUẤT TỪ DỮ LIỆU:
{template_text}

THÔNG TIN BỔ SUNG TỪ NGƯỜI DÙNG:
{json.dumps(input_data, ensure_ascii=False, indent=2)}

Hãy tạo dàn ý chi tiết cho văn bản {doc_type_label} này.
Nếu có đầu mục mẫu cùng loại, bước 1 dùng mẫu làm khung; bước 2 dựa vào yêu cầu nội dung chính của người dùng để lập các nội dung cần tìm từ dữ liệu qua `search_queries`."""

    try:
        result = await llm_service.chat_json(
            system_prompt=PLANNER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=2048,
        )

        if not result or "sections" not in result:
            # Fallback: create a basic plan
            result = {
                "summary": trich_yeu or user_request,
                "sections": [
                    {
                        "title": "Nội dung chính",
                        "key_points": [user_request],
                        "search_queries": [trich_yeu, user_request],
                        "instructions": f"Viết nội dung {doc_type_label} theo yêu cầu",
                    }
                ],
                "tone": "hành chính trang trọng",
                "total_sections": 1,
            }

        logger.info(
            f"[Planner] Created plan: {len(result.get('sections', []))} sections, "
            f"summary='{result.get('summary', '')[:60]}...'"
        )

        return {"plan": result}

    except Exception as e:
        logger.error(f"[Planner] Failed: {e}")
        return {
            "plan": {
                "summary": trich_yeu,
                "sections": [{
                    "title": "Nội dung",
                    "key_points": [user_request],
                    "search_queries": [trich_yeu, user_request],
                    "instructions": "Viết nội dung theo yêu cầu",
                }],
                "tone": "hành chính trang trọng",
                "total_sections": 1,
            },
            "error": f"Planner error: {str(e)}",
        }


def _build_fixed_ke_hoach_plan(user_request: str, trich_yeu: str, input_data: dict) -> dict:
    issuing_agency = str(input_data.get("co_quan_ban_hanh") or "cơ quan ban hành").strip()
    base_query = " ".join(
        str(value).strip()
        for value in [user_request, trich_yeu, input_data.get("can_cu", ""), input_data.get("thoi_gian_thuc_hien", "")]
        if value
    )
    sections = [
        (
            "Phần mở đầu",
            [
                "Nêu các văn bản, chỉ đạo, yêu cầu thực tiễn làm căn cứ xây dựng kế hoạch.",
                "Viết câu dẫn: cơ quan ban hành xây dựng kế hoạch ..., cụ thể như sau.",
            ],
            ["căn cứ pháp lý nghị quyết nghị định quyết định công văn chỉ đạo " + base_query],
        ),
        (
            "Mục đích, yêu cầu",
            [
                "Bắt buộc tách rõ tiểu mục 1. Mục đích và 2. Yêu cầu.",
                "Nêu mục tiêu, ý nghĩa, kết quả cần đạt; yêu cầu về tiến độ, chất lượng, tiết kiệm, hiệu quả và phối hợp thực hiện.",
            ],
            ["mục tiêu yêu cầu kết quả cần đạt tiến độ chất lượng phối hợp " + base_query],
        ),
        (
            "Nội dung thực hiện",
            [
                "Nêu từng nhiệm vụ, hoạt động triển khai; mỗi nhiệm vụ bắt buộc có tên nhiệm vụ, nội dung, cơ quan chủ trì, cơ quan phối hợp và thời gian thực hiện.",
                "Nêu giải pháp, yêu cầu đầu ra và cách triển khai của từng nhiệm vụ.",
            ],
            ["nhiệm vụ công việc giải pháp hoạt động triển khai yêu cầu đầu ra " + base_query],
        ),
        (
            "Kinh phí",
            [
                "Nêu nguồn kinh phí thực hiện kế hoạch.",
                "Nêu đơn vị bảo đảm, quản lý, thanh quyết toán kinh phí nếu có dữ liệu.",
            ],
            ["kinh phí nguồn kinh phí nội dung chi đơn vị bảo đảm kinh phí " + base_query],
        ),
        (
            "Tổ chức thực hiện",
            [
                "Phân công rõ trách nhiệm từng phòng ban, đơn vị, cá nhân; nêu đơn vị chủ trì, phối hợp nếu có dữ liệu.",
                "Nêu cách thức triển khai, chế độ báo cáo, kiểm tra, giám sát và xử lý khó khăn, vướng mắc.",
                "Kết thúc bằng câu giao các cơ quan, đơn vị căn cứ kế hoạch triển khai thực hiện.",
            ],
            ["tổ chức thực hiện phân công trách nhiệm chế độ báo cáo kiểm tra giám sát khó khăn vướng mắc " + base_query],
        ),
    ]
    if any(keyword in base_query.lower() for keyword in ("phụ lục", "liệt kê đầy đủ", "danh mục nhiệm vụ")):
        sections.append(
            (
                "Phụ lục nhiệm vụ",
                [
                    f"Lập danh mục đầy đủ các nhiệm vụ {issuing_agency} cần chủ trì hoặc tổ chức thực hiện theo đúng thẩm quyền.",
                    "Mỗi dòng nhiệm vụ phải có STT, nội dung nhiệm vụ, văn bản giao nhiệm vụ nếu có, thời hạn hoàn thành, cơ quan chủ trì và cơ quan phối hợp.",
                ],
                [f"phụ lục danh mục nhiệm vụ {issuing_agency} chủ trì tổ chức thực hiện phối hợp thời hạn " + base_query],
            )
        )

    return {
        "summary": trich_yeu or user_request,
        "sections": [
            {
                "title": title,
                "key_points": key_points,
                "search_queries": [query.strip() for query in queries if query.strip()],
                "instructions": (
                    "Viết đúng nội dung mục này theo văn phong hành chính. "
                    "Nếu kho dữ liệu và thông tin người dùng không có dữ liệu liên quan cho mục này thì trả về rỗng để không xuất hiện trong Word."
                ),
            }
            for title, key_points, queries in sections
        ],
        "tone": "kế hoạch hành chính nhà nước",
        "total_sections": len(sections),
    }


def _format_template_outline(template_outline: dict) -> str:
    if not template_outline:
        return "Không tìm thấy mẫu cùng loại trong dữ liệu; dùng cấu trúc kế hoạch hành chính mặc định."

    lines = []
    source = template_outline.get("source_filename", "")
    title = template_outline.get("title", "")
    if source:
        lines.append(f"Nguồn mẫu: {source}")
    if title:
        lines.append(f"Tên văn bản mẫu: {title}")
    notes = template_outline.get("sample_notes", "")
    if notes:
        lines.append(f"Ghi chú mẫu: {notes}")
    headings = template_outline.get("headings", [])
    if headings:
        lines.append("Các đầu mục mẫu:")
        for heading in headings:
            level = heading.get("level", 1)
            marker = heading.get("marker", "")
            title = heading.get("title", "")
            indent = "  " * max(int(level or 1) - 1, 0)
            marker_text = f"{marker}. " if marker else ""
            lines.append(f"{indent}- level {level}: {marker_text}{title}")
    return "\n".join(lines) if lines else "Không tìm thấy mẫu cùng loại trong dữ liệu."
