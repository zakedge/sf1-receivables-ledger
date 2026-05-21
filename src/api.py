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


def load_credits_from_config():
    config = load_config()

    with open(config["credits_input_file"], "r") as file:
        credits = json.load(file)

    return credits


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
    credits = load_credits_from_config()
    transaction_dates = get_available_transaction_dates(credits)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "report": None,
            "errors": None,
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
    credits = load_credits_from_config()
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
                "transaction_dates": transaction_dates,
            },
        )

    updated_credits = allocation_result["updated_credits"]
    advance_payment = allocation_result["advance_payment"]

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

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "report": report,
            "errors": None,
            "transaction_dates": transaction_dates,
        },
    )