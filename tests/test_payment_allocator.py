from src.payment_allocator import (
    allocate_payment_fifo,
    allocate_payment_lifo,
    allocate_payment_to_specific_date
)


def test_allocate_payment_to_specific_date_reduces_selected_date_only():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    ]

    result = allocate_payment_to_specific_date(
        credits,
        payment_amount=2000,
        target_date="2026-03-03"
    )

    assert result[0]["remaining"] == 5000
    assert result[1]["remaining"] == 8000