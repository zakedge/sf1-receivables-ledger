from payment_allocator import allocate_payment_fifo
from aging import split_balances_by_age


credits = [
    {"date": "2026-03-01", "amount": 5000, "remaining": 5000},
    {"date": "2026-03-03", "amount": 10000, "remaining": 10000},
    {"date": "2026-03-10", "amount": 7000, "remaining": 7000},
]

payment_amount = 6000

allocation_result = allocate_payment_fifo(credits, payment_amount)

updated_credits = allocation_result["updated_credits"]
advance_payment = allocation_result["advance_payment"]

aging_result = split_balances_by_age(
    updated_credits,
    reference_date="2026-03-10"
)

print("Updated Credits:")
print(updated_credits)

print("\nAdvance Payment:")
print(advance_payment)

print("\nAging Result:")
print(aging_result)