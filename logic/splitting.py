from decimal import Decimal, InvalidOperation

from logic.validators import ValidationError


def allocate(total, weights):
    if total < 0:
        raise ValidationError("Total cannot be negative.")

    if not weights:
        raise ValidationError("Weights cannot be empty.")

    if any(weight < 0 for weight in weights):
        raise ValidationError("Weights cannot be negative.")

    weight_sum = sum(weights)

    if weight_sum == 0:
        raise ValidationError("At least one weight must be greater than zero.")

    bases = []
    remainders = []

    for weight in weights:
        numerator = total * weight
        bases.append(numerator // weight_sum)
        remainders.append(numerator % weight_sum)

    leftover = total - sum(bases)

    order = sorted(
        range(len(weights)),
        key=lambda i: (-remainders[i], i)
    )

    for i in order[:leftover]:
        bases[i] += 1

    return bases

def equal_split(total, member_ids):
    if not member_ids:
        raise ValidationError("At least one member is required.")

    if len(member_ids) != len(set(member_ids)):
        raise ValidationError("Member IDs cannot be duplicated.")

    if total <= 0:
        raise ValidationError("Total must be greater than zero.")

    shares = allocate(total, [1] * len(member_ids))

    return dict(zip(member_ids, shares))

def custom_split(total, shares):
    if not shares:
        raise ValidationError("Shares cannot be empty.")

    if any(amount < 0 for amount in shares.values()):
        raise ValidationError("Shares cannot be negative.")

    if sum(shares.values()) != total:
        raise ValidationError(
            f"Shares must add up to the total of {total} paise."
        )

    return dict(shares)

def percentage_split(total, percentages):
    if not percentages:
        raise ValidationError("Percentages cannot be empty.")

    values = {}

    for member_id, percentage in percentages.items():
        try:
            value = Decimal(str(percentage))
        except (InvalidOperation, ValueError):
            raise ValidationError(
                f"Invalid percentage for member {member_id}."
            )

        if value < 0 or value > 100:
            raise ValidationError(
                f"Percentage for member {member_id} must be between 0 and 100."
            )

        if value.as_tuple().exponent < -2:
            raise ValidationError(
                "Percentages can have at most 2 decimal places."
            )

        values[member_id] = value

    if sum(values.values(), Decimal("0")) != Decimal("100"):
        raise ValidationError("Percentages must add up to exactly 100.")

    weights = [int(value * 100) for value in values.values()]

    shares = allocate(total, weights)

    return dict(zip(values.keys(), shares))

def item_split(items):
    if not items:
        raise ValidationError("Items cannot be empty.")

    total = 0
    shares = {}

    for amount, consumers in items:
        if amount <= 0:
            raise ValidationError("Item amount must be greater than zero.")

        if not consumers:
            raise ValidationError("Each item must have at least one consumer.")

        if len(consumers) != len(set(consumers)):
            raise ValidationError("Consumers cannot be duplicated.")

        total += amount

        parts = allocate(amount, [1] * len(consumers))

        for member_id, part in zip(consumers, parts):
            shares[member_id] = shares.get(member_id, 0) + part

    return total, shares


def validate_payers(total, payers):
    if not payers:
        raise ValidationError("Payers cannot be empty.")

    if any(amount <= 0 for amount in payers.values()):
        raise ValidationError("Payer amounts must be greater than zero.")

    if sum(payers.values()) != total:
        raise ValidationError("Payer amounts must add up to the total.")

    return dict(payers)