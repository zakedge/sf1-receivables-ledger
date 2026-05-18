from src.payment_allocator import (
    allocate_payment_fifo,
    allocate_payment_lifo,
    allocate_payment_to_specific_date,
)


def test_allocate_payment_fifo_reduces_oldest_balance_first():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    ]

    result = allocate_payment_fifo(credits, 2000)

    updated_credits = result["updated_credits"]

    assert updated_credits[0]["remaining"] == 3000
    assert updated_credits[1]["remaining"] == 10000
    assert result["advance_payment"] == 0


def test_allocate_payment_fifo_clears_first_balance_and_reduces_second():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    ]

    result = allocate_payment_fifo(credits, 7000)

    updated_credits = result["updated_credits"]

    assert updated_credits[0]["remaining"] == 0
    assert updated_credits[1]["remaining"] == 8000
    assert result["advance_payment"] == 0


def test_allocate_payment_fifo_returns_advance_when_payment_exceeds_all_balances():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    ]

    result = allocate_payment_fifo(credits, 20000)

    updated_credits = result["updated_credits"]

    assert updated_credits[0]["remaining"] == 0
    assert updated_credits[1]["remaining"] == 0
    assert result["advance_payment"] == 5000


def test_allocate_payment_lifo_reduces_latest_balance_first():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    ]

    result = allocate_payment_lifo(credits, 2000)

    updated_credits = result["updated_credits"]

    assert updated_credits[0]["remaining"] == 5000
    assert updated_credits[1]["remaining"] == 8000
    assert result["advance_payment"] == 0


def test_allocate_payment_lifo_clears_latest_balance_and_reduces_previous():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    ]

    result = allocate_payment_lifo(credits, 12000)

    updated_credits = result["updated_credits"]

    assert updated_credits[0]["remaining"] == 3000
    assert updated_credits[1]["remaining"] == 0
    assert result["advance_payment"] == 0


def test_allocate_payment_lifo_returns_advance_when_payment_exceeds_all_balances():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    ]

    result = allocate_payment_lifo(credits, 20000)

    updated_credits = result["updated_credits"]

    assert updated_credits[0]["remaining"] == 0
    assert updated_credits[1]["remaining"] == 0
    assert result["advance_payment"] == 5000


def test_allocate_payment_to_specific_date_reduces_selected_date_only():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    ]

    result = allocate_payment_to_specific_date(
        credits,
        payment_amount=2000,
        target_date="2026-03-03",
    )

    updated_credits = result["updated_credits"]

    assert updated_credits[0]["remaining"] == 5000
    assert updated_credits[1]["remaining"] == 8000
    assert result["advance_payment"] == 0
    assert result["date_found"] is True


def test_allocate_payment_to_specific_date_returns_advance_when_payment_exceeds_selected_balance():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    ]

    result = allocate_payment_to_specific_date(
        credits,
        payment_amount=12000,
        target_date="2026-03-03",
    )

    updated_credits = result["updated_credits"]

    assert updated_credits[0]["remaining"] == 5000
    assert updated_credits[1]["remaining"] == 0
    assert result["advance_payment"] == 2000
    assert result["date_found"] is True


def test_allocate_payment_to_specific_date_returns_date_found_false_when_date_not_available():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    ]

    result = allocate_payment_to_specific_date(
        credits,
        payment_amount=2000,
        target_date="2026-03-10",
    )

    updated_credits = result["updated_credits"]

    assert updated_credits[0]["remaining"] == 5000
    assert updated_credits[1]["remaining"] == 10000
    assert result["advance_payment"] == 0
    assert result["date_found"] is False