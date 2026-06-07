import os
import sys
import zipfile
import shutil
import subprocess
import requests

TMP_DIR  = "/tmp/seoul-commercial-analysis/raw"
HDFS_RAW = "/user/maria_dev/seoul-commercial-analysis/raw"
ZIP_URL  = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
CSV_URL  = "https://datafile.seoul.go.kr/bigfile/iot/sheet/csv/download.do"
CHUNK    = 1024 * 1024

DATASETS = [
    ("zip", {"infId": "OA-15572", "seq": "51", "infSeq": "3"}, "sales_2025.csv"),
    ("zip", {"infId": "OA-15572", "seq": "50", "infSeq": "3"}, "sales_2024.csv"),
    ("zip", {"infId": "OA-15577", "seq": "20", "infSeq": "3"}, "stores_2025.csv"),
    ("zip", {"infId": "OA-15577", "seq": "19", "infSeq": "3"}, "stores_2024.csv"),
    ("csv", {
        "srvType": "S", "infId": "OA-15568", "serviceKind": "1",
        "pageNo": "1", "gridTotalCnt": "46184", "ssUserId": "SAMPLE_VIEW",
        "strWhere": "", "strOrderby": "STDR_YYQU_CD DESC", "filterCol": "필터선택", "txtFilter": "",
    }, "foot_traffic.csv"),
    ("csv", {
        "srvType": "S", "infId": "OA-15560", "serviceKind": "1",
        "pageNo": "1", "gridTotalCnt": "1650", "ssUserId": "SAMPLE_VIEW",
        "strWhere": "", "strOrderby": "", "filterCol": "", "txtFilter": "",
    }, "area.csv"),
]


def _to_utf8(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        with open(path, "wb") as f:
            f.write(raw[3:])
        return
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw.decode("cp949"))


def _download_zip(payload, local):
    r = requests.post(ZIP_URL, data=payload, stream=True, timeout=120)
    r.raise_for_status()
    tmp_zip = local + ".tmp"
    with open(tmp_zip, "wb") as f:
        for chunk in r.iter_content(chunk_size=CHUNK):
            if chunk:
                f.write(chunk)
    with zipfile.ZipFile(tmp_zip, "r") as z:
        csvs = [n for n in z.namelist() if n.endswith(".csv")]
        with z.open(csvs[0]) as src, open(local, "wb") as dst:
            shutil.copyfileobj(src, dst)
    os.remove(tmp_zip)


def _download_csv(payload, local):
    r = requests.post(CSV_URL, data=payload, stream=True, timeout=120)
    r.raise_for_status()
    with open(local, "wb") as f:
        for chunk in r.iter_content(chunk_size=CHUNK):
            if chunk:
                f.write(chunk)


def main():
    os.makedirs(TMP_DIR, exist_ok=True)
    subprocess.run(["hdfs", "dfs", "-mkdir", "-p", HDFS_RAW], check=True)

    failed = []
    for mode, payload, filename in DATASETS:
        local = os.path.join(TMP_DIR, filename)
        try:
            if mode == "zip":
                _download_zip(payload, local)
            else:
                _download_csv(payload, local)
            _to_utf8(local)
            subprocess.run(["hdfs", "dfs", "-put", "-f", local, f"{HDFS_RAW}/{filename}"], check=True)
        except Exception as e:
            failed.append(f"{filename}: {e}")
        finally:
            if os.path.exists(local):
                os.remove(local)

    if failed:
        print("실패:", "\n".join(failed), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()