import json
from datetime import datetime, timedelta

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.aging import split_balances_by_age
from src.auth import (
    PAGE_ACCESS_OPTIONS,
    authenticate_user,
    create_user,
    load_users,
    user_has_access,
    users_exist,
)
from src.config_loader import load_config
from src.payment_allocator import (
    allocate_payment_fifo,
    allocate_payment_lifo,
    allocate_payment_to_specific_date,
)
from src.validator import validate_credits, validate_payment


config = load_config()

app = FastAPI(title="Strangler Fig Receivables Ledger")
app.add_middleware(
    SessionMiddleware,
    secret_key=config["session_secret_key"],
)

templates = Jinja2Templates(directory="templates")


# -------------------------
# Auth helpers
# -------------------------

def get_logged_in_user(request: Request):
    username = request.session.get("username")

    if not username:
        return None

    users = load_users()

    for user in users:
        if user["username"] == username:
            return user

    return None


def redirect_to_login():
    return RedirectResponse(url="/login", status_code=303)


def require_page_access(request: Request, page_key: str):
    if not users_exist():
        return RedirectResponse(url="/setup-admin", status_code=303)

    user = get_logged_in_user(request)

    if not user:
        return redirect_to_login()

    if not user_has_access(user, page_key):
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "total_customers": 0,
                "total_areas": 0,
                "total_pending": 0,
                "message": None,
                "errors": ["You do not have access to this page."],
            },
        )

    return None


# -------------------------
# Data helpers
# -------------------------

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
        customer_name = customer.get("customer_name", "")

        if selected_area and customer_area != selected_area:
            continue

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


def calculate_total_pending_all_customers(customers):
    total = 0

    for customer in customers.values():
        credits = customer.get("credits", [])
        total += calculate_total_pending(credits)

    return total


def build_all_balance_rows(customers):
    rows = []

    for customer_id, customer in customers.items():
        customer_name = customer.get("customer_name", "")
        area = customer.get("area", "")
        credits = customer.get("credits", [])

        if not credits:
            rows.append(
                {
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "area": area,
                    "date": "-",
                    "amount": 0,
                    "remaining": 0,
                }
            )

        for credit in credits:
            rows.append(
                {
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "area": area,
                    "date": credit.get("date", ""),
                    "amount": credit.get("amount", 0),
                    "remaining": credit.get("remaining", 0),
                }
            )

    return rows


def build_payment_page_context(
    customers,
    selected_customer_id="",
    selected_area="",
    report=None,
    errors=None,
    message=None,
):
    areas = load_areas_from_config()

    if not selected_area:
        for area in areas:
            if get_customer_options(customers, selected_area=area):
                selected_area = area
                break

    if not selected_area and areas:
        selected_area = areas[0]

    customer_options = get_customer_options(
        customers,
        selected_area=selected_area,
    )

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


def build_last_7_day_columns(reference_date):
    reference = datetime.strptime(reference_date, "%Y-%m-%d").date()
    start_date = reference - timedelta(days=6)

    columns = []

    for day_offset in range(7):
        current_date = start_date + timedelta(days=day_offset)

        columns.append(
            {
                "date_key": current_date.strftime("%Y-%m-%d"),
                "display_name": current_date.strftime("%d-%b"),
            }
        )

    return columns


def build_last_7_days_report_rows(customers, reference_date):
    date_columns = build_last_7_day_columns(reference_date)
    date_keys = [column["date_key"] for column in date_columns]

    reference = datetime.strptime(reference_date, "%Y-%m-%d").date()
    last_7_start = reference - timedelta(days=6)

    rows = []
    sr_no = 1

    for customer_id, customer in customers.items():
        customer_name = customer.get("customer_name", "")
        area = customer.get("area", "")
        credits = customer.get("credits", [])

        date_balances = {}
        old_balance = 0
        very_old_balance = 0
        total_pending = 0

        for column in date_columns:
            date_balances[column["date_key"]] = 0

        for credit in credits:
            credit_date_text = credit.get("date", "")
            remaining = credit.get("remaining", 0)

            if remaining <= 0:
                continue

            total_pending += remaining

            try:
                credit_date = datetime.strptime(
                    credit_date_text,
                    "%Y-%m-%d",
                ).date()
            except ValueError:
                continue

            if credit_date_text in date_keys:
                date_balances[credit_date_text] += remaining

            elif credit_date < last_7_start:
                old_balance += remaining

        total_credit_given = sum(date_balances.values())

        rows.append(
            {
                "sr_no": sr_no,
                "customer_id": customer_id,
                "customer_name": customer_name,
                "area": area,
                "very_old": very_old_balance,
                "old": old_balance,
                "date_balances": date_balances,
                "total_credit_given": total_credit_given,
                "cash_collected": 0,
                "pending": total_pending,
            }
        )

        sr_no += 1

    return date_columns, rows


# -------------------------
# Auth routes
# -------------------------

@app.get("/setup-admin", response_class=HTMLResponse)
def show_setup_admin(request: Request):
    if users_exist():
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request,
        "setup_admin.html",
        {
            "message": None,
            "errors": None,
        },
    )


@app.post("/setup-admin", response_class=HTMLResponse)
def setup_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if users_exist():
        return RedirectResponse(url="/login", status_code=303)

    all_pages = [page["key"] for page in PAGE_ACCESS_OPTIONS]

    success, message = create_user(
        username=username.strip(),
        password=password,
        allowed_pages=all_pages,
        is_admin=True,
    )

    if not success:
        return templates.TemplateResponse(
            request,
            "setup_admin.html",
            {
                "message": None,
                "errors": [message],
            },
        )

    request.session["username"] = username.strip()

    return RedirectResponse(url="/", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def show_login(request: Request):
    if not users_exist():
        return RedirectResponse(url="/setup-admin", status_code=303)

    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "message": None,
            "errors": None,
        },
    )


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = authenticate_user(username.strip(), password)

    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "message": None,
                "errors": ["Invalid username or password"],
            },
        )

    request.session["username"] = user["username"]

    return RedirectResponse(url="/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()

    return RedirectResponse(url="/login", status_code=303)


@app.get("/users", response_class=HTMLResponse)
def show_users(request: Request):
    access_response = require_page_access(request, "user_management")

    if access_response:
        return access_response

    return templates.TemplateResponse(
        request,
        "users.html",
        {
            "users": load_users(),
            "page_options": PAGE_ACCESS_OPTIONS,
            "message": None,
            "errors": None,
        },
    )


@app.post("/users", response_class=HTMLResponse)
def create_new_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    allowed_pages: list[str] = Form([]),
):
    access_response = require_page_access(request, "user_management")

    if access_response:
        return access_response

    success, message = create_user(
        username=username.strip(),
        password=password,
        allowed_pages=allowed_pages,
        is_admin=False,
    )

    if not success:
        return templates.TemplateResponse(
            request,
            "users.html",
            {
                "users": load_users(),
                "page_options": PAGE_ACCESS_OPTIONS,
                "message": None,
                "errors": [message],
            },
        )

    return templates.TemplateResponse(
        request,
        "users.html",
        {
            "users": load_users(),
            "page_options": PAGE_ACCESS_OPTIONS,
            "message": message,
            "errors": None,
        },
    )


# -------------------------
# App routes
# -------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    access_response = require_page_access(request, "dashboard")

    if access_response:
        return access_response

    customers = load_customers_from_config()
    areas = load_areas_from_config()

    total_customers = len(customers)
    total_areas = len(areas)
    total_pending = calculate_total_pending_all_customers(customers)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "total_customers": total_customers,
            "total_areas": total_areas,
            "total_pending": total_pending,
            "message": None,
            "errors": None,
        },
    )


@app.get("/add-customer", response_class=HTMLResponse)
def show_add_customer(request: Request):
    access_response = require_page_access(request, "add_customer")

    if access_response:
        return access_response

    areas = load_areas_from_config()

    return templates.TemplateResponse(
        request,
        "add_customer.html",
        {
            "areas": areas,
            "message": None,
            "errors": None,
        },
    )


@app.post("/add-customer", response_class=HTMLResponse)
def add_customer(
    request: Request,
    new_customer_name: str = Form(...),
    area: str = Form(...),
):
    access_response = require_page_access(request, "add_customer")

    if access_response:
        return access_response

    customers = load_customers_from_config()
    areas = load_areas_from_config()

    cleaned_name = new_customer_name.strip()
    cleaned_area = area.strip()

    if not cleaned_name:
        return templates.TemplateResponse(
            request,
            "add_customer.html",
            {
                "areas": areas,
                "message": None,
                "errors": ["Customer name cannot be empty"],
            },
        )

    if not cleaned_area:
        return templates.TemplateResponse(
            request,
            "add_customer.html",
            {
                "areas": areas,
                "message": None,
                "errors": ["Area is required"],
            },
        )

    if cleaned_area not in areas:
        areas.append(cleaned_area)
        areas.sort()
        save_areas_to_config(areas)

    if customer_exists_in_area(customers, cleaned_name, cleaned_area):
        return templates.TemplateResponse(
            request,
            "add_customer.html",
            {
                "areas": areas,
                "message": None,
                "errors": ["Customer already exists in this area"],
            },
        )

    customer_id = generate_next_customer_id(customers)

    customers[customer_id] = {
        "customer_name": cleaned_name,
        "area": cleaned_area,
        "credits": [],
    }

    save_customers_to_config(customers)

    return templates.TemplateResponse(
        request,
        "add_customer.html",
        {
            "areas": areas,
            "message": f"Customer added successfully: {cleaned_name} - {cleaned_area}",
            "errors": None,
        },
    )


@app.get("/import-customers", response_class=HTMLResponse)
def show_import_customers(request: Request):
    access_response = require_page_access(request, "import_customers")

    if access_response:
        return access_response

    return templates.TemplateResponse(
        request,
        "import_customers.html",
        {
            "message": None,
            "errors": None,
        },
    )


@app.post("/import-customers", response_class=HTMLResponse)
def import_customers(request: Request):
    access_response = require_page_access(request, "import_customers")

    if access_response:
        return access_response

    config = load_config()
    customers = load_customers_from_config()
    areas = load_areas_from_config()

    try:
        with open(config["customer_import_file"], "r") as file:
            imported_customers = json.load(file)

    except FileNotFoundError:
        return templates.TemplateResponse(
            request,
            "import_customers.html",
            {
                "message": None,
                "errors": ["Customer import file not found"],
            },
        )

    except json.JSONDecodeError:
        return templates.TemplateResponse(
            request,
            "import_customers.html",
            {
                "message": None,
                "errors": ["Customer import file is not valid JSON"],
            },
        )

    if not isinstance(imported_customers, list):
        return templates.TemplateResponse(
            request,
            "import_customers.html",
            {
                "message": None,
                "errors": ["Customer import file must contain a list"],
            },
        )

    imported_count = 0
    skipped_count = 0

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

        imported_count += 1

    areas.sort()

    save_areas_to_config(areas)
    save_customers_to_config(customers)

    return templates.TemplateResponse(
        request,
        "import_customers.html",
        {
            "message": f"Imported {imported_count} customers. Skipped {skipped_count}.",
            "errors": None,
        },
    )


@app.get("/all-balances", response_class=HTMLResponse)
def all_balances(request: Request):
    access_response = require_page_access(request, "all_balances")

    if access_response:
        return access_response

    customers = load_customers_from_config()
    rows = build_all_balance_rows(customers)

    return templates.TemplateResponse(
        request,
        "all_balances.html",
        {
            "rows": rows,
            "message": None,
            "errors": None,
        },
    )


@app.get("/add-payment", response_class=HTMLResponse)
def show_add_payment(
    request: Request,
    area: str = Query(None),
    customer_id: str = Query(None),
):
    access_response = require_page_access(request, "add_payment")

    if access_response:
        return access_response

    customers = load_customers_from_config()

    context = build_payment_page_context(
        customers=customers,
        selected_customer_id=customer_id or "",
        selected_area=area or "",
    )

    return templates.TemplateResponse(request, "add_payment.html", context)


@app.post("/process-payment", response_class=HTMLResponse)
def process_payment(
    request: Request,
    customer_id: str = Form(...),
    payment_date: str = Form(...),
    payment_amount: int = Form(...),
    allocation_method: str = Form(...),
    target_date: str = Form(None),
):
    access_response = require_page_access(request, "add_payment")

    if access_response:
        return access_response

    config = load_config()
    customers = load_customers_from_config()

    if customer_id not in customers:
        context = build_payment_page_context(
            customers=customers,
            selected_customer_id=customer_id,
            errors=["Selected customer does not exist"],
        )
        return templates.TemplateResponse(request, "add_payment.html", context)

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
        context = build_payment_page_context(
            customers=customers,
            selected_customer_id=customer_id,
            selected_area=area,
            errors=all_errors,
        )
        return templates.TemplateResponse(request, "add_payment.html", context)

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
        context = build_payment_page_context(
            customers=customers,
            selected_customer_id=customer_id,
            selected_area=area,
            errors=["Invalid allocation method"],
        )
        return templates.TemplateResponse(request, "add_payment.html", context)

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

    context = build_payment_page_context(
        customers=customers,
        selected_customer_id=customer_id,
        selected_area=area,
        report=report,
    )

    return templates.TemplateResponse(request, "add_payment.html", context)


@app.get("/last-7-days-report", response_class=HTMLResponse)
def last_7_days_report(
    request: Request,
    reference_date: str = Query("2026-03-31"),
):
    access_response = require_page_access(request, "last_7_days_report")

    if access_response:
        return access_response

    customers = load_customers_from_config()

    date_columns, rows = build_last_7_days_report_rows(
        customers,
        reference_date,
    )

    return templates.TemplateResponse(
        request,
        "last_7_days_report.html",
        {
            "reference_date": reference_date,
            "date_columns": date_columns,
            "rows": rows,
            "message": None,
            "errors": None,
        },
    )