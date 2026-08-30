# -*- coding: utf-8 -*-
"""관리자 페이지 — 사주학·관상학 지식 DB를 조회하고 CSV/PDF로 내려받는다.

비밀번호 없이 누구나 탭을 눌러 볼 수 있다(원래는 비밀번호로 막아뒀지만
사용자 요청으로 제거함). 민감한 개인정보가 아니라 참고자료 원문이라 문제
없다고 판단했다.
"""
import datetime

import pandas as pd
import streamlit as st

import knowledge_db as kdb
import knowledge_pdf as kpdf


def render():
    st.caption("사주학·관상학 참고자료 데이터베이스를 확인하고 CSV/PDF로 내려받을 수 있어요.")

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
