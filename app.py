import calendar
import smtplib
import uuid
from datetime import date, timedelta
from email.message import EmailMessage

import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="AGC Management System", page_icon="🏢", layout="wide")

IQAMA_MONTHLY_RATE = 1500.0
IQAMA_RENEWAL_OPTIONS = {
    "3 Months (SAR 4,500)": 3,
    "6 Months (SAR 9,000)": 6,
    "9 Months (SAR 13,500)": 9,
    "12 Months (SAR 18,000)": 12,
}


# =========================================================
# CONFIGURATION & SUPABASE CLIENT
# =========================================================
@st.cache_resource
def connect_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


supabase = connect_supabase()

MODULES = {
    "Employees": {
        "table": "employees",
        "fields": [
            ("full_name", "text", True),
            ("mobile", "text", False),
            ("iqama_number", "text", False),
            ("iqama_expiry", "date", False),
            ("job_title", "text", False),
            ("monthly_salary", "number", True),
            ("monthly_iqama_expense", "number", True),
            ("is_active", "boolean", True),
            ("notes", "text", False),
        ],
    },
    "Vehicles": {
        "table": "vehicles",
        "fields": [
            ("vehicle_name", "text", True),
            ("plate_number", "text", True),
            ("notes", "text", False),
        ],
    },
    "Drivers": {
        "table": "drivers",
        "fields": [
            ("full_name", "text", True),
            ("mobile", "text", False),
            ("notes", "text", False),
            ("is_active", "boolean", True),
        ],
    },
    "Driver Advances": {
        "table": "driver_advances",
        "fields": [
            ("driver_id", "fk:drivers", True),
            ("vehicle_id", "fk:vehicles", False),
            ("amount", "number", True),
            ("advance_date", "date", True),
            ("description", "text", False),
        ],
    },
    "Petty Cash Fund": {
        "table": "petty_cash_fund",
        "fields": [
            ("transaction_type", "select:IN,OUT", True),
            ("amount", "number", True),
            ("transaction_date", "date", True),
            ("description", "text", False),
        ],
    },
    "Petty Cash Expenses": {
        "table": "petty_cash_expenses",
        "fields": [
            ("driver_id", "fk:drivers", False),
            ("vehicle_id", "fk:vehicles", False),
            ("category", "select:Maintenance,Oil Change,Tyre Change,Fuel,Other", True),
            ("amount", "number", True),
            ("expense_date", "date", True),
            ("description", "text", False),
        ],
    },
    "Accommodations": {
        "table": "accommodations",
        "fields": [
            ("accommodation_name", "text", True),
            ("address", "text", False),
            ("monthly_rent", "number", True),
            ("payment_frequency", "select:Monthly,Quarterly,Half-Yearly,Yearly", True),
            ("next_due_date", "date", False),
            ("notes", "text", False),
            ("is_active", "boolean", True),
        ],
    },
    "Rent Payments": {
        "table": "accommodation_rent_payments",
        "fields": [
            ("accommodation_id", "fk:accommodations", True),
            ("amount_due", "number", True),
            ("amount_paid", "number", True),
            ("due_date", "date", True),
            ("payment_date", "date", False),
            ("status", "select:Unpaid,Partial,Paid", True),
            ("notes", "text", False),
        ],
    },
    "Utility Bills": {
        "table": "utility_bills",
        "fields": [
            ("accommodation_id", "fk:accommodations", False),
            ("bill_type", "text", True),
            ("amount", "number", True),
            ("bill_date", "date", False),
            ("due_date", "date", True),
            ("payment_date", "date", False),
            ("status", "select:Unpaid,Pending,Paid", True),
            ("description", "text", False),
        ],
    },
    "Office Expenses": {
        "table": "office_expenses",
        "fields": [
            ("category", "text", True),
            ("amount", "number", True),
            ("expense_date", "date", True),
            ("due_date", "date", False),
            ("payment_date", "date", False),
            ("status", "select:Unpaid,Pending,Paid", True),
            ("description", "text", False),
        ],
    },
    "Reminders": {
        "table": "reminders",
        "fields": [
            ("title", "text", True),
            ("message", "text", False),
            ("reminder_date", "date", True),
            ("related_type", "text", False),
            ("related_id", "text", False),
            ("is_completed", "boolean", True),
        ],
    },
    "Guardian Contacts": {
        "table": "guardian_contacts",
        "fields": [
            ("full_name", "text", True),
            ("email", "text", True),
            ("phone", "text", False),
            ("is_active", "boolean", True),
            ("notes", "text", False),
        ],
    },
}


# =========================================================
# HELPERS
# =========================================================
def notify_error(prefix, exc):
    st.error(f"{prefix}: {exc}")


def sar(amount):
    try:
        return f"SAR {float(amount or 0):,.2f}"
    except (TypeError, ValueError):
        return "SAR 0.00"


def as_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def add_months(source_date, months):
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def serialize_payload(payload):
    clean = {}
    for k, v in payload.items():
        if isinstance(v, date):
            clean[k] = v.isoformat()
        elif v == "":
            clean[k] = None
        else:
            clean[k] = v
    return clean


def get_data(table, limit=2000, silent=False):
    try:
        return supabase.table(table).select("*").limit(limit).execute().data or []
    except Exception as exc:
        if not silent:
            notify_error(f"Could not read {table}", exc)
        return []


def fk_options(table):
    rows = get_data(table)
    return {str(r["id"]): r for r in rows if r.get("id") is not None}


def display_label(row, fallback):
    return str(
        row.get("full_name")
        or row.get("accommodation_name")
        or row.get("vehicle_name")
        or row.get("title")
        or row.get("plate_number")
        or row.get("bill_type")
        or row.get("category")
        or fallback
    )


def _flash(message, kind="success"):
    st.session_state["agc_flash"] = (kind, message)


def show_flash():
    item = st.session_state.pop("agc_flash", None)
    if item:
        kind, message = item
        getattr(st, kind, st.success)(message)


def _stable_rows(rows):
    return sorted(rows, key=lambda r: (str(r.get("created_at") or ""), str(r.get("id") or "")))


def compute_salary_status(amount_due, amount_paid):
    due = round(float(amount_due or 0), 2)
    paid = round(float(amount_paid or 0), 2)
    if paid <= 0:
        return "Unpaid"
    if paid >= due:
        return "Paid"
    return "Partial"


def get_employee_advance_summary(employee_id, advances_rows=None):
    rows = advances_rows if advances_rows is not None else get_data("employee_advances", silent=True)
    emp_rows = [r for r in rows if str(r.get("employee_id")) == str(employee_id)]
    taken = sum(float(r.get("amount") or 0) for r in emp_rows if r.get("transaction_type") == "ADVANCE")
    deducted = sum(float(r.get("amount") or 0) for r in emp_rows if r.get("transaction_type") == "DEDUCTION")
    remaining = max(0.0, round(taken - deducted, 2))
    return round(taken, 2), round(deducted, 2), remaining


def render_field(field, kind, key, old=None, required=False):
    old = old or {}
    value = old.get(field)
    label = field.replace("_", " ").title()
    if field == "monthly_iqama_expense":
        label = "Iqama Renewal Fee / Month (Info Only — SAR 1,500)"

    if kind == "text":
        return st.text_input(label, value="" if value is None else str(value), key=key)
    if kind == "number":
        default_num = IQAMA_MONTHLY_RATE if (field == "monthly_iqama_expense" and value is None) else 0.0
        try:
            initial = float(value) if value is not None else default_num
        except (TypeError, ValueError):
            initial = default_num
        return st.number_input(label, min_value=0.0, value=initial, step=50.0, key=key)
    if kind == "date":
        parsed = as_date(value)
        if not required and parsed is None:
            use_date = st.checkbox(f"Set {label}", value=False, key=f"{key}_enable")
            if not use_date:
                return None
            return st.date_input(label, value=date.today(), key=key)
        return st.date_input(label, value=parsed or date.today(), key=key)
    if kind == "boolean":
        return st.checkbox(label, value=True if value is None else bool(value), key=key)
    if kind.startswith("select:"):
        choices = kind.split(":", 1)[1].split(",")
        index = choices.index(value) if value in choices else 0
        return st.selectbox(label, choices, index=index, key=key)
    if kind.startswith("fk:"):
        target = kind.split(":", 1)[1]
        options = fk_options(target)
        if not options:
            if required:
                st.warning(f"No records found in {target}. Add the related record first.")
            return None
        ids = list(options.keys())
        if not required:
            ids = [""] + ids
        selected = str(value) if value is not None else ""
        index = ids.index(selected) if selected in ids else 0
        chosen = st.selectbox(
            label,
            ids,
            index=index,
            format_func=lambda item: "— None —" if item == "" else display_label(options[item], item),
            key=key,
        )
        return chosen or None
    return None


# =========================================================
# NOTIFICATIONS & EMAIL
# =========================================================
def build_notifications():
    today = date.today()
    items = []

    def add_item(category, title, due, detail, amount=None, status=None, window_days=20):
        due_date = as_date(due)
        if not due_date:
            return
        if status and str(status).lower() == "paid":
            return
        days = (due_date - today).days
        if days <= window_days:
            if days > 0:
                timing = f"Due in {days} day(s)"
            elif days == 0:
                timing = "Due today"
            else:
                timing = f"Overdue by {abs(days)} day(s)"
            items.append({
                "category": category,
                "title": title,
                "due_date": due_date,
                "days": days,
                "timing": timing,
                "detail": detail,
                "amount": amount,
            })

    employees = get_data("employees")
    for r in employees:
        if r.get("is_active", True) and r.get("iqama_expiry"):
            exp = as_date(r.get("iqama_expiry"))
            if exp:
                days = (exp - today).days
                if days <= 0:
                    add_item(
                        "Iqama Renewal Required",
                        "Iqama Renewal Required — Action Needed",
                        exp,
                        f"Employee: {r.get('full_name', 'Employee')} — Renew in Additional Expenses",
                        window_days=30,
                    )
                elif days <= 30:
                    add_item(
                        "Iqama Expiry",
                        "Iqama Expiring Soon",
                        exp,
                        f"Employee: {r.get('full_name', 'Employee')}",
                        window_days=30,
                    )

    employee_map = {str(r.get("id")): r.get("full_name", "Employee") for r in employees}
    for r in get_data("salary_records"):
        emp = employee_map.get(str(r.get("employee_id")), "Employee")
        outstanding = max(0.0, float(r.get("amount_due") or 0) - float(r.get("amount_paid") or 0))
        st_label = str(r.get("status") or "Unpaid")
        if outstanding > 0 and st_label.lower() != "paid":
            cat = "Partial Salary" if st_label.lower() == "partial" else "Unpaid Salary"
            add_item(cat, f"{cat} ({r.get('salary_month', '')})", r.get("due_date"), f"Employee: {emp}", outstanding, st_label)

    accommodation_map = {
        str(r.get("id")): r.get("accommodation_name", "Accommodation")
        for r in get_data("accommodations")
    }
    for r in get_data("accommodation_rent_payments"):
        outstanding = max(0.0, float(r.get("amount_due") or 0) - float(r.get("amount_paid") or 0))
        if outstanding > 0:
            name = accommodation_map.get(str(r.get("accommodation_id")), "Accommodation")
            add_item("Rent Due", "Rent Payment Due", r.get("due_date"), name, outstanding, r.get("status"))

    for r in get_data("utility_bills"):
        if str(r.get("status", "")).lower() != "paid":
            name = accommodation_map.get(str(r.get("accommodation_id")), "Accommodation")
            add_item("Utility Bill", f"Utility Bill: {r.get('bill_type', 'Utility')}", r.get("due_date"), name, r.get("amount"), r.get("status"))

    for r in get_data("office_expenses"):
        if str(r.get("status", "")).lower() != "paid":
            add_item("Office Expense", f"Office Expense: {r.get('category', 'Expense')}", r.get("due_date"), r.get("description") or "Office expense", r.get("amount"), r.get("status"))

    for r in get_data("reminders"):
        if not r.get("is_completed"):
            add_item("Reminder", r.get("title", "Reminder"), r.get("reminder_date"), r.get("message") or "General reminder")

    return sorted(items, key=lambda x: x["due_date"])


def send_email(subject, body, recipients):
    cfg = st.secrets.get("email", {})
    required = ["smtp_host", "smtp_port", "smtp_username", "smtp_password", "from_email"]
    if not all(cfg.get(k) for k in required):
        return False, "Email SMTP settings are not configured in Streamlit Secrets."
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from_email"]
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=20) as server:
            server.starttls()
            server.login(cfg["smtp_username"], cfg["smtp_password"])
            server.send_message(msg)
        return True, "Email sent."
    except Exception as exc:
        return False, str(exc)


def notification_key(item, recipient):
    raw = f"{recipient}|{item['title']}|{item['due_date']}|{item['detail']}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


def process_email_notifications(items, guardian_rows):
    recipients = [r["email"] for r in guardian_rows if r.get("is_active", True) and r.get("email")]
    if not recipients:
        return 0, "No active guardian contacts with email addresses."
    sent_count = 0
    for item in items:
        days = item["days"]
        if days not in (20, 15, 7, 0) and days >= 0:
            continue
        body = (
            f"AGC Management System Reminder\n\n"
            f"Category: {item['category']}\n"
            f"Title: {item['title']}\n"
            f"Details: {item['detail']}\n"
            f"Due Date: {item['due_date']}\n"
            f"Status: {item['timing']}\n"
            f"Amount: {sar(item['amount']) if item['amount'] is not None else 'Not specified'}\n"
        )
        for recipient in recipients:
            key = notification_key(item, recipient)
            try:
                existing = (
                    supabase.table("notification_log")
                    .select("id")
                    .eq("event_key", key)
                    .limit(1)
                    .execute()
                    .data
                    or []
                )
                if existing:
                    continue
                ok, _ = send_email(f"AGC Reminder: {item['title']}", body, [recipient])
                if ok:
                    supabase.table("notification_log").insert({
                        "event_key": key,
                        "recipient_email": recipient,
                        "event_title": item["title"],
                        "due_date": item["due_date"].isoformat(),
                    }).execute()
                    sent_count += 1
            except Exception:
                pass
    return sent_count, f"Processed notifications. Sent {sent_count} new email(s)."


# =========================================================
# DASHBOARD PAGE
# =========================================================
def dashboard_page():
    st.title("AGC Management System — Dashboard")
    show_flash()

    employees = get_data("employees")
    vehicles = get_data("vehicles")
    drivers = get_data("drivers")
    salary_records = get_data("salary_records")
    emp_advances = get_data("employee_advances", silent=True)
    petty_fund = get_data("petty_cash_fund")
    petty_exp = get_data("petty_cash_expenses")
    accommodations = get_data("accommodations")
    rent_payments = get_data("accommodation_rent_payments")
    utility_bills = get_data("utility_bills")
    office_expenses = get_data("office_expenses")
    iqama_renewals = get_data("iqama_renewals", silent=True)
    reminders = get_data("reminders")

    total_employees = len(employees)
    active_employees = sum(1 for e in employees if e.get("is_active", True))
    total_vehicles = len(vehicles)
    total_drivers = len(drivers)

    # Monthly Salary strictly excludes Iqama Renewal Fees
    monthly_salary_total = sum(
        float(e.get("monthly_salary") or 0) for e in employees if e.get("is_active", True)
    )
    salary_outstanding = sum(
        max(0.0, float(r.get("amount_due") or 0) - float(r.get("amount_paid") or 0))
        for r in salary_records
        if str(r.get("status", "")).lower() != "paid"
    )

    adv_taken = sum(float(r.get("amount") or 0) for r in emp_advances if r.get("transaction_type") == "ADVANCE")
    adv_deducted = sum(float(r.get("amount") or 0) for r in emp_advances if r.get("transaction_type") == "DEDUCTION")
    employee_advances_balance = max(0.0, adv_taken - adv_deducted)

    petty_in = sum(float(r.get("amount") or 0) for r in petty_fund if str(r.get("transaction_type")).upper() == "IN")
    petty_out = sum(float(r.get("amount") or 0) for r in petty_fund if str(r.get("transaction_type")).upper() == "OUT")
    petty_expenses_total = sum(float(r.get("amount") or 0) for r in petty_exp)
    petty_cash_balance = petty_in - petty_out - petty_expenses_total

    accommodation_expenses = sum(float(r.get("amount_paid") or 0) for r in rent_payments)
    outstanding_rent = sum(
        max(0.0, float(r.get("amount_due") or 0) - float(r.get("amount_paid") or 0))
        for r in rent_payments
        if str(r.get("status", "")).lower() != "paid"
    )
    utility_bills_total = sum(float(r.get("amount") or 0) for r in utility_bills)
    office_expenses_total = sum(float(r.get("amount") or 0) for r in office_expenses)

    # Additional Expenses (Iqama Renewal Fees — strictly separate from Salary)
    additional_expenses_total = sum(float(r.get("required_amount") or 0) for r in iqama_renewals)
    iqama_renewal_outstanding = sum(
        max(0.0, float(r.get("required_amount") or 0) - float(r.get("amount_paid") or 0))
