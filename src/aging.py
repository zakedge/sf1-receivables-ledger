from datetime import datetime, timedelta


def split_balances_by_age(credits, reference_date):
    """
    Split customer credit balances into:
    1. last_7_days
    2. old_balance
    3. old_balance_breakdown

    Args:
        credits (list): List of credit records.
        reference_date (str): Date used as today's/current date in YYYY-MM-DD format.

    Returns:
        dict: Aging result.
    """

    reference = datetime.strptime(reference_date, "%Y-%m-%d").date()
    seven_days_ago = reference - timedelta(days=7)

    last_7_days = []
    old_balance_breakdown = []
    old_balance_total = 0

    for credit in credits:
        credit_date = datetime.strptime(credit["date"], "%Y-%m-%d").date()
        remaining = credit["remaining"]

        if remaining <= 0:
            continue

        if credit_date >= seven_days_ago:
            last_7_days.append(credit)
        else:
            old_balance_breakdown.append(credit)
            old_balance_total = old_balance_total + remaining

    return {
        "last_7_days": last_7_days,
        "old_balance": old_balance_total,
        "old_balance_breakdown": old_balance_breakdown,
    }