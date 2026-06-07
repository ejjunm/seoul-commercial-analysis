CONDA    := /home/maria_dev/anaconda3/bin/conda
ENV_DIR  := /home/maria_dev/anaconda3/envs/spark2_env
PYTHON   := $(ENV_DIR)/bin/python
PIP      := $(ENV_DIR)/bin/pip
SPARK    := PYSPARK_PYTHON=$(PYTHON) PYSPARK_DRIVER_PYTHON=$(PYTHON) spark-submit
INGEST   := src/ingest
PIPELINE := src/pipeline
ANALYZE  := src/analyze
HDFS     := /user/maria_dev/seoul-commercial-analysis

.PHONY: all setup ingest preprocess analyze ml dashboard dashboard-html pipeline sample hdfs-ls clean

all: setup pipeline ml analyze dashboard dashboard-html

setup:
	@echo "=== [1/6] Checking/Creating Python 3.7 Environment for Spark 2.x ==="
	@if [ ! -d "$(ENV_DIR)" ]; then \
		$(CONDA) create -p $(ENV_DIR) python=3.7 -y; \
	fi
	@echo "=== [2/6] Installing dependencies ==="
	$(PIP) install pyproj pandas requests xgboost shap scikit-learn matplotlib streamlit plotly

ingest:
	@echo "=== [3/6] Running Data Ingestion ==="
	cd $(INGEST) && $(PYTHON) collect.py

preprocess:
	@echo "=== [4/6] Running Spark Preprocessing ==="
	$(SPARK) $(PIPELINE)/preprocess.py

pipeline: ingest preprocess

ml:
	@echo "=== [5/6] Running Q3 ML (XGBoost) ==="
	$(SPARK) $(ANALYZE)/ml_insight_q3.py

analyze:
	@echo "=== [6/6] Running Q1/Q2 Analysis with Spark SQL ==="
	$(SPARK) $(ANALYZE)/run_analysis.py

dashboard:
	@echo "=== Building Dashboard CSVs ==="
	$(SPARK) $(ANALYZE)/build_dashboard_data.py

dashboard-html:
	@echo "=== Building static HTML dashboard ==="
	$(PYTHON) $(ANALYZE)/build_dashboard_html.py
	@echo "생성 완료: data/processed/dashboard/dashboard.html"

sample:
	cd $(INGEST) && $(PYTHON) make_sample.py

hdfs-ls:
	@echo "=== raw ==="       && hdfs dfs -ls $(HDFS)/data/raw       2>/dev/null || echo "(없음)"
	@echo "=== processed ===" && hdfs dfs -ls $(HDFS)/data/processed 2>/dev/null || echo "(없음)"

clean:
	rm -rf /tmp/seoul-commercial-analysis ./data/sample