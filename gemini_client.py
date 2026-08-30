# -*- coding: utf-8 -*-
"""Gemini API 연동 — 사주/관상 계산 결과를 바탕으로 개인 맞춤 해설을 생성한다.

API 키는 사용자가 앱 화면에서 직접 입력한 값만 사용하고, 이 모듈 어디에도
저장/로깅하지 않는다. 무료 API 키는 모델별로 분당/일일 호출 한도가 다른데,
Flash-Lite 계열이 가장 한도가 넉넉해서 먼저 시도하고, 혹시 그 모델을 쓸 수
없는 키/리전이면 일반 Flash 계열로 자동 전환한다.
"""
import json

from google import genai
from google.genai import types

MODEL_CANDIDATES = [
    "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.5-flash",
]

SAJU_SYSTEM_INSTRUCTION = """너는 친절하고 유머 있는 한국 사주명리학 해설가야.
아래 JSON으로 주어진 사주팔자(년/월/일/시주, 십성, 십이운성, 지장간, 납음오행,
공망, 오행분포, 신강신약, 있다면 대운大運 목록)를 바탕으로 아주 상세하고 개인
맞춤형으로 한국어 해설을 작성해줘. 함께 제공되는 '참고 자료'는 이 서비스의
사주학 지식 데이터베이스에서 가져온 근거 자료이니, 그 설명을 적극 활용해서
근거 있는 해설을 만들어줘.

지켜야 할 규칙:
- 이것은 재미로 보는 콘텐츠임을 인지하고, 의학적·재정적·법적 조언처럼 단정하지 말고
  "~한 경향이 있다고 전해진다", "~한 기운으로 볼 수 있어요" 같은 부드러운 화법을 써.
- 절대 사람을 겁주거나 불길하다고 단정하지 마. 어떤 특성이든 강점으로 재해석해서 설명해.
- 아래 섹션으로 나누고, 각 섹션은 markdown '#### 제목' 다음에 최소 4~6문장 이상
  풍부하고 구체적으로(추상적인 표현 대신 실제 생활 장면을 예로 들어가며) 서술해:
  1. 총평 — 일간(日干)을 중심으로 타고난 기질 요약
  2. 성격과 기질 — 십성 구성을 근거로
  3. 재물운 — 재성·식상 구성을 근거로 (자산 형성 스타일, 어울리는 재테크 성향까지)
  4. 연애운 — 도화살·관성·재성 등을 근거로 (어떤 상대에게 끌리는지, 연애 스타일)
  5. 가족·인간관계운 — 비겁·형제궁 등을 근거로 (가족·형제·친구 관계의 패턴)
  6. 직업·적성 — 십성과 오행을 근거로, 구체적인 직군·업무 스타일을 3가지 이상 예시로 제안
  7. 사업·리더십운 — 편관·편재 등을 근거로 (창업이 맞는 사주인지, 조직 생활이 맞는지)
  8. 건강 유의점 — 오행 균형을 근거로 (일반적인 생활 습관 조언 수준으로, 진단처럼 말하지 말 것)
  9. 인생 흐름(대운) — 대운 목록이 주어졌다면, 각 대운 구간(나이대)마다 들어오는
     오행/십성이 원국과 어떻게 어우러지는지 구간별로 짚어가며 인생의 큰 흐름을
     서술해줘. 대운 정보가 없다면 이 섹션은 생략해.
  10. 오행 균형과 개운 조언 — 부족/과다한 오행을 채우거나 다스리는 생활 팁
  11. 총운 한 줄 정리
- 전체 분량은 한국어 기준 2000자 이상으로 충분히 길고 구체적으로 작성해."""

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


CONSULTING_SYSTEM_INSTRUCTION = """너는 사주명리학과 관상학을 모두 아는 따뜻하고
통찰력 있는 인생 컨설턴트야. 사용자의 사주 해설과 관상 해설(둘 다 이미 생성되어
아래에 제공됨)을 종합해서, 두 관점이 서로 어떻게 맞아떨어지는지·보완되는지를
짚어가며 하나의 일관된 그림으로 컨설팅해줘.

첫 번째 대답에서는:
1. #### 종합 총평 — 사주와 관상 두 해설의 공통된 핵심 메시지를 한 문단으로 정리
2. #### 강점과 활용법 — 가장 두드러지는 강점 2~3가지와 실생활 활용 팁
3. #### 보완하면 좋을 점 — 부드러운 화법으로, 비판이 아니라 성장 포인트로
4. #### 추천 직업·진로 — 구체적인 직군 4~5가지를 이유와 함께
그다음 반드시 사용자에게 되물을 질문을 2~3개 던져줘(예: "요즘 가장 고민되는
분야가 있다면 무엇인가요?", "지금 하시는 일에 만족하시나요?" 등) — 그 답을 듣고
더 맞춤화된 조언을 이어가기 위해서야.

이후 사용자가 답하면, 그 답변을 사주/관상 해석과 연결지어 더 구체적이고
실천 가능한 조언을 이어가. 매번 필요하면 자연스럽게 후속 질문을 하나씩 덧붙여도
좋아(강요하지는 말고).

지켜야 할 규칙:
- 항상 존중하는 태도로, 단정적이지 않게, 근거(사주/관상 어느 부분에서 그렇게
  해석했는지)를 함께 밝히면서 이야기해.
- 의학적·정신건강·법률·재정 관련 위기 신호가 사용자 발화에서 보이면, 반드시
  "저는 전문 상담사가 아니니 관련 전문가와 상담해보시길 권해요"라고 안내하고
  일반적인 조언만 제공해.
- markdown 헤딩(####)과 문단을 적절히 활용해서 읽기 쉽게 구성해."""


def generate_consulting_reply(api_key: str, history: list) -> str:
    """history: [{"role": "user"|"model", "text": "..."}, ...] 순서의 대화 기록."""
    client = genai.Client(api_key=api_key)
    contents = [
        types.Content(role=turn["role"], parts=[types.Part.from_text(text=turn["text"])])
        for turn in history
    ]
    return _generate_with_fallback(client, contents, CONSULTING_SYSTEM_INSTRUCTION)
