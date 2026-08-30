# -*- coding: utf-8 -*-
"""FaceKorea 사주관상 — 웹캠 얼굴 트래킹 + 관상 분석 + 사주팔자 계산 (Streamlit)

다섯 가지 기능을 탭으로 제공:
  1. "관상 분석" — 실시간 웹캠 트래킹 화면에서 무표정·미소·놀람·화남·슬픔 등
     여러 표정을 순서대로 촬영하면, 랜드마크 비율 분석 + 삼정/오악/십이궁
     전통 이론으로 관상 풀이를 보여주고, Gemini에 여러 표정 사진을 함께 보내
     AI 맞춤 해설(기색 변화 포함)도 받을 수 있다.
  2. "사주 계산" — 생년월일시(양력/음력)를 입력하면 사주팔자(년/월/일/시주),
     십성·십이운성·지장간·납음오행·공망까지 계산하고, 성별을 입력하면 대운(大運)
     흐름과 오행 변화 그래프도 볼 수 있다. Gemini로 AI 맞춤 해설도 받을 수 있다.
  3. "종합 컨설팅" — 사주·관상 AI 해설을 종합해 대화형으로 컨설팅을 진행한다.
  4. "PDF 리포트" — 위 결과를 하나의 PDF 문서로 다운로드한다.
  5. "관리자" — 사주학·관상학 지식 데이터베이스(CSV/PDF)를 확인하는 비공개 페이지.

⚠️ 관상/사주 결과는 모두 재미로 즐기는 콘텐츠이며 과학적·통계적 근거가 없다.
   Gemini API 키는 사용자가 화면에서 직접 입력하며, 이 세션에서만 사용되고
   서버 어디에도 저장되지 않는다. AI 관상 해설을 요청하면 촬영한 사진이
   Google Gemini API로 전송된다.
"""
import datetime
import time

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import RTCConfiguration, VideoProcessorBase, webrtc_streamer

import admin
import gemini_client
import gwansang
import knowledge_db as kdb
import pdf_report
import saju

st.set_page_config(page_title="FaceKorea 사주관상", page_icon="🔮", layout="centered")

st.markdown(
    """
    <style>
    .stApp{background:#0e0b16;color:#eee6ff;}
    .disclaimer{background:#1e1830;border:1px solid #3a2f57;border-radius:10px;
                padding:10px 14px;font-size:.85rem;color:#c9bfe8;margin-bottom:12px;}
    .pillar-card{background:#1e1830;border:1px solid #3a2f57;border-radius:12px;
                 padding:14px;text-align:center;}
    .pillar-card .hanja{font-size:1.8rem;font-weight:800;color:#f3d9ff;}
    .pillar-card .hangul{font-size:.95rem;color:#c9bfe8;margin-top:2px;}
    .pillar-card .label{font-size:.72rem;color:#8f84ad;letter-spacing:.05em;margin-top:6px;}
    .pillar-card .detail{font-size:.68rem;color:#a898c8;margin-top:4px;line-height:1.5;}
    .gwansang-row{background:#1e1830;border:1px solid #3a2f57;border-radius:10px;
                  padding:10px 14px;margin-bottom:8px;}
    .gwansang-row b{color:#f3d9ff;}
    .ai-box{background:#241a3a;border:1px solid #4a3a70;border-radius:12px;
            padding:16px 18px;margin-top:10px;}
    .consent{font-size:.78rem;color:#b8a8d8;background:#191327;border:1px dashed #4a3a70;
              border-radius:8px;padding:8px 12px;margin:8px 0;}
    .expr-badge{display:inline-block;background:#3a2f57;color:#f3d9ff;border-radius:999px;
                padding:3px 12px;font-size:.75rem;margin:2px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🔮 FaceKorea 사주관상")
st.markdown(
    '<div class="disclaimer">이 앱의 관상·사주 풀이는 <b>재미로 즐기는 콘텐츠</b>입니다. '
    "과학적·의학적·역학적 근거가 없으니 참고용으로만 봐주세요. 얼굴 사진과 생년월일 정보는 "
    "이 앱 서버에 저장되지 않고 현재 세션에서만 사용됩니다.</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- Gemini API 키
_api_connected = bool(st.session_state.get("gemini_api_key", "").strip())
_expander_label = (
    "🔑 Gemini API 키 설정 — ✅ 연동 완료" if _api_connected
    else "🔑 Gemini API 키 설정 (AI 맞춤 해설을 받으려면 입력하세요)"
)
with st.expander(_expander_label):
    st.caption(
        "[Google AI Studio](https://aistudio.google.com/apikey)에서 무료로 발급받을 수 있어요. "
        "이 키는 이 브라우저 세션에서만 메모리에 보관되고, 앱 서버 파일이나 깃허브에는 "
        "저장되지 않습니다. AI 관상 해설을 요청하면 촬영한 사진이 Google Gemini API로 "
        "직접 전송된다는 점을 참고해주세요."
    )
    st.session_state["gemini_api_key"] = st.text_input(
        "Gemini API 키", type="password",
        value=st.session_state.get("gemini_api_key", ""),
        key="gemini_api_key_input",
    )
    if st.session_state["gemini_api_key"].strip():
        st.success("✅ API 연동 완료 — AI 맞춤 해설 버튼을 쓸 수 있어요.")
    else:
        st.caption("🔌 아직 연동되지 않았어요. 키를 입력하면 자동으로 연동돼요.")

api_key = st.session_state.get("gemini_api_key", "").strip()

RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

EXPRESSIONS = [
    ("무표정", "편안한 표정으로 정면을 바라봐주세요."),
    ("미소", "활짝 웃는 표정을 지어주세요."),
    ("놀람", "눈을 크게 뜨고 놀란 표정을 지어주세요."),
    ("화남", "미간을 찌푸리며 화난 표정을 지어주세요."),
    ("슬픔", "입꼬리를 내리며 슬픈 표정을 지어주세요."),
]

tab_gwansang, tab_saju, tab_consulting, tab_pdf, tab_admin = st.tabs(
    ["🧑 관상 분석 (실시간 카메라)", "📅 사주 계산", "🧭 종합 컨설팅", "📄 PDF 리포트", "🔒 관리자"]
)


# ---------------------------------------------------------------- 유틸: 랜드마크 그리기
def draw_landmarks(img_bgr: np.ndarray, pts: np.ndarray) -> np.ndarray:
    def polyline(indices, color, thickness=1):
        p = pts[indices].astype(np.int32)
        cv2.polylines(img_bgr, [p], isClosed=False, color=color, thickness=thickness, lineType=cv2.LINE_AA)

    polyline(gwansang.FACE_OVAL, (255, 210, 90), 2)
    polyline(gwansang.LEFT_EYE, (140, 230, 255), 1)
    polyline(gwansang.RIGHT_EYE, (140, 230, 255), 1)
    polyline(gwansang.LIPS_OUTER, (180, 140, 255), 1)
    polyline(gwansang.LEFT_EYEBROW, (150, 255, 180), 1)
    polyline(gwansang.RIGHT_EYEBROW, (150, 255, 180), 1)
    for x, y in pts:
        cv2.circle(img_bgr, (int(x), int(y)), 1, (255, 255, 255), -1, lineType=cv2.LINE_AA)
    return img_bgr


class FaceTrackProcessor(VideoProcessorBase):
    """랜드마크를 그려서 보여주는 동시에, 가장 최근 프레임을 저장해뒀다가
    '표정 캡처' 버튼을 누르면 그 프레임을 그대로 가져다 쓸 수 있게 한다."""

    def __init__(self) -> None:
        self._start = time.time()
        self.last_frame = None  # BGR numpy array, 랜드마크 오버레이 없는 원본

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        self.last_frame = img.copy()
        display = img
        try:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            ts_ms = int((time.time() - self._start) * 1000)
            pts = gwansang.detect_landmarks_video(img_rgb, max(ts_ms, 0))
            if pts is not None:
                display = draw_landmarks(img.copy(), pts)
            else:
                display = img.copy()
                cv2.putText(display, "얼굴을 인식하지 못했습니다", (14, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
        except Exception:
            pass
        return av.VideoFrame.from_ndarray(display, format="bgr24")


# ---------------------------------------------------------------- 탭 1: 관상 분석(실시간)
with tab_gwansang:
    st.caption(
        "브라우저가 웹캠 접근을 물어보면 허용해주세요. 화면에 얼굴 랜드마크가 실시간으로 "
        "그려지고, 안내에 따라 표정을 바꿔가며 여러 장을 촬영하면 더 풍부한 관상 해설을 "
        "받을 수 있어요."
    )

    with st.expander("📖 전통 관상학 참고자료 — 삼정·오악·십이궁"):
        st.markdown("**삼정(三停)** — 얼굴을 상/중/하로 나눠 인생 시기를 보는 구획")
        for name, region, desc in gwansang.SAMJEONG:
            st.markdown(f"- **{name}** ({region}): {desc}")
        st.markdown("**오악(五嶽)** — 이마·코·좌우 광대·턱, 다섯 산에 비유")
        for name, desc in gwansang.OAK:
            st.markdown(f"- **{name}**: {desc}")
        st.markdown("**십이궁(十二宮)** — 얼굴 12개 구역에 인생의 영역을 대응")
        for name, region, desc in gwansang.SIBIGUNG:
            st.markdown(f"- **{name}** ({region}): {desc}")

    ctx = webrtc_streamer(
        key="face-tracking",
        video_processor_factory=FaceTrackProcessor,
        rtc_configuration=RTC_CONFIGURATION,
        media_stream_constraints={"video": True, "audio": False},
    )

    captures = st.session_state.setdefault("expr_captures", {})
    step = st.session_state.get("expr_step", 0)

    badges = " ".join(
        f'<span class="expr-badge">{"✅" if label in captures else "⬜"} {label}</span>'
        for label, _ in EXPRESSIONS
    )
    st.markdown(badges, unsafe_allow_html=True)

    if ctx.state.playing:
        if step < len(EXPRESSIONS):
            label, instruction = EXPRESSIONS[step]
            st.info(f"📸 {step + 1}/{len(EXPRESSIONS)} — **{label}**: {instruction}")
            if st.button(f"'{label}' 표정 지금 캡처하기", use_container_width=True, key=f"capture_{step}"):
                frame = ctx.video_processor.last_frame if ctx.video_processor else None
                if frame is None:
                    st.warning("아직 카메라 프레임을 받지 못했어요. 잠시 후 다시 시도해주세요.")
                else:
                    ok, jpg = cv2.imencode(".jpg", frame)
                    if ok:
                        captures[label] = jpg.tobytes()
                        st.session_state["expr_step"] = step + 1
                        st.session_state.pop("gwansang_ai_text", None)
                        st.rerun()
        else:
            st.success("표정 촬영을 모두 마쳤어요! 아래에서 결과를 확인하세요.")
    else:
        st.caption("⬆️ 위 START 버튼을 눌러 카메라를 켜주세요.")

    if captures:
        cols = st.columns(len(captures))
        for col, (label, jpg_bytes) in zip(cols, captures.items()):
            with col:
                st.image(jpg_bytes, caption=label, use_container_width=True)

        if st.button("🔄 다시 촬영하기", key="expr_reset"):
            st.session_state["expr_captures"] = {}
            st.session_state["expr_step"] = 0
            st.session_state.pop("gwansang_ai_text", None)
            st.session_state.pop("gwansang_rule_result", None)
            st.rerun()

        # 측정 기반(무표정 우선) 분석
        base_label = "무표정" if "무표정" in captures else next(iter(captures))
        base_jpg = captures[base_label]
        file_bytes = np.frombuffer(base_jpg, dtype=np.uint8)
        img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pts = gwansang.detect_landmarks_image(img_rgb)

        if pts is None:
            st.warning("촬영한 사진에서 얼굴을 찾지 못했어요. 다시 촬영해주세요.")
        else:
            annotated = draw_landmarks(img_bgr.copy(), pts)
            st.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), caption=f"인식된 얼굴 랜드마크 ({base_label})")

            rule_result = gwansang.analyze(pts)
            st.session_state["gwansang_rule_result"] = rule_result
            ok, annotated_jpg = cv2.imencode(".jpg", annotated)
            st.session_state["gwansang_face_image"] = annotated_jpg.tobytes() if ok else None

            st.markdown("#### 🧑 관상 풀이 (측정 기반)")
            for part, (title, desc) in rule_result.items():
                st.markdown(
                    f'<div class="gwansang-row"><b>{part} · {title}</b><br/>{desc}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("---")
            n_photos = len(captures)
            st.markdown(
                f'<div class="consent">✨ 아래 버튼을 누르면 촬영한 사진 {n_photos}장이 모두 '
                "Google Gemini API로 전송되어 표정 변화까지 반영한 맞춤 해설을 생성합니다.</div>",
                unsafe_allow_html=True,
            )
            if st.button(
                "✨ Gemini로 AI 맞춤 관상 해설 받기", use_container_width=True,
                disabled=not api_key, key="gwansang_ai_btn",
            ):
                try:
                    with st.spinner("Gemini가 얼굴을 분석하고 있어요... (최대 30초 정도 걸려요)"):
                        measure_context = gwansang.analyze_to_prompt_dict(pts)
                        db_context = kdb.find_gwansang_context(rule_result)
                        images = list(captures.items())
                        ai_text = gemini_client.generate_gwansang_reading(
                            api_key, images, "image/jpeg",
                            context=measure_context, db_context=db_context,
                        )
                    st.session_state["gwansang_ai_text"] = ai_text
                except gemini_client.GeminiError as e:
                    st.error(str(e))
            if not api_key:
                st.caption("⬆️ 상단의 'Gemini API 키 설정'에 키를 입력하면 버튼이 활성화돼요.")

            if st.session_state.get("gwansang_ai_text"):
                st.markdown("#### ✨ AI 맞춤 관상 해설 (Gemini)")
                st.markdown(f'<div class="ai-box">{st.session_state["gwansang_ai_text"]}</div>',
                            unsafe_allow_html=True)

# ---------------------------------------------------------------- 탭 2: 사주 계산
with tab_saju:
    st.caption("생년월일시를 입력하면 사주팔자와 십성·십이운성·지장간·납음오행까지 계산해줘요.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("생년월일")
        _this_year = datetime.date.today().year
        ycol, mcol, dcol = st.columns(3)
        with ycol:
            year_sel = st.selectbox(
                "년", ["선택"] + [str(y) for y in range(_this_year, 1949, -1)],
                key="saju_year",
            )
        with mcol:
            month_sel = st.selectbox("월", ["선택"] + [str(m) for m in range(1, 13)], key="saju_month")
        with dcol:
            day_sel = st.selectbox("일", ["선택"] + [str(d) for d in range(1, 32)], key="saju_day")

        birth_date = None
        date_error = False
        if year_sel != "선택" and month_sel != "선택" and day_sel != "선택":
            try:
                birth_date = datetime.date(int(year_sel), int(month_sel), int(day_sel))
            except ValueError:
                date_error = True

        calendar_type = st.radio("달력 기준", ["양력", "음력"], horizontal=True, key="saju_cal")
    with c2:
        time_unknown = st.checkbox("태어난 시간 모름", key="saju_time_unknown")
        birth_time = st.time_input(
            "태어난 시각", value=None, key="saju_time", disabled=time_unknown,
        )
        gender_sel = st.selectbox(
            "성별 (대운·인생 흐름 그래프를 보려면 선택)", ["선택 안 함", "남", "여"],
            key="saju_gender",
        )

    if st.button("사주 계산하기", type="primary", use_container_width=True):
        if date_error:
            st.warning("존재하지 않는 날짜예요. 월/일을 다시 확인해주세요.")
        elif birth_date is None:
            st.warning("생년월일을 년/월/일 모두 선택해주세요.")
        elif birth_time is None and not time_unknown:
            st.warning("태어난 시각을 입력하거나 '태어난 시간 모름'을 체크해주세요.")
        else:
            hour = birth_time.hour if birth_time else 12
            minute = birth_time.minute if birth_time else 0
            try:
                result = saju.compute_saju(
                    birth_date.year, birth_date.month, birth_date.day,
                    hour=hour, minute=minute,
                    is_lunar=(calendar_type == "음력"),
                    time_unknown=time_unknown,
                    gender=(gender_sel if gender_sel in ("남", "여") else None),
                )
            except Exception as e:
                st.error(f"계산 중 오류가 발생했어요: {e}")
            else:
                st.session_state["saju_result"] = result
                st.session_state["saju_time_unknown_snapshot"] = time_unknown
                st.session_state.pop("saju_ai_text", None)

    result = st.session_state.get("saju_result")
    if result is not None:
        st.markdown(f"**음력 기준**: {result.lunar_date_str} · **띠**: {result.zodiac_kr}띠")
        st.caption(f"태원(胎元) {result.taiyuan} · 명궁(命宮) {result.minggong} · 신궁(身宮) {result.shengong}")

        cols = st.columns(len(result.pillars))
        for col, pillar in zip(cols, result.pillars):
            with col:
                zhi_str = "·".join(pillar.shishen_zhi) if pillar.shishen_zhi else "-"
                hidegan_str = "·".join(pillar.hide_gan) if pillar.hide_gan else "-"
                st.markdown(
                    f"""
                    <div class="pillar-card">
                      <div class="hanja">{pillar.hanja}</div>
                      <div class="hangul">{pillar.hangul}</div>
                      <div class="label">{pillar.label}</div>
                      <div class="label">{pillar.wuxing_hangul}</div>
                      <div class="detail">
                        십성(천간) {pillar.shishen_gan or '-'}<br/>
                        십성(지지) {zhi_str}<br/>
                        십이운성 {pillar.dishi}<br/>
                        지장간 {hidegan_str}<br/>
                        납음 {pillar.nayin}<br/>
                        공망 {pillar.xunkong}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if st.session_state.get("saju_time_unknown_snapshot"):
            st.caption("시간을 몰라 시주(時柱)는 계산하지 않았어요.")

        strength_label, same_n, other_n = result.body_strength()
        st.markdown(
            f'<div class="gwansang-row"><b>신강/신약 (간이 판정)</b>: {strength_label} '
            f"— 동조 오행 {same_n}개 : 이조 오행 {other_n}개. "
            "지지 통근이나 월령 등 정교한 규칙은 생략한 단순 버전이에요.</div>",
            unsafe_allow_html=True,
        )

        st.markdown("#### ☯️ 오행(五行) 분포")
        wc = result.wuxing_count
        if wc:
            wcols = st.columns(len(wc))
            for col, (elem, cnt) in zip(wcols, wc.items()):
                with col:
                    st.metric(saju.WUXING_KR.get(elem, elem), f"{cnt}개")

            dom = result.dominant_wuxing
            if dom:
                dom_kr = saju.WUXING_KR.get(dom, dom)
                st.markdown(
                    f'<div class="gwansang-row">가장 두드러진 기운은 <b>{dom_kr}</b>예요. '
                    f'{saju.WUXING_BLURB[dom]}</div>',
                    unsafe_allow_html=True,
                )

        if result.daeun:
            st.markdown("#### 📈 대운(大運)으로 보는 인생 흐름")
            st.caption("10년 단위로 바뀌는 큰 기운의 흐름이에요. 아래는 원국(타고난 8글자)에 각 대운 "
                       "구간의 오행을 더했을 때 오행 균형이 어떻게 움직이는지 보여줘요.")
            daeun_cols = st.columns(len(result.daeun))
            for col, d in zip(daeun_cols, result.daeun):
                with col:
                    st.markdown(
                        f"""
                        <div class="pillar-card">
                          <div class="hanja" style="font-size:1.3rem;">{d.ganzhi}</div>
                          <div class="hangul">{d.hangul}</div>
                          <div class="label">{d.start_age}~{d.end_age}세</div>
                          <div class="label">{d.wuxing_hangul}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            try:
                import pandas as pd
                elem_cols = ["목(木)", "화(火)", "토(土)", "금(金)", "수(水)"]
                rows = []
                for d in result.daeun:
                    counts = dict(result.wuxing_count)
                    for ch in d.wuxing_hanja:
                        counts[ch] = counts.get(ch, 0) + 1
                    row = {"나이대": f"{d.start_age}~{d.end_age}세"}
                    row.update({saju.WUXING_KR.get(k, k): v for k, v in counts.items()})
                    rows.append(row)
                df = pd.DataFrame(rows).set_index("나이대")
                for c in elem_cols:
                    if c not in df.columns:
                        df[c] = 0
                st.line_chart(df[elem_cols])
            except Exception:
                pass

        st.markdown("---")
        if st.button(
            "✨ Gemini로 AI 맞춤 사주 해설 받기", use_container_width=True,
            disabled=not api_key, key="saju_ai_btn",
        ):
            try:
                with st.spinner("Gemini가 사주를 풀이하고 있어요... (최대 30초 정도 걸려요)"):
                    data = saju.saju_to_prompt_dict(result)
                    db_context = kdb.find_saju_context(data)
                    ai_text = gemini_client.generate_saju_reading(api_key, data, db_context=db_context)
                st.session_state["saju_ai_text"] = ai_text
            except gemini_client.GeminiError as e:
                st.error(str(e))
        if not api_key:
            st.caption("⬆️ 상단의 'Gemini API 키 설정'에 키를 입력하면 버튼이 활성화돼요.")

        if st.session_state.get("saju_ai_text"):
            st.markdown("#### ✨ AI 맞춤 사주 해설 (Gemini)")
            st.markdown(f'<div class="ai-box">{st.session_state["saju_ai_text"]}</div>',
                        unsafe_allow_html=True)

# ---------------------------------------------------------------- 탭 3: 종합 컨설팅
with tab_consulting:
    st.caption(
        "사주·관상 AI 해설을 종합해서 컨설팅해줘요. 첫 답변 끝에 나오는 질문에 답하면 "
        "더 맞춤화된 조언으로 이어집니다."
    )

    saju_ai = st.session_state.get("saju_ai_text")
    gwansang_ai = st.session_state.get("gwansang_ai_text")

    if not saju_ai and not gwansang_ai:
        st.info(
            "먼저 '사주 계산' 탭이나 '관상 분석' 탭에서 Gemini AI 맞춤 해설을 한 번 이상 "
            "받아보세요. 그 결과를 바탕으로 종합 컨설팅을 시작할 수 있어요."
        )
    elif not api_key:
        st.warning("⬆️ 상단의 'Gemini API 키 설정'에 키를 입력해주세요.")
    else:
        messages = st.session_state.setdefault("consulting_messages", [])

        if not messages:
            have = []
            if saju_ai:
                have.append("사주 해설")
            if gwansang_ai:
                have.append("관상 해설")
            st.markdown(f"현재 반영 가능한 자료: **{' · '.join(have)}**")
            if st.button("🧭 종합 컨설팅 시작하기", type="primary", use_container_width=True, key="consulting_start"):
                intro_parts = ["아래는 이미 생성된 사주/관상 해설이야. 이를 바탕으로 컨설팅을 시작해줘."]
                if saju_ai:
                    intro_parts.append("## 사주 해설\n" + saju_ai)
                if gwansang_ai:
                    intro_parts.append("## 관상 해설\n" + gwansang_ai)
                try:
                    with st.spinner("Gemini가 사주와 관상을 종합하고 있어요... (최대 30초 정도 걸려요)"):
                        history = [{"role": "user", "text": "\n\n".join(intro_parts)}]
                        reply = gemini_client.generate_consulting_reply(api_key, history)
                    history.append({"role": "model", "text": reply})
                    st.session_state["consulting_messages"] = history
                    st.rerun()
                except gemini_client.GeminiError as e:
                    st.error(str(e))
        else:
            for i, msg in enumerate(messages):
                if i == 0:
                    continue  # 첫 메시지(내부 종합 프롬프트)는 화면에 표시하지 않음
                with st.chat_message("assistant" if msg["role"] == "model" else "user"):
                    st.markdown(msg["text"])

            user_input = st.chat_input("컨설턴트의 질문에 답하거나, 궁금한 점을 물어보세요")
            if user_input:
                messages.append({"role": "user", "text": user_input})
                try:
                    with st.spinner("Gemini가 답변을 준비하고 있어요..."):
                        reply = gemini_client.generate_consulting_reply(api_key, messages)
                    messages.append({"role": "model", "text": reply})
                except gemini_client.GeminiError as e:
                    st.error(str(e))
                    messages.pop()
                st.rerun()

            st.markdown("---")
            if st.button("🔄 컨설팅 새로 시작하기", key="consulting_reset"):
                st.session_state["consulting_messages"] = []
                st.rerun()

# ---------------------------------------------------------------- 탭 4: PDF 리포트
with tab_pdf:
    st.caption("지금까지 계산·생성된 사주/관상 결과를 하나의 PDF 리포트로 묶어 다운로드해요.")

    saju_ready = st.session_state.get("saju_result") is not None
    gwansang_ready = st.session_state.get("gwansang_rule_result") is not None

    st.markdown(f"- 사주 계산 결과: {'✅ 있음' if saju_ready else '❌ 없음 (사주 계산 탭에서 먼저 계산하세요)'}")
    st.markdown(f"- 사주 AI 해설: {'✅ 있음' if st.session_state.get('saju_ai_text') else '➖ 없음'}")
    st.markdown(f"- 관상 분석 결과: {'✅ 있음' if gwansang_ready else '❌ 없음 (관상 분석 탭에서 먼저 표정을 촬영하세요)'}")
    st.markdown(f"- 관상 AI 해설: {'✅ 있음' if st.session_state.get('gwansang_ai_text') else '➖ 없음'}")

    if not saju_ready and not gwansang_ready:
        st.info("사주 계산이나 관상 분석을 먼저 진행하면 PDF를 만들 수 있어요.")
    else:
        if st.button("📄 PDF 리포트 만들기", type="primary", use_container_width=True):
            with st.spinner("PDF를 만드는 중이에요..."):
                pdf_bytes = pdf_report.build_pdf(
                    saju_result=st.session_state.get("saju_result"),
                    saju_ai_text=st.session_state.get("saju_ai_text"),
                    gwansang_table=st.session_state.get("gwansang_rule_result"),
                    gwansang_ai_text=st.session_state.get("gwansang_ai_text"),
                    face_image_bytes=st.session_state.get("gwansang_face_image"),
                    generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                )
            st.session_state["pdf_bytes"] = pdf_bytes
            st.success("PDF가 준비됐어요!")

        if st.session_state.get("pdf_bytes"):
            st.download_button(
                "⬇️ PDF 다운로드", data=st.session_state["pdf_bytes"],
                file_name="facekorea_사주관상_리포트.pdf", mime="application/pdf",
                use_container_width=True,
            )

# ---------------------------------------------------------------- 탭 5: 관리자
with tab_admin:
    admin.render()
