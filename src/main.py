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

customer_balance_report = {
    "customer_name": "Sample Customer",
    "payment_amount": payment_amount,
    "updated_credits": updated_credits,
    "advance_payment": advance_payment,
    "aging": aging_result,
}

with open("output/customer_balance_report.json", "w") as file:
    json.dump(customer_balance_report, file, indent=4)

print("Customer balance report generated successfully.")
print("Output file: output/customer_balance_report.json")