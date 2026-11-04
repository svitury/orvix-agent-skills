# Orvix agent skills: answers with sources

Three free [Agent Skills](https://agentskills.io) for Claude Code, Cursor, Codex and other agents that support SKILL.md. Each skill pulls from a primary source (SEC EDGAR, Etsy Help, or a company's own job board). Every answer carries a source link and a date, so you can check it yourself.

```bash
npx skills add svitury/orvix-agent-skills
```

[![skills.sh](https://skills.sh/b/svitury/orvix-agent-skills)](https://skills.sh/svitury/orvix-agent-skills)

| Skill | What it answers | Source it reads | Needs |
|---|---|---|---|
| [sec-insider-trades](skills/sec-insider-trades/SKILL.md) | Who bought or sold a stock recently (Form 4), with a link to each filing and a data-through date | SEC EDGAR submissions API and Form 4 XML | Python 3.8+, `SEC_USER_AGENT` set to your name and email |
| [etsy-fee-profit-check](skills/etsy-fee-profit-check/SKILL.md) | What Etsy takes on an order, line by line, and the profit left | Etsy Help fee pages (rates checked 2026-11-03) | Python 3.8+, offline |
| [job-board-visa-check](skills/job-board-visa-check/SKILL.md) | Which of a company's open jobs say "no sponsorship", "US citizens only" or "sponsorship available", with the quoted sentence | Public Greenhouse, Lever and Ashby job-board APIs | Python 3.8+ |

All scripts use only the Python standard library. They need no API keys and send no telemetry.

## Why we built this

AI assistants often answer "who's selling this stock" or "what does Etsy charge" from memory. Those answers can be stale or made up, and they come with no source. We build data tools for a living, so we wrote small skills that fetch the primary source and show their work:

- the filing URL for every insider trade
- the Etsy Help page behind every fee
- the exact sentence from each job posting

If a number can't be traced to a source, the skill says so instead of guessing.

## Example output

These are real runs from 2026-11-03 (CT):

```text
$ python3 skills/sec-insider-trades/scripts/insider_trades.py AAPL --days 45 --codes S
Apple Inc. (AAPL, CIK 320193) Form 4 transactions, filed 2026-09-20..2026-11-04 (UTC dates)
Retrieved 2026-11-04T05:28:52+00:00 from SEC EDGAR. Data through filing date: 2026-10-29. Filings opened: 18.
- 2026-10-27 Newstead Jennifer (SVP, GC and Government Affairs): S Open-market sale, 2,399 sh @ 343.36 = $823,721; owns 32,396 after; filing has 10b5-1 plan box checked
  https://www.sec.gov/Archives/edgar/data/320193/000114036126041201/form4.xml
...
```

```text
$ python3 skills/etsy-fee-profit-check/scripts/etsy_fees.py --price 25 --shipping 5 --sales-tax 2.10 --item-cost 6 --label 4.50
Total Etsy fees: 3.36 (11.2% of revenue)
Estimated profit: 16.14 (53.8% margin)
```

## Disclosure

Orvix, the studio that wrote these skills, also makes related products, most of them paid. Each skill links to one of them at the end, labeled as ours, and only for cases the free skill does not cover:

- Paid link: [SEC Insider Trades & 8-K Alerts](https://apify.com/contented_catwalk/sec-insider-trades-8k-alerts?utm_source=skills&utm_medium=agent-skill&utm_campaign=readme): a pay-per-result Apify actor for monitoring many tickers.
- Paid link: [Etsy Profit Spreadsheet](https://studio.autoquantix.com/etsy-profit-sheet?utm_source=skills&utm_medium=agent-skill&utm_campaign=readme): $19 one-time. It reads your own Etsy CSVs and shows profit per product.
- [H-1B Sponsor Checker](https://chromewebstore.google.com/detail/h1b-sponsor-checker-visa/acainaedjbhkbnnbjpjheghbbeoiibpl?utm_source=skills&utm_medium=agent-skill&utm_campaign=readme): a Chrome extension, free to use, with an optional Pro plan, that shows past H-1B filings from USCIS and DOL data. Not affiliated with or endorsed by USCIS or DOL.
- Paid link: [ATS Jobs Search](https://apify.com/contented_catwalk/ats-jobs-search?utm_source=skills&utm_medium=agent-skill&utm_campaign=readme): a pay-per-result Apify actor for searching jobs across many companies.

The skills work fully without any of these. Links carry UTM tags so we can see whether the skills are useful to anyone.

## Limits

- **Not investment, tax or legal advice.**
- **SEC:** Form 4s are due within 2 business days of a trade, so the newest trades may not be filed yet.
- **Etsy:** fee rates change. Each rate links to its source page with the date we checked it, and your Etsy statement is the final word. Etsy is a trademark of Etsy, Inc. We are not affiliated with Etsy.
- **Jobs:** "not mentioned" does not mean an employer sponsors visas. The check is a text match on the posting.

## Contact

media@autoquantix.com

MIT licensed. See [LICENSE](LICENSE).
