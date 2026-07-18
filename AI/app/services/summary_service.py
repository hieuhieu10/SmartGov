"""Tổng hợp ý kiến góp ý thành Bảng tổng hợp tiếp thu/giải trình theo mẫu.

Áp dụng MAP-REDUCE để viết được bảng dài với nhiều văn bản góp ý:
- METADATA: trích phần thể thức (cơ quan ban hành, địa danh, tên dự thảo) từ BẢN
  DỰ THẢO (1 lần gọi nhỏ).
- MAP: chia các VĂN BẢN GÓP Ý thành batch, mỗi batch model sinh JSON các dòng góp ý
  (kèm phân loại "doi_tuong") + danh sách đơn vị thống nhất. Chạy song song có giới hạn.
- REDUCE: gộp toàn bộ dòng, phân loại vào section (Quyết định/Quy chế), khử trùng
  đơn vị thống nhất — bằng code, không cần thêm lần gọi model (tránh tràn output).

BE nhận dict ``{"metadata", "mo_dau", "sections"}`` để render .docx.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from app.config import settings
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# Giới hạn ký tự mỗi văn bản để tránh vượt context window.
_MAX_CHARS_PER_FEEDBACK = 8000
_MAX_CHARS_PER_DRAFT = 4000
# Số batch map chạy song song tối đa (bảo vệ model chính đơn luồng).
_MAP_CONCURRENCY = 4

_RESPONSE_TYPES = [
    "Tiếp thu điều chỉnh",
    "Tiếp thu, bổ sung vào dự thảo",
    "Tiếp thu, thực hiện bổ sung",
    "Tiếp thu (thực hiện khi đủ điều kiện)",
    "Đề xuất giữ nguyên theo dự thảo (kèm Lý do giải trình)",
]

_SYSTEM_PROMPT = (
    "Bạn là chuyên viên hành chính tổng hợp ý kiến góp ý dự thảo văn bản quy phạm "
    "pháp luật của cơ quan nhà nước. Chỉ dựa vào nội dung được cung cấp, TUYỆT ĐỐI "
    "không bịa thông tin; thông tin không có thì để chuỗi rỗng. Trả lời DUY NHẤT bằng "
    "một object JSON hợp lệ đúng yêu cầu, KHÔNG kèm giải thích, KHÔNG dùng rào ```; "
    "không suy nghĩ thành tiếng, không dùng thẻ <think>. /no_think"
)

# ── METADATA ────────────────────────────────────────────────────────────────
_METADATA_SKELETON = {
    "co_quan_chu_quan": "",
    "co_quan_ban_hanh": "",
    "dia_danh": "",
    "ngay_ban_hanh": "",
    "ten_du_thao": "",
}

_METADATA_USER = """\
Trích thông tin thể thức từ BẢN DỰ THẢO dưới đây, trả về JSON đúng khung:
{skeleton}

QUY TẮC:
- "co_quan_ban_hanh" = CƠ QUAN CHỦ TRÌ SOẠN THẢO dự thảo (thường là Sở/ban/ngành, ví
  dụ "Sở Khoa học và Công nghệ") — đơn vị ban hành bảng tổng hợp.
- "co_quan_chu_quan" = cơ quan cấp trên (thường "ỦY BAN NHÂN DÂN TỈNH ...").
- Dù dự thảo là Quyết định do UBND tỉnh ban hành, KHÔNG hoán đổi hai trường trên.
- "ten_du_thao": tên dự thảo. Không rõ trường nào thì để chuỗi rỗng. Chỉ xuất JSON.

BẢN DỰ THẢO:
{draft}
"""

# ── MAP (mỗi batch) ─────────────────────────────────────────────────────────
_MAP_SKELETON = {
    "rows": [
        {
            "nhom_van_de": "",
            "chu_the_gop_y": "",
            "noi_dung_gop_y": "",
            "noi_dung_tiep_thu_giai_trinh": "",
            "doi_tuong": "quy_che",
        }
    ],
    "don_vi_thong_nhat": [{"ten": "", "so_cong_van": "", "ngay": ""}],
}

_MAP_USER = """\
Dưới đây là một NHÓM VĂN BẢN GÓP Ý cho dự thảo. Trích thành JSON đúng khung:
{skeleton}

QUY TẮC:
- Mỗi Ý KIẾN góp ý là một object trong "rows" gồm: nhom_van_de (điều/khoản/vấn đề),
  chu_the_gop_y (TÊN đơn vị góp ý, lấy từ tiêu đề/nội dung văn bản), noi_dung_gop_y
  (tóm tắt, giữ nguyên ý, không bịa), noi_dung_tiep_thu_giai_trinh, và doi_tuong.
- "doi_tuong" chỉ nhận "quyet_dinh" HOẶC "quy_che":
  + "quyet_dinh": ý kiến về THỂ THỨC bản Quyết định — bố cục, trình bày, căn cứ ban
    hành, phần "Nơi nhận", hiệu lực, các Điều thuộc bản Quyết định (thường Điều 1-3).
  + "quy_che": ý kiến về NỘI DUNG Quy chế đính kèm — các Điều/khoản nghiệp vụ (Điều
    4, 5, 6, 7, 8, 9, 10, 12-15...), tiếp nhận/xử lý/phản ánh/kiến nghị, đối tượng áp
    dụng, giải thích từ ngữ. Nếu nêu Điều/khoản nghiệp vụ -> LUÔN "quy_che".
- "noi_dung_tiep_thu_giai_trinh" chỉ dùng một trong: {response_types}. Ý kiến đúng thể
  thức/pháp lý -> "Tiếp thu điều chỉnh"/"Tiếp thu, bổ sung vào dự thảo"; ý kiến đã có
  trong dự thảo -> "Đề xuất giữ nguyên theo dự thảo" kèm lý do ngắn.
- "don_vi_thong_nhat": đơn vị nào THỐNG NHẤT HOÀN TOÀN (không đề nghị sửa gì) thì đưa
  vào đây (tên + số công văn + ngày lấy từ văn bản), KHÔNG đưa vào "rows". Đơn vị có ý
  kiến chỉnh sửa thì đưa vào "rows", KHÔNG đưa vào đây. Không có thì để mảng rỗng.
- Chỉ xuất JSON.

CÁC VĂN BẢN GÓP Ý:
{feedback}
"""

_ROW_KEYS = ("nhom_van_de", "chu_the_gop_y", "noi_dung_gop_y", "noi_dung_tiep_thu_giai_trinh")


def _extract_json(text: str) -> dict:
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


def _doc_block(doc: dict, limit: int, label: str, index: int) -> str | None:
    content = (doc.get("markdown_content") or "").strip()
    if not content:
        return None
    if len(content) > limit:
        content = content[:limit] + "\n...(đã lược bớt)"
    filename = doc.get("filename") or f"{label} {index}"
    return f"### {label} {index}: {filename}\n{content}"


def _batch_feedback(documents: list[dict]) -> list[list[str]]:
    """Chia văn bản góp ý thành các batch theo số lượng + tổng ký tự."""
    batches: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    index = 0
    for doc in documents:
        index += 1
        block = _doc_block(doc, _MAX_CHARS_PER_FEEDBACK, "Văn bản góp ý", index)
        if block is None:
            continue
        if current and (
            len(current) >= settings.summary_batch_max_docs
            or current_chars + len(block) > settings.summary_batch_max_chars
        ):
            batches.append(current)
            current, current_chars = [], 0
        current.append(block)
        current_chars += len(block)
    if current:
        batches.append(current)
    return batches


class SummaryService:
    async def consolidate_feedback(
        self,
        feedback_documents: list[dict],
        draft_documents: list[dict] | None = None,
    ) -> dict:
        """Sinh bảng tổng hợp (dict) từ dự thảo + văn bản góp ý bằng map-reduce."""
        batches = _batch_feedback(feedback_documents)
        if not batches:
            raise ValueError("Không có nội dung góp ý để tổng hợp")

        logger.info(
            "Consolidating %d feedback doc(s) in %d batch(es)",
            sum(len(b) for b in batches), len(batches),
        )
        semaphore = asyncio.Semaphore(_MAP_CONCURRENCY)

        async def run(idx: int, blocks: list[str]) -> dict:
            async with semaphore:
                return await self._map_batch(idx, len(batches), blocks)

        # Trích metadata chạy SONG SONG với các batch map để chồng thời gian chờ
        # (đặc biệt khi model chính chậm/timeout, tránh cộng dồn độ trễ).
        metadata_task = asyncio.create_task(self._extract_metadata(draft_documents or []))
        batch_results = await asyncio.gather(
            *(run(i, b) for i, b in enumerate(batches, start=1))
        )
        metadata = await metadata_task

        result = self._reduce(metadata, batch_results)
        if not any(section.get("rows") for section in result["sections"]):
            raise ValueError("Bảng tổng hợp không có nội dung góp ý nào")
        return result

    async def _extract_metadata(self, draft_documents: list[dict]) -> dict:
        blocks = [
            b for i, d in enumerate(draft_documents, start=1)
            if (b := _doc_block(d, _MAX_CHARS_PER_DRAFT, "Bản dự thảo", i))
        ]
        if not blocks:
            return dict(_METADATA_SKELETON)
        user = _METADATA_USER.format(
            skeleton=json.dumps(_METADATA_SKELETON, ensure_ascii=False, indent=2),
            draft="\n\n".join(blocks),
        )
        try:
            raw = await llm_service.chat(_SYSTEM_PROMPT, user, temperature=0.1, max_tokens=1024)
            data = _extract_json(raw)
        except Exception as exc:  # noqa: BLE001 - metadata là phụ, lỗi thì để trống
            logger.warning("Không trích được metadata từ dự thảo: %s", exc)
            return dict(_METADATA_SKELETON)
        return {key: str(data.get(key, "") or "") for key in _METADATA_SKELETON}

    async def _map_batch(self, idx: int, total: int, blocks: list[str]) -> dict:
        user = _MAP_USER.format(
            skeleton=json.dumps(_MAP_SKELETON, ensure_ascii=False, indent=2),
            response_types=json.dumps(_RESPONSE_TYPES, ensure_ascii=False),
            feedback="\n\n".join(blocks),
        )
        try:
            raw = await llm_service.chat(_SYSTEM_PROMPT, user, temperature=0.1, max_tokens=8192)
            data = _extract_json(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Batch %d/%d parse lỗi, bỏ qua: %s", idx, total, exc)
            return {"rows": [], "don_vi_thong_nhat": []}
        rows = data.get("rows") if isinstance(data.get("rows"), list) else []
        thong_nhat = (
            data.get("don_vi_thong_nhat")
            if isinstance(data.get("don_vi_thong_nhat"), list) else []
        )
        logger.info("Batch %d/%d: %d dòng, %d đơn vị thống nhất", idx, total, len(rows), len(thong_nhat))
        return {"rows": rows, "don_vi_thong_nhat": thong_nhat}

    @staticmethod
    def _reduce(metadata: dict, batch_results: list[dict]) -> dict:
        """Gộp kết quả các batch, phân loại section, khử trùng — bằng code."""
        section1: list[dict] = []  # Quyết định
        section2: list[dict] = []  # Quy chế
        chu_the_co_y_kien: set[str] = set()

        for batch in batch_results:
            for row in batch.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                clean = {key: str(row.get(key, "") or "").strip() for key in _ROW_KEYS}
                if not any(clean.values()):
                    continue
                name = clean["chu_the_gop_y"]
                if name:
                    chu_the_co_y_kien.add(name.lower())
                if str(row.get("doi_tuong", "")).strip().lower() == "quyet_dinh":
                    section1.append(clean)
                else:
                    section2.append(clean)

        # Đơn vị thống nhất: gộp, khử trùng theo tên, loại đơn vị đã có ý kiến trong bảng.
        seen: set[str] = set()
        don_vi_thong_nhat: list[dict] = []
        for batch in batch_results:
            for dv in batch.get("don_vi_thong_nhat") or []:
                if not isinstance(dv, dict):
                    continue
                ten = str(dv.get("ten", "") or "").strip()
                key = ten.lower()
                if not ten or key in seen or key in chu_the_co_y_kien:
                    continue
                seen.add(key)
                don_vi_thong_nhat.append({
                    "ten": ten,
                    "so_cong_van": str(dv.get("so_cong_van", "") or "").strip(),
                    "ngay": str(dv.get("ngay", "") or "").strip(),
                })

        ten_du_thao = (metadata.get("ten_du_thao") or "").strip()
        can_cu = (
            "Căn cứ Luật Ban hành văn bản quy phạm pháp luật, cơ quan chủ trì soạn thảo "
            f"đã tổ chức lấy ý kiến đối với dự thảo {ten_du_thao or '(chưa rõ tên)'}. Kết quả:"
        )

        return {
            "metadata": metadata,
            "mo_dau": {"can_cu": can_cu, "don_vi_thong_nhat": don_vi_thong_nhat},
            "sections": [
                {"tieu_de": "1. Đối với dự thảo Quyết định", "rows": section1},
                {"tieu_de": "2. Đối với dự thảo Quy chế", "rows": section2},
            ],
        }


summary_service = SummaryService()
