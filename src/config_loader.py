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
