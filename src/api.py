import json

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.aging import split_balances_by_age
from src.config_loader import load_config
from src.payment_allocator import (
    allocate_payment_fifo,
    allocate_payment_lifo,
    allocate_payment_to_specific_date,
)
from src.validator import validate_credits, validate_payment


app = FastAPI(title="Strangler Fig Receivables Ledger")

templates = Jinja2Templates(directory="templates")


def load_customers_from_config():
    """
    Load all customers and their credit balances from customers.json.
    """

    config = load_config()

    with open(config["customers_input_file"], "r") as file:
        customers = json.load(file)

    return customers


def save_customers_to_config(customers):
    """
    Save updated customer balances back to customers.json.
    """

    config = load_config()

    with open(config["customers_input_file"], "w") as file:
        json.dump(customers, file, indent=4)


def get_customer_names(customers):
    """
    Return customer names for the customer dropdown.
    """

    return list(customers.keys())


def get_available_transaction_dates(credits):
    """
    Return only dates that have pending transaction balances.
    These dates will be shown in the SPECIFIC_DATE dropdown.
    """

    transaction_dates = []

    for credit in credits:
        if credit["remaining"] > 0:
            transaction_dates.append(credit["date"])

    return transaction_dates


@app.get("/", response_class=HTMLResponse)
def show_form(request: Request):
    customers = load_customers_from_config()
    customer_names = get_customer_names(customers)

    selected_customer = customer_names[0]
    credits = customers[selected_customer]
    transaction_dates = get_available_transaction_dates(credits)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "report": None,
            "errors": None,
            "customer_names": customer_names,
            "selected_customer": selected_customer,
            "transaction_dates": transaction_dates,
        },
    )


@app.post("/process-payment", response_class=HTMLResponse)
def process_payment(
    request: Request,
    customer_name: str = Form(...),
    payment_date: str = Form(...),
    payment_amount: float = Form(...),
    allocation_method: str = Form(...),
    target_date: str = Form(None),
):
    config = load_config()
    customers = load_customers_from_config()
    customer_names = get_customer_names(customers)

    if customer_name not in customers:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "report": None,
                "errors": ["Selected customer does not exist"],
                "customer_names": customer_names,
                "selected_customer": customer_name,
                "transaction_dates": [],
            },
        )

    credits = customers[customer_name]
    transaction_dates = get_available_transaction_dates(credits)

    payment = {
        "customer_name": customer_name,
        "payment_date": payment_date,
        "payment_amount": payment_amount,
        "allocation_method": allocation_method,
    }

    if allocation_method == "SPECIFIC_DATE":
        payment["target_date"] = target_date

    payment_errors = validate_payment(payment)
    credit_errors = validate_credits(credits)
    all_errors = payment_errors + credit_errors

    if all_errors:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "report": None,
                "errors": all_errors,
                "customer_names": customer_names,
                "selected_customer": customer_name,
                "transaction_dates": transaction_dates,
            },
        )

    if allocation_method == "FIFO":
        allocation_result = allocate_payment_fifo(credits, payment_amount)

    elif allocation_method == "LIFO":
        allocation_result = allocate_payment_lifo(credits, payment_amount)

    elif allocation_method == "SPECIFIC_DATE":
        allocation_result = allocate_payment_to_specific_date(
            credits,
            payment_amount,
            target_date,
        )

    else:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "report": None,
                "errors": ["Invalid allocation method"],
                "customer_names": customer_names,
                "selected_customer": customer_name,
                "transaction_dates": transaction_dates,
            },
        )

    updated_credits = allocation_result["updated_credits"]
    advance_payment = allocation_result["advance_payment"]

    customers[customer_name] = updated_credits
    save_customers_to_config(customers)

    aging_result = split_balances_by_age(
        updated_credits,
        reference_date=payment_date,
    )

    total_pending = sum(credit["remaining"] for credit in updated_credits)

    report = {
        "status": "SUCCESS",
        "customer_name": customer_name,
        "payment_date": payment_date,
        "payment_amount": payment_amount,
        "allocation_method": allocation_method,
        "target_date": target_date,
        "updated_credits": updated_credits,
        "advance_payment": advance_payment,
        "total_pending": total_pending,
        "aging": aging_result,
    }

    with open(config["success_output_file"], "w") as file:
        json.dump(report, file, indent=4)

    transaction_dates = get_available_transaction_dates(updated_credits)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "report": report,
            "errors": None,
            "customer_names": customer_names,
            "selected_customer": customer_name,
            "transaction_dates": transaction_dates,
        },
    )