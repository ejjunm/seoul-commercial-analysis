import os
import subprocess
import pandas as pd
from pyproj import Transformer
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

COLUMN_MAP = {
    "stdr_yyqu_cd": "기준_년분기_코드",
    "trdar_se_cd": "상권_구분_코드",
    "trdar_se_cd_nm": "상권_구분_코드_명",
    "trdar_cd": "상권_코드",
    "trdar_cd_nm": "상권_코드_명",
    "svc_induty_cd": "서비스_업종_코드",
    "svc_induty_cd_nm": "서비스_업종_코드_명",
    "thsmon_selng_amt": "당월_매출_금액",
    "thsmon_selng_co": "당월_매출_건수",
    "agrde_20_selng_amt": "연령대_20_매출_금액",
    "agrde_30_selng_amt": "연령대_30_매출_금액",
    "stor_co": "점포_수",
    "opbiz_stor_co": "개업_점포_수",
    "clsbiz_stor_co": "폐업_점포_수",
    "tot_flpop_co": "총_유동인구_수",
    "xnts_vl": "엑스좌표_값",
    "ynts_vl": "와이좌표_값",
    "signgu_cd_nm": "자치구_코드_명",
    "adstrd_cd_nm": "행정동_코드_명"
}

def standardize_headers(df):
    for eng, kor in COLUMN_MAP.items():
        if eng in df.columns:
            df = df.withColumnRenamed(eng, kor)
    return df

HDFS_BASE = "/user/maria_dev/seoul-commercial-analysis"
HDFS_RAW  = f"{HDFS_BASE}/data/raw"
HDFS_OUT  = f"{HDFS_BASE}/data/processed"
TEMP_DIR  = "/tmp/seoul-commercial-analysis"
TEMP_AREA = f"{TEMP_DIR}/area_with_coords.csv"

TARGET_QUARTERS = [20241, 20242, 20243, 20244, 20251, 20252, 20253, 20254]
TARGET_INDUSTRIES = [
    "한식음식점", "중식음식점", "일식음식점", "양식음식점", "제과점",
    "패스트푸드점", "치킨전문점", "분식전문점", "호프-간이주점", "커피-음료", "편의점"
]

spark = SparkSession.builder \
    .appName("seoul_commercial_preprocess") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

df_sales = spark.read.csv(f"{HDFS_RAW}/sales_202*.csv", header=True, encoding="utf-8") \
    .select("기준_년분기_코드", "상권_코드", "서비스_업종_코드_명",
            "당월_매출_금액", "당월_매출_건수", "연령대_20_매출_금액", "연령대_30_매출_금액") \
    .withColumn("당월_매출_금액",      col("당월_매출_금액").cast("long")) \
    .withColumn("당월_매출_건수",      col("당월_매출_건수").cast("long")) \
    .withColumn("연령대_20_매출_금액", col("연령대_20_매출_금액").cast("long")) \
    .withColumn("연령대_30_매출_금액", col("연령대_30_매출_금액").cast("long")) \
    .filter(
        col("기준_년분기_코드").isin(TARGET_QUARTERS) &
        col("서비스_업종_코드_명").isin(TARGET_INDUSTRIES) &
        (col("당월_매출_금액") > 0) &
        (col("당월_매출_건수") > 0)
    ) \
    .dropna(subset=["상권_코드", "서비스_업종_코드_명", "당월_매출_금액", "당월_매출_건수"]) \
    .fillna(0, subset=["연령대_20_매출_금액", "연령대_30_매출_금액"])

df_stores = spark.read.csv(f"{HDFS_RAW}/stores_202*.csv", header=True, encoding="utf-8") \
    .select("기준_년분기_코드", "상권_코드", "서비스_업종_코드_명",
            "점포_수", "개업_점포_수", "폐업_점포_수") \
    .withColumn("점포_수",      col("점포_수").cast("long")) \
    .withColumn("개업_점포_수", col("개업_점포_수").cast("long")) \
    .withColumn("폐업_점포_수", col("폐업_점포_수").cast("long")) \
    .filter(
        col("기준_년분기_코드").isin(TARGET_QUARTERS) &
        col("서비스_업종_코드_명").isin(TARGET_INDUSTRIES) &
        (col("점포_수") > 0)
    ) \
    .dropna(subset=["상권_코드", "서비스_업종_코드_명", "점포_수"]) \
    .fillna(0, subset=["개업_점포_수", "폐업_점포_수"])

df_foot = spark.read.csv(f"{HDFS_RAW}/foot_traffic.csv", header=True, encoding="utf-8") \
    .select("기준_년분기_코드", "상권_코드", "총_유동인구_수") \
    .withColumn("총_유동인구_수", col("총_유동인구_수").cast("long")) \
    .filter(
        col("기준_년분기_코드").isin(TARGET_QUARTERS) &
        (col("총_유동인구_수") > 0)
    ) \
    .dropna(subset=["상권_코드", "총_유동인구_수"])

os.makedirs(TEMP_DIR, exist_ok=True)
subprocess.run(
    ["hdfs", "dfs", "-get", "-f", f"{HDFS_RAW}/area.csv", f"{TEMP_DIR}/area.csv"],
    check=True
)

pdf_area = pd.read_csv(f"{TEMP_DIR}/area.csv", encoding="utf-8")
transformer = Transformer.from_crs("EPSG:5181", "EPSG:4326", always_xy=True)
xs = pd.to_numeric(pdf_area["엑스좌표_값"], errors="coerce").to_numpy()
ys = pd.to_numeric(pdf_area["와이좌표_값"], errors="coerce").to_numpy()
pdf_area["경도"], pdf_area["위도"] = transformer.transform(xs, ys)

pdf_area = pdf_area[["상권_코드", "상권_구분_코드_명", "상권_코드_명",
                    "자치구_코드_명", "행정동_코드_명", "경도", "위도"]].copy()
for c in ["상권_구분_코드_명", "상권_코드_명", "자치구_코드_명", "행정동_코드_명"]:
    pdf_area[c] = pdf_area[c].fillna("미상")
pdf_area.to_csv(TEMP_AREA, index=False, encoding="utf-8")

df_area = spark.read.csv(TEMP_AREA, header=True, encoding="utf-8") \
    .withColumn("경도", col("경도").cast("double")) \
    .withColumn("위도", col("위도").cast("double")) \
    .fillna("미상", subset=["상권_구분_코드_명", "상권_코드_명", "자치구_코드_명", "행정동_코드_명"])

df_master = df_sales \
    .join(df_stores, on=["기준_년분기_코드", "상권_코드", "서비스_업종_코드_명"], how="inner") \
    .join(df_foot,   on=["기준_년분기_코드", "상권_코드"], how="inner") \
    .join(df_area,   on=["상권_코드"], how="left") \
    .filter(
        (col("상권_구분_코드_명") != "전통시장") &
        (~col("상권_코드_명").rlike("지하|백화점|마트|역사|터미널|코엑스"))
    )

df_master.coalesce(1).write \
    .mode("overwrite") \
    .parquet(f"{HDFS_OUT}/master_dataset")

spark.stop()