VALID_ALLOCATION_METHODS = ["FIFO", "LIFO", "SPECIFIC_DATE"]


def validate_payment(payment):
    """
    Validate payment input before processing.
    """

    errors = []

    if "customer_name" not in payment:
        errors.append("customer_name is required")

    if "payment_date" not in payment:
        errors.append("payment_date is required")

    if "payment_amount" not in payment:
        errors.append("payment_amount is required")
    elif payment["payment_amount"] <= 0:
        errors.append("payment_amount must be greater than 0")

    if "allocation_method" not in payment:
        errors.append("allocation_method is required")
    elif payment["allocation_method"] not in VALID_ALLOCATION_METHODS:
        errors.append("allocation_method must be FIFO, LIFO, or SPECIFIC_DATE")

    if payment.get("allocation_method") == "SPECIFIC_DATE":
        if not payment.get("target_date"):
            errors.append("target_date is required for SPECIFIC_DATE allocation")

    return errors


def validate_credits(credits):
    """
    Validate credit records before processing.
    """

    errors = []

    for index, credit in enumerate(credits):
        if "date" not in credit:
            errors.append(f"credit record {index} date is required")

        if "amount" not in credit:
            errors.append(f"credit record {index} amount is required")

        if "remaining" not in credit:
            errors.append(f"credit record {index} remaining is required")

        if "remaining" in credit and credit["remaining"] < 0:
            errors.append(f"credit record {index} remaining cannot be negative")

    return errors