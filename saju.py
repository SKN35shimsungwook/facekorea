# -*- coding: utf-8 -*-
"""사주팔자(四柱八字) 계산 — lunar_python 라이브러리 기반.

정밀한 만세력(절기 기준 음력 변환)은 lunar_python이 처리하고, 여기서는
결과를 한글로 다듬고 오행 통계·간단한 총평 문구를 붙이는 역할만 한다.
"""
from dataclasses import dataclass, field

from lunar_python import Lunar, Solar

GAN_KR = {
    "甲": "갑", "乙": "을", "丙": "병", "丁": "정", "戊": "무",
    "己": "기", "庚": "경", "辛": "신", "壬": "임", "癸": "계",
}
ZHI_KR = {
    "子": "자", "丑": "축", "寅": "인", "卯": "묘", "辰": "진", "巳": "사",
    "午": "오", "未": "미", "申": "신", "酉": "유", "戌": "술", "亥": "해",
}
WUXING_KR = {"木": "목(木)", "火": "화(火)", "土": "토(土)", "金": "금(金)", "水": "수(水)"}
ZODIAC_KR = {
    "鼠": "쥐", "牛": "소", "虎": "호랑이", "兔": "토끼", "蛇": "뱀",
    "羊": "양", "猴": "원숭이", "狗": "개",
    # lunar_python은 일부 글자를 간체로 반환하므로(龙/马/鸡/猪) 정자/간체 모두 매핑.
    "龍": "용", "龙": "용",
    "馬": "말", "马": "말",
    "雞": "닭", "鸡": "닭",
    "豬": "돼지", "猪": "돼지",
}

WUXING_BLURB = {
    "木": "성장과 추진력을 뜻하는 기운이 두드러져요. 새로운 일을 밀어붙이는 힘이 강한 편.",
    "火": "열정과 표현력을 뜻하는 기운이 두드러져요. 사람들 앞에서 에너지가 잘 드러나는 편.",
    "土": "안정과 신뢰를 뜻하는 기운이 두드러져요. 묵묵히 중심을 잡아주는 역할을 하는 편.",
    "金": "결단력과 원칙을 뜻하는 기운이 두드러져요. 맺고 끊는 게 분명한 편.",
    "水": "지혜와 유연함을 뜻하는 기운이 두드러져요. 상황에 맞춰 잘 흘러가는 편.",
}


def hanja_to_kr(ganzhi: str) -> str:
    if not ganzhi or len(ganzhi) < 2:
        return ganzhi
    gan, zhi = ganzhi[0], ganzhi[1]
    return f"{GAN_KR.get(gan, gan)}{ZHI_KR.get(zhi, zhi)}"


@dataclass
class Pillar:
    label: str
    hanja: str
    hangul: str
    wuxing_hanja: str

    @property
    def wuxing_hangul(self) -> str:
        return "".join(WUXING_KR.get(c, c) + " " for c in self.wuxing_hanja).strip()


@dataclass
class SajuResult:
    year: Pillar
    month: Pillar
    day: Pillar
    time: Pillar | None
    zodiac_kr: str
    lunar_date_str: str
    wuxing_count: dict = field(default_factory=dict)

    @property
    def pillars(self):
        pillars = [self.year, self.month, self.day]
        if self.time is not None:
            pillars.append(self.time)
        return pillars

    @property
    def dominant_wuxing(self):
        if not self.wuxing_count:
            return None
        return max(self.wuxing_count, key=self.wuxing_count.get)


def compute_saju(
    year: int,
    month: int,
    day: int,
    hour: int = 12,
    minute: int = 0,
    is_lunar: bool = False,
    time_unknown: bool = False,
) -> SajuResult:
    """생년월일시로 사주팔자를 계산한다.

    time_unknown=True면 시주(時柱)는 계산하지 않고 년/월/일주만 반환한다.
    (시간이 없으면 정확한 시주를 알 수 없기 때문. 시 입력값은 일주 계산에
    영향을 주지 않도록 정오(12:00)로 고정한다.)
    """
    calc_hour = 12 if time_unknown else hour
    calc_minute = 0 if time_unknown else minute

    if is_lunar:
        lunar = Lunar.fromYmd(year, month, day)
        solar_date = lunar.getSolar()
        solar = Solar.fromYmdHms(
            solar_date.getYear(), solar_date.getMonth(), solar_date.getDay(),
            calc_hour, calc_minute, 0,
        )
    else:
        solar = Solar.fromYmdHms(year, month, day, calc_hour, calc_minute, 0)

    lunar = solar.getLunar()
    ec = lunar.getEightChar()

    year_p = Pillar("년주(年柱)", ec.getYear(), hanja_to_kr(ec.getYear()), ec.getYearWuXing())
    month_p = Pillar("월주(月柱)", ec.getMonth(), hanja_to_kr(ec.getMonth()), ec.getMonthWuXing())
    day_p = Pillar("일주(日柱)", ec.getDay(), hanja_to_kr(ec.getDay()), ec.getDayWuXing())
    time_p = None
    if not time_unknown:
        time_p = Pillar("시주(時柱)", ec.getTime(), hanja_to_kr(ec.getTime()), ec.getTimeWuXing())

    wuxing_count = {}
    wuxing_source = [year_p.wuxing_hanja, month_p.wuxing_hanja, day_p.wuxing_hanja]
    if time_p is not None:
        wuxing_source.append(time_p.wuxing_hanja)
    for pair in wuxing_source:
        for ch in pair:
            if ch in WUXING_KR:
                wuxing_count[ch] = wuxing_count.get(ch, 0) + 1

    zodiac_kr = ZODIAC_KR.get(lunar.getYearShengXiao(), lunar.getYearShengXiao())

    return SajuResult(
        year=year_p,
        month=month_p,
        day=day_p,
        time=time_p,
        zodiac_kr=zodiac_kr,
        lunar_date_str=lunar.toString(),
        wuxing_count=wuxing_count,
    )
