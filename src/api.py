import json
from datetime import datetime

from fastapi import FastAPI, Form, Query, Request
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
    config = load_config()

    try:
        with open(config["customers_input_file"], "r") as file:
            customers = json.load(file)

        if not isinstance(customers, dict):
            return {}

        return customers

    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_customers_to_config(customers):
    config = load_config()

    with open(config["customers_input_file"], "w") as file:
        json.dump(customers, file, indent=4)


def load_areas_from_config():
    config = load_config()

    try:
        with open(config["areas_input_file"], "r") as file:
            areas = json.load(file)

        if not isinstance(areas, list):
            return []

        return areas

    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_areas_to_config(areas):
    config = load_config()

    with open(config["areas_input_file"], "w") as file:
        json.dump(areas, file, indent=4)


def load_payment_history():
    config = load_config()

    try:
        with open(config["payment_history_file"], "r") as file:
            payment_history = json.load(file)

        if not isinstance(payment_history, list):
            return []

        return payment_history

    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_payment_history(payment_history):
    config = load_config()

    with open(config["payment_history_file"], "w") as file:
        json.dump(payment_history, file, indent=4)


def add_payment_history_record(
    customer_id,
    customer_name,
    area,
    payment_date,
    payment_amount,
    allocation_method,
    target_date,
    advance_payment,
    total_pending,
):
    payment_history = load_payment_history()

    history_record = {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "area": area,
        "payment_date": payment_date,
        "payment_amount": payment_amount,
        "allocation_method": allocation_method,
        "target_date": target_date,
        "advance_payment": advance_payment,
        "total_pending_after_payment": total_pending,
        "processed_timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    payment_history.append(history_record)
    save_payment_history(payment_history)


def generate_next_customer_id(customers):
    if not customers:
        return "CUST001"

    existing_numbers = []

    for customer_id in customers.keys():
        if customer_id.startswith("CUST"):
            number_part = customer_id.replace("CUST", "")

            if number_part.isdigit():
                existing_numbers.append(int(number_part))

    if not existing_numbers:
        return "CUST001"

    next_number = max(existing_numbers) + 1
    return f"CUST{next_number:03d}"


def customer_exists_in_area(customers, customer_name, area):
    for customer in customers.values():
        existing_name = customer.get("customer_name", "").strip().lower()
        existing_area = customer.get("area", "").strip().lower()

        if (
            existing_name == customer_name.strip().lower()
            and existing_area == area.strip().lower()
        ):
            return True

    return False


def get_customer_options(customers, selected_area=None):
    customer_options = []

    for customer_id, customer in customers.items():
        customer_area = customer.get("area", "")

        if selected_area and customer_area != selected_area:
            continue

        customer_name = customer.get("customer_name", "")

        customer_options.append(
            {
                "customer_id": customer_id,
                "customer_name": customer_name,
                "area": customer_area,
                "display_name": f"{customer_name} - {customer_area}",
            }
        )

    return customer_options


def get_available_transaction_dates(credits):
    transaction_dates = []

    for credit in credits:
        if credit.get("remaining", 0) > 0:
            transaction_dates.append(credit["date"])

    return transaction_dates


def calculate_total_pending(credits):
    return sum(credit.get("remaining", 0) for credit in credits)


def build_template_context(
    customers,
    selected_customer_id="",
    selected_area="",
    report=None,
    errors=None,
    message=None,
):
    areas = load_areas_from_config()

    # If no area selected, choose first area that has customers.
    if not selected_area:
        for area in areas:
            if get_customer_options(customers, selected_area=area):
                selected_area = area
                break

    # If still no area selected, use first area from master list.
    if not selected_area and areas:
        selected_area = areas[0]

    customer_options = get_customer_options(
        customers,
        selected_area=selected_area,
    )

    # If selected area has no customers, auto-switch to first area that has customers.
    if not customer_options:
        for area in areas:
            area_customer_options = get_customer_options(
                customers,
                selected_area=area,
            )

            if area_customer_options:
                selected_area = area
                customer_options = area_customer_options
                break

    if selected_customer_id not in customers:
        if customer_options:
            selected_customer_id = customer_options[0]["customer_id"]
        else:
            selected_customer_id = ""

    selected_customer = customers.get(selected_customer_id)

    if selected_customer:
        selected_customer_name = selected_customer.get("customer_name", "")
        selected_customer_area = selected_customer.get("area", "")
        selected_customer_credits = selected_customer.get("credits", [])
    else:
        selected_customer_name = ""
        selected_customer_area = ""
        selected_customer_credits = []

    selected_customer_total_pending = calculate_total_pending(
        selected_customer_credits
    )

    transaction_dates = get_available_transaction_dates(
        selected_customer_credits
    )

    return {
        "report": report,
        "errors": errors,
        "message": message,
        "areas": areas,
        "selected_area": selected_area,
        "customer_options": customer_options,
        "selected_customer_id": selected_customer_id,
        "selected_customer_name": selected_customer_name,
        "selected_customer_area": selected_customer_area,
        "selected_customer_credits": selected_customer_credits,
        "selected_customer_total_pending": selected_customer_total_pending,
        "transaction_dates": transaction_dates,
    }


@app.get("/", response_class=HTMLResponse)
def show_form(
    request: Request,
    area: str = Query(None),
    customer_id: str = Query(None),
):
    customers = load_customers_from_config()

    context = build_template_context(
        customers=customers,
        selected_customer_id=customer_id or "",
        selected_area=area or "",
    )

    return templates.TemplateResponse(request, "index.html", context)


@app.post("/add-customer", response_class=HTMLResponse)
def add_customer(
    request: Request,
    new_customer_name: str = Form(...),
    area: str = Form(...),
):
    customers = load_customers_from_config()
    areas = load_areas_from_config()

    cleaned_name = new_customer_name.strip()
    cleaned_area = area.strip()

    if not cleaned_name:
        context = build_template_context(
            customers=customers,
            selected_area=cleaned_area,
            errors=["Customer name cannot be empty"],
        )
        return templates.TemplateResponse(request, "index.html", context)

    if not cleaned_area:
        context = build_template_context(
            customers=customers,
            errors=["Area is required"],
        )
        return templates.TemplateResponse(request, "index.html", context)

    if cleaned_area not in areas:
        areas.append(cleaned_area)
        areas.sort()
        save_areas_to_config(areas)

    if customer_exists_in_area(customers, cleaned_name, cleaned_area):
        context = build_template_context(
            customers=customers,
            selected_area=cleaned_area,
            errors=["Customer already exists in this area"],
        )
        return templates.TemplateResponse(request, "index.html", context)

    customer_id = generate_next_customer_id(customers)

    customers[customer_id] = {
        "customer_name": cleaned_name,
        "area": cleaned_area,
        "credits": [],
    }

    save_customers_to_config(customers)

    context = build_template_context(
        customers=customers,
        selected_customer_id=customer_id,
        selected_area=cleaned_area,
        message=f"Customer added successfully: {cleaned_name} - {cleaned_area}",
    )

    return templates.TemplateResponse(request, "index.html", context)


@app.post("/import-customers", response_class=HTMLResponse)
def import_customers(request: Request):
    config = load_config()
    customers = load_customers_from_config()
    areas = load_areas_from_config()

    try:
        with open(config["customer_import_file"], "r") as file:
            imported_customers = json.load(file)

    except FileNotFoundError:
        context = build_template_context(
            customers=customers,
            errors=["Customer import file not found"],
        )
        return templates.TemplateResponse(request, "index.html", context)

    except json.JSONDecodeError:
        context = build_template_context(
            customers=customers,
            errors=["Customer import file is not valid JSON"],
        )
        return templates.TemplateResponse(request, "index.html", context)

    if not isinstance(imported_customers, list):
        context = build_template_context(
            customers=customers,
            errors=["Customer import file must contain a list"],
        )
        return templates.TemplateResponse(request, "index.html", context)

    imported_count = 0
    skipped_count = 0
    last_imported_customer_id = ""

    for customer in imported_customers:
        customer_name = customer.get("customer_name", "").strip()
        area = customer.get("area", "").strip()

        if not customer_name or not area:
            skipped_count += 1
            continue

        if customer_exists_in_area(customers, customer_name, area):
            skipped_count += 1
            continue

        if area not in areas:
            areas.append(area)

        customer_id = generate_next_customer_id(customers)

        customers[customer_id] = {
            "customer_name": customer_name,
            "area": area,
            "credits": [],
        }

        last_imported_customer_id = customer_id
        imported_count += 1

    areas.sort()

    save_areas_to_config(areas)
    save_customers_to_config(customers)

    selected_area = ""
    if last_imported_customer_id:
        selected_area = customers[last_imported_customer_id]["area"]

    context = build_template_context(
        customers=customers,
        selected_customer_id=last_imported_customer_id,
        selected_area=selected_area,
        message=f"Imported {imported_count} customers. Skipped {skipped_count}.",
    )

    return templates.TemplateResponse(request, "index.html", context)


@app.post("/process-payment", response_class=HTMLResponse)
def process_payment(
    request: Request,
    customer_id: str = Form(...),
    payment_date: str = Form(...),
    payment_amount: int = Form(...),
    allocation_method: str = Form(...),
    target_date: str = Form(None),
):
    config = load_config()
    customers = load_customers_from_config()

    if customer_id not in customers:
        context = build_template_context(
            customers=customers,
            selected_customer_id=customer_id,
            errors=["Selected customer does not exist"],
        )
        return templates.TemplateResponse(request, "index.html", context)

    selected_customer = customers[customer_id]
    customer_name = selected_customer.get("customer_name", "")
    area = selected_customer.get("area", "")
    credits = selected_customer.get("credits", [])

    current_total_pending = calculate_total_pending(credits)

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
        context = build_template_context(
            customers=customers,
            selected_customer_id=customer_id,
            selected_area=area,
            errors=all_errors,
        )
        return templates.TemplateResponse(request, "index.html", context)

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
        context = build_template_context(
            customers=customers,
            selected_customer_id=customer_id,
            selected_area=area,
            errors=["Invalid allocation method"],
        )
        return templates.TemplateResponse(request, "index.html", context)

    updated_credits = allocation_result["updated_credits"]
    advance_payment = allocation_result["advance_payment"]

    customers[customer_id]["credits"] = updated_credits
    save_customers_to_config(customers)

    aging_result = split_balances_by_age(
        updated_credits,
        reference_date=payment_date,
    )

    total_pending = calculate_total_pending(updated_credits)

    add_payment_history_record(
        customer_id=customer_id,
        customer_name=customer_name,
        area=area,
        payment_date=payment_date,
        payment_amount=payment_amount,
        allocation_method=allocation_method,
        target_date=target_date,
        advance_payment=advance_payment,
        total_pending=total_pending,
    )

    report = {
        "status": "SUCCESS",
        "customer_id": customer_id,
        "customer_name": customer_name,
        "area": area,
        "payment_date": payment_date,
        "payment_amount": payment_amount,
        "allocation_method": allocation_method,
        "target_date": target_date,
        "updated_credits": updated_credits,
        "advance_payment": advance_payment,
        "total_pending": total_pending,
        "previous_total_pending": current_total_pending,
        "aging": aging_result,
    }

    with open(config["success_output_file"], "w") as file:
        json.dump(report, file, indent=4)

    context = build_template_context(
        customers=customers,
        selected_customer_id=customer_id,
        selected_area=area,
        report=report,
    )

    return templates.TemplateResponse(request, "index.html", context)