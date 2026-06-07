import json
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.io import to_html

DATA_DIR     = "./data/processed/dashboard"
GEO_LOCAL    = "./data/geo/seoul_municipalities_geo_simple.json"
OUT_HTML     = f"{DATA_DIR}/dashboard.html"
SEOUL_CENTER = {"lat": 37.5642, "lon": 126.9979}
C_MEGA       = "#C0392B"
C_RISING     = "#2471A3"

# ── 데이터 로드 ────────────────────────────────────────────────────────
df_gu = pd.read_csv(f"{DATA_DIR}/tab1_gu_summary.csv", encoding="utf-8-sig")
df_lq = pd.read_csv(f"{DATA_DIR}/tab1_lq.csv", encoding="utf-8-sig")
df_hp = pd.read_csv(f"{DATA_DIR}/tab2_hotplaces.csv", encoding="utf-8-sig")
df_yo = pd.read_csv(f"{DATA_DIR}/tab3_youth_map.csv", encoding="utf-8-sig")
df_yo["진입가능성"]         = df_yo["진입가능성"].fillna(df_yo["진입가능성"].median())
df_yo["월_점포당_매출_만원"] = df_yo["월_점포당_매출_만원"].fillna(0)

with open(GEO_LOCAL, encoding="utf-8") as f:
    geo = json.load(f)

mega   = df_hp[df_hp["구분"] == "메가 핫플"].copy()
rising = df_hp[df_hp["구분"] == "라이징 핫플"].copy()

# Plotly figure를 div 문자열로 변환 (첫 figure만 plotly.js 포함)
_first = {"include": True}
def fig_div(fig):
    inc = "cdn" if _first["include"] else False
    _first["include"] = False
    return to_html(fig, include_plotlyjs=inc, full_html=False,
                   config={"responsive": True, "displayModeBar": True})

# ══════════════════════════════════════════════════════════════════════
# TAB 1 — 거시 지형
# ══════════════════════════════════════════════════════════════════════

# 1-B. 코로플레스 지도 (규모/실속 토글 → updatemenus 버튼)
fig_map = go.Figure()
fig_map.add_trace(go.Choroplethmapbox(
    geojson=geo, locations=df_gu["자치구_코드_명"], featureidkey="properties.name",
    z=df_gu["구_총매출_억원"], colorscale="Reds", marker_opacity=0.8,
    colorbar_title="총매출(억원)", name="규모",
    text=df_gu["자치구_코드_명"],
    hovertemplate="<b>%{text}</b><br>총매출: %{z:,.1f}억원<extra></extra>",
))
fig_map.add_trace(go.Choroplethmapbox(
    geojson=geo, locations=df_gu["자치구_코드_명"], featureidkey="properties.name",
    z=df_gu["점포당_평균매출_억원"], colorscale="Blues", marker_opacity=0.8,
    colorbar_title="점포당(억원)", name="실속", visible=False,
    text=df_gu["자치구_코드_명"],
    hovertemplate="<b>%{text}</b><br>점포당매출: %{z:.3f}억원<extra></extra>",
))
fig_map.update_layout(
    mapbox_style="carto-positron", mapbox_zoom=9.3, mapbox_center=SEOUL_CENTER,
    margin=dict(l=0, r=0, t=40, b=0), height=520,
    updatemenus=[dict(
        type="buttons", direction="right", x=0.5, xanchor="center", y=1.08, yanchor="top",
        buttons=[
            dict(label="📦 규모 (총매출)", method="update",
                 args=[{"visible": [True, False]}]),
            dict(label="💡 실속 (점포당)", method="update",
                 args=[{"visible": [False, True]}]),
        ],
    )],
)

# 1-C. 가로 막대 — 규모 + 실속 (버튼 토글)
gu_v = df_gu.sort_values("구_총매출_억원")
gu_e = df_gu.sort_values("점포당_평균매출_억원")
fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(
    x=gu_v["구_총매출_억원"], y=gu_v["자치구_코드_명"], orientation="h",
    marker=dict(color=gu_v["구_총매출_억원"], colorscale="Reds"), name="규모",
))
fig_bar.add_trace(go.Bar(
    x=gu_e["점포당_평균매출_억원"], y=gu_e["자치구_코드_명"], orientation="h",
    marker=dict(color=gu_e["점포당_평균매출_억원"], colorscale="Blues"),
    name="실속", visible=False,
))
fig_bar.update_layout(
    height=620, margin=dict(l=0, r=10, t=40, b=0), showlegend=False,
    updatemenus=[dict(
        type="buttons", direction="right", x=0.5, xanchor="center", y=1.06, yanchor="top",
        buttons=[
            dict(label="규모 랭킹", method="update", args=[{"visible": [True, False]}]),
            dict(label="실속 랭킹", method="update", args=[{"visible": [False, True]}]),
        ],
    )],
)

# 1-D. LQ 테이블
fig_lq = go.Figure(data=[go.Table(
    header=dict(values=list(df_lq.columns), fill_color="#34495E",
                font=dict(color="white", size=12), align="center"),
    cells=dict(values=[df_lq[c] for c in df_lq.columns],
               fill_color="#F8F9F9", align="center", height=26),
)])
fig_lq.update_layout(height=720, margin=dict(l=0, r=0, t=10, b=0))

# ══════════════════════════════════════════════════════════════════════
# TAB 2 — 메가 & 라이징 핫플
# ══════════════════════════════════════════════════════════════════════

# 2-B. 지도 (범례 클릭으로 메가/라이징 토글)
map_data = df_hp.dropna(subset=["경도", "위도"]).copy()
map_data["bubble_size"] = map_data["24년_월점포당_만원"].clip(lower=300)
fig_hp_map = px.scatter_mapbox(
    map_data, lat="위도", lon="경도", color="구분",
    color_discrete_map={"메가 핫플": C_MEGA, "라이징 핫플": C_RISING},
    size="bubble_size", size_max=50, zoom=10, center=SEOUL_CENTER,
    mapbox_style="carto-positron", hover_name="상권_코드_명",
    hover_data={
        "위도": False, "경도": False, "bubble_size": False,
        "구분": True, "자치구_코드_명": True, "서비스_업종_코드_명": True,
        "24년_월점포당_만원": ":,.0f", "25년_월점포당_만원": ":,.0f",
        "성장률_퍼센트": ":.1f", "up_count": True,
    },
    height=520,
)
fig_hp_map.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                         legend=dict(orientation="h", yanchor="bottom", y=1.02))

# 2-C. 성장 궤적 산점도
max_axis = max(df_hp["24년_월점포당_만원"].max(), df_hp["25년_월점포당_만원"].max()) * 1.08
fig_scatter = px.scatter(
    df_hp, x="24년_월점포당_만원", y="25년_월점포당_만원", color="구분",
    color_discrete_map={"메가 핫플": C_MEGA, "라이징 핫플": C_RISING},
    size="평균_점포수", size_max=28, text="상권_코드_명", hover_name="상권_코드_명",
    hover_data={"서비스_업종_코드_명": True, "성장률_퍼센트": ":.1f",
                "up_count": True, "평균_점포수": ":.1f"},
    height=480,
)
fig_scatter.add_shape(type="line", x0=0, y0=0, x1=max_axis, y1=max_axis,
                      line=dict(color="gray", dash="dash", width=1.5))
fig_scatter.update_traces(textposition="top center", textfont_size=8, marker_opacity=0.85)
fig_scatter.update_layout(margin=dict(l=0, r=0, t=10, b=0))

# 2-D. 상세 테이블 (메가 / 라이징)
def hp_table(df, cols, title_color):
    return go.Figure(data=[go.Table(
        header=dict(values=cols, fill_color=title_color,
                    font=dict(color="white", size=11), align="center"),
        cells=dict(values=[df[c] for c in cols], fill_color="#F8F9F9",
                   align="center", height=24),
    )]).update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0))

mega_cols   = ["상권_코드_명", "자치구_코드_명", "서비스_업종_코드_명", "평균_점포수",
               "24년_월점포당_만원", "25년_월점포당_만원", "성장률_퍼센트", "up_count", "메가_상승_총점"]
rising_cols = ["상권_코드_명", "자치구_코드_명", "서비스_업종_코드_명", "평균_점포수",
               "24년_월점포당_만원", "25년_월점포당_만원", "성장률_퍼센트", "up_count"]
fig_mega_tbl   = hp_table(mega.sort_values("메가_상승_총점", ascending=False), mega_cols, C_MEGA)
fig_rising_tbl = hp_table(rising.sort_values("성장률_퍼센트", ascending=False), rising_cols, C_RISING)

# ══════════════════════════════════════════════════════════════════════
# TAB 3 — 2030 청년 라이징
# ══════════════════════════════════════════════════════════════════════

# 3-C. AI 지도 (적합도 구간 버튼 = 슬라이더 대체)
yo = df_yo[df_yo["월_점포당_매출_만원"] > 0].dropna(subset=["경도", "위도"]).copy()
thresholds = [0.0, 0.3, 0.5, 0.7]
fig_yo = go.Figure()
for i, th in enumerate(thresholds):
    sub = yo[yo["청년안착_적합도"] >= th]
    fig_yo.add_trace(go.Scattermapbox(
        lat=sub["위도"], lon=sub["경도"], mode="markers",
        marker=dict(size=sub["진입가능성"] * 25 + 5, color=sub["청년안착_적합도"],
                    colorscale="Greens", showscale=True, colorbar_title="적합도"),
        text=sub["상권_코드_명"], visible=(i == 0),
        customdata=sub[["서비스_업종_코드_명", "자치구_코드_명", "청년안착_적합도", "진입가능성"]],
        hovertemplate="<b>%{text}</b><br>업종: %{customdata[0]}<br>자치구: %{customdata[1]}"
                      "<br>적합도: %{customdata[2]:.3f}<br>진입가능성: %{customdata[3]:.3f}<extra></extra>",
    ))
fig_yo.update_layout(
    mapbox_style="carto-positron", mapbox_zoom=10, mapbox_center=SEOUL_CENTER,
    margin=dict(l=0, r=0, t=40, b=0), height=560,
    updatemenus=[dict(
        type="buttons", direction="right", x=0.5, xanchor="center", y=1.06, yanchor="top",
        buttons=[
            dict(label=f"적합도 ≥ {th}", method="update",
                 args=[{"visible": [j == i for j in range(len(thresholds))]}])
            for i, th in enumerate(thresholds)
        ],
    )],
)

# 3-D. SHAP
shap_df = pd.DataFrame({
    "변수": ["MZ 매출 비중", "시장 활력도", "매출 변동계수", "객단가", "업종 특화도"],
    "SHAP": [0.228, 0.207, 0.160, 0.157, 0.145],
}).sort_values("SHAP")
fig_shap = px.bar(shap_df, x="SHAP", y="변수", orientation="h", color="SHAP",
                  color_continuous_scale="Greens", text="SHAP", height=320)
fig_shap.update_traces(texttemplate="%{x:.3f}", textposition="outside")
fig_shap.update_layout(showlegend=False, coloraxis_showscale=False,
                       margin=dict(l=0, r=50, t=10, b=0))

# 3-E. Top 15 테이블
top15 = yo.sort_values("청년_라이징_추천점수", ascending=False).head(15)
top15_cols = ["상권_코드_명", "자치구_코드_명", "서비스_업종_코드_명", "월_점포당_매출_만원",
              "MZ_매출_비중", "청년안착_적합도", "진입가능성", "청년_라이징_추천점수"]
fig_top15 = go.Figure(data=[go.Table(
    header=dict(values=top15_cols, fill_color="#1E8449",
                font=dict(color="white", size=11), align="center"),
    cells=dict(values=[top15[c].round(3) if top15[c].dtype == float else top15[c]
                       for c in top15_cols],
               fill_color="#F4FBF6", align="center", height=24),
)])
fig_top15.update_layout(height=440, margin=dict(l=0, r=0, t=10, b=0))

# ══════════════════════════════════════════════════════════════════════
# HTML 조립
# ══════════════════════════════════════════════════════════════════════
def card(label, value):
    return (f'<div class="card"><div class="card-label">{label}</div>'
            f'<div class="card-value">{value}</div></div>')

top_vol = df_gu.sort_values("구_총매출_억원", ascending=False).iloc[0]
top_eff = df_gu.sort_values("점포당_평균매출_억원", ascending=False).iloc[0]

tab1_cards = "".join([
    card("분석 자치구", f"{len(df_gu)}개"),
    card("매출 1위", f"{top_vol['자치구_코드_명']}"),
    card("실속 1위", f"{top_eff['자치구_코드_명']}"),
])
tab2_cards = "".join([
    card("메가 핫플", f"{len(mega)}개"),
    card("라이징 핫플", f"{len(rising)}개"),
    card("메가 평균성장", f"{mega['성장률_퍼센트'].mean():.1f}%"),
    card("라이징 평균성장", f"{rising['성장률_퍼센트'].mean():.1f}%"),
])
tab3_cards = "".join([
    card("전체 후보", f"{len(df_yo):,}건"),
    card("추천 대상", f"{len(yo):,}건"),
    card("평균 적합도", f"{yo['청년안착_적합도'].mean():.3f}"),
])

html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>서울 상권 분석 대시보드</title>
<style>
  body {{ font-family: 'Malgun Gothic', sans-serif; margin: 0; background: #f5f6fa; }}
  .header {{ background: #2C3E50; color: white; padding: 20px 40px; }}
  .header h1 {{ margin: 0; font-size: 24px; }}
  .header p {{ margin: 6px 0 0; color: #bdc3c7; font-size: 14px; }}
  .tabs {{ display: flex; background: #34495E; padding: 0 40px; }}
  .tab-btn {{ padding: 14px 24px; color: #bdc3c7; cursor: pointer; border: none;
             background: none; font-size: 15px; border-bottom: 3px solid transparent; }}
  .tab-btn.active {{ color: white; border-bottom-color: #1ABC9C; font-weight: bold; }}
  .tab-content {{ display: none; padding: 24px 40px; }}
  .tab-content.active {{ display: block; }}
  .cards {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
  .card {{ background: white; border-radius: 10px; padding: 16px 24px; min-width: 120px;
          box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .card-label {{ color: #7f8c8d; font-size: 13px; }}
  .card-value {{ color: #2C3E50; font-size: 22px; font-weight: bold; margin-top: 4px; }}
  .section {{ background: white; border-radius: 10px; padding: 20px; margin-bottom: 24px;
             box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .section h3 {{ margin: 0 0 12px; color: #2C3E50; }}
  .note {{ background: #EBF5FB; border-left: 4px solid #3498DB; padding: 12px 16px;
          border-radius: 4px; color: #34495E; font-size: 14px; margin-top: 12px; }}
  .two-col {{ display: flex; gap: 24px; flex-wrap: wrap; }}
  .two-col > div {{ flex: 1; min-width: 400px; }}
</style></head>
<body>
<div class="header">
  <h1>🏙️ 서울 상권 분석 대시보드</h1>
  <p>2024~2025년 8분기 · 편의점 제외 외식·소매 · Q1 거시 → Q2 핫플 → Q3 청년 골목</p>
</div>
<div class="tabs">
  <button class="tab-btn active" onclick="showTab(0)">① 서울 거시 지형 (Q1)</button>
  <button class="tab-btn" onclick="showTab(1)">② 메가 & 라이징 핫플 (Q2)</button>
  <button class="tab-btn" onclick="showTab(2)">③ 2030 청년 라이징 (Q3)</button>
</div>

<div class="tab-content active" id="tab0">
  <div class="cards">{tab1_cards}</div>
  <div class="section"><h3>자치구별 상권 지형 — 규모 vs 실속</h3>{fig_div(fig_map)}
    <div class="note">📌 버튼으로 규모(총매출)와 실속(점포당매출)을 전환하세요. 규모 1위 강남이 실속에서는 순위가 내려갑니다.</div></div>
  <div class="section"><h3>자치구별 랭킹 비교 (전체 25개 구)</h3>{fig_div(fig_bar)}</div>
  <div class="section"><h3>자치구별 랜드마크 업종 — 종합 특화도 LQ</h3>{fig_div(fig_lq)}</div>
</div>

<div class="tab-content" id="tab1">
  <div class="cards">{tab2_cards}</div>
  <div class="section"><h3>검증된 성장 상권 위치</h3>
    <div class="note">🔴 메가 핫플 (점포 30+) · 🔵 라이징 핫플 (점포 15~30) · 범례 클릭으로 토글 · 원 크기 = 24년 월점포당매출</div>
    {fig_div(fig_hp_map)}</div>
  <div class="section"><h3>24년 → 25년 성장 궤적</h3>{fig_div(fig_scatter)}</div>
  <div class="section"><h3>상세 결과 테이블</h3>
    <div class="two-col"><div><b style="color:{C_MEGA}">🔴 메가 핫플</b>{fig_div(fig_mega_tbl)}</div>
    <div><b style="color:{C_RISING}">🔵 라이징 핫플</b>{fig_div(fig_rising_tbl)}</div></div></div>
</div>

<div class="tab-content" id="tab2">
  <div class="cards">{tab3_cards}</div>
  <div class="section"><h3>2030 청년 라이징 상권 지도 (AI 추천)</h3>
    <div class="note">🟢 색 = AI 안착 적합도 · 원 크기 = 진입 가능성 · 버튼으로 적합도 하한 조절(슬라이더 대체)</div>
    {fig_div(fig_yo)}</div>
  <div class="two-col">
    <div class="section"><h3>XGBoost SHAP 변수 중요도</h3>{fig_div(fig_shap)}
      <div class="note">MZ 매출 비중·시장 활력도가 핵심 신호. AUC 0.55는 공공데이터 한계를 반영하며 패턴 스크리닝 도구로 활용.</div></div>
    <div class="section"><h3>라이징 추천점수 Top 15</h3>{fig_div(fig_top15)}</div>
  </div>
</div>

<script>
function showTab(n) {{
  document.querySelectorAll('.tab-content').forEach((el, i) =>
    el.classList.toggle('active', i === n));
  document.querySelectorAll('.tab-btn').forEach((el, i) =>
    el.classList.toggle('active', i === n));
  window.dispatchEvent(new Event('resize'));
}}
</script>
</body></html>"""

os.makedirs(DATA_DIR, exist_ok=True)
with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)
print(f"대시보드 HTML 생성 완료: {OUT_HTML}")