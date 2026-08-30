# -*- coding: utf-8 -*-
"""관리자 전용 페이지 — 사주학·관상학 지식 DB를 조회하고 CSV/PDF로 내려받는다.

일반 사용자에게는 노출하지 않고, 비밀번호를 입력해야만 볼 수 있다. 비밀번호는
st.secrets["ADMIN_PASSWORD"]에서 읽으며, 로컬 개발용 기본값을 함께 제공한다.
배포 시에는 반드시 Streamlit Cloud의 Secrets 설정에서 이 값을 바꿔야 한다.
"""
import datetime

import pandas as pd
import streamlit as st

import knowledge_db as kdb
import knowledge_pdf as kpdf

DEFAULT_ADMIN_PASSWORD = "facekorea-admin"


def _get_admin_password() -> str:
    try:
        return st.secrets.get("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    except Exception:
        return DEFAULT_ADMIN_PASSWORD


def _login_form():
    st.info(
        "이 페이지는 사주학·관상학 지식 데이터베이스 원문을 확인하는 관리자 전용 "
        "화면입니다. 일반 이용자에게는 공개하지 않습니다."
    )
    pw = st.text_input("관리자 비밀번호", type="password", key="admin_pw_input")
    if st.button("입장", key="admin_login_btn"):
        if pw and pw == _get_admin_password():
            st.session_state["admin_authed"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    if _get_admin_password() == DEFAULT_ADMIN_PASSWORD:
        st.caption(
            "⚠️ 기본 비밀번호(facekorea-admin)가 아직 설정되어 있어요. 배포 전 "
            "`.streamlit/secrets.toml`(로컬) 또는 Streamlit Cloud의 Secrets에서 "
            "ADMIN_PASSWORD 값을 바꿔주세요."
        )


def render():
    if not st.session_state.get("admin_authed"):
        _login_form()
        return

    top1, top2 = st.columns([4, 1])
    with top1:
        st.success("관리자 인증됨")
    with top2:
        if st.button("로그아웃", key="admin_logout_btn", use_container_width=True):
            st.session_state["admin_authed"] = False
            st.rerun()

    saju_rows = kdb.load_saju_rows()
    gw_rows = kdb.load_gwansang_rows()

    c1, c2, c3 = st.columns(3)
    c1.metric("사주학 항목", f"{len(saju_rows)}개")
    c2.metric("관상학 항목", f"{len(gw_rows)}개")
    c3.metric("전체", f"{len(saju_rows) + len(gw_rows)}개")

    st.markdown("#### 지식 데이터베이스 조회")
    domain = st.radio("도메인", ["사주학", "관상학"], horizontal=True, key="admin_domain")
    rows = saju_rows if domain == "사주학" else gw_rows

    categories = sorted({r["category"] for r in rows})
    cat_filter = st.multiselect("카테고리 필터", categories, default=categories, key=f"admin_cat_{domain}")
    query = st.text_input("검색어 (제목/본문)", key=f"admin_search_{domain}")

    q = query.strip().lower()
    filtered = [
        r for r in rows
        if r["category"] in cat_filter
        and (not q or q in r["title"].lower() or q in r["body"].lower())
    ]
    st.caption(f"{len(filtered)}개 항목 표시 중")
    if filtered:
        df = pd.DataFrame(filtered)[["id", "category", "subcategory", "title", "body", "source"]]
        st.dataframe(df, use_container_width=True, height=420)

    st.markdown("#### 원본 파일 다운로드")
    dcol1, dcol2, dcol3 = st.columns(3)
    with dcol1:
        with open(kdb.SAJU_CSV_PATH, "rb") as f:
            st.download_button("사주학 CSV", data=f.read(), file_name="saju_knowledge.csv",
                                mime="text/csv", use_container_width=True)
    with dcol2:
        with open(kdb.GWANSANG_CSV_PATH, "rb") as f:
            st.download_button("관상학 CSV", data=f.read(), file_name="gwansang_knowledge.csv",
                                mime="text/csv", use_container_width=True)
    with dcol3:
        if st.button("참고자료 PDF 생성", use_container_width=True, key="admin_build_pdf"):
            with st.spinner("PDF를 만드는 중이에요 (항목이 많아 시간이 좀 걸려요)..."):
                st.session_state["knowledge_pdf_bytes"] = kpdf.build_knowledge_pdf(saju_rows, gw_rows)

    if st.session_state.get("knowledge_pdf_bytes"):
        st.download_button(
            "⬇️ 참고자료 PDF 다운로드", data=st.session_state["knowledge_pdf_bytes"],
            file_name=f"사주학_관상학_참고자료집_{datetime.date.today()}.pdf",
            mime="application/pdf", use_container_width=True,
        )

    st.markdown("#### DB 재생성")
    st.caption("knowledge_data.py / knowledge_extra.py를 수정한 뒤 아래 버튼을 누르면 CSV가 다시 만들어져요.")
    if st.button("knowledge_data.py 기준으로 CSV 다시 만들기", key="admin_rebuild_csv"):
        n_s, n_g = kdb.export_all_csv()
        st.success(f"CSV를 다시 만들었어요 — 사주학 {n_s}개, 관상학 {n_g}개.")
        st.rerun()
