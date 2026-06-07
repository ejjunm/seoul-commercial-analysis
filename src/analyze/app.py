import json
import os
import urllib.request

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="서울 상권 분석 대시보드",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR     = "./data/processed/dashboard"
GEO_LOCAL    = "./data/geo/seoul_municipalities_geo_simple.json"
GEO_URL      = ("https://raw.githubusercontent.com/southkorea/seoul-maps/"
                "master/kostat/2013/json/seoul_municipalities_geo_simple.json")
SEOUL_CENTER = {"lat": 37.5642, "lon": 126.9979}
C_MEGA       = "#C0392B"   
C_RISING     = "#2471A3"   

@st.cache_data
def load_gu():
    return pd.read_csv(f"{DATA_DIR}/tab1_gu_summary.csv", encoding="utf-8-sig")

@st.cache_data
def load_lq():
    return pd.read_csv(f"{DATA_DIR}/tab1_lq.csv", encoding="utf-8-sig")

@st.cache_data
def load_hp():
    return pd.read_csv(f"{DATA_DIR}/tab2_hotplaces.csv", encoding="utf-8-sig")

@st.cache_data
def load_yo():
    df = pd.read_csv(f"{DATA_DIR}/tab3_youth_map.csv", encoding="utf-8-sig")
    df["진입가능성"]         = df["진입가능성"].fillna(df["진입가능성"].median())
    df["월_점포당_매출_만원"] = df["월_점포당_매출_만원"].fillna(0)
    return df

@st.cache_data
def load_geo():
    if os.path.exists(GEO_LOCAL):
        with open(GEO_LOCAL, encoding="utf-8") as f:
            return json.load(f)
    os.makedirs(os.path.dirname(GEO_LOCAL), exist_ok=True)
    with urllib.request.urlopen(GEO_URL) as r:
        geo = json.loads(r.read().decode())
    with open(GEO_LOCAL, "w", encoding="utf-8") as f:
        json.dump(geo, f, ensure_ascii=False)
    return geo

df_gu  = load_gu()
df_lq  = load_lq()
df_hp  = load_hp()
df_yo  = load_yo()
geo    = load_geo()
mega   = df_hp[df_hp["구분"] == "메가 핫플"].copy()
rising = df_hp[df_hp["구분"] == "라이징 핫플"].copy()

st.title("서울 상권 분석 대시보드")
st.caption(
    "2024~2025년 8분기 · 편의점 제외 외식·소매 · "
    "Q1 거시(자치구) → Q2 중시(핫플) → Q3 미시(2030 청년 골목) 순 탐색"
)

with st.sidebar:
    st.header("대시보드 설정")
    st.markdown("아래 필터는 **③탭 2030 청년 라이징**에만 적용됩니다.")
    st.markdown("---")

    max_rev = int(df_yo["월_점포당_매출_만원"].quantile(0.95))
    cap = st.slider(
        "💰 월 점포당 매출 상한(만원)",
        min_value=0, max_value=max_rev, value=max_rev, step=100,
        help="내릴수록 영세한 소자본 골목 위주로 필터링됩니다.",
    )
    inds = sorted(df_yo["서비스_업종_코드_명"].dropna().unique())
    sel_inds = st.multiselect("업종 선택", inds, default=list(inds))
    min_fit = st.slider(
        "최소 안착 적합도",
        0.0, 1.0, 0.0, 0.05,
        help="AI 모델이 학습한 '안착 우량 패턴' 부합도 하한.",
    )

tab1, tab2, tab3 = st.tabs([
    "① 서울 거시 지형 (Q1)",
    "② 메가 & 라이징 핫플 (Q2)",
    "③ 2030 청년 라이징 (Q3)",
])

with tab1:

    top_vol = df_gu.sort_values("구_총매출_억원", ascending=False).iloc[0]
    top_eff = df_gu.sort_values("점포당_평균매출_억원", ascending=False).iloc[0]
    top_pop = df_gu.sort_values("분기평균_유동인구_만명", ascending=False).iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("분석 자치구", f"{len(df_gu)}개")
    c2.metric("매출 규모 1위", top_vol["자치구_코드_명"],
              f"{top_vol['구_총매출_억원']:,.0f}억원")
    c3.metric("점포당 효율 1위", top_eff["자치구_코드_명"],
              f"{top_eff['점포당_평균매출_억원']:.3f}억원")
    c4.metric("유동인구 1위", top_pop["자치구_코드_명"],
              f"{top_pop['분기평균_유동인구_만명']:.1f}만명")

    st.markdown("---")

    st.subheader("자치구별 상권 지형 — 규모 vs 실속")
    metric_sel = st.radio(
        "색상 기준 선택",
        ["구 총매출 (규모)", "점포당 평균매출 (실속)"],
        horizontal=True,
    )
    if "규모" in metric_sel:
        ccol, cscale, cunit = "구_총매출_억원", "Reds", "총매출(억원)"
        note = ("강남구가 2위 중구의 약 1.5배로 압도적 1위. "
                "광진·강동·관악은 유동인구 상위권이지만 매출은 중하위 → "
                "거주형 상권의 소비 전환 한계를 보여줍니다.")
    else:
        ccol, cscale, cunit = "점포당_평균매출_억원", "Blues", "점포당매출(억원)"
        note = ("규모 1위 강남이 3위로 내려가고, 오피스·관광 밀집 중구가 1위로 역전. "
                "마포는 규모 7위 → 실속 17위 (점포 과밀). "
                "총량 1위 ≠ 효율 1위")

    fig_map = px.choropleth_mapbox(
        df_gu, geojson=geo,
        locations="자치구_코드_명", featureidkey="properties.name",
        color=ccol, color_continuous_scale=cscale,
        mapbox_style="carto-positron",
        center=SEOUL_CENTER, zoom=9.3, opacity=0.8, height=520,
        hover_name="자치구_코드_명",
        hover_data={
            "자치구_코드_명":        False,
            "구_총매출_억원":        ":,.1f",
            "점포당_평균매출_억원":   ":.3f",
            "보유_상권_수":          True,
            "분기평균_유동인구_만명":  ":.1f",
        },
        labels={
            "구_총매출_억원":        "총매출(억원)",
            "점포당_평균매출_억원":   "점포당매출(억원)",
            "보유_상권_수":          "보유상권수",
            "분기평균_유동인구_만명":  "분기평균유동인구(만명)",
        },
    )
    fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                        coloraxis_colorbar_title=cunit)
    st.plotly_chart(fig_map, use_container_width=True)
    st.info(f"{note}")

    st.markdown("---")

    st.subheader("자치구별 랭킹 비교 (전체 25개 구)")
    bc1, bc2 = st.columns(2)

    with bc1:
        st.markdown("**규모 랭킹 — 구 총매출(억원)**")
        fig_vol = px.bar(
            df_gu.sort_values("구_총매출_억원"),
            x="구_총매출_억원", y="자치구_코드_명", orientation="h",
            color="구_총매출_억원", color_continuous_scale="Reds",
            labels={"구_총매출_억원": "총매출(억원)", "자치구_코드_명": ""},
            height=620,
        )
        fig_vol.update_layout(showlegend=False, coloraxis_showscale=False,
                            margin=dict(l=0, r=10, t=10, b=0))
        st.plotly_chart(fig_vol, use_container_width=True)

    with bc2:
        st.markdown("**실속 랭킹 — 점포당 평균매출(억원)**")
        fig_eff = px.bar(
            df_gu.sort_values("점포당_평균매출_억원"),
            x="점포당_평균매출_억원", y="자치구_코드_명", orientation="h",
            color="점포당_평균매출_억원", color_continuous_scale="Blues",
            labels={"점포당_평균매출_억원": "점포당매출(억원)", "자치구_코드_명": ""},
            height=620,
        )
        fig_eff.update_layout(showlegend=False, coloraxis_showscale=False,
                            margin=dict(l=0, r=10, t=10, b=0))
        st.plotly_chart(fig_eff, use_container_width=True)

    st.markdown("---")

    st.subheader("자치구별 랜드마크 업종 — 종합 특화도 LQ (Q1-3)")
    st.caption(
        "LQ > 1.0 = 서울 평균 이상 집적 · 매출 LQ × 0.7 + 점포수 LQ × 0.3 가중합산 · "
        "각 구에서 1위 업종만 표시"
    )
    try:
        styled = df_lq.style.background_gradient(
            subset=["종합_특화도_LQ", "매출_LQ", "점포수_LQ"], cmap="YlOrRd", vmin=1.0
        )
        st.dataframe(styled, use_container_width=True, hide_index=True, height=700)
    except Exception:
        st.dataframe(df_lq, use_container_width=True, hide_index=True, height=700)


with tab2:

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("메가 핫플",        f"{len(mega)}개 상권×업종")
    c2.metric("라이징 핫플",      f"{len(rising)}개 상권×업종")
    c3.metric("메가 평균 성장률",  f"{mega['성장률_퍼센트'].mean():.1f}%")
    c4.metric("라이징 평균 성장률",f"{rising['성장률_퍼센트'].mean():.1f}%")

    st.markdown("---")

    st.subheader("검증된 성장 상권 위치")
    st.caption(
        "메가 핫플 (점포 30+, 헤비급·안정적) · "
        "라이징 핫플 (점포 15~30, 미들급·고속성장) · "
        "원 크기 = 24년 월 점포당 매출"
    )
    map_data = df_hp.dropna(subset=["경도", "위도"]).copy()
    map_data["bubble_size"] = map_data["24년_월점포당_만원"].clip(lower=300)

    fig_hp_map = px.scatter_mapbox(
        map_data,
        lat="위도", lon="경도",
        color="구분",
        color_discrete_map={"메가 핫플": C_MEGA, "라이징 핫플": C_RISING},
        size="bubble_size", size_max=50,
        zoom=10, center=SEOUL_CENTER,
        mapbox_style="carto-positron",
        hover_name="상권_코드_명",
        hover_data={
            "위도": False, "경도": False, "bubble_size": False,
            "구분": True, "자치구_코드_명": True,
            "서비스_업종_코드_명": True,
            "24년_월점포당_만원": ":,.0f",
            "25년_월점포당_만원": ":,.0f",
            "성장률_퍼센트":      ":.1f",
            "up_count":           True,
        },
        labels={
            "자치구_코드_명":      "자치구",
            "서비스_업종_코드_명": "업종",
            "24년_월점포당_만원":  "24년 월점포당(만원)",
            "25년_월점포당_만원":  "25년 월점포당(만원)",
            "성장률_퍼센트":       "성장률(%)",
            "up_count":            "연속상승 횟수",
        },
        height=480,
    )
    fig_hp_map.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_hp_map, use_container_width=True)

    st.markdown("---")

    st.subheader("24년 → 25년 성장 궤적")
    st.caption(
        "대각선 위 = 성장 (25년 > 24년) · 오른쪽 = 절대 매출 큰 메가 · "
        "원 크기 = 평균 점포수"
    )
    max_axis = max(
        df_hp["24년_월점포당_만원"].max(),
        df_hp["25년_월점포당_만원"].max(),
    ) * 1.08

    fig_scatter = px.scatter(
        df_hp,
        x="24년_월점포당_만원", y="25년_월점포당_만원",
        color="구분",
        color_discrete_map={"메가 핫플": C_MEGA, "라이징 핫플": C_RISING},
        size="평균_점포수", size_max=28,
        text="상권_코드_명",
        hover_name="상권_코드_명",
        hover_data={
            "서비스_업종_코드_명": True,
            "성장률_퍼센트":       ":.1f",
            "up_count":            True,
            "평균_점포수":         ":.1f",
        },
        labels={
            "24년_월점포당_만원": "24년 월점포당 매출(만원)",
            "25년_월점포당_만원": "25년 월점포당 매출(만원)",
        },
        height=460,
    )
    fig_scatter.add_shape(
        type="line", x0=0, y0=0, x1=max_axis, y1=max_axis,
        line=dict(color="gray", dash="dash", width=1.5),
    )
    fig_scatter.add_annotation(
        x=max_axis * 0.82, y=max_axis * 0.88,
        text="↗ 성장 기준선 (y = x)",
        showarrow=False, font=dict(color="gray", size=11),
    )
    fig_scatter.update_traces(
        textposition="top center", textfont_size=8, marker_opacity=0.85,
    )
    fig_scatter.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown("---")

    st.subheader("상세 결과 테이블")
    t1, t2 = st.columns(2)

    with t1:
        st.markdown(f"**메가 핫플 Top {len(mega)}**  \n볼륨 60% + 속도 20% + 안정 20%")
        disp_mega = (
            mega[["상권_코드_명", "자치구_코드_명", "서비스_업종_코드_명",
                  "평균_점포수", "24년_월점포당_만원", "25년_월점포당_만원",
                  "성장률_퍼센트", "up_count", "메가_상승_총점"]]
            .rename(columns={
                "상권_코드_명":    "상권", "자치구_코드_명": "구",
                "서비스_업종_코드_명": "업종",
                "up_count":        "연속상승", "메가_상승_총점": "총점",
            })
            .sort_values("총점", ascending=False)
        )
        try:
            st.dataframe(
                disp_mega.style.background_gradient(subset=["총점"], cmap="Reds"),
                hide_index=True, use_container_width=True,
            )
        except Exception:
            st.dataframe(disp_mega, hide_index=True, use_container_width=True)

    with t2:
        st.markdown(f"**라이징 핫플 Top {len(rising)}**  \n성장률 1순위 + 연속상승 3회 이상")
        disp_rising = (
            rising[["상권_코드_명", "자치구_코드_명", "서비스_업종_코드_명",
                    "평균_점포수", "24년_월점포당_만원", "25년_월점포당_만원",
                    "성장률_퍼센트", "up_count"]]
            .rename(columns={
                "상권_코드_명":    "상권", "자치구_코드_명": "구",
                "서비스_업종_코드_명": "업종", "up_count": "연속상승",
            })
            .sort_values("성장률_퍼센트", ascending=False)
        )
        try:
            st.dataframe(
                disp_rising.style.background_gradient(subset=["성장률_퍼센트"], cmap="Blues"),
                hide_index=True, use_container_width=True,
            )
        except Exception:
            st.dataframe(disp_rising, hide_index=True, use_container_width=True)


with tab3:

    f = df_yo[
        (df_yo["월_점포당_매출_만원"] > 0) &
        (df_yo["월_점포당_매출_만원"] <= cap) &
        (df_yo["서비스_업종_코드_명"].isin(sel_inds)) &
        (df_yo["청년안착_적합도"] >= min_fit)
    ].copy()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 후보 (필터 전)",  f"{len(df_yo):,}건")
    c2.metric("조건 충족 (필터 후)",  f"{len(f):,}건")
    c3.metric("평균 안착 적합도",
            f"{f['청년안착_적합도'].mean():.3f}" if len(f) else "-")
    c4.metric("평균 진입 가능성",
            f"{f['진입가능성'].mean():.3f}" if len(f) else "-")

    st.markdown("---")

    st.subheader("2030 청년 라이징 상권 지도 (AI 추천)")
    st.caption(
        "색 진하기 = AI 안착 적합도 ↑ · 원 크기 = 진입 가능성 ↑ "
        "(경쟁밀도 낮고 유동인구 적정)"
    )

    if len(f) == 0:
        st.warning("조건에 맞는 상권이 없습니다. 왼쪽 사이드바 필터를 완화하세요.")
    else:
        fig_yo = px.scatter_mapbox(
            f,
            lat="위도", lon="경도",
            color="청년안착_적합도",
            size="진입가능성",
            color_continuous_scale="Greens",
            range_color=(f["청년안착_적합도"].min(), f["청년안착_적합도"].max()),
            size_max=22,
            zoom=10, center=SEOUL_CENTER,
            mapbox_style="carto-positron",
            hover_name="상권_코드_명",
            hover_data={
                "위도": False, "경도": False,
                "서비스_업종_코드_명": True, "자치구_코드_명": True,
                "MZ_매출_비중":           ":.2f",
                "월_점포당_매출_만원":     ":,.0f",
                "청년안착_적합도":         ":.3f",
                "진입가능성":              ":.3f",
                "청년_라이징_추천점수":    ":.3f",
            },
            labels={
                "서비스_업종_코드_명":  "업종",
                "자치구_코드_명":       "자치구",
                "MZ_매출_비중":         "MZ 매출비중",
                "월_점포당_매출_만원":  "월점포당매출(만원)",
                "청년안착_적합도":      "안착 적합도",
                "진입가능성":           "진입 가능성",
                "청년_라이징_추천점수": "라이징 추천점수",
            },
            height=550,
        )
        fig_yo.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                            coloraxis_colorbar_title="적합도")
        st.plotly_chart(fig_yo, use_container_width=True)

    st.markdown("---")

    sa, sb = st.columns([1, 2])

    with sa:
        st.subheader("XGBoost SHAP 변수 중요도")
        st.caption("5-Fold CV AUC 0.551 (±0.012) · 불균형 보정 적용 · 안착비율 34.4%")

        shap_df = pd.DataFrame({
            "변수": ["MZ 매출 비중", "시장 활력도", "매출 변동계수", "객단가", "업종 특화도"],
            "SHAP": [0.228, 0.207, 0.160, 0.157, 0.145],
        }).sort_values("SHAP")

        fig_shap = px.bar(
            shap_df, x="SHAP", y="변수", orientation="h",
            color="SHAP", color_continuous_scale="Greens",
            text="SHAP",
            labels={"SHAP": "평균 |SHAP| 값", "변수": ""},
            height=300,
        )
        fig_shap.update_traces(texttemplate="%{x:.3f}", textposition="outside")
        fig_shap.update_layout(
            showlegend=False, coloraxis_showscale=False,
            margin=dict(l=0, r=50, t=10, b=0),
        )
        st.plotly_chart(fig_shap, use_container_width=True)

        st.info(
            "**MZ 매출 비중·시장 활력도**가 안착의 핵심 신호. "
            "5개 변수 기여도가 고르게 분포 → 단일 지표 과의존 없음. "
            "AUC 0.55는 공공데이터 한계(임대료·개인역량 부재)를 반영하며, "
            "모델은 예측이 아닌 패턴 기반 스크리닝 도구로 활용."
        )

    with sb:
        st.subheader(f"라이징 추천점수 Top 15")
        st.caption("안착 적합도(AI) × 진입 가능성(경쟁밀도·유동인구 적정도) 복합 점수")

        if len(f) > 0:
            top15 = (
                f.sort_values("청년_라이징_추천점수", ascending=False)
                .head(15)[[
                    "상권_코드_명", "자치구_코드_명", "서비스_업종_코드_명",
                    "월_점포당_매출_만원", "MZ_매출_비중",
                    "청년안착_적합도", "진입가능성", "청년_라이징_추천점수",
                ]]
                .rename(columns={
                    "상권_코드_명":        "상권",
                    "자치구_코드_명":      "구",
                    "서비스_업종_코드_명": "업종",
                    "월_점포당_매출_만원": "월매출(만원)",
                    "MZ_매출_비중":        "MZ비중",
                    "청년안착_적합도":     "적합도",
                    "진입가능성":          "진입가능성",
                    "청년_라이징_추천점수":"추천점수",
                })
            )
            try:
                st.dataframe(
                    top15.style.background_gradient(
                        subset=["추천점수", "적합도"], cmap="Greens"
                    ),
                    hide_index=True, use_container_width=True, height=430,
                )
            except Exception:
                st.dataframe(top15, hide_index=True, use_container_width=True, height=430)
        else:
            st.warning("필터 조건에 맞는 상권이 없습니다.")