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
├── admin.py                     # "참고자료" 탭 (지식DB 열람) — 원래 관리자 비밀번호로 잠겨있었음
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

## 트러블슈팅

Streamlit Cloud에 배포하면서 실제로 겪은 문제들을 원인과 코드 변경 기준으로 정리했어요.

**① Streamlit Cloud에서 `cv2` import부터 실패함 (`ImportError`)**

- 원인: Streamlit Cloud의 최소 컨테이너에는 `libGL.so.1`이 없는데, 일반 `opencv-python`은
  GUI 기능을 전혀 안 써도 이 라이브러리를 필요로 함.
- 해결: `opencv-python` → `opencv-python-headless`로 교체 + `packages.txt`로 필요한 시스템
  라이브러리를 apt로 설치.

```diff
- opencv-python>=4.9
+ opencv-python-headless>=4.9
```
```
+ libgl1
+ libglib2.0-0
+ libsm6
+ libxext6
+ libxrender1
```

**② 위 수정 후에도 배포가 깨짐 — `libglib2.0-0`이 base 이미지와 충돌**

- 원인: `libglib2.0-0`을 명시적으로 요청했더니 bullseye 버전이 딸려오면서, Streamlit Cloud의
  trixie 기반 이미지와 충돌해서(`libffi7` 없음) apt 자체가 실패함. 애초에 진짜 없는 건 `libgl1`
  하나뿐이었고, 나머지는 base 이미지에 이미 있었음.
- 해결: `packages.txt`를 `libgl1` 한 줄로 축소.

**③ `libgl1`만 남겼더니 이번엔 mediapipe가 `OSError`로 죽음 (EGL 관련)**

- 원인 (①②와는 별개의 문제): Debian이 64비트 time_t 전환 때문에 `libglib2.0-0`을
  `libglib2.0-0t64`로 이름을 바꿨는데, trixie 이미지는 새 이름만 제공함. 게다가 mediapipe는
  CPU 추론만 써도 GPU delegate가 런타임에 `libGLESv2`/EGL을 `dlopen`을 시도해서 별도로 죽음.
- 해결: `packages.txt`에 올바른 이름(`libglib2.0-0t64`)과 `libegl1` / `libgles2` / `libgomp1`을
  추가. 최종 `packages.txt`:

```
libgl1
libglib2.0-0t64
libegl1
libgles2
libgomp1
```

**④ 생년월일 선택 캘린더에서 연도를 1950년까지 못 내려감**

- 원인: `st.date_input`의 달력 팝업이 `min_value`를 줬는데도 연도 드롭다운을 최근 ~19년치만
  보여주는 스트림릿 자체의 UI 한계에 걸림.
- 해결: 캘린더 위젯 대신 년/월/일을 각각 `st.selectbox`로 분리 — 타이핑으로 필터링하면
  1950년까지 안정적으로 도달 가능.

**⑤ Gemini API 키를 넣어도 연동됐는지 화면에서 알기 어려움**

- 해결: 키가 입력되면 expander 제목 자체가 "🔑 Gemini API 키 설정 — ✅ 연동 완료"로 바뀌고,
  본문에도 `st.success("✅ API 연동 완료...")` 표시가 뜨도록 추가.

**⑥ 관리자 비밀번호가 실수로 커밋될 뻔함**

- 원인: `.streamlit/secrets.toml`(관리자 비밀번호 저장 파일)이 `.gitignore`에 빠져있었음.
- 해결: `.gitignore`에 `.streamlit/secrets.toml` 추가. 이후 사용자 요청으로 "참고자료" 탭에는
  민감한 개인정보가 없다는 판단 하에 비밀번호 게이트 자체를 제거하고 탭 이름도
  🔒 관리자 → 📚 참고자료로 바꿈.

---

🤖 이 저장소의 README는 Claude Code와 함께 작성했어요.
