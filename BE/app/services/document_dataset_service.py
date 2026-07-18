"""Build a stable document-dataset response for FE integration."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from app.models import DatasetField, DocumentDatasetResponse


class DocumentDatasetService:
    """Temporary contract-first extractor.

    The current implementation returns deterministic mock data from the
    uploaded filename. Later, this class can call the AI service while keeping
    the public BE response shape unchanged.
    """

    def build_mock_response(self, filename: str) -> DocumentDatasetResponse:
        title = self._title_from_filename(filename)
        document_data = self._mock_ai_document(title)
        fields, rows = self._table_view(document_data)

        return DocumentDatasetResponse(
            title=document_data.get("trich_yeu") or title,
            content=document_data.get("noi_dung") or [],
            fields=fields,
            rows=rows,
            document_data=document_data,
            source="mock",
            filename=filename,
            message=(
                "Du lieu tam thoi de FE tich hop giao dien. "
                "Khi AI extractor san sang, BE se tra cung schema nay voi source='ai'."
            ),
        )

    def build_ai_response(self, filename: str, document_data: dict) -> DocumentDatasetResponse:
        """Wrap an AI payload in the BE response contract."""
        fields, rows = self._table_view(document_data)
        return DocumentDatasetResponse(
            title=document_data.get("trich_yeu") or self._title_from_filename(filename),
            content=document_data.get("noi_dung") or [],
            fields=fields,
            rows=rows,
            document_data=document_data,
            source="ai",
            filename=filename,
        )

    def _title_from_filename(self, filename: str) -> str:
        stem = Path(filename or "tai_lieu").stem
        stem = re.sub(r"\.signed$", "", stem, flags=re.IGNORECASE)
        stem = re.sub(r"^\d+[_-]", "", stem)
        stem = stem.replace("_", " ").replace("-", " ")
        stem = re.sub(r"\b\d{2}\s\d{2}\s\d{4}\b", "", stem)
        stem = re.sub(r"\s+", " ", stem).strip()
        return stem or "Tai lieu"

    def _mock_ai_document(self, title: str) -> dict:
        return {
            "co_quan_chu_quan": "",
            "co_quan_ban_hanh": "",
            "so_ky_hieu": "",
            "dia_danh": "",
            "ngay_ban_hanh": "",
            "loai_van_ban": "KẾ HOẠCH",
            "trich_yeu": title,
            "trich_yeu_dong": [title],
            "noi_dung": [
                "Nội dung sẽ được AI trích xuất từ tài liệu.",
                "BE đang trả dữ liệu mẫu theo đúng cấu trúc AI dự kiến.",
            ],
            "thua_lenh": [],
            "chu_ky_dong": [],
            "chuc_vu": "",
            "nguoi_ky": "",
            "noi_nhan": [],
            "body_profile": {
                "preserve_numbering": True,
                "font_size": 14,
                "indent": 1.25,
                "before": 6,
                "after": 6,
                "line": 1.15,
            },
            "layout": {
                "header_widths_cm": [6.75, 9.92],
                "signature_widths_cm": [8.29, 8.63],
                "title_separator": True,
                "date_in_header": True,
                "national_font_size": 12,
                "left_header_line_length": 9,
                "right_header_line_length": 27,
            },
            "phu_luc": [
                {
                    "tieu_de": "DANH MỤC CHI TIẾT CÁC NHIỆM VỤ TRỌNG TÂM",
                    "noi_dung": [],
                    "landscape": True,
                    "bang": [
                        {
                            "headers": [
                                "STT",
                                "Nội dung nhiệm vụ",
                                "Văn bản giao nhiệm vụ",
                                "Thời hạn hoàn thành",
                                "Cơ quan chủ trì",
                                "Cơ quan phối hợp",
                            ],
                            "rows": [
                                ["1", "", "", "", "", ""],
                            ],
                        }
                    ],
                }
            ],
        }

    def _table_view(self, document_data: dict) -> tuple[list[DatasetField], list[dict[str, str]]]:
        for appendix in document_data.get("phu_luc") or []:
            for table in appendix.get("bang") or []:
                headers = table.get("headers") or []
                if not headers:
                    continue
                keys = [self._field_key(header, index) for index, header in enumerate(headers)]
                fields = [
                    DatasetField(
                        key=key,
                        label=str(header),
                        value_type="number" if index == 0 else "text",
                        required=index == 0,
                    )
                    for index, (key, header) in enumerate(zip(keys, headers))
                ]
                rows = [
                    {
                        key: str(row[index]) if index < len(row) and row[index] is not None else ""
                        for index, key in enumerate(keys)
                    }
                    for row in table.get("rows") or []
                ]
                return fields, rows
        return [], []

    def _field_key(self, label: str, index: int) -> str:
        text = str(label).strip().lower()
        text = text.replace("đ", "d")
        text = unicodedata.normalize("NFD", text)
        text = "".join(char for char in text if unicodedata.category(char) != "Mn")
        text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
        return text or f"cot_{index + 1}"


document_dataset_service = DocumentDatasetService()
