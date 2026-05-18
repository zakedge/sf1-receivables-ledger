def allocate_payment_fifo(credits,payment_amount):

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