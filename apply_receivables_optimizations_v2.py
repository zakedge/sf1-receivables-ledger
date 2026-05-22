from pathlib import Path
import re

ROOT = Path.cwd()


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, text):
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_text(path, old, new, description):
    text = read(path)
    if new in text:
        print(f"SKIP already applied: {description}")
        return False
    if old not in text:
        print(f"SKIP block not found, maybe already changed: {description}")
        return False
    write(path, text.replace(old, new, 1))
    print(f"APPLIED: {description}")
    return True


def replace_regex(path, pattern, new, description):
    text = read(path)
    if new.strip() in text:
        print(f"SKIP already applied: {description}")
        return False
    updated, count = re.subn(pattern, new, text, count=1, flags=re.DOTALL)
    if count == 0:
        print(f"SKIP pattern not found, maybe already changed: {description}")
        return False
    write(path, updated)
    print(f"APPLIED: {description}")
    return True


def insert_after(path, marker, insert_text, description):
    text = read(path)
    if insert_text.strip() in text:
        print(f"SKIP already applied: {description}")
        return False
    if marker not in text:
        print(f"SKIP marker not found, maybe already changed: {description}")
        return False
    write(path, text.replace(marker, marker + insert_text, 1))
    print(f"APPLIED: {description}")
    return True


def main():
    # src/api.py imports
    api = read("src/api.py")
    if "import os\n" not in api or "import tempfile\n" not in api:
        api = api.replace(
            "import json\nfrom datetime import datetime, timedelta\n",
            "import json\nimport os\nimport tempfile\nfrom datetime import datetime, timedelta\n",
            1,
        )
        write("src/api.py", api)
        print("APPLIED: add atomic-save imports")
    else:
        print("SKIP already applied: add atomic-save imports")

    # Data helper block. This works on untouched state. If your previous run already applied it, it skips safely.
    data_helpers_new = '''def load_customers_from_config():
    try:
        with open(config["customers_input_file"], "r", encoding="utf-8") as file:
            customers = json.load(file)

        if not isinstance(customers, dict):
            return {}

        return customers

    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json_file(path, data):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=directory,
        delete=False,
    ) as temp_file:
        json.dump(data, temp_file, indent=4)
        temp_file.write("\\n")
        temp_path = temp_file.name

    os.replace(temp_path, path)


def save_customers_to_config(customers):
    save_json_file(config["customers_input_file"], customers)


def load_areas_from_config():
    try:
        with open(config["areas_input_file"], "r", encoding="utf-8") as file:
            areas = json.load(file)

        if not isinstance(areas, list):
            return []

        return areas

    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_areas_to_config(areas):
    save_json_file(config["areas_input_file"], areas)


def load_payment_history():
    try:
        with open(config["payment_history_file"], "r", encoding="utf-8") as file:
            payment_history = json.load(file)

        if not isinstance(payment_history, list):
            return []

        return payment_history

    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_payment_history(payment_history):
    save_json_file(config["payment_history_file"], payment_history)
'''
    if "def save_json_file(path, data):" in read("src/api.py"):
        print("SKIP already applied: consolidate JSON loading/saving")
    else:
        replace_regex(
            "src/api.py",
            r"def load_customers_from_config\(\):.*?def add_payment_history_record\(",
            data_helpers_new + "\n\ndef add_payment_history_record(",
            "consolidate JSON loading/saving and use atomic writes",
        )

    replace_text(
        "src/api.py",
        '    reference = datetime.strptime(reference_date, "%Y-%m-%d").date()\n    last_7_start = reference - timedelta(days=6)\n\n    rows = []\n',
        '    reference = datetime.strptime(reference_date, "%Y-%m-%d").date()\n    last_7_start = reference - timedelta(days=6)\n    very_old_cutoff = reference - timedelta(days=30)\n\n    rows = []\n',
        "add very-old cutoff to last 7 days report",
    )

    replace_text(
        "src/api.py",
        '            if credit_date_text in date_keys:\n                date_balances[credit_date_text] += remaining\n\n            elif credit_date < last_7_start:\n                old_balance += remaining\n',
        '            if credit_date_text in date_keys:\n                date_balances[credit_date_text] += remaining\n\n            elif credit_date < very_old_cutoff:\n                very_old_balance += remaining\n\n            elif credit_date < last_7_start:\n                old_balance += remaining\n',
        "populate very_old balance instead of leaving it always zero",
    )

    replace_text(
        "src/api.py",
        '        with open(config["customer_import_file"], "r") as file:\n            imported_customers = json.load(file)\n',
        '        with open(config["customer_import_file"], "r", encoding="utf-8") as file:\n            imported_customers = json.load(file)\n',
        "read customer import file with utf-8 encoding",
    )

    insert_after(
        "src/api.py",
        '    updated_credits = allocation_result["updated_credits"]\n    advance_payment = allocation_result["advance_payment"]\n',
        '\n    if allocation_method == "SPECIFIC_DATE" and not allocation_result.get("date_found"):\n        context = build_payment_page_context(\n            customers=customers,\n            selected_customer_id=customer_id,\n            selected_area=area,\n            errors=["Selected target date is not available for this customer"],\n        )\n        return templates.TemplateResponse(request, "add_payment.html", context)\n',
        "handle SPECIFIC_DATE target dates that are not found",
    )

    # Replace the whole last_7_days_report route. Handles both original and partially modified state.
    last_7_new = '''@app.get("/last-7-days-report", response_class=HTMLResponse)
def last_7_days_report(
    request: Request,
    reference_date: str | None = Query(None),
):
    access_response = require_page_access(request, "last_7_days_report")

    if access_response:
        return access_response

    if not reference_date:
        reference_date = datetime.today().strftime("%Y-%m-%d")

    customers = load_customers_from_config()

    try:
        date_columns, rows = build_last_7_days_report_rows(
            customers,
            reference_date,
        )
        message = None
        errors = None
    except ValueError:
        reference_date = datetime.today().strftime("%Y-%m-%d")
        date_columns, rows = build_last_7_days_report_rows(
            customers,
            reference_date,
        )
        message = None
        errors = ["Invalid reference date. Showing today's report instead."]

    return templates.TemplateResponse(
        request,
        "last_7_days_report.html",
        {
            "reference_date": reference_date,
            "date_columns": date_columns,
            "rows": rows,
            "message": message,
            "errors": errors,
        },
    )
'''
    api = read("src/api.py")
    if 'reference_date: str | None = Query(None)' in api and 'Invalid reference date. Showing today' in api:
        print("SKIP already applied: use today's date by default and handle invalid report dates")
    else:
        updated, count = re.subn(
            r'@app\.get\("/last-7-days-report", response_class=HTMLResponse\)\ndef last_7_days_report\(.*?\n    \)\s*$',
            last_7_new,
            api,
            count=1,
            flags=re.DOTALL,
        )
        if count == 0:
            raise RuntimeError("Could not replace last_7_days_report route. Please paste that function here and I will tailor the fix.")
        write("src/api.py", updated)
        print("APPLIED: use today's date by default and handle invalid report dates")

    # Payment allocator dedupe.
    allocator_new = '''def _allocate_payment_by_order(credits, payment_amount, reverse=False):
    remaining_payment = payment_amount
    ordered_credits = reversed(credits) if reverse else credits

    for credit in ordered_credits:
        if remaining_payment <= 0:
            break

        current_remaining = credit["remaining"]
        amount_to_apply = min(current_remaining, remaining_payment)

        credit["remaining"] = current_remaining - amount_to_apply
        remaining_payment -= amount_to_apply

    return {
        "updated_credits": credits,
        "advance_payment": remaining_payment,
    }


def allocate_payment_fifo(credits, payment_amount):
    """
    Allocate payment using FIFO.

    FIFO = First In, First Out.
    Oldest pending balance is adjusted first.

    Returns:
        dict with:
        - updated_credits
        - advance_payment
    """
    return _allocate_payment_by_order(credits, payment_amount, reverse=False)


def allocate_payment_lifo(credits, payment_amount):
    """
    Allocate payment using LIFO.

    LIFO = Last In, First Out.
    Latest pending balance is adjusted first.

    Returns:
        dict with:
        - updated_credits
        - advance_payment
    """
    return _allocate_payment_by_order(credits, payment_amount, reverse=True)


'''
    if "def _allocate_payment_by_order" in read("src/payment_allocator.py"):
        print("SKIP already applied: deduplicate FIFO and LIFO allocation logic")
    else:
        replace_regex(
            "src/payment_allocator.py",
            r"def allocate_payment_fifo\(credits, payment_amount\):.*?\n(?=def allocate_payment_to_specific_date)",
            allocator_new,
            "deduplicate FIFO and LIFO allocation logic",
        )

    replace_text(
        "src/validator.py",
        '    if payment.get("allocation_method") == "SPECIFIC_DATE":\n        if "target_date" not in payment:\n            errors.append("target_date is required for SPECIFIC_DATE allocation")\n',
        '    if payment.get("allocation_method") == "SPECIFIC_DATE":\n        if not payment.get("target_date"):\n            errors.append("target_date is required for SPECIFIC_DATE allocation")\n',
        "reject blank SPECIFIC_DATE target date",
    )

    insert_after(
        "tests/test_validator.py",
        'def test_validate_payment_requires_target_date_for_specific_date_allocation():\n    payment = {\n        "customer_name": "Sample Customer",\n        "payment_date": "2026-03-10",\n        "payment_amount": 6000,\n        "allocation_method": "SPECIFIC_DATE",\n    }\n\n    errors = validate_payment(payment)\n\n    assert "target_date is required for SPECIFIC_DATE allocation" in errors\n\n\n',
        'def test_validate_payment_rejects_blank_target_date_for_specific_date_allocation():\n    payment = {\n        "customer_name": "Sample Customer",\n        "payment_date": "2026-03-10",\n        "payment_amount": 6000,\n        "allocation_method": "SPECIFIC_DATE",\n        "target_date": "",\n    }\n\n    errors = validate_payment(payment)\n\n    assert "target_date is required for SPECIFIC_DATE allocation" in errors\n\n\n',
        "add validator test for blank target date",
    )

    print("\nDone. Next run: pytest")


if __name__ == "__main__":
    main()
