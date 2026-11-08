"""Download daily history for NIFTY and the macro factors that move it.

Sources: Yahoo Finance chart API (prices) and FRED (US rates). Output: data/*.csv
Run: python3 fetch_data.py
"""
import csv, io, json, os, sys, time, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (option-desk research)"}

YAHOO = {
    "NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "INDIAVIX": "^INDIAVIX",
    "USDINR": "INR=X", "BRENT": "BZ=F", "WTI": "CL=F", "GOLD": "GC=F",
    "SILVER": "SI=F", "COPPER": "HG=F", "NATGAS": "NG=F",
    "SP500": "^GSPC", "NASDAQ": "^IXIC", "DOW": "^DJI", "USVIX": "^VIX",
    "DXY": "DX-Y.NYB", "US10Y": "^TNX", "US13W": "^IRX", "US30Y": "^TYX",
    "NIKKEI": "^N225", "HANGSENG": "^HSI", "SHANGHAI": "000001.SS",
    "FTSE": "^FTSE", "DAX": "^GDAXI", "BITCOIN": "BTC-USD",
}
FRED = {"FEDFUNDS": "DFF", "UST10Y": "DGS10", "UST2Y": "DGS2", "T10Y2Y": "T10Y2Y",
        "US_REAL10Y": "DFII10", "US_HY_SPREAD": "BAMLH0A0HYM2"}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(2 ** (i + 1))


def yahoo(name, sym):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym)}"
           f"?period1=1104537600&period2={int(time.time())}&interval=1d&events=div%2Csplit")
    j = json.loads(get(url))["chart"]["result"][0]
    ts, q = j["timestamp"], j["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(ts):
        c = q["close"][i]
        if c is None:
            continue
        d = datetime.fromtimestamp(t + j["meta"].get("gmtoffset", 0), tz=timezone.utc).date()
        rows.append([d.isoformat(), q["open"][i], q["high"][i], q["low"][i], c, q["volume"][i] or 0])
    with open(os.path.join(OUT, f"{name}.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "open", "high", "low", "close", "volume"]); w.writerows(rows)
    return len(rows), rows[0][0], rows[-1][0]


def fred(name, sid):
    txt = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd=2005-01-01").decode()
    rows = [r for r in csv.reader(io.StringIO(txt))][1:]
    rows = [[d, v] for d, v in rows if v not in (".", "")]
    with open(os.path.join(OUT, f"{name}.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "value"]); w.writerows(rows)
    return len(rows), rows[0][0], rows[-1][0]


if __name__ == "__main__":
    for n, s in YAHOO.items():
        try:
            print(n, *yahoo(n, s))
        except Exception as e:  # noqa: BLE001
            print(n, "FAILED", e, file=sys.stderr)
    for n, s in FRED.items():
        try:
            print(n, *fred(n, s))
        except Exception as e:  # noqa: BLE001
            print(n, "FAILED", e, file=sys.stderr)
