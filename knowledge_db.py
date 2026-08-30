# -*- coding: utf-8 -*-
"""사주학·관상학 지식 베이스를 하나의 표(DataFrame/CSV)로 만들고, 조회하는 모듈.

knowledge_data.py에 있는 원본 자료를 평탄화해서
  data/saju_knowledge.csv
  data/gwansang_knowledge.csv
두 파일로 내보내고(export_all_csv), 다시 그 CSV를 읽어(load_*) 관리자
페이지·PDF·Gemini 프롬프트 근거자료 삽입에 쓴다. CSV가 '단일 진실 공급원'이 되도록
설계했다 — knowledge_data.py를 고치고 export_all_csv()를 다시 돌리면 CSV/DB가 갱신된다.
"""
import csv
import os
from datetime import date, timedelta

import knowledge_data as kd
import knowledge_extra as ke

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SAJU_CSV_PATH = os.path.join(DATA_DIR, "saju_knowledge.csv")
GWANSANG_CSV_PATH = os.path.join(DATA_DIR, "gwansang_knowledge.csv")

CSV_FIELDS = ["id", "domain", "category", "subcategory", "hanja", "hangul", "title", "body", "source"]


def _src(key: str) -> str:
    return kd.SOURCES.get(key, "")


def _has_batchim(word: str) -> bool:
    if not word:
        return False
    code = ord(word[-1]) - 0xAC00
    if 0 <= code <= 11171:
        return code % 28 != 0
    return False


def _eun_neun(word: str) -> str:
    return "은" if _has_batchim(word) else "는"


def _gwa_wa(word: str) -> str:
    return "과" if _has_batchim(word) else "와"


def _i_ga(word: str) -> str:
    return "이" if _has_batchim(word) else "가"


def _generate_ganzi60():
    """60갑자와 납음오행을 lunar_python으로 정확히 계산해서 반환한다."""
    from lunar_python import Solar

    seen = {}
    start = date(2000, 1, 1)
    day = start
    while len(seen) < 60:
        s = Solar.fromYmdHms(day.year, day.month, day.day, 12, 0, 0)
        ec = s.getLunar().getEightChar()
        gz = ec.getDay()
        if gz not in seen:
            seen[gz] = ec.getDayNaYin()
        day += timedelta(days=1)
    # 갑자 순서(甲子부터 60개 정렬)로 정렬해서 반환
    GAN = "甲乙丙丁戊己庚辛壬癸"
    ZHI = "子丑寅卯辰巳午未申酉戌亥"
    ordered = []
    for i in range(60):
        gz = GAN[i % 10] + ZHI[i % 12]
        ordered.append((gz, seen[gz]))
    return ordered


def build_saju_entries() -> list:
    entries = []
    idx = 1

    def add(category, subcategory, hanja, hangul, title, body, source_key):
        nonlocal idx
        entries.append({
            "id": f"S{idx:03d}", "domain": "사주학", "category": category,
            "subcategory": subcategory, "hanja": hanja, "hangul": hangul,
            "title": title, "body": body, "source": _src(source_key),
        })
        idx += 1

    for e in kd.SAJU_ESSAYS:
        add("이론", e["subcategory"], "", "", e["title"], e["body"], e["source_key"])

    for hanja, hangul, title, body in kd.WUXING_ITEMS:
        add("오행", hangul, hanja, hangul, title, body, "wikipedia_saju")

    for hanja, hangul, title, body in kd.CHEONGAN_ITEMS:
        extra = ke.EXTRA_CHEONGAN.get(hangul, "")
        add("천간", f"{hangul}({hanja})", hanja, hangul, title, f"{body} {extra}".strip(), "daumcafe_cheongan")

    for hanja, hangul, animal, timerange, season, body in kd.JIJI_ITEMS:
        title = f"{hangul}({hanja}) — {animal}띠, {timerange}"
        extra = ke.EXTRA_JIJI.get(hangul, "")
        full_body = f"{body} 계절 구분상 {season}에 해당합니다. {extra}".strip()
        add("지지", f"{hangul}({hanja})", hanja, hangul, title, full_body, "namuwiki_12ji")

    for name, hanja, subtitle, body in kd.SIPSEONG_ITEMS:
        extra = ke.EXTRA_SIPSEONG.get(name, "")
        add("십성", name, hanja, name, f"{name}({hanja}) — {subtitle}", f"{body} {extra}".strip(), "sajustudy_sipseong")

    for name, hanja, subtitle, body in kd.DISHI_ITEMS:
        extra = ke.EXTRA_DISHI.get(name, "")
        add("십이운성", name, hanja, name, f"{name}({hanja}) — {subtitle}", f"{body} {extra}".strip(), "sajustudy_12unseong")

    for name, hanja, subtitle, body in kd.SINSAL_ITEMS:
        extra = ke.EXTRA_SINSAL.get(name, "")
        add("신살", name, hanja, name, f"{name}({hanja}) — {subtitle}", f"{body} {extra}".strip(), "sajustudy_sinsal")

    for name, body in kd.SIPSEONG_COMBO_ITEMS:
        add("십성 조합", name, "", "", name, body, "sazasaju_yongsin")

    for gan, season, body in kd.ILGAN_SEASON_ITEMS:
        title = f"일간 '{gan}' × {season}"
        add("일간과 계절", title, "", gan, title, body, "wikipedia_saju")

    for name, body in kd.JIJI_RELATION_ITEMS:
        add("지지 관계(형충회합)", name, "", "", name, body, "wikipedia_saju")

    for name, body in kd.CHEONGAN_HAP_ITEMS:
        add("천간합", name, "", "", name, body, "wikipedia_saju")

    for name, body in kd.JIJI_YUKHAE_ITEMS:
        add("지지 육해", name, "", "", name, body, "wikipedia_saju")

    for name, body in kd.JIJI_BANGHAP_ITEMS:
        add("지지 방합", name, "", "", name, body, "wikipedia_saju")

    for name, body in kd.WUXING_PAIR_ITEMS:
        add("오행 관계", name, "", "", name, body, "wikipedia_saju")

    cheongan_by_hanja = {h: (hangul, title) for h, hangul, title, _ in kd.CHEONGAN_ITEMS}
    jiji_by_hanja = {h: (hangul, animal) for h, hangul, animal, *_ in kd.JIJI_ITEMS}
    for gz, nayin in _generate_ganzi60():
        g_han, z_han = gz[0], gz[1]
        g_hangul, g_title = cheongan_by_hanja.get(g_han, (g_han, ""))
        z_hangul, z_animal = jiji_by_hanja.get(z_han, (z_han, ""))
        hangul = g_hangul + z_hangul
        body = (
            f"{hangul}({gz}){_eun_neun(hangul)} {g_title.split('—')[-1].strip() if '—' in g_title else g_title} 기운의 "
            f"천간 '{g_hangul}'{_gwa_wa(g_hangul)} {z_animal}띠를 상징하는 지지 '{z_hangul}'{_i_ga(z_hangul)} 결합한 간지입니다. "
            f"납음오행으로는 '{nayin}'이라 부릅니다. 두 글자의 성격이 함께 어우러져 이 갑자만의 "
            f"고유한 기질을 이룬다고 봅니다."
        )
        add("육십갑자", hangul, gz, hangul, f"{hangul}({gz}) · 납음 {nayin}", body, "wikipedia_saju")

    return entries


def build_gwansang_entries() -> list:
    entries = []
    idx = 1

    def add(category, subcategory, hanja, hangul, title, body, source_key):
        nonlocal idx
        entries.append({
            "id": f"G{idx:03d}", "domain": "관상학", "category": category,
            "subcategory": subcategory, "hanja": hanja, "hangul": hangul,
            "title": title, "body": body, "source": _src(source_key),
        })
        idx += 1

    for e in kd.GWANSANG_ESSAYS:
        add("이론", e["subcategory"], "", "", e["title"], e["body"], e["source_key"])

    for name, hanja, region, body in kd.SIBIGUNG_DETAILED:
        extra = ke.EXTRA_SIBIGUNG.get(name, "")
        add("십이궁", name, hanja, name, f"{name}({hanja}) — {region}", f"{body} {extra}".strip(), "skyedaily_12gung")

    for name, hanja, subtitle, body in kd.OHAENGHYEONG_ITEMS:
        extra = ke.EXTRA_OHAENGHYEONG.get(name, "")
        add("오행형", name, hanja, name, f"{name}({hanja}) — {subtitle}", f"{body} {extra}".strip(), "ntoday_ohaeng")

    groups = [
        ("눈", kd.EYE_TYPES, "esquire_eyes", ke.EXTRA_EYE),
        ("코", kd.NOSE_TYPES, "junsungki_face", ke.EXTRA_NOSE),
        ("입", kd.MOUTH_TYPES, "junsungki_face", ke.EXTRA_MOUTH),
        ("이마", kd.FOREHEAD_TYPES, "junsungki_forehead", ke.EXTRA_FOREHEAD),
        ("눈썹", kd.EYEBROW_TYPES, "junsungki_forehead", ke.EXTRA_EYEBROW),
        ("얼굴형", kd.CHIN_FACE_TYPES, "sajupalza_intro", ke.EXTRA_CHIN_FACE),
        ("귀", kd.EAR_TYPES, "junsungki_forehead", ke.EXTRA_EAR),
        ("인중", kd.INJUNG_TYPES, "sajupalza_intro", {}),
        ("볼·광대", kd.CHEEK_TYPES, "sajupalza_intro", {}),
    ]
    for category, items, source_key, extra_map in groups:
        closing = ke.GWANSANG_PART_CLOSING.get(category, "")
        for name, hanja, subtitle, body in items:
            extra = extra_map.get(name, "")
            full_body = f"{body} {extra} {closing}".strip()
            add(category, name, hanja if hanja != "-" else "", name, f"{name} — {subtitle}", full_body, source_key)

    return entries


def export_all_csv():
    os.makedirs(DATA_DIR, exist_ok=True)
    saju_entries = build_saju_entries()
    gwansang_entries = build_gwansang_entries()

    with open(SAJU_CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(saju_entries)

    with open(GWANSANG_CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(gwansang_entries)

    return len(saju_entries), len(gwansang_entries)


def _load_csv(path: str) -> list:
    if not os.path.exists(path):
        export_all_csv()
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_saju_rows() -> list:
    return _load_csv(SAJU_CSV_PATH)


def load_gwansang_rows() -> list:
    return _load_csv(GWANSANG_CSV_PATH)


def find_saju_context(saju_prompt_dict: dict, limit_per_pillar: int = 4) -> list:
    """사주 계산 결과에 나온 십성/십이운성/신살 이름과 일치하는 DB 항목을 찾아 반환.

    Gemini 프롬프트에 '근거 자료'로 함께 넣어줄 항목들을 고르는 용도.
    """
    rows = load_saju_rows()
    by_subcat = {}
    for r in rows:
        by_subcat.setdefault(r["subcategory"], r)

    wanted = set()
    for key in ("년주", "월주", "일주", "시주"):
        pillar = saju_prompt_dict.get(key)
        if not isinstance(pillar, dict):
            continue
        if pillar.get("십성_천간") and pillar["십성_천간"] != "일원(日元)":
            wanted.add(pillar["십성_천간"])
        for s in pillar.get("십성_지지", []) or []:
            wanted.add(s)
        if pillar.get("십이운성"):
            wanted.add(pillar["십이운성"])

    picked = [by_subcat[name] for name in wanted if name in by_subcat]
    # 오행 이론 항목도 하나씩 곁들인다.
    for r in rows:
        if r["category"] == "이론" and len(picked) < limit_per_pillar * 4:
            if r["subcategory"] in ("십성이란 무엇인가", "십이운성 개론", "신강신약과 용신"):
                picked.append(r)
    return picked[: limit_per_pillar * 5]


def find_gwansang_context(rule_result: dict, limit: int = 6) -> list:
    """관상 측정 결과(얼굴형 등)와 관련된 DB 항목을 찾아 반환."""
    rows = load_gwansang_rows()
    picked = []
    for r in rows:
        if r["category"] == "이론":
            picked.append(r)
    for r in rows:
        if r["category"] in ("십이궁", "오행형", "얼굴형"):
            picked.append(r)
        if len(picked) >= limit:
            break
    return picked[:limit]
