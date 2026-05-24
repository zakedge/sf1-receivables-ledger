import json
import sys
import threading


_PATCH_TIMER_STARTED = False


def _load_json_file(path, default_value):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_value


def _patch_all_balances_rows(config, attempts_left=30):
    api_module = sys.modules.get("src.api")

    if not api_module or not hasattr(api_module, "build_all_balance_rows"):
        if attempts_left > 0:
            timer = threading.Timer(
                0.1,
                _patch_all_balances_rows,
                args=(config, attempts_left - 1),
            )
            timer.daemon = True
            timer.start()
        return

    _add_process_payment_with_mode_route(api_module)
    _add_credit_with_modified_route(api_module)

    def build_all_balance_rows_with_payments(customers):
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
                        "modified_date": "",
                        "amount": 0,
                        "credit": 0,
                        "payment": "",
                        "payment_mode": "",
                        "remaining": 0,
                    }
                )

            for credit in credits:
                credit_amount = credit.get("amount", 0)
                modified_date = credit.get("modified_date") or credit.get("created_at") or credit.get("date", "")

                rows.append(
                    {
                        "customer_id": customer_id,
                        "customer_name": customer_name,
                        "area": area,
                        "date": credit.get("date", ""),
                        "modified_date": modified_date,
                        "amount": credit_amount,
                        "credit": credit_amount,
                        "payment": "",
                        "payment_mode": "",
                        "remaining": credit.get("remaining", 0),
                    }
                )

        payment_history = _load_json_file(
            config.get("payment_history_file", "data/payment_history.json"),
            [],
        )

        if not isinstance(payment_history, list):
            payment_history = []

        for payment in payment_history:
            modified_date = payment.get("processed_timestamp") or payment.get("payment_date", "")

            rows.append(
                {
                    "customer_id": payment.get("customer_id", ""),
                    "customer_name": payment.get("customer_name", ""),
                    "area": payment.get("area", ""),
                    "date": payment.get("payment_date", ""),
                    "modified_date": modified_date,
                    "amount": "",
                    "credit": "",
                    "payment": payment.get("payment_amount", 0),
                    "payment_mode": payment.get("payment_mode", ""),
                    "remaining": payment.get("total_pending_after_payment", ""),
                }
            )

        def sort_key(row):
            modified_date = row.get("modified_date") or row.get("date") or "0000-00-00"
            if modified_date == "-":
                modified_date = "0000-00-00"
            return modified_date

        rows.sort(key=sort_key, reverse=True)
        return rows

    api_module.build_all_balance_rows = build_all_balance_rows_with_payments


def _add_credit_with_modified_route(api_module):
    if hasattr(api_module, "_add_credit_with_modified_route_added"):
        return

    Form = api_module.Form

    @api_module.app.post("/add-credit-with-modified", response_class=api_module.HTMLResponse)
    def add_credit_with_modified(
        request: api_module.Request,
        customer_id: str = Form(...),
        credit_date: str = Form(...),
        amount: int = Form(...),
    ):
        access_response = api_module.require_page_access(request, "add_payment")
        if access_response:
            return access_response

        customers = api_module.load_customers_from_config()

        if customer_id not in customers:
            context = api_module.build_add_credit_context(
                customers=customers,
                selected_customer_id=customer_id,
                errors=["Selected customer does not exist"],
            )
            return api_module.templates.TemplateResponse(request, "add_credit.html", context)

        selected_customer = customers[customer_id]
        area = selected_customer.get("area", "")
        errors = []

        try:
            api_module.datetime.strptime(credit_date, "%Y-%m-%d")
        except ValueError:
            errors.append("Credit date must be a valid date")

        if amount <= 0:
            errors.append("Credit amount must be greater than zero")

        if errors:
            context = api_module.build_add_credit_context(
                customers=customers,
                selected_area=area,
                selected_customer_id=customer_id,
                errors=errors,
            )
            return api_module.templates.TemplateResponse(request, "add_credit.html", context)

        now_text = api_module.datetime.now().isoformat(timespec="seconds")

        credit_entry = {
            "date": credit_date,
            "amount": amount,
            "remaining": amount,
            "created_at": now_text,
            "modified_date": now_text,
        }

        customers[customer_id].setdefault("credits", []).append(credit_entry)
        customers[customer_id]["credits"].sort(key=lambda credit: credit.get("date", ""))
        api_module.save_customers_to_config(customers)

        context = api_module.build_add_credit_context(
            customers=customers,
            selected_area=area,
            selected_customer_id=customer_id,
            message="Credit entry added successfully",
            errors=None,
        )
        return api_module.templates.TemplateResponse(request, "add_credit.html", context)

    api_module._add_credit_with_modified_route_added = True


def _add_process_payment_with_mode_route(api_module):
    if hasattr(api_module, "_process_payment_with_mode_route_added"):
        return

    Form = api_module.Form

    @api_module.app.post("/process-payment-with-mode", response_class=api_module.HTMLResponse)
    def process_payment_with_mode(
        request: api_module.Request,
        customer_id: str = Form(...),
        payment_date: str = Form(...),
        payment_amount: int = Form(...),
        payment_mode: str = Form(...),
        allocation_method: str = Form(...),
        target_date: str = Form(None),
    ):
        access_response = api_module.require_page_access(request, "add_payment")
        if access_response:
            return access_response

        allowed_payment_modes = ["UPI", "Cash", "Bank Transfer"]
        customers = api_module.load_customers_from_config()

        if customer_id not in customers:
            context = api_module.build_payment_page_context(
                customers=customers,
                selected_customer_id=customer_id,
                errors=["Selected customer does not exist"],
            )
            return api_module.templates.TemplateResponse(request, "add_payment.html", context)

        if payment_mode not in allowed_payment_modes:
            selected_area = customers[customer_id].get("area", "")
            context = api_module.build_payment_page_context(
                customers=customers,
                selected_customer_id=customer_id,
                selected_area=selected_area,
                errors=["Invalid payment mode"],
            )
            return api_module.templates.TemplateResponse(request, "add_payment.html", context)

        selected_customer = customers[customer_id]
        customer_name = selected_customer.get("customer_name", "")
        area = selected_customer.get("area", "")
        credits = selected_customer.get("credits", [])
        current_total_pending = api_module.calculate_total_pending(credits)

        payment = {
            "customer_name": customer_name,
            "payment_date": payment_date,
            "payment_amount": payment_amount,
            "allocation_method": allocation_method,
        }

        if allocation_method == "SPECIFIC_DATE":
            payment["target_date"] = target_date

        all_errors = api_module.validate_payment(payment) + api_module.validate_credits(credits)

        if all_errors:
            context = api_module.build_payment_page_context(
                customers=customers,
                selected_customer_id=customer_id,
                selected_area=area,
                errors=all_errors,
            )
            return api_module.templates.TemplateResponse(request, "add_payment.html", context)

        if allocation_method == "FIFO":
            allocation_result = api_module.allocate_payment_fifo(credits, payment_amount)
        elif allocation_method == "LIFO":
            allocation_result = api_module.allocate_payment_lifo(credits, payment_amount)
        elif allocation_method == "SPECIFIC_DATE":
            allocation_result = api_module.allocate_payment_to_specific_date(
                credits,
                payment_amount,
                target_date,
            )
        else:
            context = api_module.build_payment_page_context(
                customers=customers,
                selected_customer_id=customer_id,
                selected_area=area,
                errors=["Invalid allocation method"],
            )
            return api_module.templates.TemplateResponse(request, "add_payment.html", context)

        if allocation_method == "SPECIFIC_DATE" and not allocation_result.get("date_found"):
            context = api_module.build_payment_page_context(
                customers=customers,
                selected_customer_id=customer_id,
                selected_area=area,
                errors=["Selected target date is not available for this customer"],
            )
            return api_module.templates.TemplateResponse(request, "add_payment.html", context)

        updated_credits = allocation_result["updated_credits"]
        advance_payment = allocation_result["advance_payment"]
        now_text = api_module.datetime.now().isoformat(timespec="seconds")

        for credit in updated_credits:
            credit["modified_date"] = now_text

        customers[customer_id]["credits"] = updated_credits
        api_module.save_customers_to_config(customers)

        aging_result = api_module.split_balances_by_age(
            updated_credits,
            reference_date=payment_date,
        )
        total_pending = api_module.calculate_total_pending(updated_credits)

        payment_history = api_module.load_payment_history()
        payment_history.append(
            {
                "customer_id": customer_id,
                "customer_name": customer_name,
                "area": area,
                "payment_date": payment_date,
                "payment_amount": payment_amount,
                "payment_mode": payment_mode,
                "allocation_method": allocation_method,
                "target_date": target_date,
                "advance_payment": advance_payment,
                "total_pending_after_payment": total_pending,
                "processed_timestamp": now_text,
            }
        )
        api_module.save_payment_history(payment_history)

        report = {
            "status": "SUCCESS",
            "customer_id": customer_id,
            "customer_name": customer_name,
            "area": area,
            "payment_date": payment_date,
            "payment_amount": payment_amount,
            "payment_mode": payment_mode,
            "allocation_method": allocation_method,
            "target_date": target_date,
            "updated_credits": updated_credits,
            "advance_payment": advance_payment,
            "total_pending": total_pending,
            "previous_total_pending": current_total_pending,
            "aging": aging_result,
        }

        with open(api_module.config["success_output_file"], "w", encoding="utf-8") as file:
            json.dump(report, file, indent=4)

        context = api_module.build_payment_page_context(
            customers=customers,
            selected_customer_id=customer_id,
            selected_area=area,
            report=report,
        )
        return api_module.templates.TemplateResponse(request, "add_payment.html", context)

    api_module._process_payment_with_mode_route_added = True


def _schedule_runtime_patches(config):
    global _PATCH_TIMER_STARTED

    if _PATCH_TIMER_STARTED:
        return

    _PATCH_TIMER_STARTED = True

    timer = threading.Timer(0.1, _patch_all_balances_rows, args=(config,))
    timer.daemon = True
    timer.start()


def load_config(config_file_path="config/settings.json"):
    """
    Load application configuration from JSON file.
    """

    with open(config_file_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    _schedule_runtime_patches(config)

    return config
