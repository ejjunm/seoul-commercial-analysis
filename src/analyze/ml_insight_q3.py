import os
import subprocess
import pandas as pd
import numpy as np
import xgboost as xgb
import shap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")
from pyspark.sql import SparkSession
from sklearn.model_selection import cross_val_score, StratifiedKFold, train_test_split
from sklearn.metrics import roc_auc_score, classification_report, confusion_matrix

MASTER_PATH = "/user/maria_dev/seoul-commercial-analysis/data/processed/master_dataset"
OUTPUT_PATH = "/user/maria_dev/seoul-commercial-analysis/data/processed/seoul_q3_ml_result"
TMP_DIR     = "/tmp/seoul-commercial-analysis"
SHAP_PNG    = f"{TMP_DIR}/shap_q3_summary.png"

os.makedirs(TMP_DIR, exist_ok=True)

spark = SparkSession.builder.appName("seoul_q3_youth_settlement").getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

df = spark.read.parquet(MASTER_PATH).toPandas()
df["연도"] = df["기준_년분기_코드"].astype(str).str[:4].astype(int)
df["분기"] = df["기준_년분기_코드"].astype(str).str[-1].astype(int)

fill_cols = ["당월_매출_금액", "당월_매출_건수", "연령대_20_매출_금액", "연령대_30_매출_금액", "점포_수"]
df[fill_cols] = df[fill_cols].fillna(0)

global_foot = df.groupby(["상권_코드", "기준_년분기_코드"])["총_유동인구_수"].max().reset_index()
global_foot_rank = global_foot.groupby("상권_코드")["총_유동인구_수"].mean().reset_index()
global_foot_rank = global_foot_rank.rename(columns={"총_유동인구_수": "상권_평균_유동인구"})
global_foot_rank["유동인구_하위_퍼센트"] = global_foot_rank["상권_평균_유동인구"].rank(pct=True)

quarters_24 = df[df["연도"] == 2024].groupby(["상권_코드", "서비스_업종_코드_명"])["기준_년분기_코드"].nunique().reset_index()
valid_cohort_24 = quarters_24[quarters_24["기준_년분기_코드"] == 4][["상권_코드", "서비스_업종_코드_명"]]
df_train_base = pd.merge(df, valid_cohort_24, on=["상권_코드", "서비스_업종_코드_명"], how="inner")

agg_funcs = {
    "당월_매출_금액": "mean", "당월_매출_건수": "mean",
    "연령대_20_매출_금액": "mean", "연령대_30_매출_금액": "mean",
    "점포_수": "mean", "개업_점포_수": "sum", "폐업_점포_수": "sum"
}
df_year = df_train_base.groupby(
    ["연도", "상권_코드", "상권_코드_명", "상권_구분_코드_명", "서비스_업종_코드_명"]
).agg(agg_funcs).reset_index()

df_24 = df_year[df_year["연도"] == 2024].copy()
df_25 = df_year[df_year["연도"] == 2025].copy()
df_ml = pd.merge(df_24, df_25, on=["상권_코드", "상권_코드_명", "상권_구분_코드_명", "서비스_업종_코드_명"], suffixes=("_24", "_25"), how="left")

n_quarters_25 = df[df["연도"] == 2025]["분기"].nunique()
df_25_raw = df[df["연도"] == 2025].groupby(["상권_코드", "서비스_업종_코드_명"]).agg({"폐업_점포_수": "sum", "점포_수": "mean"}).reset_index()
df_25_raw["점포_수_연환산"] = df_25_raw["점포_수"] * n_quarters_25
df_25_seoul = df_25_raw.groupby("서비스_업종_코드_명").agg({"폐업_점포_수": "sum", "점포_수_연환산": "sum"}).reset_index()
df_25_seoul["서울시_평균_폐업률_25"] = df_25_seoul["폐업_점포_수"] / df_25_seoul["점포_수_연환산"].replace(0, np.nan)
df_ml = pd.merge(df_ml, df_25_seoul[["서비스_업종_코드_명", "서울시_평균_폐업률_25"]], on="서비스_업종_코드_명")

avail_q25 = df[df["연도"] == 2025]["분기"].unique()
df_24_matched = df[(df["연도"] == 2024) & (df["분기"].isin(avail_q25))]
df_24_tgt = df_24_matched.groupby(["상권_코드", "서비스_업종_코드_명"]).agg({"당월_매출_금액": "mean", "점포_수": "mean"}).reset_index()
df_24_tgt["공정_점포당_매출_24"] = df_24_tgt["당월_매출_금액"] / df_24_tgt["점포_수"].replace(0, np.nan)
df_ml = pd.merge(df_ml, df_24_tgt[["상권_코드", "서비스_업종_코드_명", "공정_점포당_매출_24"]], on=["상권_코드", "서비스_업종_코드_명"], how="left")

df_ml["점포당_매출_25"] = df_ml["당월_매출_금액_25"] / df_ml["점포_수_25"].replace(0, np.nan)

cond_survival = (df_ml["폐업_점포_수_25"] / (df_ml["점포_수_25"] * n_quarters_25).replace(0, np.nan)) <= df_ml["서울시_평균_폐업률_25"]
cond_persist = df_ml["점포_수_25"] >= df_ml["점포_수_24"] * 0.90
cond_revenue = df_ml["점포당_매출_25"] >= df_ml["공정_점포당_매출_24"] * 0.85
df_ml["Target"] = np.where(cond_survival & cond_persist & cond_revenue, 1, 0)

df_24_raw = df[df["연도"] == 2024].groupby(["상권_코드", "서비스_업종_코드_명"]).agg({"당월_매출_금액": "mean", "당월_매출_건수": "mean", "점포_수": "mean"}).reset_index()
df_ml = pd.merge(df_ml, global_foot_rank[["상권_코드", "유동인구_하위_퍼센트", "상권_평균_유동인구"]], on="상권_코드")

df_ml["MZ_매출_비중"] = (df_ml["연령대_20_매출_금액_24"] + df_ml["연령대_30_매출_금액_24"]) / df_ml["당월_매출_금액_24"].replace(0, np.nan)
df_ml["상권_객단가_24"] = df_ml["당월_매출_금액_24"] / df_ml["당월_매출_건수_24"].replace(0, np.nan)

seoul_ticket = df_24_raw.groupby("서비스_업종_코드_명").apply(lambda x: x["당월_매출_금액"].sum() / x["당월_매출_건수"].sum() if x["당월_매출_건수"].sum() > 0 else np.nan).reset_index(name="서울시_평균_객단가")
df_ml = pd.merge(df_ml, seoul_ticket, on="서비스_업종_코드_명")
df_ml["상대_객단가_비율"] = df_ml["상권_객단가_24"] / df_ml["서울시_평균_객단가"].replace(0, np.nan)

df_ml["상권_활력도_24"] = df_ml["당월_매출_건수_24"] / df_ml["점포_수_24"].replace(0, np.nan)
seoul_vital = df_24_raw.groupby("서비스_업종_코드_명").apply(lambda x: x["당월_매출_건수"].sum() / x["점포_수"].sum() if x["점포_수"].sum() > 0 else np.nan).reset_index(name="서울시_평균_활력도")
df_ml = pd.merge(df_ml, seoul_vital, on="서비스_업종_코드_명")
df_ml["상대_시장활력도_비율"] = df_ml["상권_활력도_24"] / df_ml["서울시_평균_활력도"].replace(0, np.nan)

area_stores = df_24_raw.groupby("상권_코드")["점포_수"].sum().reset_index(name="상권_전체_점포수")
df_ml = pd.merge(df_ml, area_stores, on="상권_코드")
df_ml["상권_경쟁밀도"] = df_ml["상권_전체_점포수"] / (df_ml["상권_평균_유동인구"] + 1)

df_ml["상권내_업종비중"] = df_ml["점포_수_24"] / df_ml["상권_전체_점포수"].replace(0, np.nan)
seoul_total_stores = df_24_raw["점포_수"].sum()
seoul_ind_stores = df_24_raw.groupby("서비스_업종_코드_명")["점포_수"].sum().reset_index(name="서울시_해당업종_점포수")
seoul_ind_stores["서울시_업종비중"] = seoul_ind_stores["서울시_해당업종_점포수"] / seoul_total_stores
df_ml = pd.merge(df_ml, seoul_ind_stores[["서비스_업종_코드_명", "서울시_업종비중"]], on="서비스_업종_코드_명")
df_ml["상권_특화도_LQ"] = df_ml["상권내_업종비중"] / df_ml["서울시_업종비중"].replace(0, np.nan)

q_std = df[df["연도"] == 2024].groupby(["상권_코드", "서비스_업종_코드_명"])["당월_매출_금액"].agg(["mean", "std"]).reset_index()
q_std["매출_변동계수"] = q_std["std"] / q_std["mean"].replace(0, np.nan)
df_ml = pd.merge(df_ml, q_std[["상권_코드", "서비스_업종_코드_명", "매출_변동계수"]], on=["상권_코드", "서비스_업종_코드_명"], how="left")
df_ml["매출_변동계수"] = df_ml["매출_변동계수"].fillna(df_ml["매출_변동계수"].median())

features = ["MZ_매출_비중", "상대_시장활력도_비율", "상대_객단가_비율", "상권_특화도_LQ", "매출_변동계수"]

df_train = df_ml[
    (df_ml["상권_구분_코드_명"] == "골목상권") &
    (df_ml["점포_수_24"] >= 3)
].dropna(subset=["Target"] + features).copy()

X_train = df_train[features]
y_train = df_train["Target"]

model = xgb.XGBClassifier(
    objective="binary:logistic", eval_metric="logloss",
    max_depth=5, learning_rate=0.05, n_estimators=200, random_state=42,
    scale_pos_weight=(len(y_train) - y_train.sum()) / (y_train.sum() + 1e-9)
)
model.fit(X_train, y_train)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_auc = cross_val_score(model, X_train, y_train, cv=cv, scoring="roc_auc")
print(f"5-Fold CV AUC: {cv_auc.mean():.3f} (+/-{cv_auc.std():.3f})")

X_tr, X_te, y_tr, y_te = train_test_split(X_train, y_train, test_size=0.25, stratify=y_train, random_state=42)
eval_model = xgb.XGBClassifier(
    objective="binary:logistic", eval_metric="logloss", max_depth=5, learning_rate=0.05, n_estimators=200, random_state=42,
    scale_pos_weight=(len(y_tr) - y_tr.sum()) / (y_tr.sum() + 1e-9))
eval_model.fit(X_tr, y_tr)
test_proba = eval_model.predict_proba(X_te)[:, 1]
test_pred = eval_model.predict(X_te)
print(f"Hold-out Test AUC: {roc_auc_score(y_te, test_proba):.3f}")
print(confusion_matrix(y_te, test_pred))
print(classification_report(y_te, test_pred, target_names=["비안착", "안착"], zero_division=0))

explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_train)
plt.figure()
shap.summary_plot(shap_values, X_train, feature_names=features, show=False)
plt.tight_layout()
plt.savefig(SHAP_PNG, dpi=120, bbox_inches="tight")
plt.close()

shap_importance = pd.DataFrame({
    "feature": features, "mean_abs_shap": np.abs(shap_values).mean(axis=0)
}).sort_values("mean_abs_shap", ascending=False)
print(shap_importance.to_string(index=False))

df_25_inf = df[df["연도"] == 2025].groupby(
    ["상권_코드", "상권_코드_명", "상권_구분_코드_명", "서비스_업종_코드_명"]).agg({
    "당월_매출_금액": "mean", "당월_매출_건수": "mean",
    "연령대_20_매출_금액": "mean", "연령대_30_매출_금액": "mean", "점포_수": "mean"
}).reset_index()

cur_ticket = df_25_inf.groupby("서비스_업종_코드_명").apply(lambda x: x["당월_매출_금액"].sum() / x["당월_매출_건수"].sum() if x["당월_매출_건수"].sum() > 0 else np.nan).reset_index(name="서울시_평균_객단가")
cur_vital = df_25_inf.groupby("서비스_업종_코드_명").apply(lambda x: x["당월_매출_건수"].sum() / x["점포_수"].sum() if x["점포_수"].sum() > 0 else np.nan).reset_index(name="서울시_평균_활력도")
cur_area_stores = df_25_inf.groupby("상권_코드")["점포_수"].sum().reset_index(name="상권_전체_점포수")

df_current = pd.merge(df_25_inf, global_foot_rank[["상권_코드", "유동인구_하위_퍼센트", "상권_평균_유동인구"]], on="상권_코드")
df_current["MZ_매출_비중"] = (df_current["연령대_20_매출_금액"] + df_current["연령대_30_매출_금액"]) / df_current["당월_매출_금액"].replace(0, np.nan)
df_current["상권_객단가"] = df_current["당월_매출_금액"] / df_current["당월_매출_건수"].replace(0, np.nan)
df_current = pd.merge(df_current, cur_ticket, on="서비스_업종_코드_명")
df_current["상대_객단가_비율"] = df_current["상권_객단가"] / df_current["서울시_평균_객단가"].replace(0, np.nan)
df_current["상권_활력도"] = df_current["당월_매출_건수"] / df_current["점포_수"].replace(0, np.nan)
df_current = pd.merge(df_current, cur_vital, on="서비스_업종_코드_명")
df_current["상대_시장활력도_비율"] = df_current["상권_활력도"] / df_current["서울시_평균_활력도"].replace(0, np.nan)
df_current = pd.merge(df_current, cur_area_stores, on="상권_코드")
df_current["상권_경쟁밀도"] = df_current["상권_전체_점포수"] / (df_current["상권_평균_유동인구"] + 1)

cur_total = df_25_inf["점포_수"].sum()
cur_ind = df_25_inf.groupby("서비스_업종_코드_명")["점포_수"].sum().reset_index(name="서울시_해당업종_점포수")
cur_ind["서울시_업종비중"] = cur_ind["서울시_해당업종_점포수"] / cur_total
df_current["상권내_업종비중"] = df_current["점포_수"] / df_current["상권_전체_점포수"].replace(0, np.nan)
df_current = pd.merge(df_current, cur_ind[["서비스_업종_코드_명", "서울시_업종비중"]], on="서비스_업종_코드_명")
df_current["상권_특화도_LQ"] = df_current["상권내_업종비중"] / df_current["서울시_업종비중"].replace(0, np.nan)

q_std_25 = df[df["연도"] == 2025].groupby(["상권_코드", "서비스_업종_코드_명"])["당월_매출_금액"].agg(["mean", "std"]).reset_index()
q_std_25["매출_변동계수"] = q_std_25["std"] / q_std_25["mean"].replace(0, np.nan)
df_current = pd.merge(df_current, q_std_25[["상권_코드", "서비스_업종_코드_명", "매출_변동계수"]], on=["상권_코드", "서비스_업종_코드_명"], how="left")
df_current["매출_변동계수"] = df_current["매출_변동계수"].fillna(df_current["매출_변동계수"].median())

df_cur_alley = df_current[df_current["상권_구분_코드_명"] == "골목상권"].copy()
df_cur_alley["점포당_매출_최신"] = df_cur_alley["당월_매출_금액"] / df_cur_alley["점포_수"].replace(0, np.nan)

Q1_sc = df_cur_alley.groupby("서비스_업종_코드_명")["점포당_매출_최신"].transform(lambda x: x.quantile(0.25))
Q3_sc = df_cur_alley.groupby("서비스_업종_코드_명")["점포당_매출_최신"].transform(lambda x: x.quantile(0.75))
df_cur_alley["매출_상한선_최신"] = Q3_sc + 1.5 * (Q3_sc - Q1_sc)
Q1_tc = df_cur_alley.groupby("서비스_업종_코드_명")["상권_객단가"].transform(lambda x: x.quantile(0.25))
Q3_tc = df_cur_alley.groupby("서비스_업종_코드_명")["상권_객단가"].transform(lambda x: x.quantile(0.75))
df_cur_alley["객단가_하한선_최신"] = np.maximum(Q1_tc - 1.5 * (Q3_tc - Q1_tc), 3000)
df_cur_alley["객단가_상한선_최신"] = Q3_tc + 1.5 * (Q3_tc - Q1_tc)

latest_q = df["기준_년분기_코드"].max()
active = df[(df["기준_년분기_코드"] == latest_q) & (df["점포_수"] > 0)][["상권_코드", "서비스_업종_코드_명"]].drop_duplicates()
df_cur_alley = pd.merge(active, df_cur_alley, on=["상권_코드", "서비스_업종_코드_명"], how="inner")

uniq_c = df_cur_alley[["상권_코드", "상권_전체_점포수"]].drop_duplicates()
Q1_tsc, Q3_tsc = uniq_c["상권_전체_점포수"].quantile(0.25), uniq_c["상권_전체_점포수"].quantile(0.75)
df_cur_alley["총점포수_상한선_최신"] = Q3_tsc + 1.5 * (Q3_tsc - Q1_tsc)

df_predict = df_cur_alley[
    (df_cur_alley["유동인구_하위_퍼센트"] >= 0.20) &
    (df_cur_alley["점포_수"] >= 3) &
    (df_cur_alley["상권_전체_점포수"] <= df_cur_alley["총점포수_상한선_최신"]) &
    (df_cur_alley["점포당_매출_최신"] >= 4500000) &
    (df_cur_alley["점포당_매출_최신"] <= df_cur_alley["매출_상한선_최신"]) &
    (df_cur_alley["상권_객단가"] >= df_cur_alley["객단가_하한선_최신"]) &
    (df_cur_alley["상권_객단가"] <= df_cur_alley["객단가_상한선_최신"]) &
    (df_cur_alley["MZ_매출_비중"] >= 0.30)
].dropna(subset=features).copy()
print(f"예측 대상: {len(df_predict)}건")

if len(df_predict) == 0:
    spark.stop()
    raise SystemExit("예측 대상 0건")

df_predict["청년안착_적합도"] = model.predict_proba(df_predict[features])[:, 1]

def minmax(s):
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) if hi > lo else s * 0

comp_n = minmax(df_predict["상권_경쟁밀도"])
foot = df_predict["유동인구_하위_퍼센트"]
foot_fit = 1 - (foot - 0.65).abs() / 0.65
foot_fit = foot_fit.clip(lower=0)
df_predict["진입가능성"] = (1 - comp_n) * 0.7 + foot_fit * 0.3
df_predict["청년_라이징_추천점수"] = df_predict["청년안착_적합도"] * df_predict["진입가능성"]

final_ranking = df_predict[[
    "상권_코드", "상권_코드_명", "서비스_업종_코드_명",
    "MZ_매출_비중", "상대_시장활력도_비율", "상권_특화도_LQ",
    "상권_경쟁밀도", "청년안착_적합도", "진입가능성", "청년_라이징_추천점수"
]].sort_values("청년_라이징_추천점수", ascending=False)

print("\n=== Q3 청년 라이징 추천 Top 15 (상권 × 업종) ===")      
print(final_ranking.head(15).round(3).to_string(index=False)) 

LOCAL_RESULT = f"{TMP_DIR}/seoul_q3_ml_result.parquet"
final_ranking.to_parquet(LOCAL_RESULT, index=False)

spark.stop()

subprocess.run(["hdfs", "dfs", "-mkdir", "-p", OUTPUT_PATH], check=True)
subprocess.run(["hdfs", "dfs", "-put", "-f", LOCAL_RESULT, f"{OUTPUT_PATH}/part-0.parquet"], check=True)
os.remove(LOCAL_RESULT)
print(f"저장 완료: {OUTPUT_PATH}")
print(f"SHAP 플롯: {SHAP_PNG}")