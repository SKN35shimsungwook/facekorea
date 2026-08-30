# -*- coding: utf-8 -*-
"""얼굴 랜드마크 기반 '관상' 분석 (재미용 콘텐츠, 과학적 근거 없음).

mediapipe Face Landmarker(Tasks API)로 얼굴의 468개 랜드마크를 뽑아 각 부위의
비율을 계산하고, 그 비율 구간에 맞는 전통 관상 화법 느낌의 문구를 붙여준다.
모든 문구는 재미로 즐기는 긍정적인 톤으로만 구성했다.
"""
import os
import urllib.request

import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "face_landmarker.task")

# 표준 mediapipe face mesh(468pt) 인덱스 — 얼굴 윤곽/눈/눈썹/입 외곽선을
# 그릴 때 쓰는 순회 순서.
FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397,
             365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58,
             132, 93, 234, 127, 162, 21, 54, 103, 67, 109, 10]
LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159,
            160, 161, 246, 33]
RIGHT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387,
             386, 385, 384, 398, 362]
LIPS_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324,
              318, 402, 317, 14, 87, 178, 88, 95, 61]
LEFT_EYEBROW = [70, 63, 105, 66, 107, 55, 65]
RIGHT_EYEBROW = [336, 296, 334, 293, 300, 285, 295]


def ensure_model() -> str:
    os.makedirs(MODEL_DIR, exist_ok=True)
    if not os.path.exists(MODEL_PATH):
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


_landmarker_cache = {}


def get_landmarker(running_mode: RunningMode = RunningMode.IMAGE) -> FaceLandmarker:
    if running_mode not in _landmarker_cache:
        model_path = ensure_model()
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=running_mode,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        _landmarker_cache[running_mode] = FaceLandmarker.create_from_options(options)
    return _landmarker_cache[running_mode]


def detect_landmarks_image(image_rgb: np.ndarray):
    """정지 이미지 1장에서 얼굴 랜드마크(px 좌표)를 뽑는다. 얼굴 없으면 None."""
    landmarker = get_landmarker(RunningMode.IMAGE)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(image_rgb))
    result = landmarker.detect(mp_image)
    if not result.face_landmarks:
        return None
    h, w = image_rgb.shape[:2]
    lm = result.face_landmarks[0]
    return np.array([[p.x * w, p.y * h] for p in lm], dtype=np.float32)


def detect_landmarks_video(image_rgb: np.ndarray, timestamp_ms: int):
    """비디오 프레임 스트림용(연속 프레임 트래킹에 최적화된 러닝 모드)."""
    landmarker = get_landmarker(RunningMode.VIDEO)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(image_rgb))
    result = landmarker.detect_for_video(mp_image, timestamp_ms)
    if not result.face_landmarks:
        return None
    h, w = image_rgb.shape[:2]
    lm = result.face_landmarks[0]
    return np.array([[p.x * w, p.y * h] for p in lm], dtype=np.float32)


def _dist(pts, i, j) -> float:
    return float(np.linalg.norm(pts[i] - pts[j]))


def _bucket(value: float, low: float, high: float) -> str:
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "mid"


PHRASES = {
    "face_shape": {
        "long": ("긴 얼굴형(장방형)", "차분하고 사려 깊은 인상을 주는 상으로, 장기적인 안목이 필요한 일에서 진가를 발휘하는 얼굴형이라고 봐요."),
        "oval": ("갸름한 계란형", "균형 잡힌 조화형으로, 예로부터 대인관계 운이 좋다고 전해지는 얼굴형이에요."),
        "round_square": ("둥글고 다부진 얼굴형", "결단력 있고 추진력이 좋은 상으로, 한번 마음먹은 일은 끝까지 해내는 뚝심이 느껴지는 얼굴형이에요."),
    },
    "forehead": {
        "high": ("넓고 시원한 이마", "예로부터 지혜와 초년 운을 상징한다고 전해지는 이마예요. 생각이 트여있고 배움을 즐기는 상."),
        "mid": ("반듯하고 균형 잡힌 이마", "무난하고 안정적인 초년 운을 상징한다고 여겨지는 이마예요."),
        "low": ("아담하고 야무진 이마", "실속을 중시하고 현실 감각이 뛰어나다고 전해지는 이마예요."),
    },
    "eyes": {
        "high": ("크고 또렷한 눈매", "표현력이 풍부하고 감정에 솔직하다고 전해지는 눈매예요. 사람을 끌어당기는 매력이 있는 상."),
        "mid": ("균형 잡힌 눈매", "관찰력이 좋고 침착하다고 여겨지는 눈매예요."),
        "low": ("가늘고 깊은 눈매", "속이 깊고 신중하다고 전해지는 눈매예요. 한번 신뢰를 주면 오래가는 상."),
    },
    "eye_gap": {
        "high": ("여유로운 미간", "마음이 넓고 느긋하다고 전해지는 관상 포인트예요."),
        "mid": ("적당한 미간", "균형감 있고 판단이 빠르다고 여겨져요."),
        "low": ("좁고 또렷한 미간", "집중력이 좋고 몰입을 잘한다고 전해지는 상이에요."),
    },
    "nose": {
        "high": ("오뚝하고 시원한 콧대", "재물운과 자존감을 상징한다고 전해지는 코예요. 주관이 뚜렷한 상."),
        "mid": ("균형 잡힌 콧대", "안정적인 재물 관리 능력을 상징한다고 여겨지는 코예요."),
        "low": ("부드럽고 둥근 코끝", "온화하고 사람을 편하게 해주는 인상을 상징한다고 전해져요."),
    },
    "mouth": {
        "high": ("큼직하고 시원한 입매", "리더십과 사교성을 상징한다고 전해지는 입매예요. 말과 행동에 힘이 있는 상."),
        "mid": ("단정한 입매", "신뢰감을 주는 균형 잡힌 입매라고 전해져요."),
        "low": ("아담하고 야무진 입매", "섬세하고 신중한 언행을 상징한다고 여겨지는 입매예요."),
    },
    "eyebrows": {
        "high": ("눈과 가까운 짙은 눈썹", "결단력과 추진력을 상징한다고 전해지는 눈썹이에요."),
        "mid": ("적당히 여유로운 눈썹", "온화하면서도 소신 있는 성격을 상징한다고 여겨져요."),
        "low": ("눈과 여유를 둔 눈썹", "느긋하고 대범한 성격을 상징한다고 전해지는 눈썹이에요."),
    },
}


def analyze(pts: np.ndarray) -> dict:
    """랜드마크 좌표 배열을 받아 부위별 (제목, 설명) 딕셔너리를 반환."""
    face_width = _dist(pts, 234, 454)
    face_height = _dist(pts, 10, 152)
    face_ratio = face_height / face_width if face_width else 0

    jaw_width = _dist(pts, 172, 397)
    jaw_ratio = jaw_width / face_width if face_width else 0

    eye_l_w, eye_l_h = _dist(pts, 33, 133), _dist(pts, 159, 145)
    eye_r_w, eye_r_h = _dist(pts, 362, 263), _dist(pts, 386, 374)
    eye_w = (eye_l_w + eye_r_w) / 2
    eye_h = (eye_l_h + eye_r_h) / 2
    eye_ar = eye_h / eye_w if eye_w else 0

    eye_gap = _dist(pts, 133, 362)
    eye_gap_ratio = eye_gap / face_width if face_width else 0

    nose_width_ratio = _dist(pts, 129, 358) / face_width if face_width else 0

    mouth_width_ratio = _dist(pts, 61, 291) / face_width if face_width else 0

    eyebrow_eye_gap = (_dist(pts, 105, 159) + _dist(pts, 336, 386)) / 2
    eyebrow_ratio = eyebrow_eye_gap / eye_h if eye_h else 0

    eyebrow_mid = (pts[105] + pts[336]) / 2
    forehead_height = float(np.linalg.norm(pts[10] - eyebrow_mid))
    forehead_ratio = forehead_height / face_height if face_height else 0

    if face_ratio > 1.35:
        shape_key = "long"
    elif jaw_ratio > 0.82:
        shape_key = "round_square"
    else:
        shape_key = "oval"

    result = {
        "얼굴형": PHRASES["face_shape"][shape_key],
        "이마": PHRASES["forehead"][_bucket(forehead_ratio, 0.33, 0.42)],
        "눈": PHRASES["eyes"][_bucket(eye_ar, 0.28, 0.38)],
        "미간": PHRASES["eye_gap"][_bucket(eye_gap_ratio, 0.22, 0.28)],
        "코": PHRASES["nose"][_bucket(nose_width_ratio, 0.24, 0.30)],
        "입": PHRASES["mouth"][_bucket(mouth_width_ratio, 0.38, 0.46)],
        "눈썹": PHRASES["eyebrows"][_bucket(eyebrow_ratio, 0.55, 0.85)],
    }
    return result
