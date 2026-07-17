"""
Citation Checker — Validate source citations in generated documents.

Responsibilities:
  - Extract citations from draft text (pattern: [Nguồn: file | Mục: heading])
  - Cross-reference each citation against research data (retrieved chunks)
  - Detect fabricated/hallucinated citations
  - Identify major claims without source attribution
  - Generate a structured validation report

Citation format expected from Writer:
  [Nguồn: tên_file]
  [Nguồn: tên_file | Mục: heading]
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Regex to find citation patterns in text
CITATION_PATTERN = re.compile(
    r'\[Nguồn:\s*([^\]|]+?)(?:\s*\|\s*Mục:\s*([^\]]+?))?\]',
    re.IGNORECASE,
)


class CitationChecker:
    """Validate citations in generated documents against source data."""

    def extract_citations(self, text: str) -> list[dict]:
        """
        Extract all citation annotations from text.

        Args:
            text: Document draft text.

        Returns:
            List of citation dicts: {
                source_file: str,
                heading: str (optional),
                full_match: str,
                position: int (char offset),
                context: str (surrounding text)
            }
        """
        citations = []
        for match in CITATION_PATTERN.finditer(text):
            source_file = match.group(1).strip()
            heading = match.group(2).strip() if match.group(2) else ""
            position = match.start()

            # Extract surrounding context (50 chars before, 100 chars after)
            ctx_start = max(0, position - 50)
            ctx_end = min(len(text), match.end() + 100)
            context = text[ctx_start:ctx_end].strip()

            citations.append({
                "source_file": source_file,
                "heading": heading,
                "full_match": match.group(0),
                "position": position,
                "context": context,
            })

        logger.info(f"[CitationChecker] Extracted {len(citations)} citations from text")
        return citations

    def validate_against_research(
        self,
        citations: list[dict],
        research_data: list[dict],
    ) -> dict:
        """
        Validate citations against research data (scanner results).

        Checks:
        1. Source file exists in research data

        Args:
            citations: Extracted citations from extract_citations().
            research_data: Retrieved data from DocumentScanner.

        Returns:
            Validation report dict.
        """
        if not citations:
            return {
                "total": 0, "valid": 0, "invalid": 0,
                "results": [],
                "score": 1.0,
            }

        # Build lookup index from research data
        source_files = set()

        for chunk in research_data:
            sf = chunk.get("source_file", "") or chunk.get("filename", "")
            if sf:
                sf_normalized = sf.strip()
                source_files.add(sf_normalized)
                source_files.add(re.sub(r'\.[^.]+$', '', sf_normalized))

        # Validate each citation
        results = []
        valid_count = 0

        for citation in citations:
            sf = citation["source_file"]

            sf_found = self._fuzzy_match_source(sf, source_files)

            if not sf_found:
                results.append({
                    "citation": citation["full_match"],
                    "valid": False,
                    "reason": f"Không tìm thấy file nguồn '{sf}' trong dữ liệu kho",
                    "matched_chunk": None,
                })
                continue

            results.append({
                "citation": citation["full_match"],
                "valid": True,
                "reason": "Trích dẫn hợp lệ",
                "matched_chunk": sf_found,
            })
            valid_count += 1

        invalid_count = len(citations) - valid_count
        score = valid_count / len(citations) if citations else 1.0

        report = {
            "total": len(citations),
            "valid": valid_count,
            "invalid": invalid_count,
            "score": round(score, 2),
            "results": results,
        }

        logger.info(
            f"[CitationChecker] Validation: {valid_count}/{len(citations)} valid "
            f"(score={score:.2f})"
        )
        return report

    async def semantic_verify(
        self,
        claim_text: str,
        research_data: list[dict],
        threshold: float = 0.55,
    ) -> dict:
        """
        Semantic verification is not available (embedding service removed).
        Returns unsupported status.
        """
        logger.warning("[CitationChecker] semantic_verify called but embedding service is removed")
        return {"supported": False, "best_score": 0.0, "best_match": ""}

    def check_citation_coverage(
        self,
        draft_text: str,
        research_data: list[dict],
    ) -> dict:
        """
        Check overall citation coverage in the draft.

        Analyzes:
        - Number of paragraphs/sections with citations
        - Number without citations
        - Overall coverage ratio
        """
        paragraphs = re.split(r'\n\n|\n(?=\d+\.)', draft_text)
        paragraphs = [p.strip() for p in paragraphs if p.strip() and len(p.strip()) > 20]

        cited = 0
        uncited_sections = []

        for para in paragraphs:
            if CITATION_PATTERN.search(para):
                cited += 1
            else:
                if len(para) > 50:
                    uncited_sections.append(para[:80] + "...")

        total = len(paragraphs)
        coverage = cited / total if total > 0 else 0

        return {
            "total_paragraphs": total,
            "cited_paragraphs": cited,
            "uncited_paragraphs": total - cited,
            "coverage": round(coverage, 2),
            "uncited_sections": uncited_sections[:5],
        }

    def generate_full_report(
        self,
        draft_text: str,
        research_data: list[dict],
    ) -> dict:
        """Generate a comprehensive citation validation report."""
        citations = self.extract_citations(draft_text)
        validation = self.validate_against_research(citations, research_data)
        coverage = self.check_citation_coverage(draft_text, research_data)

        citation_score = validation["score"]
        coverage_score = coverage["coverage"]
        overall_score = (citation_score * 0.6 + coverage_score * 0.4)

        report = {
            "citations": {
                "total": validation["total"],
                "valid": validation["valid"],
                "invalid": validation["invalid"],
                "accuracy_score": citation_score,
                "details": validation["results"],
            },
            "coverage": coverage,
            "overall_score": round(overall_score, 2),
            "pass": overall_score >= 0.5,
            "summary": self._build_summary(validation, coverage, overall_score),
        }

        logger.info(
            f"[CitationChecker] Full report: "
            f"citations={validation['total']}, "
            f"accuracy={citation_score:.2f}, "
            f"coverage={coverage_score:.2f}, "
            f"overall={overall_score:.2f}"
        )
        return report

    # ── Private Helpers ───────────────────────────────────────────────

    @staticmethod
    def _fuzzy_match_source(citation_source: str, known_sources: set[str]) -> Optional[str]:
        """Fuzzy match a citation source against known sources."""
        cs = citation_source.strip().lower()

        for src in known_sources:
            src_lower = src.lower()
            if cs == src_lower:
                return src
            if cs in src_lower or src_lower in cs:
                return src
            cs_clean = re.sub(r'^(nguồn|kho|tài liệu):\s*', '', cs)
            if cs_clean and (cs_clean in src_lower or src_lower in cs_clean):
                return src

        return None

    @staticmethod
    def _build_summary(
        validation: dict, coverage: dict, overall_score: float
    ) -> str:
        """Build a human-readable summary of the citation report."""
        parts = []

        if validation["invalid"] > 0:
            parts.append(
                f"⚠️ {validation['invalid']}/{validation['total']} trích dẫn không hợp lệ"
            )
        elif validation["total"] > 0:
            parts.append(f"✅ Tất cả {validation['total']} trích dẫn đều hợp lệ")
        else:
            parts.append("⚠️ Không có trích dẫn nguồn nào trong văn bản")

        cov_pct = int(coverage["coverage"] * 100)
        parts.append(f"📊 Độ bao phủ trích dẫn: {cov_pct}%")

        if coverage["uncited_paragraphs"] > 0:
            parts.append(
                f"📝 {coverage['uncited_paragraphs']} đoạn chưa có trích dẫn nguồn"
            )

        if overall_score >= 0.7:
            parts.append("✅ Chất lượng trích dẫn: TỐT")
        elif overall_score >= 0.5:
            parts.append("⚠️ Chất lượng trích dẫn: TRUNG BÌNH — cần bổ sung thêm nguồn")
        else:
            parts.append("❌ Chất lượng trích dẫn: YẾU — nhiều nội dung thiếu căn cứ")

        return "\n".join(parts)


# Singleton
citation_checker = CitationChecker()
