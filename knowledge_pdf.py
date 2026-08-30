# -*- coding: utf-8 -*-
"""사주학·관상학 지식 베이스 전체를 큰 참고자료 PDF로 렌더링하는 모듈.

pdf_report.py의 폰트(Noto Sans KR) 인프라를 그대로 재사용한다. 개인화된
사용자 리포트(pdf_report.py)와는 별개로, 이 모듈은 지식 베이스 원문 그대로를
목차 없이 쭉 나열하는 '사전형' 참고자료 PDF를 만든다.
"""
import io

from fpdf import FPDF

from pdf_report import ensure_fonts, _strip_markdown  # 폰트/유틸 재사용


class KnowledgePDF(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        fonts = ensure_fonts()
        self.add_font("Nanum", "", fonts["regular"])
        self.add_font("Nanum", "B", fonts["bold"])
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(18, 16, 18)

    def cover(self, title: str, subtitle: str, count_line: str):
        self.add_page()
        self.set_font("Nanum", "B", 26)
        self.set_text_color(60, 30, 90)
        self.ln(60)
        self.multi_cell(0, 14, title, align="C")
        self.ln(6)
        self.set_font("Nanum", "", 13)
        self.set_text_color(90, 70, 120)
        self.multi_cell(0, 8, subtitle, align="C")
        self.ln(10)
        self.set_font("Nanum", "", 10)
        self.set_text_color(130, 130, 130)
        self.multi_cell(0, 6, count_line, align="C")

    def section_title(self, text: str):
        self.add_page()
        self.set_font("Nanum", "B", 20)
        self.set_text_color(60, 30, 90)
        self.multi_cell(0, 12, text)
        self.set_draw_color(160, 120, 200)
        self.line(self.get_x(), self.get_y(), self.get_x() + 174, self.get_y())
        self.ln(6)

    def category_heading(self, text: str):
        if self.get_y() > 260:
            self.add_page()
        self.ln(4)
        self.set_font("Nanum", "B", 14)
        self.set_text_color(120, 70, 150)
        self.multi_cell(0, 9, text)
        self.ln(1)

    def entry(self, row: dict):
        self.set_font("Nanum", "B", 12.5)
        self.set_text_color(35, 35, 35)
        self.multi_cell(0, 7.5, f"[{row['id']}] {row['title']}")
        self.ln(1)
        self.set_font("Nanum", "", 11)
        self.set_text_color(70, 70, 70)
        self.multi_cell(0, 7.2, _strip_markdown(row["body"]))
        self.ln(1)
        if row.get("source"):
            self.set_font("Nanum", "", 8.5)
            self.set_text_color(140, 140, 140)
            self.multi_cell(0, 5.2, f"참고: {row['source']}")
        self.ln(5)


def _render_domain(pdf: KnowledgePDF, title: str, rows: list):
    pdf.section_title(title)
    current_cat = None
    for row in rows:
        if row["category"] != current_cat:
            current_cat = row["category"]
            pdf.category_heading(f"■ {current_cat}")
        pdf.entry(row)


def build_knowledge_pdf(saju_rows: list, gwansang_rows: list) -> bytes:
    pdf = KnowledgePDF()
    pdf.cover(
        "사주학·관상학 참고자료집",
        "FaceKorea 사주관상 — 관리자용 지식 베이스 전체 문서",
        f"사주학 {len(saju_rows)}개 항목 · 관상학 {len(gwansang_rows)}개 항목 · "
        f"총 {len(saju_rows) + len(gwansang_rows)}개 항목\n\n"
        "이 문서는 온라인에 공개된 여러 사주·관상 자료를 참고해 정리한 자체 요약본이며,\n"
        "재미로 보는 전통 이론 소개 자료입니다. 각 항목 하단에 참고한 출처를 표기했습니다.",
    )
    _render_domain(pdf, "1부 — 사주학(四柱命理學)", saju_rows)
    _render_domain(pdf, "2부 — 관상학(觀相學)", gwansang_rows)

    out = pdf.output()
    return bytes(out)
