# -*- coding: utf-8 -*-
"""FaceKorea 사주관상 — 웹캠 얼굴 트래킹 + 관상 분석 + 사주팔자 계산 (Streamlit)

네 가지 기능을 탭으로 제공:
  1. "실시간 얼굴 트래킹" — streamlit-webrtc로 브라우저 웹캠 영상을 받아
     mediapipe Face Landmarker로 매 프레임 얼굴 랜드마크를 그려준다.
  2. "관상 분석" — 카메라로 사진 한 장을 찍으면 랜드마크 비율 + 삼정/오악/
     십이궁 전통 이론으로 관상 풀이를 보여주고, Gemini에 사진을 직접 보내
     AI 맞춤 해설도 받을 수 있다.
  3. "사주 계산" — 생년월일시(양력/음력)를 입력하면 사주팔자(년/월/일/시주),
     십성·십이운성·지장간·납음오행·공망까지 계산하고, Gemini로 AI 맞춤
     해설을 받을 수 있다.
  4. "PDF 리포트" — 위 결과를 하나의 PDF 문서로 다운로드한다.

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

import gemini_client
import gwansang
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
with st.expander("🔑 Gemini API 키 설정 (AI 맞춤 해설을 받으려면 입력하세요)"):
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

api_key = st.session_state.get("gemini_api_key", "").strip()

RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

tab_track, tab_gwansang, tab_saju, tab_pdf = st.tabs(
    ["🎥 실시간 얼굴 트래킹", "🧑 관상 분석", "📅 사주 계산", "📄 PDF 리포트"]
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


# ---------------------------------------------------------------- 탭 1: 실시간 트래킹
with tab_track:
    st.caption("브라우저가 웹캠 접근을 물어보면 허용해주세요. 얼굴에 초록/노랑 선으로 랜드마크가 그려집니다.")

    class FaceTrackProcessor(VideoProcessorBase):
        def __init__(self) -> None:
            self._start = time.time()

        def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
            img = frame.to_ndarray(format="bgr24")
            try:
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                ts_ms = int((time.time() - self._start) * 1000)
                pts = gwansang.detect_landmarks_video(img_rgb, max(ts_ms, 0))
                if pts is not None:
                    img = draw_landmarks(img, pts)
                else:
                    cv2.putText(img, "얼굴을 인식하지 못했습니다", (14, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
            except Exception:
                pass
            return av.VideoFrame.from_ndarray(img, format="bgr24")

    webrtc_streamer(
        key="face-tracking",
        video_processor_factory=FaceTrackProcessor,
        rtc_configuration=RTC_CONFIGURATION,
        media_stream_constraints={"video": True, "audio": False},
    )

# ---------------------------------------------------------------- 탭 2: 관상 분석
with tab_gwansang:
    st.caption("정면을 보고 사진을 한 장 찍으면, 얼굴 비율을 분석해서 관상 풀이를 보여줘요.")

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

    photo = st.camera_input("정면 사진 촬영", key="gwansang_camera")

    if photo is not None:
        file_bytes = np.frombuffer(photo.getvalue(), dtype=np.uint8)
        img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        with st.spinner("얼굴을 분석하는 중..."):
            pts = gwansang.detect_landmarks_image(img_rgb)

        if pts is None:
            st.warning("얼굴을 찾지 못했어요. 조명을 밝게 하고 정면으로 다시 찍어주세요.")
            st.session_state.pop("gwansang_rule_result", None)
        else:
            annotated = draw_landmarks(img_bgr.copy(), pts)
            st.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), caption="인식된 얼굴 랜드마크")

            rule_result = gwansang.analyze(pts)
            photo_id = hash(photo.getvalue())
            if st.session_state.get("gwansang_photo_id") != photo_id:
                st.session_state["gwansang_photo_id"] = photo_id
                st.session_state.pop("gwansang_ai_text", None)

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
            st.markdown(
                '<div class="consent">✨ 아래 버튼을 누르면 방금 촬영한 사진이 '
                "Google Gemini API로 전송되어 더 상세한 맞춤 해설을 생성합니다.</div>",
                unsafe_allow_html=True,
            )
            if st.button(
                "✨ Gemini로 AI 맞춤 관상 해설 받기", use_container_width=True,
                disabled=not api_key, key="gwansang_ai_btn",
            ):
                try:
                    with st.spinner("Gemini가 얼굴을 분석하고 있어요... (최대 30초 정도 걸려요)"):
                        context = gwansang.analyze_to_prompt_dict(pts)
                        ai_text = gemini_client.generate_gwansang_reading(
                            api_key, photo.getvalue(), "image/jpeg", context=context,
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

# ---------------------------------------------------------------- 탭 3: 사주 계산
with tab_saju:
    st.caption("생년월일시를 입력하면 사주팔자와 십성·십이운성·지장간·납음오행까지 계산해줘요.")

    c1, c2 = st.columns(2)
    with c1:
        birth_date = st.date_input(
            "생년월일", value=None,
            min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today(),
            key="saju_date", format="YYYY-MM-DD",
        )
        calendar_type = st.radio("달력 기준", ["양력", "음력"], horizontal=True, key="saju_cal")
    with c2:
        time_unknown = st.checkbox("태어난 시간 모름", key="saju_time_unknown")
        birth_time = st.time_input(
            "태어난 시각", value=None, key="saju_time", disabled=time_unknown,
        )

    if st.button("사주 계산하기", type="primary", use_container_width=True):
        if birth_date is None:
            st.warning("생년월일을 입력해주세요.")
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

        st.markdown("---")
        if st.button(
            "✨ Gemini로 AI 맞춤 사주 해설 받기", use_container_width=True,
            disabled=not api_key, key="saju_ai_btn",
        ):
            try:
                with st.spinner("Gemini가 사주를 풀이하고 있어요... (최대 30초 정도 걸려요)"):
                    data = saju.saju_to_prompt_dict(result)
                    ai_text = gemini_client.generate_saju_reading(api_key, data)
                st.session_state["saju_ai_text"] = ai_text
            except gemini_client.GeminiError as e:
                st.error(str(e))
        if not api_key:
            st.caption("⬆️ 상단의 'Gemini API 키 설정'에 키를 입력하면 버튼이 활성화돼요.")

        if st.session_state.get("saju_ai_text"):
            st.markdown("#### ✨ AI 맞춤 사주 해설 (Gemini)")
            st.markdown(f'<div class="ai-box">{st.session_state["saju_ai_text"]}</div>',
                        unsafe_allow_html=True)

# ---------------------------------------------------------------- 탭 4: PDF 리포트
with tab_pdf:
    st.caption("지금까지 계산·생성된 사주/관상 결과를 하나의 PDF 리포트로 묶어 다운로드해요.")

    saju_ready = st.session_state.get("saju_result") is not None
    gwansang_ready = st.session_state.get("gwansang_rule_result") is not None

    st.markdown(f"- 사주 계산 결과: {'✅ 있음' if saju_ready else '❌ 없음 (사주 계산 탭에서 먼저 계산하세요)'}")
    st.markdown(f"- 사주 AI 해설: {'✅ 있음' if st.session_state.get('saju_ai_text') else '➖ 없음'}")
    st.markdown(f"- 관상 분석 결과: {'✅ 있음' if gwansang_ready else '❌ 없음 (관상 분석 탭에서 먼저 사진을 찍으세요)'}")
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
