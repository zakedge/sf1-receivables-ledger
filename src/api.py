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


@app.get("/", response_class=HTMLResponse)
def show_form(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "report": None,
            "errors": None,
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

    with open(config["credits_input_file"], "r") as file:
        credits = json.load(file)

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
            },
        )

    updated_credits = allocation_result["updated_credits"]
    advance_payment = allocation_result["advance_payment"]

    aging_result = split_balances_by_age(
        updated_credits,
        reference_date=payment_date,
    )

    report = {
        "status": "SUCCESS",
        "customer_name": customer_name,
        "payment_date": payment_date,
        "payment_amount": payment_amount,
        "allocation_method": allocation_method,
        "updated_credits": updated_credits,
        "advance_payment": advance_payment,
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
        },
    )