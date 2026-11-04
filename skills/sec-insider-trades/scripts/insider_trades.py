#!/usr/bin/env python3
"""Recent SEC Form 4 insider transactions for one ticker, straight from SEC EDGAR.

Standard library only. Every row carries the filing URL. The output header states
when the data was retrieved and the newest filing date it covers ("data through").

SEC fair-access rules: declare who you are (SEC_USER_AGENT="Your Name you@example.com")
and stay under 10 requests per second. This script pauses between requests.
https://www.sec.gov/os/accessing-edgar-data
"""
import argparse, datetime as dt, json, os, re, sys, time, urllib.error, urllib.request
import xml.etree.ElementTree as ET

CODES = {"P": "Open-market purchase", "S": "Open-market sale", "A": "Grant or award",
         "M": "Option exercise / conversion", "F": "Tax withholding (shares withheld)",
         "G": "Gift", "D": "Disposition to issuer", "C": "Conversion of derivative",
         "X": "Exercise of in-the-money option", "J": "Other (see footnotes)"}
_last = [0.0]

def get(url, ua):
    wait = 0.15 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 2:
                time.sleep(2 * (attempt + 1)); continue
            raise

def val(node, path):
    el = node.find(path)
    if el is None:
        return None
    v = el.find("value")
    t = (v.text if v is not None else el.text) or ""
    return t.strip() or None

def num(s):
    try:
        return float(s) if s is not None else None
    except ValueError:
        return None

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ticker")
    ap.add_argument("--days", type=int, default=30, help="look back this many days by filing date (default 30)")
    ap.add_argument("--codes", default="", help="comma list of transaction codes to keep, e.g. P,S (default all)")
    ap.add_argument("--max-filings", type=int, default=25, help="max Form 4 filings to open (default 25)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    a = ap.parse_args()
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not re.search(r"\S+@\S+\.\S+", ua):
        sys.exit("Set SEC_USER_AGENT to your name and email first, e.g.\n"
                 "  export SEC_USER_AGENT=\"Jane Doe jane@example.com\"\n"
                 "The SEC requires it: https://www.sec.gov/os/accessing-edgar-data")
    retrieved = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    tick = a.ticker.upper().replace(".", "-")
    tickers = json.loads(get("https://www.sec.gov/files/company_tickers.json", ua))
    hit = next((t for t in tickers.values() if t["ticker"].upper() == tick), None)
    if not hit:
        sys.exit(f"Ticker {tick} not found in https://www.sec.gov/files/company_tickers.json")
    cik = int(hit["cik_str"])
    sub = json.loads(get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", ua))
    rec = sub["filings"]["recent"]
    newest_any = max(rec["filingDate"]) if rec["filingDate"] else None
    since = (retrieved.date() - dt.timedelta(days=a.days)).isoformat()
    keep = {c.strip().upper() for c in a.codes.split(",") if c.strip()}
    rows, opened = [], 0
    for i, form in enumerate(rec["form"]):
        if form not in ("4", "4/A") or rec["filingDate"][i] < since:
            continue
        if opened >= a.max_filings:
            break
        opened += 1
        acc = rec["accessionNumber"][i]; accn = acc.replace("-", "")
        doc = rec["primaryDocument"][i].split("/")[-1]
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn}"
        xml_url = f"{base}/{doc}"
        try:
            root = ET.fromstring(get(xml_url, ua))
        except Exception as e:
            print(f"warn: could not read {xml_url}: {e}", file=sys.stderr); continue
        owners = []
        for o in root.findall("reportingOwner"):
            rel = o.find("reportingOwnerRelationship")
            role = []
            if rel is not None:
                if (rel.findtext("isDirector") or "").strip() in ("1", "true"): role.append("Director")
                if (rel.findtext("isOfficer") or "").strip() in ("1", "true"): role.append((rel.findtext("officerTitle") or "Officer").strip())
                if (rel.findtext("isTenPercentOwner") or "").strip() in ("1", "true"): role.append("10% owner")
            owners.append({"name": (o.findtext("reportingOwnerId/rptOwnerName") or "").strip(), "role": ", ".join(role) or None})
        plan = (root.findtext("aff10b5One") or "").strip() in ("1", "true")
        for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
            code = val(t, "transactionCoding/transactionCode")
            if keep and code not in keep:
                continue
            sh, px = num(val(t, "transactionAmounts/transactionShares")), num(val(t, "transactionAmounts/transactionPricePerShare"))
            rows.append({
                "filing_date": rec["filingDate"][i], "form": form,
                "insider": "; ".join(o["name"] for o in owners), "role": "; ".join(o["role"] or "" for o in owners) or None,
                "transaction_date": val(t, "transactionDate"), "code": code, "code_meaning": CODES.get(code, "See SEC Form 4 code list"),
                "acquired_or_disposed": val(t, "transactionAmounts/transactionAcquiredDisposedCode"),
                "shares": sh, "price": px, "value_usd": round(sh * px, 2) if sh and px else None,
                "shares_owned_after": num(val(t, "postTransactionAmounts/sharesOwnedFollowingTransaction")),
                "rule_10b5_1_plan_box_checked": plan,
                "filing_url": xml_url, "filing_index_url": f"{base}/{acc}-index.htm"})
    out = {"ticker": tick, "issuer": sub.get("name"), "cik": cik,
           "source": f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
           "retrieved_at_utc": retrieved.isoformat(), "window_filing_dates": f"{since}..{retrieved.date().isoformat()}",
           "data_through_filing_date": max((r["filing_date"] for r in rows), default=None),
           "newest_filing_of_any_form": newest_any, "form4_filings_opened": opened, "transactions": rows,
           "note": "Public SEC data. Not investment advice. Form 4 is due within 2 business days of the trade, so the newest trades may not be filed yet."}
    if a.json:
        print(json.dumps(out, indent=1)); return
    print(f"{out['issuer']} ({tick}, CIK {cik}) Form 4 transactions, filed {out['window_filing_dates']} (UTC dates)")
    print(f"Retrieved {out['retrieved_at_utc']} from SEC EDGAR. Data through filing date: {out['data_through_filing_date'] or 'no Form 4 in window'}. Filings opened: {opened}.")
    for r in rows:
        v = f"${r['value_usd']:,.0f}" if r["value_usd"] else "n/a"
        print(f"- {r['transaction_date']} {r['insider']} ({r['role'] or 'n/a'}): {r['code']} {r['code_meaning']}, "
              f"{r['shares'] or 0:,.0f} sh @ {r['price'] if r['price'] is not None else 'n/a'} = {v}; "
              f"owns {r['shares_owned_after'] or 0:,.0f} after{'; filing has 10b5-1 plan box checked' if r['rule_10b5_1_plan_box_checked'] else ''}\n  {r['filing_url']}")
    print(out["note"])

if __name__ == "__main__":
    main()
