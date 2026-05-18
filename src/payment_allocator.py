def allocate_payment_fifo(credits,payment_amount):
    """
    Allocate a payment against customer credit entries using FIFO.

    FIFO means First In, First Out:
    the oldest pending balance is adjusted first.

    Args:
        credits (list): List of credit records.
        payment_amount (float): Amount paid by customer.

    Returns:
        list: Updated credit records with remaining balances.
    """
    remaining_payment = payment_amount

    for credit in credits:
        if remaining_payment <= 0:
            break


        current_remaining = credit["remaining"]


        if current_remaining <= remaining_payment:
            remaining_payment = current_remaining
            credit["remaining"] = 0
        else:
            credit["remaining"] = current_remaining - remaining_payment
            remaining_payment = 0


    return credits



def allocate_payment_lifo(credits,payment_amount):

    """
    Allocate a payment against customer credit entries using LIFO.

    LIFO means Last In, First Out:
    the latest pending balance is adjusted first.

    Args:
        credits (list): List of credit records.
        payment_amount (float): Amount paid by customer.

    Returns:
        list: Updated credit records with remaining balances.
    """

    remaining_payment = payment_amount

    for credit in reversed(credits):
        if remaining_payment <= 0 :
            break


        current_remaining = credit["remaining"]

        if current_remaining <= remaining_payment:
            remaining_payment -= current_remaining
            credit["remaining"] = 0
        else:
            credit["remaining"] = current_remaining - remaining_payment
            remaining_payment = 0

    return credits



def allocate_payment_to_specific_date(credits,payment_amount,target_date):

   """
    Allocate payment against one specific credit date.

    Example:
    If customer has balances on 2026-03-01 and 2026-03-03,
    the owner can choose to adjust payment only against 2026-03-03.
    """

   for credit in credits:
        if credit["date"] == target_date:
         current_remaining = credit["remaining"]


         if payment_amount >= current_remaining:
             credit["remaining"] = 0

         else:
            credit["remaining"] = current_remaining - payment_amount
            break

   return credits
