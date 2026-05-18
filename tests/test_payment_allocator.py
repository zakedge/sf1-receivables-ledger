from src.payment_allocator import allocate_payment_fifo


def test_allocate_payment_fifo_reduces_oldest_balance_first():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    ]

    result = allocate_payment_fifo(credits, 2000)

    assert result[0]["remaining"] == 3000
    assert result[1]["remaining"] == 10000