import json

from payment_allocator import allocate_payment_fifo
from aging import split_balances_by_age


with open("data/sample_credits.json", "r") as file:
    credits = json.load(file)


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