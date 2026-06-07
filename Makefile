PYTHON  := /home/maria_dev/anaconda3/bin/python
PIP      := /home/maria_dev/anaconda3/bin/pip
SPARK    := PYSPARK_PYTHON=/home/maria_dev/anaconda3/bin/python PYSPARK_DRIVER_PYTHON=/home/maria_dev/anaconda3/bin/python spark-submit
INGEST   := src/ingest
PIPELINE := src/pipeline
HDFS     := /user/maria_dev/seoul-commercial-analysis

.PHONY: all setup ingest preprocess pipeline sample hdfs-ls clean

all: setup pipeline sample

setup:
	$(PIP) install pyproj
	@if [ -w /usr/hdp/current/spark2-client/conf/spark-defaults.conf ]; then \
		if ! grep -q "spark.executorEnv.PYTHONPATH" /usr/hdp/current/spark2-client/conf/spark-defaults.conf; then \
			echo "spark.executorEnv.PYTHONPATH /home/maria_dev/anaconda3/bin/python" >> /usr/hdp/current/spark2-client/conf/spark-defaults.conf; \
			echo "spark.yarn.appMasterEnv.PYTHONPATH /home/maria_dev/anaconda3/bin/python" >> /usr/hdp/current/spark2-client/conf/spark-defaults.conf; \
		fi \
	fi

ingest:
	cd $(INGEST) && $(PYTHON) collect.py

preprocess:
	$(SPARK) $(PIPELINE)/preprocess.py

pipeline: ingest preprocess

sample:
	cd $(INGEST) && $(PYTHON) make_sample.py

hdfs-ls:
	@echo "=== raw ===" && hdfs dfs -ls $(HDFS)/data/raw       2>/dev/null || echo "(없음)"
	@echo "=== processed ===" && hdfs dfs -ls $(HDFS)/data/processed 2>/dev/null || echo "(없음)"

clean:
	rm -rf /tmp/seoul-commercial-analysis ./data/sample