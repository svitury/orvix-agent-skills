#!/usr/bin/env python3
"""Estimate Etsy fees and profit for one order, line by line, with the Etsy Help page for each fee.

Standard library only. Fee rates were checked on Etsy Help on 2026-11-03 (see FEES_VERIFIED_ON).
Etsy can change fees at any time: open the source links before relying on a number.
This is an estimate. Your Etsy payment account statement shows what Etsy actually charged.
"""
import argparse, json

FEES_VERIFIED_ON = "2026-11-03"
SRC = {
    "fees": "https://help.etsy.com/hc/en-us/articles/115014483627",
    "processing": "https://help.etsy.com/hc/en-us/articles/115015628847",
    "listing": "https://help.etsy.com/hc/en-us/articles/115014483627",
    "offsite": "https://help.etsy.com/hc/en-us/articles/360000338367",
    "regulatory": "https://help.etsy.com/hc/en-us/articles/1500011073202",
}
# Etsy Payments processing: percent of total sale price (item + shipping + sales tax) + flat fee per order.
# Only rows we read on the Etsy page are included. Other countries: pass --processing-pct and --processing-flat.
PROCESSING = {"US": (3.0, 0.25, "USD"), "CA": (3.0, 0.25, "CAD"), "CA-INTL": (4.0, 0.25, "CAD"),
              "UK": (4.0, 0.20, "GBP"), "AU": (3.0, 0.25, "AUD"), "AU-INTL": (4.0, 0.25, "AUD")}
# Regulatory operating fee (% of item price + shipping + gift wrap), by seller location.
REGULATORY = {"CA": 0.50, "FR": 1.14, "HU": 1.97, "IT": 0.80, "IN": 0.05, "ES": 0.88, "TR": 1.67, "UK": 0.48, "VN": 1.24}

def r2(x):
    return round(x + 1e-9, 2)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--price", type=float, required=True, help="item price per unit, before tax")
    ap.add_argument("--qty", type=int, default=1)
    ap.add_argument("--shipping", type=float, default=0.0, help="shipping you charged the buyer")
    ap.add_argument("--gift-wrap", type=float, default=0.0)
    ap.add_argument("--sales-tax", type=float, default=0.0, help="sales tax the buyer paid (affects processing fee only)")
    ap.add_argument("--country", default="US", help="seller bank country for processing: " + ", ".join(PROCESSING))
    ap.add_argument("--processing-pct", type=float); ap.add_argument("--processing-flat", type=float)
    ap.add_argument("--regulatory", default="", help="seller location code if a regulatory operating fee applies: " + ", ".join(REGULATORY))
    ap.add_argument("--offsite-ads", choices=["none", "15", "12"], default="none", help="order came from an Offsite Ad: 15 (<$10k sales in 365 days) or 12")
    ap.add_argument("--currency-conversion", action="store_true", help="listing currency differs from payment account currency (2.5%%)")
    ap.add_argument("--item-cost", type=float, default=0.0, help="your cost per unit (materials, COGS)")
    ap.add_argument("--label", type=float, default=0.0, help="shipping label cost")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    items = a.price * a.qty
    order_total = items + a.shipping + a.gift_wrap          # transaction, regulatory and Offsite Ads base
    sale_total = order_total + a.sales_tax                   # processing base (includes sales tax)
    pct, flat, cur = PROCESSING.get(a.country.upper(), (None, None, None))
    if a.processing_pct is not None: pct = a.processing_pct
    if a.processing_flat is not None: flat = a.processing_flat
    if pct is None or flat is None:
        raise SystemExit(f"No verified processing rate for {a.country}. Look it up at {SRC['processing']} and pass --processing-pct/--processing-flat.")
    lines = [
        ("Transaction fee 6.5% of item + shipping + gift wrap", r2(order_total * 0.065), SRC["fees"]),
        (f"Payment processing {pct}% of item + shipping + sales tax + {flat} flat", r2(sale_total * pct / 100 + flat), SRC["processing"]),
        (f"Listing fee $0.20 x {a.qty} sold (first sale uses the listing fee; each extra quantity sold renews at $0.20)", r2(0.20 * a.qty), SRC["listing"]),
    ]
    if a.regulatory:
        rp = REGULATORY.get(a.regulatory.upper())
        if rp is None:
            raise SystemExit(f"Unknown regulatory code {a.regulatory}. See {SRC['regulatory']}")
        lines.append((f"Regulatory operating fee {rp}% ({a.regulatory.upper()})", r2(order_total * rp / 100), SRC["regulatory"]))
    if a.offsite_ads != "none":
        rate = int(a.offsite_ads)
        lines.append((f"Offsite Ads {rate}% of order total, capped at $100 (USD per Etsy)", r2(min(order_total * rate / 100, 100.0)), SRC["offsite"]))
    if a.currency_conversion:
        lines.append(("Currency conversion 2.5%", r2(sale_total * 0.025), SRC["fees"]))
    fees = r2(sum(x[1] for x in lines))
    cogs = r2(a.item_cost * a.qty)
    profit = r2(order_total - fees - cogs - a.label)
    out = {"fees_verified_on": FEES_VERIFIED_ON, "currency_note": f"processing flat fee is in {cur or 'your currency'}; other amounts in your listing currency",
           "revenue_excl_tax": r2(order_total), "fee_lines": [{"fee": n, "amount": v, "source": s} for n, v, s in lines],
           "total_fees": fees, "fees_pct_of_revenue": r2(fees / order_total * 100) if order_total else None,
           "item_cost_total": cogs, "shipping_label": r2(a.label), "estimated_profit": profit,
           "margin_pct": r2(profit / order_total * 100) if order_total else None,
           "caveat": "Estimate from published rates. Taxes on fees (VAT/GST), shipping-label adjustments, refunds and Etsy Ads are not included. Your Etsy statement is the source of truth."}
    if a.json:
        print(json.dumps(out, indent=1)); return
    print(f"Revenue (excl. sales tax): {out['revenue_excl_tax']:.2f}   [fee rates checked on Etsy Help {FEES_VERIFIED_ON}]")
    for l in out["fee_lines"]:
        print(f"  - {l['fee']}: {l['amount']:.2f}\n    {l['source']}")
    print(f"Total Etsy fees: {fees:.2f} ({out['fees_pct_of_revenue']}% of revenue)")
    print(f"Item cost: {cogs:.2f}   Shipping label: {a.label:.2f}")
    print(f"Estimated profit: {profit:.2f} ({out['margin_pct']}% margin)")
    print(out["caveat"])

if __name__ == "__main__":
    main()
