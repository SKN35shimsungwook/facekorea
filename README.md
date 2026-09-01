# 🔮 FaceKorea 사주관상

웹캠으로 표정을 찍으면 **관상**을 봐주고, 생년월일시를 입력하면 **사주팔자**를 계산해주는
Streamlit 웹앱이에요. AI(Gemini)가 그 결과를 바탕으로 맞춤 해설도 해줘요.

> ⚠️ 관상/사주 결과는 재미로 즐기는 콘텐츠이며 과학적·통계적 근거가 없습니다.

## 기능

앱 안에서 탭으로 5가지 기능을 제공해요.

| 탭 | 뭘 하나요? |
|---|---|
| **관상 분석** | 웹캠으로 무표정·미소·놀람·화남·슬픔 등 여러 표정을 순서대로 촬영 → 얼굴 랜드마크 비율 분석 + 삼정/오악/십이궁 전통 이론으로 풀이 → Gemini에 사진들을 보내 AI 맞춤 해설(기색 변화 포함)도 받을 수 있음 |
| **사주 계산** | 생년월일시(양력/음력) 입력 → 사주팔자(년/월/일/시주), 십성·십이운성·지장간·납음오행·공망 계산, 성별 입력 시 대운(大運) 흐름과 오행 변화 그래프까지. Gemini AI 해설도 가능 |
| **종합 컨설팅** | 사주·관상 AI 해설을 종합해서 대화형으로 컨설팅 진행 |
| **PDF 리포트** | 위 결과를 PDF 문서 하나로 다운로드 |
| **참고자료** | 사주학·관상학 지식 데이터베이스(CSV/PDF) 열람 |

## 기술 스택

| 기술 | 역할 |
|---|---|
| **Streamlit** | 웹앱 화면 전체 |
| **streamlit-webrtc** | 브라우저 웹캠 영상을 실시간으로 서버에 스트리밍 |
| **MediaPipe** | 얼굴의 랜드마크(눈·코·입 등 특징점) 좌표를 실시간으로 추출 |
| **OpenCV** | 영상 프레임 처리 |
| **lunar_python** | 양력 ↔ 음력 변환, 사주 계산의 기반 |
| **Google Gemini API** (`google-genai`) | 촬영한 표정 사진과 사주 데이터를 바탕으로 AI 맞춤 해설 생성 |
| **fpdf2** | 분석 결과를 PDF 리포트로 출력 |
| **pandas** | 관상학/사주학 지식 데이터베이스(CSV) 처리 |

## 파일 구조

```
facekorea/
├── main.py                    # Streamlit 앱 진입점, 5개 탭 구성
├── gwansang.py                 # 관상 분석 로직 (랜드마크 → 얼굴 비율/이론 풀이)
├── saju.py                     # 사주팔자 계산 로직
├── gemini_client.py             # Gemini API 호출 (AI 해설)
├── pdf_report.py                 # PDF 리포트 생성
├── knowledge_db.py / knowledge_data.py / knowledge_extra.py / knowledge_pdf.py
│                                 # 사주학·관상학 지식 데이터베이스 관리
├── admin.py                     # 관리 기능
├── data/
│   ├── gwansang_knowledge.csv
│   └── saju_knowledge.csv
├── packages.txt                 # Streamlit Cloud 배포용 시스템 패키지 목록
└── requirements.txt
```

## 실행하기

```bash
pip install -r requirements.txt
streamlit run main.py
```

Gemini API 키는 화면에서 직접 입력하며, 이 세션에서만 사용되고 서버에 저장되지 않아요.
AI 해설을 요청하면 촬영한 사진이 Google Gemini API로 전송돼요.

---

🤖 이 저장소의 README는 Claude Code와 함께 작성했어요.
