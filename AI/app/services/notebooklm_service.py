"""
STTNB NotebookLM Service — Integration with notebooklm-py.

Handles:
1. Creating a temporary notebook
2. Uploading audio file as a source
3. Asking NotebookLM to generate structured meeting minutes
4. Parsing the response into MeetingMinutes model
5. Cleaning up the notebook

Extended for Repository Management:
6. Creating persistent notebooks for repositories
7. Uploading document sources
8. Chat Q&A for repositories
9. Deleting notebooks
"""

import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Optional

from notebooklm import NotebookLMClient

from app.models import MeetingMinutes, ContentSection

logger = logging.getLogger(__name__)

# ─── Prompt cho NotebookLM ────────────────────────────────────────────

MEETING_MINUTES_PROMPT = """Bạn là chuyên viên văn phòng cơ quan nhà nước. Hãy phân tích toàn bộ nội dung ghi âm cuộc họp này và soạn **biên bản cuộc họp** theo đúng thể thức văn bản hành chính nhà nước Việt Nam.

Trả về kết quả dưới dạng JSON với cấu trúc CHÍNH XÁC như sau (CHỈ trả về JSON thuần, KHÔNG có markdown, KHÔNG có ```json):

{
    "ten_co_quan_chu_quan": "Tên cơ quan chủ quản cấp trên viết hoa (vd: UBND TỈNH TÂY NINH). Nếu không rõ để chuỗi rỗng.",
    "ten_don_vi": "Tên đơn vị tổ chức cuộc họp viết hoa (vd: SỞ KHOA HỌC VÀ CÔNG NGHỆ)",
    "tieu_de": "BIÊN BẢN",
    "tieu_de_noi_dung": "Tên/chủ đề cuộc họp (vd: Họp thống nhất quy trình triển khai các bài toán lớn của tỉnh, các sở, ngành, địa phương)",
    "mo_dau": "Viết đoạn mở đầu theo đúng mẫu: 'Vào lúc [giờ] phút, ngày [ngày] tháng [tháng] năm [năm], tại [địa điểm], [liệt kê thành phần tham dự tóm tắt], đã tiến hành cuộc họp [mục đích cuộc họp].' Nếu KHÔNG nghe rõ thời gian hoặc địa điểm, để trống phần đó bằng dấu '......' (vd: 'Vào lúc ...... phút, ngày ...... tháng ...... năm ......, tại ......,')",
    "chu_tri": "Đ/c [Họ Tên] - [Chức vụ] (vd: Đ/c Huỳnh Thị Hồng Nhung - Giám đốc Sở)",
    "thu_ky": "Đ/c [Họ Tên] - [Chức vụ]. Nếu không rõ để chuỗi rỗng.",
    "thanh_vien": [
        "- Đ/c [Họ Tên] - [Chức vụ];",
        "- Đ/c [Họ Tên] - [Chức vụ];",
        "- Đ/c [Họ Tên] - [Chức vụ]."
    ],
    "dan_nhap_noi_dung": "Viết đoạn dẫn nhập nội dung theo mẫu: 'Sau khi nghe [ai] báo cáo [nội dung gì], trên cơ sở ý kiến thảo luận của các thành viên dự họp, [Chức vụ chủ trì] đã thống nhất và kết luận các nội dung cụ thể như sau:'",
    "noi_dung": [
        {
            "tieu_de_muc": "1. Về [vấn đề thứ nhất]",
            "mo_ta": "Đoạn mô tả tổng quan nếu cần (có thể để rỗng)",
            "chi_tiet": [
                "- Giao [Phòng/Bộ phận]: nội dung công việc cụ thể;",
                "+ Chi tiết 1: mô tả cụ thể nhiệm vụ, trách nhiệm, thời hạn;",
                "+ Chi tiết 2: nội dung tiếp theo."
            ],
            "luu_y": "Phần lưu ý đặc biệt nếu có (có thể để rỗng)"
        },
        {
            "tieu_de_muc": "2. Về [vấn đề thứ hai]",
            "mo_ta": "Mô tả tóm tắt về vấn đề, nhấn mạnh tính cấp thiết/cần thiết.",
            "chi_tiet": [
                "- Giao [Phòng/Bộ phận] chủ trì, phối hợp với [đơn vị khác], thực hiện [nội dung], báo cáo trước ngày [DD/MM/YYYY]."
            ],
            "luu_y": ""
        }
    ],
    "ket_luan": "Viết đoạn kết luận của chủ trì theo mẫu: '[Chức vụ chủ trì] yêu cầu các [đơn vị/cá nhân] sát sao, đôn đốc các đơn vị được giao phụ trách thực hiện nghiêm túc theo các nội dung đã thống nhất.'",
    "ket_thuc": "Cuộc họp kết thúc vào lúc [giờ] phút cùng ngày./. Nếu không rõ giờ kết thúc thì ghi: 'Cuộc họp kết thúc vào lúc ...... phút cùng ngày./.'"",
    "ten_thu_ky": "Họ tên thư ký (chỉ họ tên, không chức danh). Nếu không rõ để rỗng.",
    "ten_chu_tri": "Họ tên chủ trì (chỉ họ tên, không chức danh)"
}

QUY TẮC VĂN PHONG VÀ THỂ THỨC BẮT BUỘC:
1. Văn phong hành chính, trang trọng, chính xác. KHÔNG dùng ngôn ngữ nói, KHÔNG dùng từ lóng.
2. Dùng "Đ/c" (đồng chí) khi xưng hô. Ghi đầy đủ họ tên và chức vụ.
3. Nội dung phải rõ ràng: AI làm GÌ, KHI NÀO, BÁO CÁO cho AI.
4. Mỗi mục nội dung bắt đầu bằng số thứ tự "1.", "2.", "3.".  
5. Gạch đầu dòng dùng "-" cho cấp 1, "+" cho cấp 2.
6. Ghi chính xác tên người, chức vụ, tên phòng ban, thời hạn, con số được đề cập.
7. Nếu không nghe rõ tên/thông tin, ghi "[...]" để đánh dấu cần bổ sung.
8. Nếu không có thông tin (vd: thư ký), để chuỗi RỖNG "".
9. Đoạn "mo_dau" phải viết thành MỘT câu dài hoàn chỉnh.
10. Thời gian, địa điểm: Nếu KHÔNG nghe rõ trong bản ghi âm, dùng dấu "......" để bỏ trống, KHÔNG ĐƯỢC tự bịa ra.
11. CHỈ trả về JSON thuần — KHÔNG có markdown, KHÔNG có giải thích.
"""


class NotebookLMService:
    """Service to interact with Google NotebookLM via unofficial API."""

    def __init__(self):
        pass

    async def _get_client(self) -> NotebookLMClient:
        """Get a fresh NotebookLM client from stored credentials."""
        return await NotebookLMClient.from_storage()

    async def check_auth(self) -> bool:
        """Check if NotebookLM authentication is valid."""
        try:
            client = await self._get_client()
            async with client:
                notebooks = await client.notebooks.list()
                logger.info(f"Auth OK — found {len(notebooks)} notebooks")
                return True
        except Exception as e:
            logger.error(f"Auth check failed: {e}")
            return False

    def get_session_fingerprint(self) -> str:
        """
        Return a stable hash for the currently stored NotebookLM session.

        The raw session/cookies are never stored in the application database;
        only this digest is used to detect that the active NotebookLM account
        or session has changed.
        """
        candidates = [
            Path.home() / ".notebooklm" / "profiles" / "default" / "storage_state.json",
            Path.home() / ".notebooklm" / "storage_state.json",
        ]
        digest = hashlib.sha256()
        found = False
        for path in candidates:
            if not path.exists():
                continue
            try:
                content = path.read_bytes()
            except OSError as e:
                logger.warning("Could not read NotebookLM session file %s: %s", path, e)
                continue
            found = True
            digest.update(str(path.name).encode("utf-8"))
            digest.update(content)

        return digest.hexdigest() if found else ""

    # ─── Repository Management Methods ───────────────────────────────

    async def create_notebook(self, name: str) -> str:
        """Create a new notebook and return its ID."""
        client = await self._get_client()
        async with client:
            nb = await client.notebooks.create(name)
            logger.info(f"Created notebook: {nb.id} — {name}")
            return nb.id

    async def delete_notebook(self, notebook_id: str):
        """Delete a notebook by ID."""
        client = await self._get_client()
        async with client:
            await client.notebooks.delete(notebook_id)
            logger.info(f"Deleted notebook: {notebook_id}")

    async def upload_source(self, notebook_id: str, file_path: str) -> Optional[str]:
        """
        Upload a file as a source to a notebook.
        Returns the source ID if available.
        """
        client = await self._get_client()
        async with client:
            result = await client.sources.add_file(notebook_id, file_path, wait=True)
            source_id = getattr(result, 'id', None) if result else None
            logger.info(f"Uploaded source to notebook {notebook_id}: {file_path} → {source_id}")
            return source_id

    async def delete_source(self, notebook_id: str, source_id: str):
        """Delete a source from a notebook."""
        client = await self._get_client()
        async with client:
            await client.sources.delete(notebook_id, source_id)
            logger.info(f"Deleted source {source_id} from notebook {notebook_id}")

    async def chat_ask(self, notebook_id: str, question: str) -> str:
        """
        Send a question to a notebook's chat and return the answer text.
        """
        client = await self._get_client()
        async with client:
            result = await client.chat.ask(notebook_id, question)
            answer = result.answer
            
            # Remove NotebookLM citations like [1], [1, 2], [15, 16]
            answer = re.sub(r'\s*\[\d+(?:[,\s\-]+\d+)*\]', '', answer)
            
            logger.info(f"Chat response from notebook {notebook_id}: {len(answer)} chars")
            return answer

    # ─── Legacy Audio Processing ─────────────────────────────────────

    async def process_audio(self, audio_path: str, on_status=None) -> MeetingMinutes:
        """
        Full pipeline: upload audio → ask NotebookLM → parse meeting minutes.
        """
        notebook_id = None
        
        async def update_status(message: str):
            logger.info(message)
            if on_status:
                await on_status(message)

        try:
            client = await self._get_client()
            
            async with client:
                # Step 1: Create a new notebook
                await update_status("Đang tạo file mới trên hệ thống...")
                filename = Path(audio_path).stem
                nb = await client.notebooks.create(f"Biên bản: {filename}")
                notebook_id = nb.id
                logger.info(f"Created notebook: {notebook_id}")

                # Step 2: Upload audio file as source
                await update_status("Đang upload file ghi âm lên hệ thống...")
                await client.sources.add_file(notebook_id, audio_path, wait=True)
                logger.info(f"Uploaded audio source: {audio_path}")

                # Step 3: Wait for source processing
                await update_status("Hệ thống đang xử lý file ghi âm...")
                await asyncio.sleep(5)

                # Step 4: Ask NotebookLM to generate meeting minutes
                await update_status("Đang tạo biên bản họp từ nội dung ghi âm...")
                result = await client.chat.ask(notebook_id, MEETING_MINUTES_PROMPT)
                raw_response = result.answer
                
                # Remove NotebookLM citations like [1], [1, 2], [15, 16]
                raw_response = re.sub(r'\s*\[\d+(?:[,\s\-]+\d+)*\]', '', raw_response)
                
                logger.info(f"Got response from system ({len(raw_response)} chars)")

                # Step 5: Parse the response
                await update_status("Đang phân tích và cấu trúc biên bản họp...")
                minutes = self._parse_response(raw_response)

                # Step 6: Cleanup
                await update_status("Đang dọn dẹp file tạm...")
                try:
                    await client.notebooks.delete(notebook_id)
                    logger.info(f"Deleted temporary notebook: {notebook_id}")
                except Exception as cleanup_err:
                    logger.warning(f"Could not delete notebook {notebook_id}: {cleanup_err}")

                return minutes

        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            if notebook_id:
                try:
                    client = await self._get_client()
                    async with client:
                        await client.notebooks.delete(notebook_id)
                except Exception:
                    pass
            raise

    def _parse_response(self, raw_response: str) -> MeetingMinutes:
        """Parse NotebookLM's response into a MeetingMinutes object."""
        json_str = self._extract_json(raw_response)
        
        if json_str:
            try:
                data = json.loads(json_str)
                
                # Convert noi_dung items to ContentSection objects
                if "noi_dung" in data and isinstance(data["noi_dung"], list):
                    data["noi_dung"] = [
                        ContentSection(**item) if isinstance(item, dict) else item
                        for item in data["noi_dung"]
                    ]
                
                return MeetingMinutes(**data)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"JSON parse failed: {e}, falling back to text parsing")
        
        # Fallback: create basic minutes from raw text
        return MeetingMinutes(
            tieu_de="BIÊN BẢN",
            tieu_de_noi_dung="Cuộc họp",
            noi_dung=[
                ContentSection(
                    tieu_de_muc="1. Nội dung cuộc họp",
                    chi_tiet=[raw_response]
                )
            ],
        )

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON string from text that may contain markdown or other wrapping."""
        text_stripped = text.strip()
        if text_stripped.startswith("{"):
            return text_stripped

        patterns = [
            r'```json\s*\n(.*?)\n\s*```',
            r'```\s*\n(.*?)\n\s*```',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                candidate = match.group(1).strip()
                if candidate.startswith("{"):
                    return candidate

        match = re.search(r'\{[\s\S]*\}', text, re.DOTALL)
        if match:
            return match.group(0).strip()

        return None


# Singleton service instance
notebooklm_service = NotebookLMService()
