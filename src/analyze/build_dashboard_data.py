import os
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window

spark = SparkSession.builder.appName("Dashboard_Data_Prep").getOrCreate()

out_dir = "./data/processed/dashboard"
os.makedirs(out_dir, exist_ok=True)

m = spark.read.parquet("/user/maria_dev/seoul-commercial-analysis/data/processed/master_dataset")
m = m.withColumn("기준_년분기_코드", F.col("기준_년분기_코드").cast("string"))

mg = m.filter(F.col("자치구_코드_명").isNotNull() & (F.col("자치구_코드_명") != "미상"))

# 상권당 좌표 (Q2·Q3 지도 join 공용)
coords = m.groupBy("상권_코드").agg(
    F.first("경도",         True).alias("경도"),
    F.first("위도",         True).alias("위도"),
    F.first("자치구_코드_명", True).alias("자치구_코드_명"),
)

base = mg.groupBy("자치구_코드_명", "상권_코드", "기준_년분기_코드").agg(
    F.sum("당월_매출_금액").alias("분기_총매출"),
    F.max("총_유동인구_수").alias("분기_최대_유동인구"),
    F.sum("점포_수").alias("분기_총점포수"),
)
gu = base.groupBy("자치구_코드_명").agg(
    F.countDistinct("상권_코드").alias("보유_상권_수"),
    F.sum("분기_총매출").alias("구_총매출_원"),
    F.avg("분기_최대_유동인구").alias("분기평균_유동인구"),
    F.avg("분기_총매출").alias("평균_분기매출"),
    F.avg("분기_총점포수").alias("평균_분기점포수"),
).withColumn("구_총매출_억원",    F.round(F.col("구_총매출_원") / 1e8, 1)) \
 .withColumn("분기평균_유동인구_만명", F.round(F.col("분기평균_유동인구") / 1e4, 1)) \
 .withColumn("점포당_평균매출_억원",
     F.round(F.col("평균_분기매출") / F.col("평균_분기점포수") / 1e8, 3))

tab1 = gu.select("자치구_코드_명", "보유_상권_수", "구_총매출_억원",
                 "분기평균_유동인구_만명", "점포당_평균매출_억원").toPandas()
tab1.to_csv(f"{out_dir}/tab1_gu_summary.csv", index=False, encoding="utf-8-sig")

base_lq = mg.groupBy("자치구_코드_명", "서비스_업종_코드_명").agg(
    F.sum("당월_매출_금액").alias("매출"),
    F.sum("점포_수").alias("점포수"),
)
gu_tot = base_lq.groupBy("자치구_코드_명").agg(
    F.sum("매출").alias("구_매출"),
    F.sum("점포수").alias("구_점포수"),
)
s_rev   = float(base_lq.agg(F.sum("매출")).collect()[0][0])
s_store = float(base_lq.agg(F.sum("점포수")).collect()[0][0])
ind_tot = base_lq.groupBy("서비스_업종_코드_명").agg(
    F.sum("매출").alias("업종_매출"),
    F.sum("점포수").alias("업종_점포수"),
)
lq_df = base_lq.join(gu_tot, "자치구_코드_명").join(ind_tot, "서비스_업종_코드_명") \
    .withColumn("Rev_LQ",
        (F.col("매출")   / F.col("구_매출"))   / (F.col("업종_매출")   / F.lit(s_rev))) \
    .withColumn("Store_LQ",
        (F.col("점포수") / F.col("구_점포수")) / (F.col("업종_점포수") / F.lit(s_store))) \
    .withColumn("종합_LQ", F.col("Rev_LQ") * 0.7 + F.col("Store_LQ") * 0.3)

w_lq = Window.partitionBy("자치구_코드_명").orderBy(F.col("종합_LQ").desc())
tab1_lq = lq_df.withColumn("rn", F.row_number().over(w_lq)).filter(F.col("rn") == 1) \
    .select(
        "자치구_코드_명",
        F.col("서비스_업종_코드_명").alias("랜드마크_업종"),
        F.round("종합_LQ",   2).alias("종합_특화도_LQ"),
        F.round("Rev_LQ",   2).alias("매출_LQ"),
        F.round("Store_LQ", 2).alias("점포수_LQ"),
    ).toPandas().sort_values("종합_특화도_LQ", ascending=False)
tab1_lq.to_csv(f"{out_dir}/tab1_lq.csv", index=False, encoding="utf-8-sig")

q2_qtr = m.filter(F.col("점포_수") > 0).groupBy(
    "상권_코드", "상권_코드_명", "자치구_코드_명", "서비스_업종_코드_명", "기준_년분기_코드"
).agg(
    (F.sum("당월_매출_금액") / F.sum("점포_수") / 3.0).alias("월_점포당_매출"),
    F.avg("점포_수").alias("분기_점포수"),
)

def qr(code):
    return F.coalesce(
        F.max(F.when(F.col("기준_년분기_코드") == code, F.col("월_점포당_매출"))),
        F.lit(0.0),
    )

q2_pivot = q2_qtr.groupBy(
    "상권_코드", "상권_코드_명", "자치구_코드_명", "서비스_업종_코드_명"
).agg(
    F.count("기준_년분기_코드").alias("영업_분기수"),
    F.avg("분기_점포수").alias("평균_점포수"),
    qr("20241").alias("Q1"), qr("20242").alias("Q2"),
    qr("20243").alias("Q3"), qr("20244").alias("Q4"),
    qr("20251").alias("Q5"), qr("20252").alias("Q6"),
    qr("20253").alias("Q7"), qr("20254").alias("Q8"),
)

q2_m = q2_pivot.filter(F.col("영업_분기수") >= 4) \
    .withColumn("전반기_평균", (F.col("Q1")+F.col("Q2")+F.col("Q3")+F.col("Q4"))/4.0) \
    .withColumn("후반기_평균", (F.col("Q5")+F.col("Q6")+F.col("Q7")+F.col("Q8"))/4.0) \
    .withColumn("abs_growth",  F.col("후반기_평균") - F.col("전반기_평균")) \
    .withColumn("growth_rate",
        F.when(F.col("전반기_평균") > 0,
               F.col("후반기_평균") / F.col("전반기_평균") - 1.0).otherwise(None)) \
    .withColumn("up_count",
        F.when(F.col("Q2")>F.col("Q1"),1).otherwise(0) +
        F.when(F.col("Q3")>F.col("Q2"),1).otherwise(0) +
        F.when(F.col("Q4")>F.col("Q3"),1).otherwise(0) +
        F.when(F.col("Q5")>F.col("Q4"),1).otherwise(0) +
        F.when(F.col("Q6")>F.col("Q5"),1).otherwise(0) +
        F.when(F.col("Q7")>F.col("Q6"),1).otherwise(0) +
        F.when(F.col("Q8")>F.col("Q7"),1).otherwise(0))

w_ind = Window.partitionBy("서비스_업종_코드_명")

mega = q2_m.filter(
    (F.col("평균_점포수") >= 30) &
    (F.col("전반기_평균") >= 40_000_000) &
    (F.col("growth_rate") > 0) &
    F.col("growth_rate").isNotNull()
).withColumn("ind_cnt", F.count("*").over(w_ind)) \
 .filter(F.col("ind_cnt") >= 3) \
 .withColumn("min_vol", F.min("abs_growth").over(w_ind)) \
 .withColumn("max_vol", F.max("abs_growth").over(w_ind)) \
 .withColumn("min_spd", F.min("growth_rate").over(w_ind)) \
 .withColumn("max_spd", F.max("growth_rate").over(w_ind)) \
 .withColumn("norm_vol",
     F.when(F.col("max_vol") != F.col("min_vol"),
            (F.col("abs_growth")-F.col("min_vol")) /
            (F.col("max_vol")-F.col("min_vol")) * 100
     ).otherwise(F.lit(50.0))
 ).withColumn("norm_spd",
     F.when(F.col("max_spd") != F.col("min_spd"),
            (F.col("growth_rate")-F.col("min_spd")) /
            (F.col("max_spd")-F.col("min_spd")) * 100
     ).otherwise(F.lit(50.0))
 ).withColumn("norm_cnt", F.col("up_count") / 7.0 * 100) \
 .withColumn("메가_상승_총점",
     F.col("norm_vol")*0.6 + F.col("norm_spd")*0.2 + F.col("norm_cnt")*0.2) \
 .withColumn("구분", F.lit("메가 핫플")) \
 .orderBy(F.col("메가_상승_총점").desc()).limit(10)

rising = q2_m.filter(
    (F.col("평균_점포수") >= 15) & (F.col("평균_점포수") < 30) &
    (F.col("전반기_평균") >= 20_000_000) & (F.col("전반기_평균") < 40_000_000) &
    (F.col("growth_rate") >= 0.20) &
    (F.col("up_count") >= 3) &
    F.col("growth_rate").isNotNull()
).withColumn("구분", F.lit("라이징 핫플")) \
 .withColumn("메가_상승_총점", F.lit(None).cast("double")) \
 .orderBy(F.col("growth_rate").desc()).limit(10)

sel = ["상권_코드", "상권_코드_명", "자치구_코드_명", "서비스_업종_코드_명",
       "구분", "평균_점포수", "전반기_평균", "후반기_평균",
       "growth_rate", "up_count", "메가_상승_총점"]

tab2 = mega.select(sel).union(rising.select(sel)) \
           .join(coords, "상권_코드", "left") \
           .toPandas()

tab2["24년_월점포당_만원"] = (tab2["전반기_평균"] / 10_000).round(0).astype("Int64")
tab2["25년_월점포당_만원"] = (tab2["후반기_평균"] / 10_000).round(0).astype("Int64")
tab2["성장률_퍼센트"]      = (tab2["growth_rate"] * 100).round(1)
tab2["평균_점포수"]        = tab2["평균_점포수"].round(1)
tab2["메가_상승_총점"]     = tab2["메가_상승_총점"].round(2)
tab2.to_csv(f"{out_dir}/tab2_hotplaces.csv", index=False, encoding="utf-8-sig")

q3  = spark.read.parquet("/user/maria_dev/seoul-commercial-analysis/data/processed/seoul_q3_ml_result")
m25 = m.filter(F.col("기준_년분기_코드").substr(1, 4) == "2025")
rev = m25.groupBy("상권_코드", "서비스_업종_코드_명").agg(
    (F.sum("당월_매출_금액") / F.sum("점포_수") / 3.0).alias("월_점포당_매출_원")
).withColumn("월_점포당_매출_만원", F.round(F.col("월_점포당_매출_원") / 1e4, 0))

tab3_pd = q3.join(coords, "상권_코드", "left") \
            .join(rev.select("상권_코드", "서비스_업종_코드_명", "월_점포당_매출_만원"),
                  on=["상권_코드", "서비스_업종_코드_명"], how="left") \
            .filter(F.col("경도").isNotNull() & F.col("위도").isNotNull()) \
            .select(
                "상권_코드", "상권_코드_명", "자치구_코드_명", "서비스_업종_코드_명",
                "경도", "위도", "월_점포당_매출_만원",
                "MZ_매출_비중", "상대_시장활력도_비율", "상권_특화도_LQ", "상권_경쟁밀도",
                "청년안착_적합도", "진입가능성", "청년_라이징_추천점수",
            ).toPandas()
tab3_pd.to_csv(f"{out_dir}/tab3_youth_map.csv", index=False, encoding="utf-8-sig")

spark.stop()
