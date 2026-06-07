import os
import sys
import subprocess
import pandas as pd

HDFS_RAW    = "/user/maria_dev/seoul_commercial_analysis/raw"
SAMPLE_DIR  = "./data/sample"
SAMPLE_ROWS = 100
TMP_DIR     = "/tmp/seoul_commercial_analysis/raw"


def main():
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    result = subprocess.run(
        ["hdfs", "dfs", "-ls", HDFS_RAW],
        capture_output=True, text=True
    )
    csv_files = [
        line.split()[-1]
        for line in result.stdout.splitlines()
        if line.startswith("-") and line.endswith(".csv")
    ]

    failed = []
    for hdfs_path in csv_files:
        name  = os.path.basename(hdfs_path)
        local = os.path.join(TMP_DIR, name)
        out   = os.path.join(SAMPLE_DIR, f"sample_{name}")
        try:
            subprocess.run(["hdfs", "dfs", "-get", "-f", hdfs_path, local], check=True)
            try:
                df = pd.read_csv(local, nrows=SAMPLE_ROWS, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(local, nrows=SAMPLE_ROWS, encoding="cp949")
            df.to_csv(out, index=False, encoding="utf-8")
        except Exception as e:
            failed.append(f"{name}: {e}")
        finally:
            if os.path.exists(local):
                os.remove(local)

    if failed:
        print("실패:", "\n".join(failed), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()