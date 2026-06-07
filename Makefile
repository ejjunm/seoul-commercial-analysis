PYTHON  := /home/maria_dev/anaconda3/bin/python
SPARK    SPARK    := PYSPARK_PYTHON=/home/maria_dev/anaconda3/bin/python PYSPARK_DRIVER_PYTHON=/home/maria_dev/anaconda3/bin/python spark-submit
INGEST   := src/ingest
PIPELINE := src/pipeline
HDFS     := /user/maria_dev/seoul-commercial-analysis

.PHONY: all ingest preprocess pipeline sample hdfs-ls clean

all: pipeline sample

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