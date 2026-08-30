# -*- coding: utf-8 -*-
"""사주·관상 결과를 하나의 PDF 리포트로 묶어주는 모듈.

한글 표시를 위해 Google Fonts의 나눔고딕(OFL 라이선스)을 최초 실행 시
다운로드해 로컬에 캐시해두고 fpdf2에 등록한다.
"""
import io
import os
import re
import urllib.request

from fpdf import FPDF

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
# NanumGothic은 한글 전용이라 사주 간지에 쓰이는 한자(甲子丙丁 등) 글리프가 없다.
# Noto Sans KR은 한글+한자를 모두 포함하므로 이걸 쓴다(가변 폰트라 굵기 인스턴스는
# regular 하나로 통일 — fpdf2는 가변축 선택을 지원하지 않는다).
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf"
FONT_PATH = os.path.join(FONT_DIR, "NotoSansKR.ttf")


def ensure_fonts() -> dict:
    os.makedirs(FONT_DIR, exist_ok=True)
    if not os.path.exists(FONT_PATH):
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
    return {"regular": FONT_PATH, "bold": FONT_PATH}


def _strip_markdown(text: str) -> str:
    """Gemini가 준 markdown(#### 제목, **볼드**, - 목록)을 PDF용 평문으로 단순화."""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"^[-*]\s+", "• ", line)
        lines.append(line)
    return "\n".join(lines)


class ReportPDF(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        fonts = ensure_fonts()
        self.add_font("Nanum", "", fonts["regular"])
        self.add_font("Nanum", "B", fonts["bold"])
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 18, 18)

    def h1(self, text: str):
        self.set_font("Nanum", "B", 20)
        self.set_text_color(60, 30, 90)
        self.multi_cell(0, 12, text)
        self.ln(2)

    def h2(self, text: str):
        self.set_font("Nanum", "B", 14)
        self.set_text_color(90, 50, 130)
        self.ln(3)
        self.multi_cell(0, 9, text)
        self.set_draw_color(200, 190, 220)
        self.line(self.get_x(), self.get_y(), self.get_x() + 174, self.get_y())
        self.ln(2)

    def body(self, text: str):
        self.set_font("Nanum", "", 10.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 6.5, _strip_markdown(text))
        self.ln(1)

    def caption(self, text: str):
        self.set_font("Nanum", "", 8.5)
        self.set_text_color(120, 120, 120)
        self.multi_cell(0, 5, text)
        self.ln(1)


def build_pdf(
    saju_result=None,
    saju_ai_text: str | None = None,
    gwansang_table: dict | None = None,
    gwansang_ai_text: str | None = None,
    face_image_bytes: bytes | None = None,
    generated_at: str = "",
) -> bytes:
    import saju as saju_mod

    pdf = ReportPDF()
    pdf.add_page()

    pdf.h1("FaceKorea 사주관상 리포트")
    pdf.caption(f"생성 시각: {generated_at}" if generated_at else "")
    pdf.caption(
        "이 리포트는 재미로 즐기는 콘텐츠입니다. 과학적·의학적·역학적 근거가 없으니 "
        "참고용으로만 봐주세요."
    )
    pdf.ln(4)

    # ---------------- 사주 ----------------
    if saju_result is not None:
        pdf.h2("1부. 사주팔자(四柱八字)")
        pdf.body(f"음력 기준: {saju_result.lunar_date_str}   |   띠: {saju_result.zodiac_kr}띠")
        pdf.body(
            f"태원(胎元): {saju_result.taiyuan}   명궁(命宮): {saju_result.minggong}   "
            f"신궁(身宮): {saju_result.shengong}"
        )
        strength_label, same_n, other_n = saju_result.body_strength()
        pdf.body(f"신강/신약 간이 판정: {strength_label}  (동조 오행 {same_n} : 이조 오행 {other_n})")
        pdf.ln(2)

        for p in saju_result.pillars:
            pdf.set_font("Nanum", "B", 11)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(0, 7, f"{p.label}  {p.hanja}({p.hangul})  ·  오행 {p.wuxing_hangul}", ln=1)
            pdf.set_font("Nanum", "", 9.5)
            pdf.set_text_color(70, 70, 70)
            detail = (
                f"  십성(천간): {p.shishen_gan or '-'}   십성(지지): {', '.join(p.shishen_zhi) or '-'}\n"
                f"  십이운성: {p.dishi}   지장간: {', '.join(p.hide_gan)}\n"
                f"  납음오행: {p.nayin}   공망: {p.xunkong}"
            )
            pdf.multi_cell(0, 5.5, detail)
            pdf.ln(1)

        pdf.ln(2)
        pdf.body("오행 분포: " + ", ".join(
            f"{saju_mod.WUXING_KR.get(k, k)} {v}개" for k, v in saju_result.wuxing_count.items()
        ))

        if saju_ai_text:
            pdf.add_page()
            pdf.h2("2부. AI 맞춤 사주 해설 (Gemini)")
            pdf.body(saju_ai_text)

    # ---------------- 관상 ----------------
    if gwansang_table or gwansang_ai_text or face_image_bytes:
        pdf.add_page()
        pdf.h2("3부. 관상 분석")

        if face_image_bytes:
            try:
                pdf.image(io.BytesIO(face_image_bytes), w=70)
                pdf.ln(3)
            except Exception:
                pass

        if gwansang_table:
            for part, (title, desc) in gwansang_table.items():
                pdf.set_font("Nanum", "B", 11)
                pdf.set_text_color(50, 50, 50)
                pdf.cell(0, 7, f"{part} · {title}", ln=1)
                pdf.set_font("Nanum", "", 9.5)
                pdf.set_text_color(70, 70, 70)
                pdf.multi_cell(0, 5.5, desc)
                pdf.ln(1)

        if gwansang_ai_text:
            pdf.add_page()
            pdf.h2("4부. AI 맞춤 관상 해설 (Gemini)")
            pdf.body(gwansang_ai_text)

    out = pdf.output()
    return bytes(out)
