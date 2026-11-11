"""The authoritative side: a company's transactions for two periods.

A variance explanation is a claim about how an account moved between a prior and
a current period, and why. Everything needed to test it is in the general ledger:
the balances (did it move by that much, in that direction?), the transactions
behind the movement (which payments actually changed?), and the history of each
vendor (does this invoice usually land in this account?).

WHAT IS DECLARED, NOT INFERRED

The chart of accounts — names and the aliases a writer may use for them — is
supplied with the ledger. A checker that infers what an account is from column
names or wording manufactures findings out of its own guesses, so here what an
account is called is a fact someone states, never a guess the checker makes. `default_aliases()` exists only for an uploaded CSV that
carries no chart, and it is mechanical (the name, lower-cased and split on "&").
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Iterable

#: The pseudo-account a claim about total operating expenses resolves to.
TOTAL = "Total operating expenses"
TOTAL_ALIASES = (
    "total operating expenses", "operating expenses", "total opex", "opex",
    "total expenses", "total spend", "overall spend",
)


@dataclass(frozen=True)
class Transaction:
    """One posted transaction. `amount` is positive for an expense, negative for a credit."""
    id: str
    date: str          # ISO date, "2026-10-14"
    account: str
    vendor: str
    memo: str
    amount: float      # expense positive; a refund or credit is negative

    @property
    def period(self) -> str:
        return self.date[:7]

    @property
    def searchable(self) -> str:
        return f"{self.vendor} {self.memo}".lower()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Account:
    """An account in the chart, with the aliases a writer may use for it."""
    name: str
    aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"name": self.name, "aliases": list(self.aliases)}


@dataclass(frozen=True)
class Variance:
    """An account's balance in the prior and current period, and the change between them."""
    prior: float
    current: float

    @property
    def change(self) -> float:
        return self.current - self.prior

    @property
    def change_pct(self) -> float | None:
        """Percentage change in points, or None when the prior period is zero."""
        if abs(self.prior) < 0.005:
            return None
        return self.change / abs(self.prior) * 100.0


@dataclass(frozen=True)
class Contribution:
    """One vendor's part in an account's movement."""

    vendor: str
    prior: float
    current: float
    txn_ids: tuple[str, ...]

    @property
    def change(self) -> float:
        return self.current - self.prior

    def to_dict(self) -> dict:
        return {"vendor": self.vendor, "prior": round(self.prior, 2),
                "current": round(self.current, 2), "change": round(self.change, 2),
                "txn_ids": list(self.txn_ids)}


@dataclass(frozen=True)
class VendorHome:
    """Where a vendor's invoices usually land, and how consistently."""

    account: str
    count: int
    total: int


def default_aliases(name: str) -> tuple[str, ...]:
    """Mechanical aliases for an account that arrived without any."""
    lower = name.lower().strip()
    parts = [p.strip() for p in re.split(r"\s*(?:&|/|\band\b)\s*", lower) if p.strip()]
    aliases = {lower, lower.replace("&", "and")}
    for part in parts:
        aliases.add(part)
        bare = re.sub(r"\s+(fees|costs|expenses|expense)$", "", part)
        if len(bare) >= 3:
            aliases.add(bare)
    return tuple(sorted(aliases, key=lambda a: (-len(a), a)))


@dataclass
class Ledger:
    """A company's transactions, its chart of accounts, and the two periods being compared.

    Validated on construction: every transaction must book to an account in the
    chart, and transaction ids must be unique.
    """
    entity: str
    prior_period: str      # "2026-09"
    current_period: str    # "2026-10"
    accounts: tuple[Account, ...]
    transactions: tuple[Transaction, ...]
    _by_id: dict[str, Transaction] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        names = {a.name for a in self.accounts}
        seen: set[str] = set()
        for txn in self.transactions:
            if txn.account not in names:
                raise ValueError(
                    f"transaction {txn.id} is booked to {txn.account!r}, which is not "
                    f"in the chart of accounts")
            if txn.id in seen:
                raise ValueError(f"duplicate transaction id {txn.id}")
            seen.add(txn.id)
        self._by_id = {t.id: t for t in self.transactions}

    # ── lookups ──────────────────────────────────────────────────────────

    @property
    def account_names(self) -> list[str]:
        return [a.name for a in self.accounts]

    def txn(self, txn_id: str) -> Transaction:
        return self._by_id[txn_id]

    def in_scope(self, account: str, period: str | None = None) -> list[Transaction]:
        """Transactions in an account (or all of them, for TOTAL), optionally one period."""
        periods = (self.prior_period, self.current_period) if period is None else (period,)
        return [t for t in self.transactions
                if t.period in periods and (account == TOTAL or t.account == account)]

    def variance(self, account: str) -> Variance:
        prior = sum(t.amount for t in self.in_scope(account, self.prior_period))
        current = sum(t.amount for t in self.in_scope(account, self.current_period))
        return Variance(prior=prior, current=current)

    def contributions(self, account: str, exclude: Iterable[str] = ()) -> list[Contribution]:
        """Each vendor's movement in an account, largest first."""
        excluded = set(exclude)
        grouped: dict[str, list[Transaction]] = {}
        for txn in self.in_scope(account):
            if txn.id not in excluded:
                grouped.setdefault(txn.vendor, []).append(txn)
        out = []
        for vendor, txns in grouped.items():
            prior = sum(t.amount for t in txns if t.period == self.prior_period)
            current = sum(t.amount for t in txns if t.period == self.current_period)
            out.append(Contribution(vendor, prior, current, tuple(t.id for t in txns)))
        return sorted(out, key=lambda c: (-abs(c.change), c.vendor))

    def vendor_home(self, vendor: str, exclude_id: str, *, min_count: int,
                    min_share: float) -> VendorHome | None:
        """The account a vendor books to, if its history makes that unambiguous.

        Computed over every *other* transaction from the vendor, so the one under
        suspicion cannot vote for itself. None when the vendor has too little
        history or splits across accounts — a vendor with no clear home is not
        evidence of anything.
        """
        counts: dict[str, int] = {}
        for txn in self.transactions:
            if txn.vendor == vendor and txn.id != exclude_id:
                counts[txn.account] = counts.get(txn.account, 0) + 1
        total = sum(counts.values())
        if total < min_count:
            return None
        account, count = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
        if count / total < min_share:
            return None
        return VendorHome(account=account, count=count, total=total)

    # ── identity and serialisation ───────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "entity": self.entity,
            "prior_period": self.prior_period,
            "current_period": self.current_period,
            "accounts": [a.to_dict() for a in self.accounts],
            "transactions": [t.to_dict() for t in self.transactions],
        }

    def sha256(self) -> str:
        """Identity of the ledger's content: a verdict is a statement about particular bytes."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: dict) -> "Ledger":
        accounts = tuple(
            Account(a["name"], tuple(a.get("aliases") or default_aliases(a["name"])))
            for a in data["accounts"])
        transactions = tuple(
            Transaction(id=str(t["id"]), date=str(t["date"]), account=str(t["account"]),
                        vendor=str(t["vendor"]), memo=str(t.get("memo", "")),
                        amount=float(t["amount"]))
            for t in data["transactions"])
        return cls(entity=data.get("entity", ""), prior_period=data["prior_period"],
                   current_period=data["current_period"], accounts=accounts,
                   transactions=transactions)

    def to_csv(self) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["id", "date", "account", "vendor", "memo", "amount"])
        for t in self.transactions:
            writer.writerow([t.id, t.date, t.account, t.vendor, t.memo, f"{t.amount:.2f}"])
        return buffer.getvalue()

    @classmethod
    def from_csv(cls, text: str, entity: str = "Uploaded ledger") -> "Ledger":
        """A ledger from a GL export: columns id, date, account, vendor, memo, amount.

        The two most recent months present become the prior and current periods.
        Amounts may use thousands separators or accounting parentheses.
        """
        reader = csv.DictReader(io.StringIO(text.strip()))
        required = {"id", "date", "account", "vendor", "amount"}
        header = {h.strip().lower() for h in (reader.fieldnames or [])}
        missing = required - header
        if missing:
            raise ValueError(f"ledger CSV is missing column(s): {', '.join(sorted(missing))}")
        rows = []
        for raw in reader:
            row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
            amount_text = row["amount"].replace(",", "").replace("$", "")
            negative = amount_text.startswith("(") and amount_text.endswith(")")
            amount = float(amount_text.strip("()"))
            rows.append(Transaction(row["id"], row["date"], row["account"], row["vendor"],
                                    row.get("memo", ""), -amount if negative else amount))
        months = sorted({r.period for r in rows})
        if len(months) < 2:
            raise ValueError("ledger CSV needs transactions in at least two months")
        names = sorted({r.account for r in rows})
        return cls(entity=entity, prior_period=months[-2], current_period=months[-1],
                   accounts=tuple(Account(n, default_aliases(n)) for n in names),
                   transactions=tuple(rows))
