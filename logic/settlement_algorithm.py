"""Settlement algorithms (business logic layer). Pure Python, no database.

Input is always {member_id: net_paise}: positive = is owed money,
negative = owes money. Output is a list of (from_member_id, to_member_id,
amount_paise) payments.
"""

from logic.validators import ValidationError


def greedy_settlement(balances):
    """Settle everyone by repeatedly matching the biggest debtor with the
    biggest creditor. Always correct; usually, but not always, the fewest payments.
    """
    if sum(balances.values()) != 0:
        raise ValidationError("Balances must add up to zero.")

    # Each entry is [member_id, positive_amount]. Lists are changed in place.
    debtors = [[m, -net] for m, net in balances.items() if net < 0]
    creditors = [[m, net] for m, net in balances.items() if net > 0]

    payments = []
    while debtors and creditors:
        # Sort so the biggest amount is last (ties: smaller member id is last).
        debtors.sort(key=lambda x: (x[1], -x[0]))
        creditors.sort(key=lambda x: (x[1], -x[0]))

        debtor = debtors[-1]
        creditor = creditors[-1]
        pay = min(debtor[1], creditor[1])

        payments.append((debtor[0], creditor[0], pay))  # debtor pays creditor
        debtor[1] -= pay
        creditor[1] -= pay

        if debtor[1] == 0:
            debtors.pop()
        if creditor[1] == 0:
            creditors.pop()

    return payments

EXACT_LIMIT = 12  # above this many people with a balance, use greedy instead


def exact_settlement(balances):
    """Settle everyone with the provably fewest payments.

    Splits the people into the largest possible number of groups whose
    balances each add up to zero. A group of k people needs k - 1 payments.
    Time is about 2^n * n, so use it only for small groups.
    """
    if sum(balances.values()) != 0:
        raise ValidationError("Balances must add up to zero.")

    people = sorted(m for m, net in balances.items() if net != 0)
    n = len(people)
    if n == 0:
        return []
    amounts = [balances[p] for p in people]
    size = 1 << n  # number of subsets

    # total[mask] = sum of balances of the people in that subset
    total = [0] * size
    for mask in range(1, size):
        low = mask & -mask                 # lowest set bit
        total[mask] = total[mask ^ low] + amounts[low.bit_length() - 1]

    # dp[mask] = most zero-sum groups possible inside that subset
    dp = [0] * size
    choice = [0] * size                    # which person was removed last
    for mask in range(1, size):
        best = -1
        for i in range(n):
            if mask >> i & 1 and dp[mask ^ (1 << i)] > best:
                best = dp[mask ^ (1 << i)]
                choice[mask] = i
        dp[mask] = best + (1 if total[mask] == 0 else 0)

    # Rebuild an ordering of people, then cut it wherever the running sum is 0.
    order = []
    mask = size - 1
    while mask:
        order.append(choice[mask])
        mask ^= 1 << choice[mask]
    order.reverse()

    groups, group, running = [], [], 0
    for i in order:
        group.append(i)
        running += amounts[i]
        if running == 0:
            groups.append(group)
            group = []

    # Each group cannot be split further, so greedy uses exactly k - 1 payments.
    payments = []
    for group in groups:
        payments.extend(greedy_settlement({people[i]: amounts[i] for i in group}))
    return payments


def settle(balances, exact_limit=EXACT_LIMIT):
    """Exact method for small groups, greedy for large ones."""
    people = sum(1 for net in balances.values() if net != 0)
    if people <= exact_limit:
        return exact_settlement(balances)
    return greedy_settlement(balances)