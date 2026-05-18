def allocate_payment_fifo(credits, payment_amount):
    """
    Allocate payment using FIFO.

    FIFO = First In, First Out.
    Oldest pending balance is adjusted first.

    Returns:
        dict with:
        - updated_credits
        - advance_payment
    """

    remaining_payment = payment_amount

    for credit in credits:
        if remaining_payment <= 0:
            break

        current_remaining = credit["remaining"]

        if current_remaining <= remaining_payment:
            remaining_payment = remaining_payment - current_remaining
            credit["remaining"] = 0
        else:
            credit["remaining"] = current_remaining - remaining_payment
            remaining_payment = 0

    return {
        "updated_credits": credits,
        "advance_payment": remaining_payment,
    }


def allocate_payment_lifo(credits, payment_amount):
    """
    Allocate payment using LIFO.

    LIFO = Last In, First Out.
    Latest pending balance is adjusted first.

    Returns:
        dict with:
        - updated_credits
        - advance_payment
    """

    remaining_payment = payment_amount

    for credit in reversed(credits):
        if remaining_payment <= 0:
            break

        current_remaining = credit["remaining"]

        if current_remaining <= remaining_payment:
            remaining_payment = remaining_payment - current_remaining
            credit["remaining"] = 0
        else:
            credit["remaining"] = current_remaining - remaining_payment
            remaining_payment = 0

    return {
        "updated_credits": credits,
        "advance_payment": remaining_payment,
    }


def allocate_payment_to_specific_date(credits, payment_amount, target_date):
    """
    Allocate payment against one selected credit date.

    Example:
    If customer has balances on 2026-03-01 and 2026-03-03,
    owner can choose to adjust payment only against 2026-03-03.

    Returns:
        dict with:
        - updated_credits
        - advance_payment
        - date_found
    """

    advance_payment = 0
    date_found = False

    for credit in credits:
        if credit["date"] == target_date:
            date_found = True
            current_remaining = credit["remaining"]

            if current_remaining <= payment_amount:
                credit["remaining"] = 0
                advance_payment = payment_amount - current_remaining
            else:
                credit["remaining"] = current_remaining - payment_amount
                advance_payment = 0

            break

    return {
        "updated_credits": credits,
        "advance_payment": advance_payment,
        "date_found": date_found,
    }