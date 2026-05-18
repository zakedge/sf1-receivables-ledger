# sf1-receivables-ledger

A Python-based modernization project that converts a manual Excel-style fruit business receivables ledger into a structured payment allocation and aging system.

This is Project 1 under the Strangler Fig modernization portfolio.

---

## Business Problem

A fruit business tracks daily customer credit, payments, and pending balances manually in Excel.

The business needs a system that can:

- Track customer balances by transaction date
- Show the last 7 days of pending balances
- Move anything older than 7 days into Old Balance
- Show Old Balance breakdown on demand
- Adjust customer payments against old balances by default
- Allow payment adjustment against latest or selected transaction date
- Track advance payment when customer pays more than pending balance
- Generate structured output reports

---

## Modernization Approach

This project follows the Strangler Fig pattern.

Instead of replacing the existing Excel process immediately, the system modernizes one piece at a time:

1. Start with sample JSON input
2. Build payment allocation logic
3. Add balance aging logic
4. Add input validation
5. Generate structured JSON reports
6. Later connect to Excel
7. Later move to API, database, dashboard, and cloud deployment

---

## Current Features

- Read customer credit balances from JSON
- Read customer payment details from JSON
- Validate payment and credit input
- Allocate payments using:
  - FIFO: oldest balance first
  - LIFO: latest balance first
  - SPECIFIC_DATE: selected transaction date
- Track advance payment
- Split balances into:
  - Last 7 days
  - Old Balance
  - Old Balance Breakdown
- Generate success report
- Generate validation error report
- Unit tests using pytest

---

## Project Structure

```text
strangler-fig-project-1-receivables-ledger/
│
├── data/
│   ├── sample_credits.json
│   └── sample_payment.json
│
├── output/
│   ├── customer_balance_report.json
│   └── error_report.json
│
├── src/
│   ├── aging.py
│   ├── main.py
│   ├── payment_allocator.py
│   └── validator.py
│
├── tests/
│   ├── test_aging.py
│   ├── test_payment_allocator.py
│   └── test_validator.py
│
├── README.md
├── requirements.txt
└── .gitignore