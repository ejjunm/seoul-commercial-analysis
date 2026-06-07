CONDA    := /home/maria_dev/anaconda3/bin/conda
ENV_DIR  := /home/maria_dev/anaconda3/envs/spark2_env
PYTHON   := $(ENV_DIR)/bin/python
PIP      := $(ENV_DIR)/bin/pip
SPARK    := PYSPARK_PYTHON=$(PYTHON) PYSPARK_DRIVER_PYTHON=$(PYTHON) spark-submit
INGEST   := src/ingest
PIPELINE := src/pipeline
HDFS     := /user/maria_dev/seoul-commercial-analysis

.PHONY: all setup ingest preprocess pipeline sample hdfs-ls clean

all: setup pipeline sample

setup:
	@echo "=== [1/4] Checking/Creating Python 3.7 Environment for Spark 2.x ==="
	@if [ ! -d "$(ENV_DIR)" ]; then \
		$(CONDA) create -p $(ENV_DIR) python=3.7 -y; \
	fi
	@echo "=== [2/4] Installing dependencies ==="
	$(PIP) install pyproj pandas requests

ingest:
	@echo "=== [3/4] Running Data Ingestion ==="
	cd $(INGEST) && $(PYTHON) collect.py

preprocess:
	@echo "=== [4/4] Running Spark Preprocessing ==="
	$(SPARK) $(PIPELINE)/preprocess.py

pipeline: ingest preprocess

sample:
	@echo "=== [5/5] Extracting Samples ==="
	cd $(INGEST) && $(PYTHON) make_sample.py

hdfs-ls:
	@echo "=== raw ===" && hdfs dfs -ls $(HDFS)/data/raw 2>/dev/null || echo "(없음)"
	@echo "=== processed ===" && hdfs dfs -ls $(HDFS)/data/processed 2>/dev/null || echo "(없음)"

clean:
	rm -rf /tmp/seoul-commercial-analysis ./data/sample