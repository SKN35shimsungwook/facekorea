# -*- coding: utf-8 -*-
"""사주팔자(四柱八字) 심화 계산 — lunar_python 라이브러리 기반.

정밀한 만세력(절기 기준 음력 변환), 십성(十星), 십이운성(十二運星),
지장간(支藏干), 납음오행(納音五行), 공망(空亡), 태원/명궁/신궁까지
lunar_python의 EightChar이 계산한 값을 한글로 다듬어 반환한다.
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
# 오행 생(生) 순환: 목생화, 화생토, 토생금, 금생수, 수생목
WUXING_GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}

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

# 십성(十星)/십신(十神) — 일간(日干) 기준 상대적 오행 생극 관계.
# lunar_python은 간체/정체가 섞여 나오므로 둘 다 매핑해둔다.
SHISHEN_KR = {
    "比肩": "비견", "劫财": "겁재", "劫財": "겁재",
    "食神": "식신", "伤官": "상관", "傷官": "상관",
    "偏财": "편재", "偏財": "편재", "正财": "정재", "正財": "정재",
    "七杀": "편관", "七殺": "편관", "偏官": "편관",
    "正官": "정관",
    "偏印": "편인", "正印": "정인",
}
SHISHEN_BLURB = {
    "비견": "나와 같은 오행·같은 음양의 기운. 자존심이 강하고 독립적이며, 동료와 어깨를 나란히 하려는 힘을 상징한다고 전해져요.",
    "겁재": "나와 같은 오행·다른 음양의 기운. 승부욕과 추진력이 강하고, 필요할 때 과감히 나서는 힘을 상징한다고 전해져요.",
    "식신": "내가 생(生)하는 기운 중 같은 음양. 여유롭고 낙천적이며, 먹고사는 복과 표현력을 상징한다고 전해져요.",
    "상관": "내가 생(生)하는 기운 중 다른 음양. 재기발랄하고 표현이 화려하며, 틀을 깨는 창의력을 상징한다고 전해져요.",
    "편재": "내가 극(剋)하는 기운 중 같은 음양. 통이 크고 사교적이며, 활동적으로 재물을 굴리는 힘을 상징한다고 전해져요.",
    "정재": "내가 극(剋)하는 기운 중 다른 음양. 성실하고 계획적이며, 차곡차곡 쌓는 재물운을 상징한다고 전해져요.",
    "편관": "나를 극(剋)하는 기운 중 같은 음양. 흔히 '칠살'이라 불리며, 강한 추진력과 위기 대응력, 카리스마를 상징한다고 전해져요.",
    "정관": "나를 극(剋)하는 기운 중 다른 음양. 원칙적이고 책임감이 강하며, 명예와 지위를 상징한다고 전해져요.",
    "편인": "나를 생(生)하는 기운 중 같은 음양. 독특한 발상과 직관력, 남다른 전문성을 상징한다고 전해져요.",
    "정인": "나를 생(生)하는 기운 중 다른 음양. 학문과 문서, 어른의 보살핌과 안정적인 배움운을 상징한다고 전해져요.",
}

# 십이운성(十二運星, 포태법) — 일간이 각 지지 위에서 겪는 생로병사 12단계.
DISHI_KR = {
    "长生": "장생", "長生": "장생",
    "沐浴": "목욕",
    "冠带": "관대", "冠帶": "관대",
    "临官": "건록", "臨官": "건록", "建禄": "건록", "建祿": "건록",
    "帝旺": "제왕",
    "衰": "쇠",
    "病": "병",
    "死": "사",
    "墓": "묘",
    "绝": "절", "絶": "절",
    "胎": "태",
    "养": "양", "養": "양",
}
DISHI_BLURB = {
    "장생": "갓 태어난 새싹처럼 시작하는 기운. 새로운 일을 벌이는 순수한 추진력을 상징한다고 전해져요.",
    "목욕": "태어나 씻기는 단계. 변화가 많고 감정 기복이 있지만 매력과 끼가 두드러진다고 전해져요.",
    "관대": "성인이 되어 의관을 갖추는 단계. 자신감이 오르고 사회에 나설 준비를 갖춘 기운이라고 전해져요.",
    "건록": "스스로 녹(祿)을 버는 전성기 초입. 자립심과 실행력이 가장 안정적으로 발휘되는 시기라고 전해져요.",
    "제왕": "인생의 절정, 가장 왕성한 기운. 주도권을 쥐고 앞장서는 리더십을 상징한다고 전해져요.",
    "쇠": "절정을 지나 한 박자 쉬어가는 단계. 노련하고 신중해지며 관리자형 기질이 강해진다고 전해져요.",
    "병": "기운이 한풀 꺾이는 단계. 섬세하고 배려심이 많아지며 남을 돌보는 힘이 커진다고 전해져요.",
    "사": "활동성이 잦아드는 단계. 깊이 몰두하고 한 우물을 파는 집중력을 상징한다고 전해져요.",
    "묘": "기운을 갈무리해 저장하는 단계. 절약하고 계획하는 힘, 축적의 기운을 상징한다고 전해져요.",
    "절": "기운이 끊겼다 다시 이어지기 직전의 단계. 변화와 전환, 새 출발의 씨앗을 상징한다고 전해져요.",
    "태": "새 생명이 잉태되는 단계. 아이디어와 가능성이 움트는 기획력을 상징한다고 전해져요.",
    "양": "태내에서 자라나는 단계. 보호받으며 차근차근 성장하는 안정적인 기운이라고 전해져요.",
}


def hanja_to_kr(ganzhi: str) -> str:
    if not ganzhi or len(ganzhi) < 2:
        return ganzhi
    gan, zhi = ganzhi[0], ganzhi[1]
    return f"{GAN_KR.get(gan, gan)}{ZHI_KR.get(zhi, zhi)}"


def _gan_kr(ch: str) -> str:
    return GAN_KR.get(ch, ch)


def _shishen_kr(hanja: str) -> str:
    return SHISHEN_KR.get(hanja, hanja)


def _dishi_kr(hanja: str) -> str:
    return DISHI_KR.get(hanja, hanja)


@dataclass
class Pillar:
    label: str
    hanja: str
    hangul: str
    wuxing_hanja: str
    shishen_gan: str = ""              # 천간 십성 (일주는 '일원'이라 비워둠)
    shishen_zhi: list = field(default_factory=list)  # 지장간 기준 십성 목록
    dishi: str = ""                    # 십이운성
    hide_gan: list = field(default_factory=list)      # 지장간(한글)
    nayin: str = ""                    # 납음오행 (한자 원문)
    xunkong: str = ""                  # 공망

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
    taiyuan: str = ""     # 태원(胎元)
    minggong: str = ""    # 명궁(命宮)
    shengong: str = ""    # 신궁(身宮)
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

    @property
    def day_master_wuxing(self) -> str:
        """일간(日干)의 오행 한 글자."""
        return self.day.wuxing_hanja[0] if self.day.wuxing_hanja else ""

    def body_strength(self) -> tuple:
        """아주 단순화한 신강/신약 판정.

        여덟 글자의 오행을 일간과 비교해 '같은 편(비겁·인성)' vs
        '다른 편(식상·재성·관성)' 개수를 세는 방식 — 지지 통근(通根)이나
        월령(月令) 같은 정교한 규칙은 생략한 간이 버전임을 밝혀둔다.
        """
        dm = self.day_master_wuxing
        if not dm:
            return ("판정불가", 0, 0)
        same_side = 0   # 비겁(같은 오행) + 인성(나를 생하는 오행)
        other_side = 0  # 식상(내가 생) + 재성(내가 극) + 관성(나를 극)
        for p in self.pillars:
            for ch in p.wuxing_hanja:
                if ch not in WUXING_KR:
                    continue
                if ch == dm or WUXING_GENERATES.get(ch) == dm:
                    same_side += 1
                else:
                    other_side += 1
        label = "신강(身强)" if same_side >= other_side else "신약(身弱)"
        return (label, same_side, other_side)


def compute_saju(
    year: int,
    month: int,
    day: int,
    hour: int = 12,
    minute: int = 0,
    is_lunar: bool = False,
    time_unknown: bool = False,
) -> SajuResult:
    """생년월일시로 사주팔자(십성·십이운성·지장간·납음·공망 포함)를 계산한다.

    time_unknown=True면 시주(時柱)는 계산하지 않는다(시간이 없으면 정확한
    시주를 알 수 없기 때문). 시 입력값은 일주 계산에 영향을 주지 않도록
    정오(12:00)로 고정한다.
    """
    calc_hour = 12 if time_unknown else hour
    calc_minute = 0 if time_unknown else minute

    if is_lunar:
        lunar_in = Lunar.fromYmd(year, month, day)
        solar_date = lunar_in.getSolar()
        solar = Solar.fromYmdHms(
            solar_date.getYear(), solar_date.getMonth(), solar_date.getDay(),
            calc_hour, calc_minute, 0,
        )
    else:
        solar = Solar.fromYmdHms(year, month, day, calc_hour, calc_minute, 0)

    lunar = solar.getLunar()
    ec = lunar.getEightChar()

    year_p = Pillar(
        label="년주(年柱)", hanja=ec.getYear(), hangul=hanja_to_kr(ec.getYear()),
        wuxing_hanja=ec.getYearWuXing(),
        shishen_gan=_shishen_kr(ec.getYearShiShenGan()),
        shishen_zhi=[_shishen_kr(s) for s in ec.getYearShiShenZhi()],
        dishi=_dishi_kr(ec.getYearDiShi()),
        hide_gan=[_gan_kr(g) for g in ec.getYearHideGan()],
        nayin=ec.getYearNaYin(),
        xunkong=ec.getYearXunKong(),
    )
    month_p = Pillar(
        label="월주(月柱)", hanja=ec.getMonth(), hangul=hanja_to_kr(ec.getMonth()),
        wuxing_hanja=ec.getMonthWuXing(),
        shishen_gan=_shishen_kr(ec.getMonthShiShenGan()),
        shishen_zhi=[_shishen_kr(s) for s in ec.getMonthShiShenZhi()],
        dishi=_dishi_kr(ec.getMonthDiShi()),
        hide_gan=[_gan_kr(g) for g in ec.getMonthHideGan()],
        nayin=ec.getMonthNaYin(),
        xunkong=ec.getMonthXunKong(),
    )
    day_p = Pillar(
        label="일주(日柱)", hanja=ec.getDay(), hangul=hanja_to_kr(ec.getDay()),
        wuxing_hanja=ec.getDayWuXing(),
        shishen_gan="일원(日元)",
        shishen_zhi=[_shishen_kr(s) for s in ec.getDayShiShenZhi()],
        dishi=_dishi_kr(ec.getDayDiShi()),
        hide_gan=[_gan_kr(g) for g in ec.getDayHideGan()],
        nayin=ec.getDayNaYin(),
        xunkong=ec.getDayXunKong(),
    )
    time_p = None
    if not time_unknown:
        time_p = Pillar(
            label="시주(時柱)", hanja=ec.getTime(), hangul=hanja_to_kr(ec.getTime()),
            wuxing_hanja=ec.getTimeWuXing(),
            shishen_gan=_shishen_kr(ec.getTimeShiShenGan()),
            shishen_zhi=[_shishen_kr(s) for s in ec.getTimeShiShenZhi()],
            dishi=_dishi_kr(ec.getTimeDiShi()),
            hide_gan=[_gan_kr(g) for g in ec.getTimeHideGan()],
            nayin=ec.getTimeNaYin(),
            xunkong=ec.getTimeXunKong(),
        )

    wuxing_count = {}
    for p in [year_p, month_p, day_p] + ([time_p] if time_p else []):
        for ch in p.wuxing_hanja:
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
        taiyuan=hanja_to_kr(ec.getTaiYuan()),
        minggong=hanja_to_kr(ec.getMingGong()),
        shengong=hanja_to_kr(ec.getShenGong()),
        wuxing_count=wuxing_count,
    )


def saju_to_prompt_dict(result: SajuResult) -> dict:
    """Gemini 프롬프트용 구조화 데이터로 변환."""
    def pillar_dict(p: Pillar) -> dict:
        return {
            "이름": p.label,
            "간지": f"{p.hanja}({p.hangul})",
            "오행": p.wuxing_hangul,
            "십성_천간": p.shishen_gan,
            "십성_지지": p.shishen_zhi,
            "십이운성": p.dishi,
            "지장간": p.hide_gan,
            "납음오행": p.nayin,
            "공망": p.xunkong,
        }

    strength_label, same_n, other_n = result.body_strength()
    return {
        "음력생일": result.lunar_date_str,
        "띠": result.zodiac_kr + "띠",
        "년주": pillar_dict(result.year),
        "월주": pillar_dict(result.month),
        "일주": pillar_dict(result.day),
        "시주": pillar_dict(result.time) if result.time else "모름",
        "태원": result.taiyuan,
        "명궁": result.minggong,
        "신궁": result.shengong,
        "오행분포": {WUXING_KR.get(k, k): v for k, v in result.wuxing_count.items()},
        "신강신약_간이판정": f"{strength_label} (동조 {same_n} : 이조 {other_n})",
    }
