from src.validator import validate_payment, validate_credits


def test_validate_payment_returns_no_errors_for_valid_fifo_payment():
    payment = {
        "customer_name": "Sample Customer",
        "payment_date": "2026-03-10",
        "payment_amount": 6000,
        "allocation_method": "FIFO",
    }

    errors = validate_payment(payment)

    assert errors == []


def test_validate_payment_requires_positive_payment_amount():
    payment = {
        "customer_name": "Sample Customer",
        "payment_date": "2026-03-10",
        "payment_amount": 0,
        "allocation_method": "FIFO",
    }

    errors = validate_payment(payment)

    assert "payment_amount must be greater than 0" in errors


def test_validate_payment_rejects_invalid_allocation_method():
    payment = {
        "customer_name": "Sample Customer",
        "payment_date": "2026-03-10",
        "payment_amount": 6000,
        "allocation_method": "RANDOM",
    }

    errors = validate_payment(payment)

    assert "allocation_method must be FIFO, LIFO, or SPECIFIC_DATE" in errors


def test_validate_payment_requires_target_date_for_specific_date_allocation():
    payment = {
        "customer_name": "Sample Customer",
        "payment_date": "2026-03-10",
        "payment_amount": 6000,
        "allocation_method": "SPECIFIC_DATE",
    }

    errors = validate_payment(payment)

    assert "target_date is required for SPECIFIC_DATE allocation" in errors


def test_validate_credits_returns_no_errors_for_valid_credits():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    ]

    errors = validate_credits(credits)

    assert errors == []


def test_validate_credits_requires_remaining_field():
    credits = [
        {"date": "2026-03-01", "amount": 5000}
    ]

    errors = validate_credits(credits)

    assert "credit record 0 remaining is required" in errors


def test_validate_credits_rejects_negative_remaining():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": -100}
    ]

    errors = validate_credits(credits)

    assert "credit record 0 remaining cannot be negative" in errors