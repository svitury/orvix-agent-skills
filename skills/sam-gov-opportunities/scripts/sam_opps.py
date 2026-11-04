#!/usr/bin/env python3
"""Search SAM.gov's public Contract Opportunities extract. Standard library only, no API key."""
import argparse, csv, datetime as dt, io, json, sys, time, urllib.request
CSV_URL = "https://falextracts.s3.amazonaws.com/Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv"
USAS = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
UA = {"User-Agent": "orvix-agent-skill sam-gov-opportunities/0.1"}

def similar(naics, today, n=3):
    body = {"filters": {"award_type_codes": ["A", "B", "C", "D"], "naics_codes": {"require": [naics]},
            "time_period": [{"start_date": str(today - dt.timedelta(days=3 * 365)), "end_date": str(today)}]},
            "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "generated_internal_id"],
            "limit": n, "sort": "Award Amount", "order": "desc"}
    req = urllib.request.Request(USAS, json.dumps(body).encode(), {**UA, "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=60))["results"]
    except Exception as e:
        return {"error": str(e), "awards": []}
    return {"scope": f"top {n} contract awards by amount, NAICS {naics}, all agencies, last 3 years (USAspending.gov)",
            "awards": [{"recipient": a["Recipient Name"], "amountUsd": a["Award Amount"], "agency": a["Awarding Agency"],
                        "url": "https://www.usaspending.gov/award/" + a["generated_internal_id"]} for a in r]}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--keyword", action="append", default=[]); p.add_argument("--in-description", action="store_true")
    p.add_argument("--naics", action="append", default=[]); p.add_argument("--set-aside", action="append", default=[])
    p.add_argument("--agency", action="append", default=[]); p.add_argument("--days", type=int, default=30)
    p.add_argument("--max", type=int, default=20); p.add_argument("--similar", action="store_true"); p.add_argument("--json", action="store_true")
    a = p.parse_args()
    today = dt.date.today(); since = str(today - dt.timedelta(days=a.days))
    resp = urllib.request.urlopen(urllib.request.Request(CSV_URL, headers=UA), timeout=300)
    extract = resp.headers.get("x-amz-meta-lastmodifieddate") or resp.headers.get("Last-Modified")
    csv.field_size_limit(10**9)
    rows = csv.DictReader(io.TextIOWrapper(resp, encoding="cp1252", errors="replace", newline=""))
    kw = [k.lower() for k in a.keyword]; sa = [s.upper() for s in a.set_aside]; ag = [x.lower() for x in a.agency]
    hits = []
    for r in rows:
        if r["Active"] != "Yes" or r["PostedDate"][:10] < since: continue
        due = r["ResponseDeadLine"][:10]
        if due and due < str(today): continue
        if a.naics and not any(r["NaicsCode"].startswith(n) for n in a.naics): continue
        if sa and r["SetASideCode"].upper() not in sa: continue
        if ag and not any(x in f'{r["Department/Ind.Agency"]} {r["Sub-Tier"]} {r["Office"]}'.lower() for x in ag): continue
        text = (r["Title"] + (" " + r["Description"] if a.in_description else "")).lower()
        if kw and not any(k in text for k in kw): continue
        hits.append(r)
    hits.sort(key=lambda r: r["PostedDate"], reverse=True)
    seen, out = set(), []
    for r in hits:  # each amendment is its own notice; keep the newest per solicitation number
        key = (r["Sol#"], r["AAC Code"]) if r["Sol#"] else r["NoticeId"]
        if key in seen: continue
        seen.add(key)
        out.append({"title": r["Title"], "agency": f'{r["Department/Ind.Agency"]} / {r["Sub-Tier"]}', "type": r["Type"],
                    "setAside": r["SetASide"] or "n/a", "naics": r["NaicsCode"] or "n/a", "posted": r["PostedDate"] + " ET",
                    "responseDeadline": r["ResponseDeadLine"] or "n/a", "url": r["Link"]})
        if len(out) >= a.max: break
    if a.similar:
        cache = {}
        for o in out:
            if o["naics"] != "n/a":
                if o["naics"] not in cache: cache[o["naics"]] = similar(o["naics"], today); time.sleep(0.5)
                o["similarPastAwards"] = cache[o["naics"]]
    if a.json:
        print(json.dumps({"extractDate": extract, "matched": len(seen), "shown": len(out), "results": out}, indent=1)); return
    print(f"SAM.gov extract of {extract}. {len(out)} shown of {len(seen)} active matching notices (newest version per solicitation).")
    for o in out:
        print(f'\n- {o["title"]}\n  {o["agency"]} | {o["type"]} | set-aside: {o["setAside"]} | NAICS {o["naics"]}\n  posted {o["posted"]}, respond by {o["responseDeadline"]}\n  {o["url"]}')
        for s in o.get("similarPastAwards", {}).get("awards", []):
            print(f'    similar past award: {s["recipient"]} ${s["amountUsd"]:,.2f} ({s["agency"]}) {s["url"]}')
    print("\nPublic government data, not bid or legal advice. Confirm details on sam.gov.")

if __name__ == "__main__":
    main()
