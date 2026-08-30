# -*- coding: utf-8 -*-
"""Gemini API 연동 — 사주/관상 계산 결과를 바탕으로 개인 맞춤 해설을 생성한다.

API 키는 사용자가 앱 화면에서 직접 입력한 값만 사용하고, 이 모듈 어디에도
저장/로깅하지 않는다. 모델은 최신 Flash 계열부터 순서대로 시도하고, 특정
모델이 일시적으로 과부하(503)이거나 지원 종료(404)면 다음 후보로 넘어간다.
"""
import json

from google import genai
from google.genai import types

MODEL_CANDIDATES = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]

SAJU_SYSTEM_INSTRUCTION = """너는 친절하고 유머 있는 한국 사주명리학 해설가야.
아래 JSON으로 주어진 사주팔자(년/월/일/시주, 십성, 십이운성, 지장간, 납음오행,
공망, 오행분포, 신강신약)를 바탕으로 아주 상세하고 개인 맞춤형으로 한국어 해설을
작성해줘. 함께 제공되는 '참고 자료'는 이 서비스의 사주학 지식 데이터베이스에서
가져온 근거 자료이니, 그 설명을 적극 활용해서 근거 있는 해설을 만들어줘.

지켜야 할 규칙:
- 이것은 재미로 보는 콘텐츠임을 인지하고, 의학적·재정적·법적 조언처럼 단정하지 말고
  "~한 경향이 있다고 전해진다", "~한 기운으로 볼 수 있어요" 같은 부드러운 화법을 써.
- 절대 사람을 겁주거나 불길하다고 단정하지 마. 어떤 특성이든 강점으로 재해석해서 설명해.
- 아래 8개 섹션으로 나누고, 각 섹션은 markdown '#### 제목' 다음에 최소 4~6문장 이상
  풍부하게 서술해:
  1. 총평 — 일간(日干)을 중심으로 타고난 기질 요약
  2. 성격과 기질 — 십성 구성을 근거로
  3. 재물운 — 재성·식상 구성을 근거로
  4. 애정·인간관계운 — 관성·비겁 구성을 근거로
  5. 직업·적성 — 십성과 오행을 근거로 어울리는 분야 제안
  6. 건강 유의점 — 오행 균형을 근거로 (일반적인 생활 습관 조언 수준으로, 진단처럼 말하지 말 것)
  7. 오행 균형과 개운 조언 — 부족/과다한 오행을 채우거나 다스리는 생활 팁
  8. 총운 한 줄 정리
- 전체 분량은 한국어 기준 1500자 이상으로 충분히 길고 구체적으로 작성해."""

GWANSANG_SYSTEM_INSTRUCTION = """너는 친절하고 유머 있는 한국 전통 관상학 해설가야.
사용자가 보낸 얼굴 사진(무표정·미소 등 여러 표정을 보낼 수도 있어)을 보고 전통
관상 화법으로 아주 상세한 개인 맞춤형 한국어 해설을 작성해줘. 참고로 전통
관상학의 삼정(상정/중정/하정), 오악(이마·코·좌우광대·턱), 십이궁(명궁·재백궁·
형제궁·전택궁·남녀궁·노복궁·처첩궁·질액궁·천이궁·관록궁·복덕궁·부모궁), 형·기·신
이론(기색론 — 표정과 눈빛도 함께 본다)을 활용해도 좋아. 함께 제공되는 '참고
자료'는 이 서비스의 관상학 지식 데이터베이스에서 가져온 근거 자료이니, 그 설명을
적극 활용해서 근거 있는 해설을 만들어줘. 사진이 여러 장이면 표정에 따라 달라지는
인상(기색)까지 짚어줘.

지켜야 할 규칙:
- 반드시 외모를 비하하거나 부정적으로 평가하지 마. 모든 특징을 흥미롭고 긍정적인
  강점으로 재해석해서 설명해. 이것은 재미로 보는 콘텐츠임을 인지하고 단정적인
  표현 대신 "~한 인상이에요", "~하다고 전해져요" 같은 부드러운 화법을 써.
- 나이, 인종, 성별을 단정짓거나 신체를 과도하게 특정하는 묘사는 피하고, 관상학적
  해석에 집중해.
- 아래 섹션으로 나누고, 각 섹션은 markdown '#### 제목' 다음에 최소 4~6문장 이상
  풍부하게 서술해:
  1. 전체 인상과 얼굴형 (삼정 균형 포함)
  2. 이마 — 초년운·지혜
  3. 눈썹과 눈 — 대인관계·감정 표현
  4. 코 — 재물운·자존감
  5. 입과 턱 — 말년운·의지·포용력
  6. 십이궁으로 보는 세부 운 (눈에 띄는 2~3개 궁을 골라서)
  7. 표정·기색으로 보는 인상 (사진이 여러 장일 때만, 표정별 차이를 짚어서)
  8. 종합 총평과 이미지 메이킹 팁
- 전체 분량은 한국어 기준 1500자 이상으로 충분히 길고 구체적으로 작성해."""


class GeminiError(RuntimeError):
    pass


def _generate_with_fallback(client: genai.Client, contents, system_instruction: str) -> str:
    last_err = None
    for model in MODEL_CANDIDATES:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=system_instruction),
            )
            if resp.text:
                return resp.text
            last_err = RuntimeError(f"{model}: 빈 응답")
        except Exception as e:  # noqa: BLE001 - 다음 후보 모델로 넘어가기 위해 넓게 처리
            last_err = e
            continue
    raise GeminiError(f"모든 Gemini 모델 호출에 실패했어요: {last_err}")


def _format_db_context(rows: list) -> str:
    if not rows:
        return ""
    lines = []
    for r in rows:
        lines.append(f"- [{r.get('subcategory', r.get('title',''))}] {r.get('body','')}")
    return "\n".join(lines)


def generate_saju_reading(api_key: str, saju_data: dict, db_context: list | None = None) -> str:
    client = genai.Client(api_key=api_key)
    prompt = "다음은 한 사람의 사주팔자 계산 결과야:\n\n" + json.dumps(saju_data, ensure_ascii=False, indent=2)
    ctx_text = _format_db_context(db_context)
    if ctx_text:
        prompt += "\n\n[참고 자료 — 사주학 지식 DB에서 발췌]\n" + ctx_text
    return _generate_with_fallback(client, prompt, SAJU_SYSTEM_INSTRUCTION)


def generate_gwansang_reading(api_key: str, images: list, mime_type: str = "image/jpeg",
                               context: dict | None = None, db_context: list | None = None) -> str:
    """images: [(label, bytes), ...] — 표정별로 촬영한 사진 1장 이상."""
    client = genai.Client(api_key=api_key)
    parts = []
    for label, image_bytes in images:
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
        parts.append(f"(위 사진은 '{label}' 표정입니다.)")

    text = "위 사진 속 얼굴을 관상학적으로 풀이해줘."
    if context:
        text += "\n\n(참고용 얼굴 비율 측정 데이터: " + json.dumps(context, ensure_ascii=False) + ")"
    ctx_text = _format_db_context(db_context)
    if ctx_text:
        text += "\n\n[참고 자료 — 관상학 지식 DB에서 발췌]\n" + ctx_text
    parts.append(text)
    return _generate_with_fallback(client, parts, GWANSANG_SYSTEM_INSTRUCTION)
