from src.aging import split_balances_by_age


def test_split_balances_by_age_separates_last_7_days_and_old_balance():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
        {"date": "2026-03-05", "amount": 3000, "remaining": 3000},
        {"date": "2026-03-10", "amount": 7000, "remaining": 7000},
    ]

    result = split_balances_by_age(
        credits,
        reference_date="2026-03-10"
    )

    assert len(result["last_7_days"]) == 2
    assert result["old_balance"] == 5000
    assert len(result["old_balance_breakdown"]) == 1
    assert result["old_balance_breakdown"][0]["date"] == "2026-03-01"


def test_split_balances_by_age_ignores_fully_paid_balances():
    credits = [
        {"date": "2026-03-01", "amount": 5000, "remaining": 0},
        {"date": "2026-03-10", "amount": 7000, "remaining": 7000},
    ]

    result = split_balances_by_age(
        credits,
        reference_date="2026-03-10"
    )

    assert len(result["last_7_days"]) == 1
    assert result["old_balance"] == 0
    assert len(result["old_balance_breakdown"]) == 0