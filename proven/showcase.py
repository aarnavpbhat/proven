"""The demo close: one company, one month, one AI-drafted commentary with every kind of problem.

Lumen Robotics is fictional. Its ledger is written out by hand so that every
number in the story below can be traced to a line of this file; the commentary
is what an FP&A copilot might draft from it, including the pitch's own example
sentence. What Proven should say about each sentence is pinned by
`tests/test_showcase.py`, so the demo cannot drift from what the code does.

    Legal costs rose $90K because of our Series B funding round.
        FAIL. Legal moved +$44,900 as booked. A $45,100 Harbor & Vale invoice
        for the Series B was booked to Marketing; reclassified, Legal rose
        $90,000 and the sentence would be right.
    Marketing spend increased $67K, driven by the DevSummit sponsorship.
        FAIL. The amount is right, but DevSummit is a third of it; the rest is
        the same misbooked legal invoice, flagged as a possible misclassification.
    Cloud hosting grew approximately 16% to $94.5K, primarily due to higher
    AWS usage during the data migration.
        PASS. Percentage, balance and reason all check out.
    Software & subscriptions rose $31.6K due to annual license renewals.
        PASS.
    Contractor costs increased $22K due to the website redesign.
        FAIL. The redesign cost the same in both months; the increase is the
        mobile-app contract engineers.
    The $45K increase in recruiting fees was primarily due to the VP
    Engineering search.
        PASS. The search is two thirds of it, and "primarily" claims a majority.
    Travel fell $12K, reflecting fewer customer visits.
        REVIEW. The amount is right, but no transaction mentions customer
        visits; the fall is September's company offsite not recurring.
    Lab equipment spend rose $15K for the new test rig.
        REVIEW. There is no lab-equipment account to check it against.
    Total operating expenses increased $212K month over month, primarily
    driven by the Series B and the VP Engineering search.
        PASS. Across all accounts, those two causes are 57% of the movement —
        the total is right even where the categories are not.
"""
from __future__ import annotations

from proven.ledger import Ledger, Transaction
from proven.synth import CHART

ENTITY = "Lumen Robotics, Inc."

EXPLANATION = """October 2026 close — operating expense commentary (draft prepared by FP&A copilot).

Legal costs rose $90K because of our Series B funding round.
Marketing spend increased $67K, driven by the DevSummit sponsorship.
Cloud hosting grew approximately 16% to $94.5K, primarily due to higher AWS usage during the data migration.
Software & subscriptions rose $31.6K due to annual license renewals.
Contractor costs increased $22K due to the website redesign.
The $45K increase in recruiting fees was primarily due to the VP Engineering search.
Travel fell $12K, reflecting fewer customer visits.
Lab equipment spend rose $15K for the new test rig.
Headcount-related costs remain the largest component of our $1.2M quarterly run-rate.
Total operating expenses increased $212K month over month, primarily driven by the Series B and the VP Engineering search.
All other accounts were in line with September."""

LEGAL = "Legal & Professional Fees"
MARKETING = "Marketing & Advertising"
CLOUD = "Cloud Hosting"
SOFTWARE = "Software & Subscriptions"
TRAVEL = "Travel & Entertainment"
RENT = "Rent & Facilities"
CONTRACTORS = "Contractors"
RECRUITING = "Recruiting"
INSURANCE = "Insurance"

# (date, account, vendor, memo, amount). Three months: August is history only,
# and exists so that every recurring vendor has a usual account.
_ROWS: tuple[tuple[str, str, str, str, float], ...] = (
    # Legal & Professional Fees
    ("2026-08-04", LEGAL, "Harbor & Vale LLP", "General corporate retainer", 6000.00),
    ("2026-09-03", LEGAL, "Harbor & Vale LLP", "General corporate retainer", 6000.00),
    ("2026-10-02", LEGAL, "Harbor & Vale LLP", "General corporate retainer", 6000.00),
    ("2026-08-28", LEGAL, "Ledgerline CPAs", "Monthly close support", 3500.00),
    ("2026-09-29", LEGAL, "Ledgerline CPAs", "Monthly close support", 3500.00),
    ("2026-10-28", LEGAL, "Ledgerline CPAs", "Monthly close support", 3620.00),
    ("2026-10-17", LEGAL, "Harbor & Vale LLP", "Series B financing — closing documents", 44780.00),
    # The misbooking: a Series B legal invoice coded to Marketing.
    ("2026-10-21", MARKETING, "Harbor & Vale LLP", "Series B — investor rights agreements", 45100.00),
    # Marketing & Advertising
    ("2026-08-01", MARKETING, "Google Ads", "Search ads — always on", 9050.00),
    ("2026-09-01", MARKETING, "Google Ads", "Search ads — always on", 9000.00),
    ("2026-10-01", MARKETING, "Google Ads", "Search ads — always on", 9150.00),
    ("2026-08-15", MARKETING, "Brightwave Agency", "Content retainer", 5000.00),
    ("2026-09-15", MARKETING, "Brightwave Agency", "Content retainer", 5000.00),
    ("2026-10-15", MARKETING, "Brightwave Agency", "Content retainer", 5000.00),
    ("2026-10-09", MARKETING, "Expo Collective", "DevSummit 2026 — booth sponsorship", 18000.00),
    ("2026-10-23", MARKETING, "Expo Collective", "DevSummit 2026 — booth build", 4150.00),
    # Cloud Hosting
    ("2026-08-31", CLOUD, "Amazon Web Services", "Production hosting", 71800.00),
    ("2026-09-30", CLOUD, "Amazon Web Services", "Production hosting", 72000.00),
    ("2026-10-31", CLOUD, "Amazon Web Services", "Production hosting", 72400.00),
    ("2026-08-31", CLOUD, "Datadog", "Monitoring", 9500.00),
    ("2026-09-30", CLOUD, "Datadog", "Monitoring", 9500.00),
    ("2026-10-31", CLOUD, "Datadog", "Monitoring", 9500.00),
    ("2026-10-20", CLOUD, "Amazon Web Services", "EC2 — data migration load testing", 12600.00),
    # Software & Subscriptions
    ("2026-08-05", SOFTWARE, "Slack", "Workspace — monthly", 2400.00),
    ("2026-09-05", SOFTWARE, "Slack", "Workspace — monthly", 2400.00),
    ("2026-10-05", SOFTWARE, "Slack", "Workspace — monthly", 2480.00),
    ("2026-08-07", SOFTWARE, "GitHub", "Team plan — monthly", 2100.00),
    ("2026-09-07", SOFTWARE, "GitHub", "Team plan — monthly", 2100.00),
    ("2026-10-07", SOFTWARE, "GitHub", "Team plan — monthly", 2100.00),
    ("2026-08-12", SOFTWARE, "Figma", "Design team — monthly", 1500.00),
    ("2026-09-12", SOFTWARE, "Figma", "Design team — monthly", 1500.00),
    ("2026-10-12", SOFTWARE, "Figma", "Design team — monthly", 1500.00),
    ("2026-08-20", SOFTWARE, "Salesforce", "CRM — monthly", 3200.00),
    ("2026-09-20", SOFTWARE, "Salesforce", "CRM — monthly", 3200.00),
    ("2026-10-20", SOFTWARE, "Salesforce", "CRM — monthly", 3200.00),
    ("2026-10-14", SOFTWARE, "Salesforce", "Annual renewal — 2027 CRM licenses", 31500.00),
    # Travel & Entertainment
    ("2026-08-18", TRAVEL, "Delta Air Lines", "Flights", 4100.00),
    ("2026-09-18", TRAVEL, "Delta Air Lines", "Flights", 4200.00),
    ("2026-10-18", TRAVEL, "Delta Air Lines", "Flights", 4350.00),
    ("2026-08-22", TRAVEL, "Marriott", "Hotel stays", 3000.00),
    ("2026-09-22", TRAVEL, "Marriott", "Hotel stays", 3100.00),
    ("2026-10-22", TRAVEL, "Marriott", "Hotel stays", 3000.00),
    ("2026-08-25", TRAVEL, "Uber", "Ground transport", 880.00),
    ("2026-09-25", TRAVEL, "Uber", "Ground transport", 900.00),
    ("2026-10-25", TRAVEL, "Uber", "Ground transport", 1050.00),
    ("2026-09-11", TRAVEL, "Lakeside Lodge", "Company offsite — venue and lodging", 12400.00),
    # Rent & Facilities
    ("2026-08-01", RENT, "Bayview Properties", "HQ rent", 18000.00),
    ("2026-09-01", RENT, "Bayview Properties", "HQ rent", 18000.00),
    ("2026-10-01", RENT, "Bayview Properties", "HQ rent", 18000.00),
    ("2026-08-30", RENT, "Brightline Janitorial", "Cleaning service", 1200.00),
    ("2026-09-30", RENT, "Brightline Janitorial", "Cleaning service", 1200.00),
    ("2026-10-30", RENT, "Brightline Janitorial", "Cleaning service", 1240.00),
    # Contractors
    ("2026-08-26", CONTRACTORS, "Deel", "Monthly payroll — international team", 12000.00),
    ("2026-09-26", CONTRACTORS, "Deel", "Monthly payroll — international team", 12000.00),
    ("2026-10-26", CONTRACTORS, "Deel", "Monthly payroll — international team", 12000.00),
    ("2026-08-14", CONTRACTORS, "Upwork", "Freelance support", 1900.00),
    ("2026-09-14", CONTRACTORS, "Upwork", "Freelance support", 2000.00),
    ("2026-10-14", CONTRACTORS, "Upwork", "Freelance support", 2000.00),
    ("2026-09-10", CONTRACTORS, "Kestrel Design Studio", "Website redesign — phase 1", 11000.00),
    ("2026-10-10", CONTRACTORS, "Kestrel Design Studio", "Website redesign — phase 2", 11000.00),
    ("2026-10-27", CONTRACTORS, "Deel", "Contract engineers — mobile app build", 22300.00),
    # Recruiting
    ("2026-08-03", RECRUITING, "Greenhouse", "ATS subscription", 1800.00),
    ("2026-09-03", RECRUITING, "Greenhouse", "ATS subscription", 1800.00),
    ("2026-10-03", RECRUITING, "Greenhouse", "ATS subscription", 1800.00),
    ("2026-08-08", RECRUITING, "LinkedIn", "Talent platform — monthly", 2500.00),
    ("2026-09-08", RECRUITING, "LinkedIn", "Talent platform — monthly", 2500.00),
    ("2026-10-08", RECRUITING, "LinkedIn", "Talent platform — monthly", 2500.00),
    ("2026-08-10", RECRUITING, "Talentbridge Partners", "Retainer — monthly", 3000.00),
    ("2026-09-10", RECRUITING, "Talentbridge Partners", "Retainer — monthly", 3000.00),
    ("2026-10-10", RECRUITING, "Talentbridge Partners", "Retainer — monthly", 3000.00),
    ("2026-10-16", RECRUITING, "Talentbridge Partners", "VP Engineering search — placement fee", 30000.00),
    ("2026-10-24", RECRUITING, "Campus Connect", "University career fairs — booth fees", 14800.00),
    # Insurance
    ("2026-08-02", INSURANCE, "Atlas Mutual", "General liability — monthly", 2600.00),
    ("2026-09-02", INSURANCE, "Atlas Mutual", "General liability — monthly", 2600.00),
    ("2026-10-02", INSURANCE, "Atlas Mutual", "General liability — monthly", 2600.00),
    ("2026-08-02", INSURANCE, "Shieldpoint", "Workers comp — monthly", 900.00),
    ("2026-09-02", INSURANCE, "Shieldpoint", "Workers comp — monthly", 900.00),
    ("2026-10-02", INSURANCE, "Shieldpoint", "Workers comp — monthly", 900.00),
)


def ledger() -> Ledger:
    """The demo close's ledger: 78 transactions over August, September and October 2026."""
    order = sorted(range(len(_ROWS)), key=lambda i: (_ROWS[i][0], i))
    transactions = tuple(
        Transaction(f"TX-{2001 + n}", *_ROWS[i]) for n, i in enumerate(order))
    return Ledger(ENTITY, "2026-09", "2026-10", CHART, transactions)


#: What the demo must show, sentence by sentence. Pinned by tests/test_showcase.py.
EXPECTED: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Legal costs rose $90K", "FAIL", ("WRONG_AMOUNT", "POSSIBLE_MISCLASSIFICATION")),
    ("Marketing spend increased $67K", "FAIL", ("PARTIAL_EXPLANATION", "POSSIBLE_MISCLASSIFICATION")),
    ("Cloud hosting grew", "PASS", ()),
    ("Software & subscriptions rose", "PASS", ()),
    ("Contractor costs increased", "FAIL", ("WRONG_CAUSE",)),
    ("The $45K increase in recruiting", "PASS", ()),
    ("Travel fell $12K", "REVIEW", ("REASON_NOT_FOUND",)),
    ("Lab equipment spend", "REVIEW", ("ACCOUNT_NOT_FOUND",)),
    ("Total operating expenses", "PASS", ()),
)
