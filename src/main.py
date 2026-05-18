import json

from payment_allocator import (
    allocate_payment_fifo,
    allocate_payment_lifo,
    allocate_payment_to_specific_date,
)
from aging import split_balances_by_age


with open("data/sample_credits.json", "r") as file:
    credits = json.load(file)

with open("data/sample_payment.json", "r") as file:
    payment = json.load(file)


customer_name = payment["customer_name"]
payment_amount = payment["payment_amount"]
allocation_method = payment["allocation_method"]


if allocation_method == "FIFO":
    allocation_result = allocate_payment_fifo(credits, payment_amount)

elif allocation_method == "LIFO":
    allocation_result = allocate_payment_lifo(credits, payment_amount)

elif allocation_method == "SPECIFIC_DATE":
    target_date = payment["target_date"]

    allocation_result = allocate_payment_to_specific_date(
        credits,
        payment_amount,
        target_date,
    )

else:
    raise ValueError("Invalid allocation method")


updated_credits = allocation_result["updated_credits"]
advance_payment = allocation_result["advance_payment"]

aging_result = split_balances_by_age(
    updated_credits,
    reference_date=payment["payment_date"],
)

customer_balance_report = {
    "customer_name": customer_name,
    "payment_date": payment["payment_date"],
    "payment_amount": payment_amount,
    "allocation_method": allocation_method,
    "updated_credits": updated_credits,
    "advance_payment": advance_payment,
    "aging": aging_result,
}

with open("output/customer_balance_report.json", "w") as file:
    json.dump(customer_balance_report, file, indent=4)

print("Customer balance report generated successfully.")
print("Output file: output/customer_balance_report.json")