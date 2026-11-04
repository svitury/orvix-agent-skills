#!/usr/bin/env python3
"""List open jobs from a company's public Greenhouse, Lever or Ashby board and flag visa-sponsorship language.

Standard library only. Reads the public job-board APIs the ATS vendors publish for this purpose:
  Greenhouse  https://developers.greenhouse.io/job-board.html
  Lever       https://github.com/lever/postings-api
  Ashby       https://developers.ashbyhq.com/docs/public-job-posting-api
Each row has the posting URL and the posting's own updated/published date when the board gives one.

The sponsorship flag is a text match on the posting. It is not legal advice, and a posting that says
nothing about sponsorship does not mean the employer will sponsor.
"""
import argparse, datetime as dt, html, json, re, sys, urllib.request

DATE_KIND = {"greenhouse": "updated", "lever": "created", "ashby": "published"}
NO_SPON = [  # same patterns the Orvix H-1B Sponsor Checker extension uses
    r"\b(?:unable|not able|cannot|can ?not|will not|won'?t|do not|does not|don'?t|doesn'?t|are not able|is not able)\s+(?:to\s+)?sponsor\b",
    r"\b(?:unable|not able|cannot|can ?not|will not|won'?t|do not|does not|don'?t|doesn'?t)\s+(?:to\s+)?(?:offer|provide|support)\s+(?:(?:any|visa|immigration|employment|work|h-?1b|authorization|or)\s+){0,4}sponsorship\b",
    r"\bno\s+(?:(?:visa|immigration|employment|h-?1b)\s+){0,2}sponsorship\b",
    r"\bsponsorship\s+(?:is\s+|will\s+)?(?:not\s+(?:be\s+)?(?:available|offered|provided)|unavailable)\b",
    r"\bnot\s+(?:be\s+)?eligible\s+for\s+(?:(?:visa|immigration|employment|h-?1b)\s+){0,2}sponsorship\b",
    r"\bwithout\s+(?:the\s+)?(?:need\s+for\s+)?(?:(?:current|or|future|now|in|the|visa|employer|employment|immigration|h-?1b)\s+){0,6}sponsorship\b",
]
YES_SPON = [
    r"\b(?:visa|h-?1b|immigration)\s+sponsorship\s+(?:is\s+)?(?:available|offered|provided)\b",
    r"\b(?:we|company|employer)\s+(?:will|can|may|does|do)\s+sponsor\b",
    r"\bsponsorship\s+(?:is\s+)?available\b",
]
CITIZEN = [r"\bu\.?s\.?\s+citizen(?:ship)?\s+(?:is\s+)?required\b", r"\bmust\s+be\s+a\s+u\.?s\.?\s+citizen\b",
           r"\b(?:active|current)\s+(?:secret|top secret|ts/sci|security)\s+clearance\b"]
NO_RE, YES_RE, CIT_RE = ([re.compile(p, re.I) for p in g] for g in (NO_SPON, YES_SPON, CITIZEN))

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "orvix-agent-skills/1.0 (job-board-visa-check)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def text(s):
    s = html.unescape(s or "")
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\s+", " ", s).strip()

def ms(ts):
    try:
        return dt.datetime.fromtimestamp(int(ts) / 1000, dt.timezone.utc).date().isoformat()
    except Exception:
        return None

def board(kind, slug):
    if kind == "greenhouse":
        d = fetch(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
        for j in d.get("jobs", []):
            yield {"title": j.get("title"), "location": (j.get("location") or {}).get("name"), "url": j.get("absolute_url"),
                   "date": (j.get("updated_at") or "")[:10] or None, "body": text(j.get("content"))}
    elif kind == "lever":
        for j in fetch(f"https://api.lever.co/v0/postings/{slug}?mode=json"):
            body = " ".join([j.get("descriptionPlain") or ""] + [text(l.get("content")) + " " + (l.get("text") or "") for l in j.get("lists", [])] + [j.get("additionalPlain") or ""])
            yield {"title": j.get("text"), "location": (j.get("categories") or {}).get("location"), "url": j.get("hostedUrl"),
                   "date": ms(j.get("createdAt")), "body": text(body)}
    elif kind == "ashby":
        d = fetch(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
        for j in d.get("jobs", []):
            yield {"title": j.get("title"), "location": j.get("location"), "url": j.get("jobUrl"),
                   "date": (j.get("publishedAt") or "")[:10] or None, "body": text(j.get("descriptionPlain") or j.get("descriptionHtml"))}

def snippet(body, m):
    return "..." + body[max(0, m.start() - 80): m.end() + 60] + "..."

def classify(body):
    for name, regs in (("no_sponsorship", NO_RE), ("citizenship_or_clearance", CIT_RE), ("sponsorship_mentioned_available", YES_RE)):
        for r in regs:
            m = r.search(body)
            if m:
                return name, snippet(body, m)
    return "not_mentioned", None

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--greenhouse"); g.add_argument("--lever"); g.add_argument("--ashby")
    ap.add_argument("--query", default="", help="keep jobs whose title contains this text (case-insensitive)")
    ap.add_argument("--location", default="", help="keep jobs whose location contains this text")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    kind = "greenhouse" if a.greenhouse else "lever" if a.lever else "ashby"
    slug = a.greenhouse or a.lever or a.ashby
    fetched = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    try:
        jobs = list(board(kind, slug))
    except Exception as e:
        sys.exit(f"Could not read the {kind} board '{slug}': {e}. Check the slug in the company's careers URL.")
    total = len(jobs)
    jobs = [j for j in jobs if a.query.lower() in (j["title"] or "").lower() and a.location.lower() in (j["location"] or "").lower()]
    rows = []
    for j in jobs[: a.limit]:
        flag, ev = classify(j.pop("body"))
        rows.append({**j, "sponsorship_flag": flag, "evidence": ev})
    counts = {}
    for r in rows:
        counts[r["sponsorship_flag"]] = counts.get(r["sponsorship_flag"], 0) + 1
    out = {"ats": kind, "board": slug, "date_field": DATE_KIND[kind], "fetched_at_utc": fetched, "jobs_on_board": total, "jobs_matching": len(jobs),
           "shown": len(rows), "flag_counts": counts, "jobs": rows,
           "note": "Text match on the posting only. Not legal advice. 'not_mentioned' does not mean the employer sponsors."}
    if a.json:
        print(json.dumps(out, indent=1)); return
    print(f"{kind}:{slug} fetched {fetched}: {total} jobs on board, {len(jobs)} match, showing {len(rows)}. Flags: {counts}")
    for r in rows:
        print(f"- {r['title']} | {r['location']} | {DATE_KIND[kind]} {r['date']} | {r['sponsorship_flag']}\n  {r['url']}")
        if r["evidence"]:
            print(f"  evidence: {r['evidence']}")
    print(out["note"])

if __name__ == "__main__":
    main()
