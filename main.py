# -*- coding: utf-8 -*-
"""FaceKorea 사주관상 — 웹캠 얼굴 트래킹 + 관상 분석 + 사주팔자 계산 (Streamlit)

세 가지 기능을 탭으로 제공:
  1. "실시간 얼굴 트래킹" — streamlit-webrtc로 브라우저 웹캠 영상을 받아
     mediapipe Face Landmarker로 매 프레임 얼굴 랜드마크를 그려준다.
  2. "관상 분석" — 카메라로 사진 한 장을 찍으면 랜드마크 비율을 계산해
     전통 관상 화법 느낌의 재미용 결과를 보여준다.
  3. "사주 계산" — 생년월일시(양력/음력)를 입력하면 사주팔자(년/월/일/시주)와
     오행 분포를 계산해 보여준다.

⚠️ 관상/사주 결과는 모두 재미로 즐기는 콘텐츠이며 과학적·통계적 근거가 없다.
"""
import time

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import RTCConfiguration, VideoProcessorBase, webrtc_streamer

import gwansang
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
    .gwansang-row{background:#1e1830;border:1px solid #3a2f57;border-radius:10px;
                  padding:10px 14px;margin-bottom:8px;}
    .gwansang-row b{color:#f3d9ff;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🔮 FaceKorea 사주관상")
st.markdown(
    '<div class="disclaimer">이 앱의 관상·사주 풀이는 <b>재미로 즐기는 콘텐츠</b>입니다. '
    "과학적·의학적·역학적 근거가 없으니 참고용으로만 봐주세요. 얼굴 사진과 생년월일 정보는 "
    "서버에 저장되지 않고 현재 세션에서만 사용됩니다.</div>",
    unsafe_allow_html=True,
)

RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

tab_track, tab_gwansang, tab_saju = st.tabs(
    ["🎥 실시간 얼굴 트래킹", "🧑 관상 분석", "📅 사주 계산"]
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
    photo = st.camera_input("정면 사진 촬영", key="gwansang_camera")

    if photo is not None:
        file_bytes = np.frombuffer(photo.getvalue(), dtype=np.uint8)
        img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        with st.spinner("얼굴을 분석하는 중..."):
            pts = gwansang.detect_landmarks_image(img_rgb)

        if pts is None:
            st.warning("얼굴을 찾지 못했어요. 조명을 밝게 하고 정면으로 다시 찍어주세요.")
        else:
            annotated = draw_landmarks(img_bgr.copy(), pts)
            st.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), caption="인식된 얼굴 랜드마크")

            result = gwansang.analyze(pts)
            st.markdown("#### 🧑 관상 풀이")
            for part, (title, desc) in result.items():
                st.markdown(
                    f'<div class="gwansang-row"><b>{part} · {title}</b><br/>{desc}</div>',
                    unsafe_allow_html=True,
                )

# ---------------------------------------------------------------- 탭 3: 사주 계산
with tab_saju:
    st.caption("생년월일시를 입력하면 사주팔자(년/월/일/시주)와 오행 분포를 계산해줘요.")

    c1, c2 = st.columns(2)
    with c1:
        birth_date = st.date_input(
            "생년월일", value=None, min_value=None, max_value=None,
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
                st.markdown(f"**음력 기준**: {result.lunar_date_str} · **띠**: {result.zodiac_kr}띠")

                cols = st.columns(len(result.pillars))
                for col, pillar in zip(cols, result.pillars):
                    with col:
                        st.markdown(
                            f"""
                            <div class="pillar-card">
                              <div class="hanja">{pillar.hanja}</div>
                              <div class="hangul">{pillar.hangul}</div>
                              <div class="label">{pillar.label}</div>
                              <div class="label">{pillar.wuxing_hangul}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                if time_unknown:
                    st.caption("시간을 몰라 시주(時柱)는 계산하지 않았어요.")

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
