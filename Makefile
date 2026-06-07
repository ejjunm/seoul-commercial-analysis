PYTHON  := /home/maria_dev/anaconda3/bin/python
PIP      := /home/maria_dev/anaconda3/bin/pip
SPARK    := PYSPARK_PYTHON=/home/maria_dev/anaconda3/bin/python PYSPARK_DRIVER_PYTHON=/home/maria_dev/anaconda3/bin/python spark-submit
INGEST   := src/ingest
PIPELINE := src/pipeline
HDFS     := /user/maria_dev/seoul-commercial-analysis

.PHONY: all setup ingest preprocess pipeline sample hdfs-ls clean

all: setup pipeline sample

setup:
	$(PIP) install pyproj cloudpickle

ingest:
	cd $(INGEST) && $(PYTHON) collect.py

preprocess:
	export SPARK_MINIDUMP_CONFIG=1 && \
	export PYSPARK_PYTHON=$(PYTHON) && \
	export PYSPARK_DRIVER_PYTHON=$(PYTHON) && \
	spark-submit \
		--conf spark.executorEnv.PYTHONPATH=$(PYTHON) \
		--conf spark.yarn.appMasterEnv.PYTHONPATH=$(PYTHON) \
		$(PIPELINE)/preprocess.py

pipeline: ingest preprocess

sample:
	cd $(INGEST) && $(PYTHON) make_sample.py

hdfs-ls:
	@echo "=== raw ===" && hdfs dfs -ls $(HDFS)/data/raw       2>/dev/null || echo "(없음)"
	@echo "=== processed ===" && hdfs dfs -ls $(HDFS)/data/processed 2>/dev/null || echo "(없음)"

clean:
	rm -rf /tmp/seoul-commercial-analysis ./data/sample