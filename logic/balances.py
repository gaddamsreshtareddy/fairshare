def calculate_balances(expenses, member_ids):
    result = {
        member_id: {"paid": 0, "owed": 0, "net": 0}
        for member_id in member_ids
    }

    for expense in expenses:
        for payer in expense.payers:
            record = result.setdefault(
                payer.member_id,
                {"paid": 0, "owed": 0, "net": 0},
            )
            record["paid"] += payer.amount_paid

        for split in expense.splits:
            record = result.setdefault(
                split.member_id,
                {"paid": 0, "owed": 0, "net": 0},
            )
            record["owed"] += split.share_amount

    for record in result.values():
        record["net"] = record["paid"] - record["owed"]

    return result