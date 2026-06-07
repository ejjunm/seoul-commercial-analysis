import sys
import traceback
from pyspark.sql import SparkSession

MASTER_PATH = "/user/maria_dev/seoul-commercial-analysis/data/processed/master_dataset"
ML_PATH     = "/user/maria_dev/seoul-commercial-analysis/data/processed/seoul_q3_ml_result"
HQL_PATH    = "./src/analyze/analyze_insight.hql"

spark = SparkSession.builder \
    .appName("Seoul_Commercial_Analysis_Runner") \
    .config("spark.sql.legacy.timeParserPolicy", "LEGACY") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

try:
    df_master = spark.read.parquet(MASTER_PATH)
    df_master.createOrReplaceTempView("seoul_commercial_master")

    df_ml = spark.read.parquet(ML_PATH)
    df_ml.createOrReplaceTempView("seoul_q3_ml_result")

except Exception as e:
    print("파케이 데이터 로드 실패. preprocess.py와 ml_insight_q3.py가 완료됐는지 확인하세요.", flush=True)
    traceback.print_exc()
    spark.stop()
    sys.exit(1)

with open(HQL_PATH, 'r', encoding='utf-8') as f:
    lines = f.readlines()

clean_lines = []
for line in lines:
    if '--' in line:
        line = line.split('--')[0]
    clean_lines.append(line)

queries = [q.strip() for q in " ".join(clean_lines).split(';') if q.strip()]

query_count = 1
for query in queries:
    if query.upper().startswith(("DROP", "CREATE", "MSCK", "USE")):
        continue

    print(f"[Query {query_count}] 실행 중...", flush=True)
    try:
        result_df = spark.sql(query)
        result_df.show(20, truncate=False)
        query_count += 1
    except Exception as e:
        print(f"[Query {query_count}] 실패", flush=True)
        traceback.print_exc()
        break

spark.stop()