"""Writes the eight hand-designed ledgers of the independent test set.

This file is the test set's own source, written for this purpose and independent of
`proven/synth.py` (it imports nothing from `proven`). Each company is described by hand:
its chart of accounts with the aliases its finance team uses, its recurring costs (rent,
payroll runs on the real calendar, subscriptions, usage bills), card and supplier noise
drawn from a fixed seed, and the month's events typed in one by one (accruals and their
reversals, credit memos, reclasses, prepaid amortisation, late invoices, FX conversions).

The commentary and the answer key were written afterwards, by reading the balances this
script produces, the way a controller reads a trial balance.

    python benchmarks/independent/build_ledgers.py      # rewrites proven/examples/independent/*/
"""
from __future__ import annotations

import calendar
import csv
import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "proven" / "examples" / "independent"
MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH = ["", "January", "February", "March", "April", "May", "June", "July", "August",
         "September", "October", "November", "December"]


class Co:
    def __init__(self, slug: str, entity: str, industry: str, months: list[str], seed: int,
                 id_fn) -> None:
        self.slug, self.entity, self.industry, self.months = slug, entity, industry, months
        self.rng = random.Random(seed)
        self.id_fn = id_fn
        self.accounts: list[dict] = []
        self.rows: list[dict] = []

    # chart
    def acct(self, name: str, *aliases: str) -> None:
        self.accounts.append({"name": name, "aliases": list(aliases)})

    # one transaction; memo placeholders: {Mon} {MON} {Month} {mm} {yy} {m/yy}
    def add(self, month: str, day: int, account: str, vendor: str, memo: str, amount: float) -> None:
        y, m = int(month[:4]), int(month[5:7])
        day = min(day, calendar.monthrange(y, m)[1])
        memo = (memo.replace("{Mon}", MON[m]).replace("{MON}", MON[m].upper())
                .replace("{Month}", MONTH[m]).replace("{mm}", f"{m:02d}")
                .replace("{yy}", str(y)[2:]).replace("{m/yy}", f"{m}/{str(y)[2:]}"))
        self.rows.append({"date": f"{y}-{m:02d}-{day:02d}", "account": account, "vendor": vendor,
                          "memo": memo, "amount": round(amount, 2), "n": len(self.rows)})

    def jit(self, base: float, pct: float) -> float:
        return round(base * (1 + self.rng.uniform(-pct, pct)), 2)

    def every(self, account: str, vendor: str, memo: str, amount, day: int, jitter: float = 0.0,
              months: list[str] | None = None) -> None:
        """A recurring line every month (amount may be a dict month -> amount)."""
        for month in months or self.months:
            base = amount[month] if isinstance(amount, dict) else amount
            if base is None:
                continue
            self.add(month, day, account, vendor, memo, self.jit(base, jitter) if jitter else base)

    def noise(self, account: str, choices: list[tuple[str, list[str]]], count: tuple[int, int],
              low: float, high: float, months: list[str] | None = None) -> None:
        """Card or supplier purchases of varying size: count per month, uniform amount."""
        for month in months or self.months:
            for _ in range(self.rng.randint(*count)):
                vendor, memos = self.rng.choice(choices)
                self.add(month, self.rng.randint(1, 28), account, vendor, self.rng.choice(memos),
                         round(self.rng.uniform(low, high), 2))

    def fridays(self, month: str) -> list[int]:
        y, m = int(month[:4]), int(month[5:7])
        return [d for d in range(1, calendar.monthrange(y, m)[1] + 1) if calendar.weekday(y, m, d) == 4]

    def last(self, month: str) -> int:
        return calendar.monthrange(int(month[:4]), int(month[5:7]))[1]

    def write(self) -> None:
        rows = sorted(self.rows, key=lambda r: (r["date"], r["n"]))
        folder = OUT / self.slug
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / "ledger.csv", "w", encoding="utf-8", newline="") as handle:
            out = csv.writer(handle, lineterminator="\n")
            out.writerow(["id", "date", "account", "vendor", "memo", "amount"])
            for i, r in enumerate(rows, start=1):
                out.writerow([self.id_fn(i, r), r["date"], r["account"], r["vendor"], r["memo"],
                              f"{r['amount']:.2f}"])
        chart = {"entity": self.entity, "industry": self.industry,
                 "history_periods": self.months[:-2], "prior_period": self.months[-2],
                 "current_period": self.months[-1], "accounts": self.accounts}
        (folder / "chart.json").write_text(json.dumps(chart, indent=2) + "\n", encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
def brightline() -> Co:
    c = Co("brightline", "Brightline Analytics, Inc.", "B2B SaaS (data analytics platform)",
           ["2026-08", "2026-09", "2026-10"], 11, lambda i, r: f"JE-{104500 + i}")
    A, S, O = "2026-08", "2026-09", "2026-10"
    c.acct("Hosting & Infrastructure", "hosting & infrastructure", "hosting and infrastructure",
           "hosting", "infrastructure", "cloud costs")
    c.acct("Software Subscriptions", "software subscriptions", "software", "subscriptions")
    c.acct("Salaries & Wages", "salaries & wages", "salaries and wages", "salaries", "wages", "payroll")
    c.acct("Benefits & Payroll Taxes", "benefits & payroll taxes", "benefits", "payroll taxes")
    c.acct("Contractors", "contractors", "contractor spend", "contract labor")
    c.acct("Sales Commissions", "sales commissions", "commissions")
    c.acct("Marketing Programs", "marketing programs", "marketing", "demand gen")
    c.acct("Travel & Entertainment", "travel & entertainment", "travel and entertainment", "t&e", "travel")
    c.acct("Recruiting", "recruiting")
    c.acct("Legal & Professional", "legal & professional", "legal and professional fees",
           "legal and professional", "professional fees", "legal")
    c.acct("Rent & Facilities", "rent & facilities", "rent and facilities", "rent", "facilities")
    c.acct("Insurance", "insurance")
    c.acct("Merchant & Bank Fees", "merchant & bank fees", "merchant fees", "bank fees")
    c.acct("Office & Supplies", "office & supplies", "office supplies", "office")

    # rent and facilities
    c.every("Rent & Facilities", "Pier 70 Holdings LLC", "Suite 400 rent - {Mon} 2026", 18450.00, 1)
    c.every("Rent & Facilities", "Bayside Facility Services", "Janitorial svc {Mon}", 1240.00, 5)
    c.every("Rent & Facilities", "Bay Area Power & Light", "Electric acct 88-1024 {Mon}",
            {A: 1082.17, S: 1045.90, O: 1698.33}, 12)
    c.every("Rent & Facilities", "Cascade Fiber", "Fiber 1G circuit {Mon}", 389.00, 15)
    c.add(O, 24, "Rent & Facilities", "Bayside Facility Services", "Carpet extraction + window washing (one-time)", 1950.00)
    # hosting
    c.every("Hosting & Infrastructure", "Nimbus Cloud Services", "Compute + storage usage {Mon} - acct 4471-2290",
            {A: 41212.55, S: 42048.10, O: 63880.42}, 3)
    c.every("Hosting & Infrastructure", "Glacier Data Cloud", "Capacity credits - {Mon} (on-demand overage incl.)",
            {A: 9804.00, S: 10152.00, O: 19416.00}, 4)
    c.every("Hosting & Infrastructure", "Watchtower Monitoring", "Infra + APM hosts {Mon}", 6300.00, 6, 0.03)
    c.every("Hosting & Infrastructure", "EdgeShield", "Pro plan + Argo {Mon}", 1250.00, 7)
    c.every("Hosting & Infrastructure", "OnCall Alerts", "Business plan 14 users", 588.00, 9)
    # software
    for vendor, memo, amt, day in [("Chatterbox Workspace", "Business+ 96 seats", 2880.00, 2),
                                   ("Trellis Dev Tools", "Issue tracker + wiki cloud {Mon}", {A: 3150.00, S: 3150.00, O: 3240.00}, 2),
                                   ("CodeHarbor", "Team plan {Mon}", 1470.00, 3),
                                   ("MeetLine Video", "Business 40 licenses", 610.00, 8),
                                   ("Suite Mail & Docs", "Business Std {Mon}", 1836.00, 1),
                                   ("Notebook HQ", "Team plan", 480.00, 10),
                                   ("Funnelwise", "Marketing Hub Pro {Mon}", 3200.00, 11)]:
        c.every("Software Subscriptions", vendor, memo, amt, day)
    c.add(A, 31, "Software Subscriptions", "Pipeline CRM", "Prepaid amort - Pipeline CRM FY26 contract 11/12", 4950.00)
    c.add(S, 30, "Software Subscriptions", "Pipeline CRM", "Prepaid amort - Pipeline CRM FY26 contract 12/12", 4950.00)
    c.add(O, 31, "Software Subscriptions", "Pipeline CRM", "Prepaid amort - Pipeline CRM FY27 contract 1/12", 5395.50)
    c.add(O, 6, "Software Subscriptions", "Voxly Inc", "Voxly annual license 10/26-10/27 (24 seats) - paid on card", 14400.00)
    # payroll: semi-monthly, by department
    base = {"Engineering": 118000.00, "Sales": 46000.00, "Customer Success": 21000.00, "G&A": 27500.00}
    for month in c.months:
        for day in (15, c.last(month)):
            for dept, amt in base.items():
                extra = 0.0
                if month == O and dept == "Engineering":
                    extra = 1315.00 if day == 15 else 7600.00
                gross = c.jit(amt, 0.002) + extra
                c.add(month, day, "Salaries & Wages", "PayBridge Payroll",
                      f"Payroll {int(month[5:]):02d}/{day:02d}/26 - {dept}", gross)
                c.add(month, day, "Benefits & Payroll Taxes", "PayBridge Payroll",
                      f"ER taxes {int(month[5:]):02d}/{day:02d}/26 - {dept}", round(gross * 0.0712, 2))
                c.add(month, day, "Benefits & Payroll Taxes", "Nestegg 401k",
                      f"401k match {int(month[5:]):02d}/{day:02d} - {dept}", round(gross * 0.03, 2))
    c.every("Benefits & Payroll Taxes", "Golden State Health Plan", "Group medical/dental/vision {Mon}", 31200.00, 1)
    # contractors (Kestrel is billed in GBP)
    for month, rate in ((A, 1.2712), (S, 1.3105), (O, 1.2690)):
        c.add(month, 20, "Contractors", "Kestrel Dev Studio Ltd",
              f"GBP 9,500.00 @{rate:.4f} - {MON[int(month[5:])]} sprint retainer", round(9500 * rate, 2))
    c.every("Contractors", "Ana Ribeiro Design", "Product design - {Mon}", 6200.00, 25, months=[A, S])
    c.add(O, 22, "Contractors", "Polaris QA Labs", "Regression test pod - Oct (new SOW)", 3800.00)
    # commissions
    c.every("Sales Commissions", "PayBridge Payroll", "Commissions - {Mon} base plan",
            {A: 17400.00, S: 18000.00, O: 19150.00}, 28)
    c.add(S, 30, "Sales Commissions", "PayBridge Payroll", "Q3 accelerator true-up - AE team", 26400.00)
    # marketing
    c.every("Marketing Programs", "SearchReach Ads", "Search campaigns {Mon}", {A: 8900.00, S: 9150.00, O: 9420.00}, 30)
    c.every("Marketing Programs", "ProNet Ads", "Sponsored content {Mon}", {A: 7500.00, S: 7480.00, O: 7610.00}, 29)
    c.every("Marketing Programs", "PeerGrid", "Profile listing {Mon}", 1650.00, 2)
    c.add(S, 16, "Marketing Programs", "Lumen Webcasts", "Webinar series production - Q3", 3000.00)
    c.add(O, 8, "Marketing Programs", "Summit Collective LLC", "DataOps World 2026 - Gold sponsorship", 24000.00)
    c.add(O, 19, "Marketing Programs", "ExhibitPro", "Booth build, drayage + shipping - DataOps World", 6850.00)
    # T&E: card feed
    te = [("Westwind Airlines", ["SFO-JFK", "SFO-ORD rt", "SFO-SEA", "OAK-BOS"]),
          ("Metro Rideshare", ["Ride", "Ride - airport"]),
          ("Harborview Hotel", ["Lodging 2 nts", "Lodging 3 nts"]),
          ("Juniper Kitchen", ["Customer dinner", "Team lunch"]),
          ("Cityline Taxi", ["Taxi"]),
          ("Bluebird Coffee", ["Coffee w/ prospect"])]
    c.noise("Travel & Entertainment", te, (38, 44), 30, 720)
    c.add(S, 24, "Travel & Entertainment", "Vintners Ridge Resort", "Q4 SKO offsite - lodging + F&B", 21300.00)
    c.add(S, 24, "Travel & Entertainment", "Napa Valley Coach Lines", "Q4 SKO offsite - shuttle", 2400.00)
    # recruiting
    c.every("Recruiting", "Talentloop ATS", "ATS subscription {Mon}", 1150.00, 4)
    c.every("Recruiting", "ProNet Ads", "Recruiter Lite seats (4)", 2400.00, 4)
    c.add(S, 18, "Recruiting", "Talent Bridge Partners", "Placement fee - Enterprise AE (M. Chen)", 24000.00)
    c.add(O, 14, "Recruiting", "Talent Bridge Partners", "Placement fee - Sr Backend Eng (J. Okafor)", 30000.00)
    c.add(O, 21, "Recruiting", "Talent Bridge Partners", "Placement fee - Backend Eng (R. Sato)", 28500.00)
    # legal & professional
    c.every("Legal & Professional", "Larkspur CPAs", "Monthly close + tax provision support", 4500.00, 10)
    c.add(A, 17, "Legal & Professional", "Haldane Pryce LLP", "Inv 22-0817 - commercial contracts", 6200.00)
    c.add(S, 30, "Legal & Professional", "Haldane Pryce LLP", "Accrued legal fees - Sep (est.) MSA negotiations", 15000.00)
    c.add(O, 1, "Legal & Professional", "Haldane Pryce LLP", "Reverse Sep accrual - legal fees", -15000.00)
    c.add(O, 16, "Legal & Professional", "Haldane Pryce LLP", "Inv 22-0931 - Sep svcs: MSA negotiations, DPA review", 16800.00)
    c.add(O, 31, "Legal & Professional", "Haldane Pryce LLP", "Accrued legal fees - Oct (est.)", 9000.00)
    c.add(O, 23, "Legal & Professional", "Ardent Assurance LLC", "SOC 2 Type II - progress bill 1 of 2", 12500.00)
    # insurance (prepaid)
    c.add(A, 31, "Insurance", "Halyard Insurance Brokers", "Prepaid amort - D&O / cyber", 3950.00)
    c.add(S, 30, "Insurance", "Halyard Insurance Brokers", "Prepaid amort - D&O / cyber", 3950.00)
    c.add(O, 31, "Insurance", "Halyard Insurance Brokers", "Prepaid amort - D&O / cyber (renewed 10/1)", 4610.00)
    # fees and office
    c.every("Merchant & Bank Fees", "Payflow Processing", "Card processing fees {Mon}", 2900.00, 2, 0.06)
    c.every("Merchant & Bank Fees", "Harbor Commerce Bank", "Analysis fees", 85.00, 3)
    c.noise("Office & Supplies", [("Supplyhub", ["Office supplies", "Snacks", "Printer toner"]),
                                  ("Desk & Dock", ["Monitor", "Dock", "Keyboard"])], (6, 9), 40, 420)
    return c


# ─────────────────────────────────────────────────────────────────────────────
def ember() -> Co:
    c = Co("ember_rye", "Ember & Rye Hospitality Group", "Restaurant group (3 locations)",
           ["2026-05", "2026-06", "2026-07"], 23, lambda i, r: f"ER26-{i:05d}")
    M, J, L = "2026-05", "2026-06", "2026-07"
    locs = ["Fremont", "Ballard", "Capitol Hill"]
    c.acct("Food Cost", "food cost", "food", "food purchases")
    c.acct("Beverage Cost", "beverage cost", "beverage", "bev cost")
    c.acct("Hourly Labor", "hourly labor", "hourly wages", "labor")
    c.acct("Management Salaries", "management salaries", "management")
    c.acct("Payroll Taxes & Benefits", "payroll taxes & benefits", "payroll taxes", "benefits")
    c.acct("Repairs & Maintenance", "repairs & maintenance", "repairs and maintenance", "r&m", "repairs")
    c.acct("Utilities", "utilities")
    c.acct("Occupancy", "occupancy", "rent")
    c.acct("Smallwares & Supplies", "smallwares & supplies", "smallwares", "supplies")
    c.acct("Linen & Laundry", "linen & laundry", "linen", "laundry")
    c.acct("Card Processing Fees", "card processing fees", "card fees", "processing fees")
    c.acct("Third-Party Delivery", "third-party delivery", "3pd", "delivery commissions")
    c.acct("Marketing", "marketing")
    c.acct("Entertainment & Events", "entertainment & events", "entertainment and events",
           "entertainment", "events")

    # food: broadline twice a week, produce twice a week, seafood weekly, per location
    volume = {M: 1.0, J: 1.03, L: 1.115}
    for month in c.months:
        for loc, size in zip(locs, (1.0, 0.86, 0.78)):
            for day in (2, 5, 9, 12, 16, 19, 23, 26):
                c.add(month, day, "Food Cost", "Evergreen Foodservice", f"Inv - {loc} delivery",
                      c.jit(2100 * size * volume[month], 0.07))
            for day in (3, 7, 10, 14, 17, 21, 24, 28):
                c.add(month, day, "Food Cost", "Puget Produce Co", f"Produce - {loc}",
                      c.jit(640 * size * volume[month], 0.10))
            for day in (4, 11, 18, 25):
                c.add(month, day, "Food Cost", "Salish Sea Seafood", f"Seafood order {loc}",
                      c.jit(980 * size * volume[month], 0.08))
    c.add(L, 14, "Food Cost", "Evergreen Foodservice", "CM 77120 - product loss, walk-in failure 7/09 (Fremont)", -1840.00)
    # beverage
    for month in c.months:
        summer = 1.15 if month == L else 1.0
        for loc, size in zip(locs, (1.0, 0.9, 1.1)):
            for day in (6, 13, 20, 27):
                c.add(month, day, "Beverage Cost", "Cascade Wine & Spirits", f"Wine/spirits - {loc}",
                      c.jit(1400 * size * summer, 0.06))
                c.add(month, day + 1, "Beverage Cost", "Rainier Beverage Distributing", f"Beer - {loc}",
                      c.jit(650 * size * summer, 0.06))
    c.add(J, 3, "Beverage Cost", "Cascade Wine & Spirits", "Rose allocation - 25 cs Cotes de Provence (summer promo)", 4375.00)
    c.add(L, 1, "Beverage Cost", "Rainier Beverage Distributing", "Kegs + CO2 - 7/4 Ballard block party", 3980.00)
    # labor: hourly paid biweekly on Fridays (three pay dates in July), management semi-monthly
    hourly = {"Fremont": 21500.00, "Ballard": 18200.00, "Capitol Hill": 16800.00}
    for month in c.months:
        anchors = {M: [8, 22], J: [5, 19], L: [3, 17, 31]}[month]
        for day in anchors:
            for loc, amt in hourly.items():
                lift = 1.04 if month == L else 1.0
                ot = 650.00 if (month == L and day == 17) else 0.0
                gross = c.jit(amt * lift, 0.01) + ot
                c.add(month, day, "Hourly Labor", "Paystream Payroll", f"Payroll {int(month[5:])}/{day} - {loc} hourly", gross)
                c.add(month, day, "Payroll Taxes & Benefits", "Paystream Payroll",
                      f"ER taxes {int(month[5:])}/{day} - {loc}", round(gross * 0.095, 2))
        for day in (15, c.last(month)):
            for loc in locs:
                c.add(month, day, "Management Salaries", "Paystream Payroll", f"Salaried mgmt {int(month[5:])}/{day} - {loc}", 6250.00)
    c.every("Payroll Taxes & Benefits", "Northgate Health Plan", "Group health - mgmt + FT", 9850.00, 1)
    # R&M
    rm = [("Rapid Kitchen Repair", ["Fryer thermostat", "Dish machine service", "Range igniter", "Ice machine service"]),
          ("Pacific Plumbing & Drain", ["Grease trap pump", "Drain clear - bar sink"]),
          ("Handy Pro Services", ["Patio door hinge", "Booth reupholster"])]
    c.noise("Repairs & Maintenance", rm, (4, 6), 180, 950)
    for loc in locs:
        c.add(J, 9, "Repairs & Maintenance", "Northwest Hood & Duct", f"Quarterly hood cleaning - {loc}", 1350.00)
    c.add(L, 10, "Repairs & Maintenance", "Arctic Air Refrigeration", "Walk-in cooler compressor replacement - Fremont", 7450.00)
    c.add(L, 10, "Repairs & Maintenance", "Arctic Air Refrigeration", "Emergency call-out 7/09 after-hours - Fremont", 685.00)
    # utilities
    elec = {M: 1900.00, J: 2050.00, L: 2800.00}
    gas = {M: 1620.00, J: 1500.00, L: 1190.00}
    for month in c.months:
        for loc, size in zip(locs, (1.0, 0.95, 0.9)):
            c.add(month, 12, "Utilities", "Cascade Public Power", f"Electric - {loc}", c.jit(elec[month] * size, 0.02))
            c.add(month, 14, "Utilities", "Sound Gas & Energy", f"Gas - {loc}", c.jit(gas[month] * size, 0.02))
            c.add(month, 20, "Utilities", "City Water & Sewer", f"Water/sewer - {loc}", c.jit(620 * size, 0.02))
    # occupancy
    for loc, amt in zip(locs, (14500.00, 12800.00, 13950.00)):
        c.every("Occupancy", "Ridgeway Property Mgmt" if loc != "Ballard" else "Ballard Ave Partners LLC",
                f"Rent - {loc}", amt, 1)
    # smallwares
    c.noise("Smallwares & Supplies", [("Restaurant Depot Supply", ["Smallwares", "Deli containers", "Gloves + film"]),
                                      ("ChefLine Supply", ["Hotel pans", "Ramekins", "Knives sharpening"])], (8, 12), 90, 620)
    # linen: one invoice per location per month, Ballard's June invoice posted on 2 July
    for month in c.months:
        for loc, amt in zip(locs, (2140.00, 2060.00, 1930.00)):
            if month == J and loc == "Ballard":
                continue
            c.add(month, 28, "Linen & Laundry", "Unitex Linen Service", f"Inv - {MON[int(month[5:])]} svc - {loc}", amt)
    c.add(L, 2, "Linen & Laundry", "Unitex Linen Service", "Inv 4091223 - Jun svc - Ballard", 2060.00)
    # card fees
    for month, scale in ((M, 1.0), (J, 1.04), (L, 1.12)):
        for loc, base in zip(locs, (5900.00, 5100.00, 4700.00)):
            c.add(month, 3, "Card Processing Fees", "Tillpoint Merchant Services", f"Merchant statement - {loc}", c.jit(base * scale, 0.02))
    # third-party delivery: semi-monthly statements
    dd = {"Fremont": 1150.00, "Ballard": 980.00, "Capitol Hill": 1600.00}
    for month in c.months:
        mm, end = int(month[5:]), c.last(month)
        for loc, amt in dd.items():
            rate = "15%"
            if loc == "Capitol Hill" and month == L:
                amt, rate = 2650.00, "Premier 25%"
            c.add(month, 16, "Third-Party Delivery", "DashCart", f"Commissions {mm}/01-{mm}/15 - {loc} ({rate})", c.jit(amt, 0.03))
            c.add(month, end, "Third-Party Delivery", "DashCart", f"Commissions {mm}/16-{mm}/{end} - {loc} ({rate})", c.jit(amt, 0.03))
        for loc in locs:
            c.add(month, 20, "Third-Party Delivery", "Plated Delivery", f"Marketplace fees - {loc}", c.jit(420.00, 0.05))
    # marketing
    c.every("Marketing", "Lantern Social", "Social retainer - {Mon}", 3000.00, 1)
    c.add(L, 15, "Marketing", "Lantern Social", "Photo shoot - summer menu", 2400.00)
    c.add(L, 6, "Marketing", "Emerald City Restaurant Week", "RW listing - Ballard (Jul 19-Aug 1)", 2750.00)
    c.add(L, 21, "Marketing", "Emerald City Restaurant Week", "Credit - RW listing cancelled (Ballard withdrew)", -2750.00)
    c.every("Marketing", "Hearthside Print", "Menu reprints", {M: 380.00, J: 410.00, L: 395.00}, 18)
    # entertainment
    for month in c.months:
        for day in c.fridays(month):
            c.add(month, day, "Entertainment & Events", "Quartet Collective", "Jazz Friday - Ballard", 450.00)
    c.add(L, 4, "Entertainment & Events", "Soundstage Rentals", "Stage + PA rental 7/4 Ballard", 2350.00)
    c.add(L, 4, "Entertainment & Events", "The Larkin Brothers Band", "Band - Independence Day set 7/4", 2200.00)
    c.add(L, 1, "Entertainment & Events", "City of Seattle - SDOT", "Street use permit SU-26-0718 (7/4 event)", 1050.00)
    return c


# ─────────────────────────────────────────────────────────────────────────────
def keystone() -> Co:
    def kid(i: int, r: dict) -> str:
        if r["vendor"] in ("Keystone Payroll Svc",):
            return f"PR-{30000 + i}"
        if r["vendor"] in ("Reclass JE", "Accrual JE") or r["memo"].lower().startswith(("accrue", "reverse", "prepaid amort", "reclass")):
            return f"GJ-{30000 + i}"
        return f"AP-{30000 + i}"

    c = Co("keystone", "Keystone Mechanical Contractors, LLC", "Construction subcontractor (HVAC/plumbing)",
           ["2026-07", "2026-08", "2026-09"], 37, kid)
    J, A, S = "2026-07", "2026-08", "2026-09"
    c.acct("Job Materials", "job materials", "materials")
    c.acct("Subcontractors", "subcontractors", "subcontract costs", "subcontractor costs", "subs")
    c.acct("Field Labor", "field labor", "field payroll")
    c.acct("Equipment Rental", "equipment rental", "rentals")
    c.acct("Fuel", "fuel")
    c.acct("Vehicle Repairs", "vehicle repairs", "fleet repairs", "truck repairs")
    c.acct("Small Tools & Consumables", "small tools & consumables", "small tools", "consumables")
    c.acct("Permits & Inspections", "permits & inspections", "permits and inspections", "permits")
    c.acct("Insurance", "insurance")
    c.acct("Office Salaries", "office salaries", "office payroll")
    c.acct("Office Rent", "office rent")
    c.acct("Professional Fees", "professional fees")
    c.acct("Safety & Training", "safety & training", "safety and training", "safety", "training")
    c.acct("Waste & Disposal", "waste & disposal", "disposal", "dumpsters")

    # materials
    c.noise("Job Materials", [("Allied Pipe & Supply", ["Ticket - Job 2398 copper/fittings", "Ticket - Job 2405 PVC + hangers",
                                                       "Ticket - Job 2411 valves", "Ticket - shop stock"])], (18, 21), 400, 4200)
    c.noise("Job Materials", [("Mountain States HVAC Supply", ["Job 2405 - flex duct + registers", "Job 2411 - mini-split heads",
                                                              "Job 2398 - line sets", "Job 2422 - furnaces (2)"])], (10, 12), 900, 7000)
    c.noise("Job Materials", [("Front Range Electric Supply", ["Disconnects + whip", "Thermostat wire", "Controls wire"])], (2, 3), 200, 1400)
    c.add(A, 12, "Job Materials", "Allied Pipe & Supply", "Job 2398 Belmar Apts - 4in type L copper + fittings (bulk)", 22000.00)
    c.add(S, 9, "Job Materials", "Mountain States HVAC Supply", "Job 2417 Mercy Ridge - (3) 25-ton RTUs", 86400.00)
    c.add(S, 22, "Job Materials", "Allied Pipe & Supply", "CM - returned 4in type L copper, Job 2398", -6850.00)
    # subcontractors, with month-end accruals for work not yet billed
    c.add(J, 15, "Subcontractors", "Rocky Mountain Insulation", "Inv 5402 - Jun/Jul insulation Belmar", 16000.00)
    c.add(J, 25, "Subcontractors", "Precision Controls Inc", "Controls progress bill - Job 2398", 20000.00)
    c.add(J, 28, "Subcontractors", "Front Range Sheet Metal", "Ductwork progress bill 3 - Belmar", 38500.00)
    c.add(A, 25, "Subcontractors", "Precision Controls Inc", "Controls progress bill - Job 2398/2405", 21000.00)
    c.add(A, 28, "Subcontractors", "Front Range Sheet Metal", "Ductwork progress bill 4 - Belmar", 41000.00)
    c.add(A, 31, "Subcontractors", "Rocky Mountain Insulation", "Accrue Aug insulation - Mercy Ridge (not yet billed)", 18000.00)
    c.add(S, 1, "Subcontractors", "Rocky Mountain Insulation", "Reverse Aug accrual - insulation", -18000.00)
    c.add(S, 14, "Subcontractors", "Rocky Mountain Insulation", "Inv 5521 - Aug insulation Mercy Ridge", 19250.00)
    c.add(S, 25, "Subcontractors", "Precision Controls Inc", "Controls progress bill - Job 2405/2417", 22500.00)
    c.add(S, 28, "Subcontractors", "Front Range Sheet Metal", "Final ductwork bill 5 - Belmar", 9200.00)
    c.add(S, 30, "Subcontractors", "Rocky Mountain Insulation", "Accrue Sep insulation - Mercy Ridge (not yet billed)", 17500.00)
    # field labor: weekly, four crews
    for month in c.months:
        for day in c.fridays(month):
            for crew in "ABCD":
                gross = c.jit(9800.00, 0.012)
                c.add(month, day, "Field Labor", "Keystone Payroll Svc", f"Field payroll WE {int(month[5:]):02d}/{day:02d} - Crew {crew}", gross)
    c.add(S, 11, "Field Labor", "Keystone Payroll Svc", "OT premium WE 09/11 - Mercy Ridge set", 3400.00)
    c.add(S, 18, "Field Labor", "Keystone Payroll Svc", "OT premium WE 09/18 - Mercy Ridge set", 4100.00)
    # equipment rental
    c.every("Equipment Rental", "Peak Equipment Rentals", "Scissor/boom lifts - monthly", {J: 3900.00, A: 4200.00, S: 4620.00}, 30)
    c.add(S, 15, "Equipment Rental", "Summit Crane & Rigging", "Crane pick - RTUs 9/14, Job 2417", 9800.00)
    # fuel: semi-monthly fleet card statements
    c.every("Fuel", "FleetOne Card Services", "Fleet fuel 1st-15th", {J: 4480.00, A: 4550.00, S: 5150.00}, 16)
    c.every("Fuel", "FleetOne Card Services", "Fleet fuel 16th-EOM", {J: 4390.00, A: 4610.00, S: 4610.00}, 28)
    # vehicle repairs; Truck 14's rebuild was keyed to small tools and reclassed
    c.noise("Vehicle Repairs", [("Mile High Fleet Service", ["Oil change + PM", "Brake pads", "Tires rotate/balance", "Wiper/lamp", "Battery"])], (4, 6), 90, 450)
    c.add(S, 8, "Small Tools & Consumables", "Mile High Fleet Service", "Inv 30981 - Truck 14 trans rebuild", 6850.00)
    c.add(S, 30, "Small Tools & Consumables", "Reclass JE", "Reclass Truck 14 trans rebuild to vehicle repairs", -6850.00)
    c.add(S, 30, "Vehicle Repairs", "Reclass JE", "Reclass Truck 14 trans rebuild from small tools", 6850.00)
    c.noise("Small Tools & Consumables", [("Toolcrib Direct", ["Drill bits", "Press tool jaws", "Sawzall blades", "Hand tools"]),
                                          ("Allied Pipe & Supply", ["Solder/flux", "Thread sealant"])], (8, 10), 40, 520)
    # permits
    c.add(J, 9, "Permits & Inspections", "City of Denver - CPD", "Mechanical permit - Job 2411", 1250.00)
    c.add(A, 6, "Permits & Inspections", "City of Denver - CPD", "Mechanical permit - Mercy Ridge, Job 2417", 1900.00)
    c.add(S, 10, "Permits & Inspections", "City of Aurora - Building Div", "Plumbing permits (12 units) - Cherry Creek Lofts, Job 2422", 2350.00)
    c.add(S, 19, "Permits & Inspections", "City of Denver - CPD", "Re-inspection fee - Belmar", 150.00)
    c.add(S, 24, "Permits & Inspections", "Backflow Testers of Colorado", "Backflow test certs - Belmar (24)", 1600.00)
    c.every("Permits & Inspections", "Colorado State Electrical Board", "Contractor license renewals", 300.00, 3)
    # insurance
    c.every("Insurance", "Accrual JE", "Prepaid amort - GL/auto/umbrella policy 26-27", 7800.00, 31)
    c.every("Insurance", "Front Range Mutual", "WC installment", 5400.00, 5)
    c.add(S, 17, "Insurance", "Front Range Mutual", "WC final audit 25-26 - additional premium", 11300.00)
    # overhead
    for month in c.months:
        for day in (15, c.last(month)):
            c.add(month, day, "Office Salaries", "Keystone Payroll Svc", f"Office payroll {int(month[5:]):02d}/{day:02d}", 14200.00)
    c.every("Office Rent", "Arapahoe Flex Space LLC", "Office/shop rent", 8900.00, 1)
    c.every("Professional Fees", "Brenner & Lowe CPAs", "Monthly accounting + WIP schedule", 2800.00, 12)
    c.every("Safety & Training", "SafetyFirst Consulting", "Monthly safety program", 650.00, 3)
    c.add(S, 21, "Safety & Training", "Rocky Mountain Safety Council", "OSHA 30 Construction - 6 foremen", 2100.00)
    c.add(S, 23, "Safety & Training", "Industrial Safety Supply", "Fall protection kits (harness + SRL) x8", 3200.00)
    c.noise("Waste & Disposal", [("Alpine Waste & Recycling", ["Roll-off 20yd swap", "Roll-off 30yd haul"])], (3, 4), 380, 640)
    return c


# ─────────────────────────────────────────────────────────────────────────────
def cedar() -> Co:
    c = Co("cedar_valley", "Cedar Valley Family Medicine, PC", "Medical practice (6-provider family medicine)",
           ["2026-08", "2026-09", "2026-10"], 41, lambda i, r: f"CV{10000 + i}")
    A, S, O = "2026-08", "2026-09", "2026-10"
    c.acct("Medical Supplies", "medical supplies", "clinical supplies", "supplies")
    c.acct("Vaccines", "vaccines", "vaccine purchases", "immunizations")
    c.acct("Reference Lab Fees", "reference lab fees", "lab fees", "reference lab")
    c.acct("Clinical Wages", "clinical wages", "clinical staff wages", "clinical staff")
    c.acct("Front Office Wages", "front office wages", "front office")
    c.acct("Provider Compensation", "provider compensation", "provider comp", "physician compensation")
    c.acct("Locum Tenens", "locum tenens", "locum costs", "locums", "locum coverage")
    c.acct("Payroll Taxes & Benefits", "payroll taxes & benefits", "payroll taxes", "benefits")
    c.acct("Billing Service", "billing service fees", "billing service", "billing fees", "rcm fees")
    c.acct("EHR & IT", "ehr & it", "ehr and it", "ehr", "it")
    c.acct("Malpractice Insurance", "malpractice insurance", "malpractice", "med mal")
    c.acct("Rent & CAM", "rent & cam", "rent", "occupancy")
    c.acct("Medical Waste & Janitorial", "medical waste & janitorial", "medical waste", "janitorial")
    c.acct("Continuing Education", "continuing education", "cme")
    c.acct("Office & Admin", "office & admin", "office expense", "admin")

    # supplies weekly
    for month in c.months:
        for day in (3, 10, 17, 24):
            c.add(month, day, "Medical Supplies", "Bridgewell Medical Supply", "Weekly supply order", c.jit(1250.00, 0.12))
        c.add(month, 15, "Medical Supplies", "Bridgewell Medical Supply", "Exam table paper + gowns (case)", c.jit(420.00, 0.05))
        for day in (6, 13, 20, 27):
            c.add(month, day, "Medical Supplies", "Clinica Direct", "Point-of-care test kits + specimen cups", c.jit(310.00, 0.10))
    c.noise("Office & Admin", [("Officemart", ["Toner", "Paper + folders", "Label printer rolls"]),
                               ("Postal Annex", ["Postage - statements", "Certified mail"]),
                               ("Breakroom Co", ["Coffee + water service"])], (19, 23), 20, 200)
    # vaccines
    c.every("Vaccines", "Pinnacle Vaccine Distributors", "VFC-ineligible pediatric restock", 6000.00, 8, 0.04)
    c.add(S, 14, "Vaccines", "Pinnacle Vaccine Distributors", "Flu pre-book shipment 1 of 2 (HD + QIV)", 21600.00)
    c.add(O, 6, "Vaccines", "Pinnacle Vaccine Distributors", "Flu pre-book shipment 2 of 2 (HD + QIV)", 34800.00)
    # labs: September's invoice was posted twice and credited in October
    c.add(A, 12, "Reference Lab Fees", "Valley Reference Laboratories", "Inv 87990 - Jul client bill", 6150.00)
    c.add(S, 11, "Reference Lab Fees", "Valley Reference Laboratories", "Inv 88213 - Aug client bill", 6400.00)
    c.add(S, 18, "Reference Lab Fees", "Valley Reference Laboratories", "Inv 88213 - Aug client bill", 6400.00)
    c.add(O, 12, "Reference Lab Fees", "Valley Reference Laboratories", "Inv 88541 - Sep client bill", 6700.00)
    c.add(O, 20, "Reference Lab Fees", "Valley Reference Laboratories", "Credit memo - duplicate posting inv 88213", -6400.00)
    # payroll: semi-monthly
    providers = ["Dr. Alvarez", "Dr. Kim", "Dr. Osei", "Dr. Brandt", "J. Moreno PA-C", "L. Huang NP"]
    pay = {"Dr. Alvarez": 11500.00, "Dr. Kim": 11500.00, "Dr. Osei": 11200.00, "Dr. Brandt": 10800.00,
           "J. Moreno PA-C": 6400.00, "L. Huang NP": 6300.00}
    for month in c.months:
        for day in (15, c.last(month)):
            for who in providers:
                amt = pay[who]
                if month == O and who == "Dr. Alvarez":
                    amt = 4200.00 if day == 15 else 0.0
                if amt:
                    c.add(month, day, "Provider Compensation", "Clearwater Payroll", f"Provider pay {int(month[5:])}/{day} - {who}", amt)
                    c.add(month, day, "Payroll Taxes & Benefits", "Clearwater Payroll", f"ER taxes {int(month[5:])}/{day} - {who}", round(amt * 0.062, 2))
            clin = 0.0
            for role, base in (("RN", 17400.00), ("MA", 15800.00), ("lab/x-ray tech", 4800.00)):
                amt = c.jit(base, 0.004)
                clin += amt
                c.add(month, day, "Clinical Wages", "Clearwater Payroll", f"Payroll {int(month[5:])}/{day} - clinical staff ({role})", amt)
            front = 0.0
            for role, base in (("front desk", 9800.00), ("referrals/prior auth", 4300.00), ("practice manager", 3500.00)):
                amt = c.jit(base, 0.004)
                front += amt
                c.add(month, day, "Front Office Wages", "Clearwater Payroll", f"Payroll {int(month[5:])}/{day} - front office ({role})", amt)
            c.add(month, day, "Payroll Taxes & Benefits", "Clearwater Payroll", f"ER taxes {int(month[5:])}/{day} - staff",
                  round((clin + front) * 0.0765, 2))
    c.add(O, 31, "Provider Compensation", "Clearwater Payroll", "Q3 quality incentive - providers", 9600.00)
    c.add(S, 30, "Clinical Wages", "Clearwater Payroll", "OT - Saturday flu clinic 9/26", 900.00)
    c.add(O, 15, "Clinical Wages", "Clearwater Payroll", "OT - Saturday flu clinics 10/03, 10/10", 2300.00)
    c.add(O, 31, "Clinical Wages", "Clearwater Payroll", "OT - Saturday flu clinics 10/17, 10/24", 2450.00)
    c.every("Payroll Taxes & Benefits", "Cascadia Health Plan", "Group health {Mon}", 14300.00, 1)
    # locums
    for day in (9, 16, 23, 30):
        c.add(O, day, "Locum Tenens", "Summit Locums Group", f"Locum coverage wk ending 10/{day:02d} - Dr. R. Ingram (for Dr. Alvarez)", 7200.00)
    # billing service: % of prior month collections
    c.add(A, 10, "Billing Service", "MedBill Partners", "5.5% of Jul collections ($281,400)", 15477.00)
    c.add(S, 10, "Billing Service", "MedBill Partners", "5.5% of Aug collections ($284,900)", 15669.50)
    c.add(O, 10, "Billing Service", "MedBill Partners", "5.5% of Sep collections ($312,600)", 17193.00)
    c.add(O, 22, "Billing Service", "MedBill Partners", "Payer credentialing - 2 new plans", 800.00)
    # EHR & IT
    c.every("EHR & IT", "ChartWell EHR", "EHR subscription - 6 providers", 2700.00, 1)
    c.every("EHR & IT", "Bluestone IT", "Managed IT - {Mon}", 2950.00, 1)
    c.every("EHR & IT", "Faxline Cloud", "eFax + phone tree", 189.00, 5)
    c.add(O, 14, "EHR & IT", "ChartWell EHR", "Patient portal module - implementation (one-time)", 4500.00)
    c.add(O, 20, "EHR & IT", "Bluestone IT", "SLA credit - 9/18 network outage", -900.00)
    # malpractice (prepaid, renewed Oct 1)
    c.add(A, 31, "Malpractice Insurance", "Sentinel Physicians Mutual", "Prepaid amort - med mal policy 25-26", 9350.00)
    c.add(S, 30, "Malpractice Insurance", "Sentinel Physicians Mutual", "Prepaid amort - med mal policy 25-26", 9350.00)
    c.add(O, 31, "Malpractice Insurance", "Sentinel Physicians Mutual", "Prepaid amort - med mal policy 26-27", 10120.00)
    # occupancy, waste, janitorial
    c.every("Rent & CAM", "Cedar Crossing Medical Plaza", "Suite 210 rent + CAM est.", 24800.00, 1)
    c.every("Medical Waste & Janitorial", "SafeCycle Medical Waste", "Regulated waste pickup (2x/mo)", 780.00, 6)
    c.every("Medical Waste & Janitorial", "BrightPath Janitorial", "Nightly cleaning - {Mon}", 2400.00, 2)
    c.add(O, 9, "Medical Waste & Janitorial", "SafeCycle Medical Waste", "Sharps mail-back program - setup + 40 containers", 3100.00)
    # CME
    c.every("Continuing Education", "MedEd Online", "CME subscription", 150.00, 4)
    c.add(O, 2, "Continuing Education", "Family Medicine Assembly", "FMX 2026 registration - Dr. Kim", 1195.00)
    c.add(O, 3, "Continuing Education", "Westwind Airlines", "DEN-ORD rt - Dr. Kim", 640.00)
    c.add(O, 28, "Continuing Education", "Lakeshore Grand Hotel", "Lodging 3 nts - Dr. Kim", 1410.00)
    return c


# ─────────────────────────────────────────────────────────────────────────────
def lumen() -> Co:
    c = Co("lumen_loom", "Lumen & Loom Home Co.", "E-commerce (DTC home textiles)",
           ["2026-08", "2026-09", "2026-10"], 53, lambda i, r: f"LL-{200000 + i}")
    A, S, O = "2026-08", "2026-09", "2026-10"
    c.acct("Paid Social", "paid social", "social ads")
    c.acct("Paid Search", "paid search", "search", "sem")
    c.acct("Affiliates & Influencers", "affiliates & influencers", "affiliate & influencer",
           "affiliates and influencers", "affiliates", "influencers")
    c.acct("3PL Fulfillment", "3pl fulfillment", "3pl", "fulfillment")
    c.acct("Outbound Shipping", "outbound shipping", "shipping", "postage")
    c.acct("Packaging", "packaging")
    c.acct("Payment Processing", "payment processing", "processing fees", "merchant fees")
    c.acct("Returns & Refund Costs", "returns & refund costs", "returns costs", "returns")
    c.acct("Ecommerce Platform & Apps", "ecommerce platform & apps", "platform & apps",
           "platform and apps", "platform", "apps")
    c.acct("Customer Support", "customer support", "cx", "support")
    c.acct("Content & Photography", "content & photography", "content", "photography", "creative")
    c.acct("Salaries", "salaries", "payroll")
    c.acct("Rent", "rent", "office rent")
    c.acct("General & Admin", "general & admin", "g&a")

    # paid social: charged at a $2,500 billing threshold
    for month, n in ((A, 15), (S, 17), (O, 26)):
        days = sorted(c.rng.randint(1, 28) for _ in range(n))
        for day in days:
            c.add(month, day, "Paid Social", "SocialReach Ads", "Ad charges - acct 2231 (threshold)", 2500.00)
    for day in (8, 15, 22, 29):
        c.add(O, day, "Paid Social", "Clipstream Ads", "Campaign HEARTH_FALL26 - prepaid top-up", 2000.00)
    # paid search: weekly
    for month, total in ((A, 18100.00), (S, 18400.00), (O, 14350.00)):
        days = c.last(month)
        for day in range(1, days + 1):
            c.add(month, day, "Paid Search", "SearchReach Ads", "Search + shopping campaigns - daily", round(total / days, 2))
    # affiliates & influencers (creator retainer billed in EUR)
    for month, rate in ((A, 1.0840), (S, 1.0905), (O, 1.1650)):
        c.add(month, 5, "Affiliates & Influencers", "Marta Ferreira Studio",
              f"EUR 6,000.00 @{rate:.4f} - creator retainer {MON[int(month[5:])]}", round(6000 * rate, 2))
    c.every("Affiliates & Influencers", "Affinity Network", "Affiliate commissions - {Mon}", {A: 2950.00, S: 3100.00, O: 7900.00}, 3)
    c.every("Affiliates & Influencers", "Affinity Network", "Network fee", 350.00, 3)
    # 3PL
    for month, pick in ((A, 5300.00), (S, 5400.00), (O, 5800.00)):
        for day in (7, 14, 21, 28):
            c.add(month, day, "3PL Fulfillment", "Ridgeline Fulfillment", "Pick/pack - weekly orders", c.jit(pick, 0.01))
    c.add(A, 31, "3PL Fulfillment", "Ridgeline Fulfillment", "Storage - 270 pallets @ $45", 12150.00)
    c.add(S, 30, "3PL Fulfillment", "Ridgeline Fulfillment", "Storage - 286 pallets @ $45", 12870.00)
    c.add(O, 31, "3PL Fulfillment", "Ridgeline Fulfillment", "Storage - 412 pallets @ $45", 18540.00)
    c.every("3PL Fulfillment", "Ridgeline Fulfillment", "Inbound receiving", {A: 450.00, S: 450.00, O: 650.00}, 20)
    # outbound shipping
    for month, base in ((A, 6900.00), (S, 7000.00), (O, 7300.00)):
        for day in (6, 13, 20, 27):
            c.add(month, day, "Outbound Shipping", "Harbor Parcel", "Weekly parcel invoice - ground", c.jit(base, 0.01))
    for day in (13, 20, 27):
        c.add(O, day, "Outbound Shipping", "Harbor Parcel", "Demand surcharge - residential", 1640.00)
    c.every("Outbound Shipping", "National Post ePostage", "ePostage - lightweight", {A: 1450.00, S: 1480.00, O: 1520.00}, 30)
    # packaging
    c.noise("Packaging", [("Boxwell Packaging", ["Mailers 14x19", "Boxes 18x14x6", "Tissue + stickers"])], (8, 10), 250, 700)
    # payment processing
    c.every("Payment Processing", "CartPay Payments", "Processing fees - {Mon}", {A: 10980.00, S: 11240.00, O: 14330.00}, 2)
    c.every("Payment Processing", "CartPay Payments", "Chargeback fees", {A: 225.00, S: 240.00, O: 255.00}, 2)
    # returns
    for month in c.months:
        for day in (6, 13, 20, 27):
            c.add(month, day, "Returns & Refund Costs", "Harbor Parcel", "Return labels - weekly", c.jit(905.00, 0.03))
    c.add(S, 17, "Returns & Refund Costs", "Liquidity Freight Co", "Freight - returns pallets to liquidator", 2300.00)
    # platform & apps
    c.every("Ecommerce Platform & Apps", "Storefront Plus", "Plus plan - {Mon}", 2300.00, 1)
    c.every("Ecommerce Platform & Apps", "Mailwise", "Email/SMS - 120k profiles", 1800.00, 3)
    c.every("Ecommerce Platform & Apps", "Reviewly", "Reviews app", 499.00, 4)
    c.every("Ecommerce Platform & Apps", "Bundlr", "Bundles app", 149.00, 4)
    c.add(O, 11, "Ecommerce Platform & Apps", "Searchlight Apps", "Searchlight Pro - annual plan renewal", 5988.00)
    # support
    for month, base in ((A, 4800.00), (S, 4850.00), (O, 5100.00)):
        c.add(month, 15, "Customer Support", "Harbor CX", "Agent hours 1st-15th", c.jit(base, 0.02))
        c.add(month, c.last(month), "Customer Support", "Harbor CX", "Agent hours 16th-EOM", c.jit(base, 0.02))
    c.every("Customer Support", "Helpline Desk", "Helpdesk seats (12)", 720.00, 2)
    # content
    c.every("Content & Photography", "Ivy Park Copy", "Freelance copy - {Mon}", 1200.00, 25)
    c.add(A, 19, "Content & Photography", "Studio Nove", "Lifestyle stills - Aug drops", 2900.00)
    c.add(S, 12, "Content & Photography", "Studio Nove", "Hearth campaign shoot - 2 days, stills + video", 14500.00)
    c.add(O, 9, "Content & Photography", "Studio Nove", "Retouching - Hearth selects", 1800.00)
    # people and rent
    for month in c.months:
        for day in (15, c.last(month)):
            c.add(month, day, "Salaries", "Gridline Payroll", f"Payroll {int(month[5:])}/{day}", c.jit(31500.00, 0.003))
    c.every("Rent", "Foundry Row Studios", "Studio/office rent", 6400.00, 1)
    c.noise("General & Admin", [("Officemart", ["Office supplies", "Printer ink"]), ("Metro Rideshare", ["Ride - 3PL visit"]),
                                ("Juniper Kitchen", ["Team lunch"]), ("SignPad", ["E-sign plan"])], (12, 16), 20, 240)
    return c


# ─────────────────────────────────────────────────────────────────────────────
def riverbend() -> Co:
    c = Co("riverbend", "Riverbend Community Food Network", "Non-profit (regional food bank)",
           ["2026-04", "2026-05", "2026-06"], 67, lambda i, r: f"RB-{i:04d}")
    P, M, J = "2026-04", "2026-05", "2026-06"
    c.acct("Food Purchases", "food purchases", "purchased food", "program food")
    c.acct("Program Supplies", "program supplies")
    c.acct("Program Salaries", "program salaries", "program staff")
    c.acct("Admin Salaries", "admin salaries", "administrative salaries")
    c.acct("Benefits & Payroll Taxes", "benefits & payroll taxes", "benefits", "payroll taxes")
    c.acct("Fleet & Fuel", "fleet & fuel", "fleet costs", "fleet", "fuel")
    c.acct("Warehouse Occupancy", "warehouse occupancy", "warehouse rent", "warehouse")
    c.acct("Utilities", "utilities")
    c.acct("Special Events", "special events", "events")
    c.acct("Printing & Postage", "printing & postage", "printing and postage", "printing", "postage")
    c.acct("Partner Agency Grants", "partner agency grants", "grants to partner agencies", "partner grants", "agency grants")
    c.acct("Professional Fees", "professional fees")
    c.acct("Technology", "technology", "it")
    c.acct("Volunteer Program", "volunteer program", "volunteer costs")
    c.acct("Office & Admin", "office & admin", "office expense")

    # food: weekly co-op and produce orders on Thursdays
    for month in c.months:
        y, m = int(month[:4]), int(month[5:])
        for day in [d for d in range(1, calendar.monthrange(y, m)[1] + 1) if calendar.weekday(y, m, d) == 3]:
            c.add(month, day, "Food Purchases", "Northwest Grocers Cooperative", "Staples order - Thu", c.jit(3000.00, 0.025))
            c.add(month, day - 3 if day > 3 else day + 1, "Food Purchases", "Northwest Grocers Cooperative", "Staples order - Mon", c.jit(3000.00, 0.025))
            c.add(month, day, "Food Purchases", "Valley Fresh Produce", "Produce - weekly", c.jit(2400.00, 0.03))
    for day in (15, 22, 29):
        c.add(J, day, "Food Purchases", "Sunrise Meal Kits", f"Summer meals kits - wk of 6/{day}", 5800.00)
    c.noise("Program Supplies", [("Shipline West", ["Banana boxes", "Pallet wrap", "Produce bags"]),
                                 ("Packline Supply", ["Tape + labels", "Gloves/hairnets"])], (10, 13), 60, 420)
    # payroll
    for month in c.months:
        for day in (15, c.last(month)):
            prog = c.jit(38800.00, 0.003)
            c.add(month, day, "Program Salaries", "Evergreen Nonprofit Payroll", f"Payroll {m_d(month, day)} - program staff", prog)
            admin = c.jit(14200.00, 0.003)
            c.add(month, day, "Admin Salaries", "Evergreen Nonprofit Payroll", f"Payroll {m_d(month, day)} - admin", admin)
            c.add(month, day, "Benefits & Payroll Taxes", "Evergreen Nonprofit Payroll", f"ER taxes {m_d(month, day)}", round((prog + admin) * 0.0765, 2))
    c.add(J, 30, "Program Salaries", "Evergreen Nonprofit Payroll", "Payroll 6/30 - summer meals seasonal (8)", 9800.00)
    c.add(J, 30, "Benefits & Payroll Taxes", "Evergreen Nonprofit Payroll", "ER taxes 6/30 - seasonal", 749.70)
    c.every("Benefits & Payroll Taxes", "Northwest Nonprofit Health Trust", "Group health", 11200.00, 1)
    # fleet
    for month in c.months:
        for truck in (1, 2, 3, 4):
            c.add(month, 15, "Fleet & Fuel", "Coastline Fleet Card", f"Fuel - Truck {truck}, 1st-15th", c.jit(412.00, 0.03))
            c.add(month, c.last(month), "Fleet & Fuel", "Coastline Fleet Card", f"Fuel - Truck {truck}, 16th-EOM", c.jit(412.00, 0.03))
    c.every("Fleet & Fuel", "Northline Truck Service", "PM service - rotating unit", {P: 420.00, M: 455.00, J: 430.00}, 18)
    c.add(J, 11, "Fleet & Fuel", "Cascade Truck & Reefer", "Reefer unit repair - Truck 3 (compressor)", 5600.00)
    # occupancy and utilities
    c.every("Warehouse Occupancy", "Riverside Industrial Partners", "Warehouse rent - Bldg C", 9600.00, 1)
    c.every("Warehouse Occupancy", "Riverside Industrial Partners", "CAM estimate", 1150.00, 1)
    c.add(J, 18, "Warehouse Occupancy", "Riverside Industrial Partners", "CAM reconciliation 2025 - credit", -2200.00)
    c.every("Utilities", "Clark County PUD", "Electric - warehouse + cold storage", {P: 3820.00, M: 3905.00, J: 4110.00}, 9)
    c.every("Utilities", "Clark County PUD", "Water", {P: 210.00, M: 215.00, J: 240.00}, 9)
    c.every("Utilities", "Waste Connections NW", "Organics + cardboard hauling", 690.00, 20)
    # special events: Harvest Table gala on 16 May, caterer's final bill in June
    c.add(P, 22, "Special Events", "BidHive", "Auction platform - setup", 400.00)
    c.add(M, 2, "Special Events", "Columbia Ballroom at the Hallett", "Harvest Table Gala - venue + rentals", 14000.00)
    c.add(M, 9, "Special Events", "Fireside Catering Co", "Gala catering - deposit (85%)", 12300.00)
    c.add(M, 16, "Special Events", "Brightstage AV", "Gala AV + lighting", 3800.00)
    c.add(M, 20, "Special Events", "BidHive", "Auction platform - event fee", 650.00)
    c.add(J, 4, "Special Events", "Fireside Catering Co", "Final balance - Harvest Table Gala (5/16)", 4200.00)
    # printing & postage
    c.add(P, 14, "Printing & Postage", "Millrace Print & Mail", "Gala save-the-dates - 1,800 pcs", 1400.00)
    c.add(M, 5, "Printing & Postage", "Millrace Print & Mail", "Gala invitations + RSVP cards - 1,800 pcs", 2900.00)
    c.add(M, 6, "Printing & Postage", "Postmaster - Vancouver", "Permit 112 postage - gala invitations", 600.00)
    c.add(J, 10, "Printing & Postage", "Millrace Print & Mail", "Spring appeal mailing - 12,400 pcs (print + mailhouse)", 4700.00)
    c.add(J, 12, "Printing & Postage", "Postmaster - Vancouver", "Nonprofit permit postage - spring appeal", 2000.00)
    # partner agency grants: quarterly
    for i, pantry in enumerate(["Eastside Neighbors Pantry", "Hazel Dell Food Shelf", "St. Brigid Outreach",
                                "Orchards Family Pantry", "Fruit Valley Community Table", "Battle Ground Helping Hands"]):
        c.add(J, 20 + (i % 3), "Partner Agency Grants", pantry, "Grant - Q4 FY26 distribution support", 8000.00)
    # professional fees
    c.every("Professional Fees", "Hollis & Grant CPAs", "Bookkeeping + payroll filings", 2500.00, 8)
    c.add(J, 30, "Professional Fees", "Whitcomb Nonprofit Audit LLP", "Accrue FY26 audit - est. per engagement letter", 18000.00)
    # technology
    c.every("Technology", "TechBridge Managed IT", "Managed IT - {Mon}", 1450.00, 1)
    c.every("Technology", "Officeline 365", "Nonprofit seats (22)", 220.00, 3)
    c.add(J, 3, "Technology", "GiveTrack CRM", "Annual subscription FY27", 4400.00)
    c.add(J, 12, "Technology", "GiveTrack CRM", "Credit - invoice issued in error (nonprofit grant applied)", -4400.00)
    c.add(J, 16, "Technology", "TechBridge Refurb", "Refurb laptops x6 (warehouse + intake)", 4350.00)
    # volunteers
    c.noise("Volunteer Program", [("Bulkmart Business Ctr", ["Volunteer snacks/water"]),
                                  ("Shirt Shack Printing", ["Volunteer t-shirts"]),
                                  ("VolunteerLink", ["Scheduling app"])], (6, 9), 30, 260)
    c.noise("Office & Admin", [("Officemart", ["Office supplies", "Toner"]), ("Postal Annex", ["Postage - donor receipts"]),
                               ("Breakroom Co", ["Coffee service"])], (21, 24), 15, 160)
    return c


def m_d(month: str, day: int) -> str:
    return f"{int(month[5:])}/{day}"


# ─────────────────────────────────────────────────────────────────────────────
def halvorsen() -> Co:
    c = Co("halvorsen", "Halvorsen Precision Components, Inc.", "Manufacturing (CNC machining job shop)",
           ["2026-07", "2026-08", "2026-09"], 79, lambda i, r: f"GL{4000 + i:06d}")
    J, A, S = "2026-07", "2026-08", "2026-09"
    c.acct("Raw Materials", "raw materials", "bar stock")
    c.acct("Direct Labor", "direct labor")
    c.acct("Indirect Labor", "indirect labor")
    c.acct("Tooling & Inserts", "tooling & inserts", "tooling", "cutting tools")
    c.acct("Machine Maintenance", "machine maintenance", "maintenance")
    c.acct("Shop Supplies", "shop supplies")
    c.acct("Plant Utilities", "plant utilities", "utilities")
    c.acct("Freight In", "freight in", "inbound freight")
    c.acct("Freight Out", "freight out", "outbound freight")
    c.acct("Quality & Certification", "quality & certification", "quality costs", "quality", "certification")
    c.acct("Outside Processing", "outside processing")
    c.acct("Equipment Leases", "equipment leases", "leases")
    c.acct("Plant Rent", "plant rent", "rent")
    c.acct("Insurance", "insurance")

    # raw materials
    c.noise("Raw Materials", [("Alcove Metals Service Center", ["PO - 6061-T6 bar", "PO - 7075 plate", "PO - 6061 plate drops"])],
            (13, 13), 3700, 7400)
    c.noise("Raw Materials", [("Keller Specialty Steel", ["PO - 17-4 PH bar", "PO - 304 SS sheet"])], (3, 3), 4000, 9000)
    c.every("Raw Materials", "Alcove Metals Service Center", "Alloy surcharge - {Mon}", {J: 1480.00, A: 1520.00, S: 1560.00}, 30)
    c.add(S, 3, "Raw Materials", "Alcove Metals Service Center", "PO 7790 - 6061-T6 plate 1.5in - Aerovane AV-220 brackets", 18600.00)
    c.add(S, 10, "Raw Materials", "Alcove Metals Service Center", "PO 7801 - 6061-T6 bar 2in - AV-220", 14900.00)
    c.add(S, 21, "Raw Materials", "Alcove Metals Service Center", "PO 7815 - 6061 plate - AV-220 run 2", 11400.00)
    c.add(S, 24, "Raw Materials", "Alcove Metals Service Center", "RMA credit - 6061 bar out of tolerance, PO 7782", -7200.00)
    # labor: weekly payroll, shifts
    for month in c.months:
        for day in c.fridays(month):
            second = {J: 6100.00, A: 6200.00, S: 9900.00}[month]
            c.add(month, day, "Direct Labor", "Northwoods Payroll", f"Payroll WE {int(month[5:]):02d}/{day:02d} - Direct - 1st shift", c.jit(31500.00, 0.006))
            c.add(month, day, "Direct Labor", "Northwoods Payroll", f"Payroll WE {int(month[5:]):02d}/{day:02d} - Direct - 2nd shift", c.jit(second, 0.006))
            c.add(month, day, "Indirect Labor", "Northwoods Payroll", f"Payroll WE {int(month[5:]):02d}/{day:02d} - Indirect (QC, maint, shipping)", c.jit(8700.00, 0.006))
    # tooling
    c.noise("Tooling & Inserts", [("Carbide Edge Tooling", ["Inserts CNMG", "End mills 1/2 4fl", "Drills carbide"]),
                                  ("Ridgeway Cutting Tools", ["Face mill inserts", "Taps + reamers"])], (11, 14), 150, 1200)
    # maintenance
    c.noise("Machine Maintenance", [("Apex Machine Service", ["PM - lathe 2", "Way lube pump", "Chip conveyor repair", "Tool changer adj."])],
            (2, 3), 300, 1400)
    c.add(S, 12, "Machine Maintenance", "Precision Spindle Service", "Spindle rebuild - Mill 3 (VF-4), incl. bearings", 14800.00)
    c.add(S, 19, "Machine Maintenance", "Crestline Industrial Fluids", "Coolant system flush + recharge - all mills", 3900.00)
    # shop supplies
    c.every("Shop Supplies", "Crestline Industrial Fluids", "Coolant concentrate (2 drums)", 1180.00, 5)
    c.noise("Shop Supplies", [("Fastline Industrial", ["Shop rags", "Fasteners", "Deburr tools", "Gloves"]),
                              ("Packline Supply", ["Boxes + foam", "Stretch wrap"])], (9, 10), 50, 330)
    # utilities
    c.every("Plant Utilities", "Northern Power Cooperative", "Energy - acct 55-0912", {J: 14260.00, A: 14420.00, S: 14510.00}, 8)
    c.every("Plant Utilities", "Northern Power Cooperative", "Demand charge - acct 55-0912", 3100.00, 8)
    c.add(S, 15, "Plant Utilities", "Northern Power Cooperative", "Back-bill - meter misread Jun-Aug (acct 55-0912)", 3300.00)
    c.every("Plant Utilities", "Lakeside Gas", "Gas service", {J: 640.00, A: 610.00, S: 650.00}, 14)
    # freight
    c.noise("Freight In", [("Midwest LTL", ["Inbound - bar stock", "Inbound - tooling"])], (8, 9), 200, 650)
    c.add(S, 16, "Freight In", "SkyBridge Expedite", "Air freight - expedite 17-4 SS bar (Keller shipped late)", 6350.00)
    for month, base in ((J, 640.00), (A, 650.00), (S, 845.00)):
        for day in (3, 7, 10, 14, 17, 21, 24, 28):
            c.add(month, day, "Freight Out", "Midwest LTL", "Outbound - customer shipment", c.jit(base, 0.02))
    # quality
    c.every("Quality & Certification", "Metrology Partners", "Gauge calibration - monthly contract", 600.00, 2)
    c.add(S, 9, "Quality & Certification", "Meridian Registrar Services", "AS9100D surveillance audit - 2 days", 5500.00)
    c.add(S, 26, "Quality & Certification", "Metrology Partners", "CMM recalibration + probe replacement", 6100.00)
    # outside processing
    c.every("Outside Processing", "Lakeshore Anodizing", "Anodize lots - {Mon}", {J: 8700.00, A: 9000.00, S: 20400.00}, 27)
    c.every("Outside Processing", "Northline Heat Treat", "Heat treat - 17-4 H1025", 2400.00, 18)
    # fixed
    for unit, amt in (("Mill 1 (VF-2)", 2150.00), ("Mill 3 (VF-4)", 2890.00), ("Lathe 2 (ST-20)", 2420.00)):
        c.every("Equipment Leases", "Ironbridge Equipment Finance", f"Lease pmt - {unit}", amt, 1)
    c.every("Plant Rent", "Lakeview Industrial Park LLC", "Plant rent - 2400 Commerce Dr", 16500.00, 1)
    c.every("Insurance", "Halvorsen Prepaid JE", "Prepaid amort - property/GL/product liability", 4250.00, 30)
    return c


# ─────────────────────────────────────────────────────────────────────────────
def northstar() -> Co:
    c = Co("northstar", "Northstar Freightways, Inc.", "Logistics (regional truckload carrier)",
           ["2026-08", "2026-09", "2026-10"], 97, lambda i, r: f"NSF-{55000 + i}")
    A, S, O = "2026-08", "2026-09", "2026-10"
    c.acct("Fuel", "fuel", "diesel")
    c.acct("Driver Wages", "driver wages", "driver pay")
    c.acct("Purchased Transportation", "purchased transportation", "owner-operator settlements", "brokered freight")
    c.acct("Tolls & Permits", "tolls & permits", "tolls and permits", "tolls", "permits")
    c.acct("Tractor & Trailer Maintenance", "tractor & trailer maintenance", "maintenance", "repairs")
    c.acct("Tires", "tires")
    c.acct("Equipment Leases", "equipment leases", "tractor leases", "leases")
    c.acct("Insurance", "insurance")
    c.acct("Cargo Claims", "cargo claims", "claims")
    c.acct("Dispatch & ELD Software", "dispatch & eld software", "dispatch software", "eld", "software")
    c.acct("Terminal Rent", "terminal rent", "rent")
    c.acct("Driver Recruiting", "driver recruiting", "recruiting")
    c.acct("Compliance & Testing", "compliance & testing", "compliance", "drug testing")
    c.acct("Office Salaries", "office salaries")

    # fuel: daily fleet-card summaries in USD, plus Manitoba fuel billed in CAD
    daily = {A: 5150.00, S: 5300.00, O: 5560.00}
    for month in c.months:
        for day in range(1, c.last(month) + 1):
            c.add(month, day, "Fuel", "Interstate Fuel Network", f"Fuel card daily summary {int(month[5:])}/{day}", c.jit(daily[month], 0.05))
    for month, rate, n in ((A, 0.7290, 5), (S, 0.7215, 5), (O, 0.7340, 8)):
        for k in range(n):
            cad = round(c.rng.uniform(2200, 2600), 2)
            c.add(month, 3 + k * 3, "Fuel", "Prairie Fuels Ltd (MB)", f"Brandon MB - CAD {cad:,.2f} @{rate:.4f}", round(cad * rate, 2))
    # driver wages: semi-monthly, mileage pay
    for month, lift in ((A, 0.99), (S, 1.0), (O, 1.06)):
        for day in (15, c.last(month)):
            c.add(month, day, "Driver Wages", "Plainsview Payroll", f"Driver settlements {int(month[5:])}/{day} - mileage + accessorials", c.jit(91500.00 * lift, 0.004))
    # purchased transportation: weekly owner-operator settlements and brokered loads
    ops = {"Ridgeback Carriers LLC": 9200.00, "J&M Haulage": 7800.00, "Prairie Star Transport": 11400.00,
           "Kestrel Logistics (broker)": 8900.00}
    for month, lift in ((A, 0.98), (S, 1.0), (O, 1.185)):
        for day in (5, 12, 19, 26):
            for vendor, amt in ops.items():
                c.add(month, day, "Purchased Transportation", vendor, "Weekly settlement - loads per rate cons", c.jit(amt * lift, 0.015))
    # tolls & permits
    c.every("Tolls & Permits", "TollLink", "Tolls 1st-15th", {A: 4380.00, S: 4420.00, O: 4510.00}, 16)
    c.every("Tolls & Permits", "TollLink", "Tolls 16th-EOM", {A: 4410.00, S: 4460.00, O: 4450.00}, 28)
    c.every("Tolls & Permits", "Manitoba Infrastructure", "Oversize/IRP permits", {A: 180.00, S: 180.00, O: 240.00}, 10)
    # maintenance
    c.noise("Tractor & Trailer Maintenance", [("Midstate Truck Service", ["PM-A service", "PM-B service", "Brake job", "Air leak repair", "Trailer lights"])],
            (10, 12), 400, 1600)
    c.add(S, 17, "Tractor & Trailer Maintenance", "Midstate Truck Service", "In-frame overhaul - unit 2207", 18500.00)
    c.add(O, 21, "Tractor & Trailer Maintenance", "Prairie Diesel Emissions", "DPF clean x 22 units", 6600.00)
    # tires
    c.every("Tires", "Northland Tire", "Road service + repairs", {A: 2650.00, S: 2800.00, O: 2900.00}, 25)
    c.add(O, 13, "Tires", "Northland Tire", "Steer tire replacement - 14 tractors (winter program)", 9940.00)
    # leases
    for k in range(12):
        c.every("Equipment Leases", "Ironhorse Leasing", f"Tractor lease - unit {2201 + k}", 2150.00, 1)
    c.every("Equipment Leases", "Great Plains Trailer Pool", "Trailer pool - 30 units", 6400.00, 1)
    c.add(O, 18, "Equipment Leases", "TrackPoint Telematics", "Trailer tracker install (40) + Oct svc", 3300.00)
    # insurance (prepaid, renewed 1 Oct)
    c.add(A, 31, "Insurance", "Prepaid JE", "Prepaid amort - auto liab/cargo (policy 10/1/25)", 31200.00)
    c.add(S, 30, "Insurance", "Prepaid JE", "Prepaid amort - auto liab/cargo (policy 10/1/25)", 31200.00)
    c.add(O, 31, "Insurance", "Prepaid JE", "Prepaid amort - auto liab/cargo (renewal 10/1/26)", 36800.00)
    c.every("Insurance", "Plains Mutual WC", "Workers comp installment", 6900.00, 5)
    # cargo claims
    c.add(A, 14, "Cargo Claims", "Dakota Home Goods", "Claim C-2270 - shortage, 2 cartons", 380.00)
    c.add(S, 22, "Cargo Claims", "Lindqvist Appliance", "Claim C-2284 - forklift damage", 600.00)
    c.add(O, 9, "Cargo Claims", "Harlow Foods Inc", "Claim C-2291 - water-damaged pallets, load 88412", 12400.00)
    c.add(O, 27, "Cargo Claims", "Bluewater Cargo Underwriters", "Recovery - claim C-2291 (net of $3,000 deductible)", -9400.00)
    # software
    c.every("Dispatch & ELD Software", "RouteMax TMS", "TMS subscription", 2950.00, 1)
    c.every("Dispatch & ELD Software", "LogBook ELD", "ELD units", {A: 980.00, S: 980.00, O: 1050.00}, 1)
    # rent, recruiting, compliance, office
    c.every("Terminal Rent", "Red River Terminal Properties", "Terminal + yard lease", 14800.00, 1)
    c.every("Driver Recruiting", "HaulHire Job Board", "Job board campaign", {A: 1550.00, S: 1600.00, O: 4500.00}, 6)
    c.add(O, 24, "Driver Recruiting", "Plainsview CDL Academy", "CDL school tuition reimbursement - 2 hires", 4700.00)
    c.noise("Compliance & Testing", [("ClearPath Testing", ["DOT drug screen", "Random pool fees"]),
                                     ("MVR Direct", ["MVR pulls"])], (3, 5), 45, 380)
    for month in c.months:
        for day in (15, c.last(month)):
            c.add(month, day, "Office Salaries", "Plainsview Payroll", f"Office/dispatch payroll {int(month[5:])}/{day}", 22800.00)
    return c


def main() -> None:
    for build in (brightline, ember, keystone, cedar, lumen, riverbend, halvorsen, northstar):
        co = build()
        co.write()
        periods = {}
        for r in co.rows:
            periods[r["date"][:7]] = periods.get(r["date"][:7], 0) + 1
        print(f"{co.slug:14s} {periods}")


if __name__ == "__main__":
    main()
