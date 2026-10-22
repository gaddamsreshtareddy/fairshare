"""Data models for FairShare.

Each model is a small class that mirrors one database table.
Money amounts are always integers in minor units (paise/cents).
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

@dataclass
class Group:
    """A group of people who share expenses (table: groups)."""

    id: int | None
    name: str
    base_currency: str = "INR"
    created_at: str | None = None

    @classmethod
    def from_row(cls, row) -> "Group":
        """Build a Group from a database row."""
        return cls(
            id=row["id"],
            name=row["name"],
            base_currency=row["base_currency"],
            created_at=row["created_at"],
        )


@dataclass
class Member:
    """A person in a group (table: members)."""

    id: int | None
    group_id: int
    name: str
    is_active: bool = True
    created_at: str | None = None

    @classmethod
    def from_row(cls, row) -> "Member":
        """Build a Member from a database row."""
        return cls(
            id=row["id"],
            group_id=row["group_id"],
            name=row["name"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )


@dataclass
class PayerShare:
    """One person who paid part of an expense."""

    member_id: int
    amount_paid: int
    id: int | None = None
    expense_id: int | None = None

    @classmethod
    def from_row(cls, row) -> "PayerShare":
        return cls(
            id=row["id"],
            expense_id=row["expense_id"],
            member_id=row["member_id"],
            amount_paid=row["amount_paid"],
        )


@dataclass
class Split:
    """One member's share of an expense."""

    member_id: int
    share_amount: int
    percentage: float | None = None
    id: int | None = None
    expense_id: int | None = None

    @classmethod
    def from_row(cls, row) -> "Split":
        return cls(
            id=row["id"],
            expense_id=row["expense_id"],
            member_id=row["member_id"],
            share_amount=row["share_amount"],
            percentage=row["percentage"],
        )


@dataclass
class Item:
    """One item on an item-based expense."""

    name: str
    amount: int
    consumer_ids: list[int] = field(default_factory=list)
    id: int | None = None
    expense_id: int | None = None

    @classmethod
    def from_row(cls, row) -> "Item":
        """Build an Item from an items database row."""
        return cls(
            id=row["id"],
            expense_id=row["expense_id"],
            name=row["name"],
            amount=row["amount"],
        )


@dataclass
class Expense:
    """One shared expense with payers, splits and items."""

    # Required fields FIRST
    group_id: int
    title: str
    expense_date: str
    currency: str
    original_amount: int
    base_amount: int
    split_method: str

    # Fields with defaults AFTER required fields
    category: str = "Other"
    exchange_rate: float = 1.0
    id: int | None = None
    created_at: str | None = None
    payers: list[PayerShare] = field(default_factory=list)
    splits: list[Split] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)

    @classmethod
    def from_row(cls, row) -> "Expense":
        """Build an Expense from an expenses database row."""
        return cls(
            id=row["id"],
            group_id=row["group_id"],
            title=row["title"],
            expense_date=row["expense_date"],
            currency=row["currency"],
            original_amount=row["original_amount"],
            base_amount=row["base_amount"],
            split_method=row["split_method"],
            category=row["category"],
            exchange_rate=row["exchange_rate"],
            created_at=row["created_at"],
        )


@dataclass
class Settlement:
    """One 'who pays whom' transaction (table: settlements)."""
    id: int | None
    group_id: int
    from_member_id: int
    to_member_id: int
    amount: int
    status: str = "Pending"
    created_at: str | None = None
    completed_at: str | None = None

    @property
    def is_completed(self) -> bool:
        return self.status == "Completed"

    @classmethod
    def from_row(cls, row) -> "Settlement":
        return cls(
            id=row["id"],
            group_id=row["group_id"],
            from_member_id=row["from_member_id"],
            to_member_id=row["to_member_id"],
            amount=row["amount"],
            status=row["status"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )


# Money helpers
CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "AED": "AED ",
}


def to_minor(amount) -> int:
    """Convert a human amount to integer paise/cents."""
    try:
        value = Decimal(str(amount).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"Invalid money amount: {amount!r}") from None

    if not value.is_finite():
        raise ValueError(f"Invalid money amount: {amount!r}")

    return int(
        (value * 100).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP
        )
    )


def from_minor(minor: int) -> Decimal:
    """Convert integer paise/cents to an exact Decimal."""
    return Decimal(minor).scaleb(-2)


def format_money(minor: int, currency: str = "INR") -> str:
    """Format minor units for display."""
    sign = "-" if minor < 0 else ""
    symbol = CURRENCY_SYMBOLS.get(currency, f"{currency} ")

    return f"{sign}{symbol}{abs(from_minor(minor)):,.2f}"