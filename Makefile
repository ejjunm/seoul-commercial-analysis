PYTHON := python3
SRC    := src/ingestion
HDFS   := /user/maria_dev/seoul_commercial_analysis

.PHONY: all collect sample hdfs-ls clean

all: collect sample

collect:
	cd $(SRC) && $(PYTHON) collect.py

sample:
	cd $(SRC) && $(PYTHON) make_sample.py

hdfs-ls:
	@hdfs dfs -ls $(HDFS)/raw 2>/dev/null || echo "(없음)"

clean:
	rm -rf /tmp/seoul_commercial_analysis ./data/sample