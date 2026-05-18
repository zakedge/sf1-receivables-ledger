import json

from aging import split_balances_by_age
from logger import setup_logger
from payment_allocator import (
    allocate_payment_fifo,
    allocate_payment_lifo,
    allocate_payment_to_specific_date,
)
from validator import validate_credits, validate_payment


logger = setup_logger()
logger.info("Application started")


with open("data/sample_credits.json", "r") as file:
    credits = json.load(file)

with open("data/sample_payment.json", "r") as file:
    payment = json.load(file)

logger.info("Input files loaded successfully")


payment_errors = validate_payment(payment)
credit_errors = validate_credits(credits)

all_errors = payment_errors + credit_errors

if all_errors:
    error_report = {
        "status": "FAILED",
        "errors": all_errors,
    }

    with open("output/error_report.json", "w") as file:
        json.dump(error_report, file, indent=4)

    logger.error("Validation failed: %s", all_errors)

    print("Validation failed.")
    print("Output file: output/error_report.json")

    raise SystemExit


logger.info("Validation passed")


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


logger.info("Payment allocation completed using method: %s", allocation_method)


updated_credits = allocation_result["updated_credits"]
advance_payment = allocation_result["advance_payment"]

aging_result = split_balances_by_age(
    updated_credits,
    reference_date=payment["payment_date"],
)

customer_balance_report = {
    "status": "SUCCESS",
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

logger.info("Customer balance report generated successfully")

print("Customer balance report generated successfully.")
print("Output file: output/customer_balance_report.json")