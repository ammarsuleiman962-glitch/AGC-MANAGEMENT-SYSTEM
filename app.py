import streamlit as st
import pandas as pd
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from calendar import monthrange
from supabase import create_client

# ============================================================
# AGC MANAGEMENT SYSTEM
# Existing Streamlit + Supabase application upgrade
# ============================================================

st.set_page_config(
    page_title="AGC Management System",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

IQAMA_RATE = Decimal("1500.00")
RENEWAL_PERIODS = [3, 6, 9, 12]


# ============================================================
# SUPABASE CONNECTION
# ============================================================

@st.cache_resource
def connect_supabase():
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY are required in Streamlit Secrets."
        )

    return create_client(url, key)


try:
    supabase = connect_supabase()
except Exception as exc:
    st.error(f"Supabase connection error: {exc}")
    st.stop()


# ============================================================
# DATABASE HELPERS
# ============================================================

def read_rows(table, limit=5000):
    try:
        response = (
            supabase.table(table)
            .select("*")
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception as exc:
        st.error(f"Unable to read {table}: {exc}")
        return []


def insert_row(table, values):
    return supabase.table(table).insert(values).execute()


def update_row(table, record_id, values):
    return (
        supabase.table(table)
        .update(values)
        .eq("id", record_id)
        .execute()
    )


def delete_row(table, record_id):
    return (
        supabase.table(table)
        .delete()
        .eq("id", record_id)
        .execute()
    )


def decimal(value):
    try:
        return Decimal(str(value if value is not None else 0))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def money(value):
    return f"SAR {decimal(value):,.2f}"


def parse_date(value):
    if not value:
        return None

    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def clean_values(values):
    result = {}

    for key, value in values.items():
        if isinstance(value, (date, datetime)):
            result[key] = value.isoformat()
        elif value == "":
            result[key] = None
        else:
            result[key] = value

    return result


def status_for(amount_due, amount_paid):
    due = decimal(amount_due)
    paid = decimal(amount_paid)

    if paid <= 0:
        return "Unpaid"

    if paid >= due:
        return "Paid"

    return "Partial"


def add_months(original_date, months):
    month_index = original_date.month - 1 + months
    year = original_date.year + month_index // 12
    month = month_index % 12 + 1

    day = min(
        original_date.day,
        monthrange(year, month)[1]
    )

    return date(year, month, day)


def month_start(value):
    return value.replace(day=1)


def show_flash():
    item = st.session_state.pop("agc_flash", None)

    if item:
        kind, message = item
        getattr(st, kind, st.success)(message)


def flash(message, kind="success"):
    st.session_state["agc_flash"] = (kind, message)


def record_label(row):
    return str(
        row.get("full_name")
        or row.get("accommodation_name")
        or row.get("vehicle_name")
        or row.get("title")
        or row.get("plate_number")
        or row.get("name")
        or str(row.get("id", ""))[:8]
    )


def foreign_options(table):
    rows = read_rows(table)
    return {
        str(row["id"]): row
        for row in rows
        if row.get("id")
    }


def employee_name(employee_id, employees):
    for employee in employees:
        if str(employee["id"]) == str(employee_id):
            return record_label(employee)

    return "Unknown employee"


# ============================================================
# DATABASE MODULE DEFINITIONS
# ============================================================

MODULES = {
    "Employees": {
        "table": "employees",
        "fields": [
            ("full_name", "text", True),
            ("mobile", "text", False),
            ("iqama_number", "text", False),
            ("iqama_expiry", "optional_date", False),
            ("job_title", "text", False),
            ("monthly_salary", "money", True),
            ("monthly_iqama_expense", "money", True),
            ("is_active", "boolean", True),
            ("notes", "textarea", False),
        ],
    },

    "Vehicles": {
        "table": "vehicles",
        "fields": [
            ("vehicle_name", "text", True),
            ("plate_number", "text", True),
            ("notes", "textarea", False),
            ("is_active", "boolean", True),
        ],
    },

    "Drivers": {
        "table": "drivers",
        "fields": [
            ("full_name", "text", True),
            ("mobile", "text", False),
            ("notes", "textarea", False),
            ("is_active", "boolean", True),
        ],
    },

    "Driver Advances": {
        "table": "driver_advances",
        "fields": [
            ("driver_id", "fk:drivers", True),
            ("vehicle_id", "fk:vehicles", False),
            ("amount", "money", True),
            ("advance_date", "date", True),
            ("description", "textarea", False),
        ],
    },

    "Petty Cash Fund": {
        "table": "petty_cash_fund",
        "fields": [
            ("transaction_type", "select:IN,OUT", True),
            ("amount", "money", True),
            ("transaction_date", "date", True),
            ("description", "textarea", False),
        ],
    },

    "Petty Cash Expenses": {
        "table": "petty_cash_expenses",
        "fields": [
            ("driver_id", "fk:drivers", False),
            ("vehicle_id", "fk:vehicles", False),
            (
                "category",
                "select:Maintenance,Oil Change,Tyre Change,Fuel,Other",
                True
            ),
            ("amount", "money", True),
            ("expense_date", "date", True),
            ("description", "textarea", False),
        ],
    },

    "Accommodations": {
        "table": "accommodations",
        "fields": [
            ("accommodation_name", "text", True),
            ("address", "text", False),
            ("monthly_rent", "money", True),
            (
                "payment_frequency",
                "select:Monthly,Quarterly,Half-Yearly,Yearly",
                True
            ),
            ("next_due_date", "optional_date", False),
            ("notes", "textarea", False),
            ("is_active", "boolean", True),
        ],
    },

    "Rent Payments": {
        "table": "accommodation_rent_payments",
        "fields": [
            ("accommodation_id", "fk:accommodations", True),
            ("amount_due", "money", True),
            ("amount_paid", "money", True),
            ("due_date", "date", True),
            ("payment_date", "optional_date", False),
            ("status", "select:Unpaid,Partial,Paid", True),
            ("notes", "textarea", False),
        ],
    },

    "Utility Bills": {
        "table": "utility_bills",
        "fields": [
            ("accommodation_id", "fk:accommodations", False),
            ("bill_type", "text", True),
            ("amount", "money", True),
            ("bill_date", "optional_date", False),
            ("due_date", "date", True),
            ("payment_date", "optional_date", False),
            ("status", "select:Unpaid,Pending,Paid", True),
            ("description", "textarea", False),
        ],
    },

    "Office Expenses": {
        "table": "office_expenses",
        "fields": [
            ("category", "text", True),
            ("amount", "money", True),
            ("expense_date", "date", True),
            ("due_date", "optional_date", False),
            ("payment_date", "optional_date", False),
            ("status", "select:Unpaid,Pending,Paid", True),
            ("description", "textarea", False),
        ],
    },

    "Reminders": {
        "table": "reminders",
        "fields": [
            ("title", "text", True),
            ("message", "textarea", False),
            ("reminder_date", "date", True),
            ("related_type", "text", False),
            ("related_id", "text", False),
            ("is_completed", "boolean", True),
        ],
    },

    "Guardian Contacts": {
        "table": "guardian_contacts",
        "fields": [
            ("name", "text", True),
            ("email", "text", True),
            ("is_active", "boolean", True),
        ],
    },
}


# ============================================================
# FORM RENDERING
# ============================================================

def render_field(field, kind, key, old=None):
    old = old or {}
    value = old.get(field)
    label = field.replace("_", " ").title()

    if kind == "text":
        return st.text_input(
            label,
            value=str(value or ""),
            key=key
        )

    if kind == "textarea":
        return st.text_area(
            label,
            value=str(value or ""),
            key=key
        )

    if kind == "money":
        return st.number_input(
            label,
            min_value=0.0,
            value=float(decimal(value)),
            step=100.0,
            format="%.2f",
            key=key
        )

    if kind == "date":
        return st.date_input(
            label,
            value=parse_date(value) or date.today(),
            key=key
        )

    if kind == "optional_date":
        current = parse_date(value)

        enabled = st.checkbox(
            f"Set {label}",
            value=current is not None,
            key=f"{key}_enabled"
        )

        if not enabled:
            return None

        return st.date_input(
            label,
            value=current or date.today(),
            key=key
        )

    if kind == "boolean":
        return st.checkbox(
            label,
            value=True if value is None else bool(value),
            key=key
        )

    if kind.startswith("select:"):
        choices = kind.split(":", 1)[1].split(",")

        selected = str(value) if value is not None else choices[0]

        return st.selectbox(
            label,
            choices,
            index=choices.index(selected) if selected in choices else 0,
            key=key
        )

    if kind.startswith("fk:"):
        target = kind.split(":", 1)[1]
        options = foreign_options(target)

        optional = field in (
            "vehicle_id",
            "driver_id",
            "accommodation_id"
        )

        if not options:
            st.warning(f"Add a record to {target} first.")
            return None

        choices = ([""] if optional else []) + list(options)

        old_id = str(value) if value else ""

        selected = st.selectbox(
            label,
            choices,
            index=choices.index(old_id) if old_id in choices else 0,
            format_func=lambda x:
                "— None —" if not x else record_label(options[x]),
            key=key
        )

        return selected or None

    return None


def validate_form(fields, values):
    missing = [
        field.replace("_", " ").title()
        for field, _, required in fields
        if required and (
            values.get(field) is None
            or values.get(field) == ""
        )
    ]

    if missing:
        return "Complete required fields: " + ", ".join(missing)

    if "amount_due" in values and "amount_paid" in values:
        if decimal(values["amount_paid"]) > decimal(values["amount_due"]):
            return "Amount paid cannot exceed amount due."

    return None


# ============================================================
# GENERIC CRUD MODULE
# ============================================================

def generic_module(name, config):
    table = config["table"]
    fields = config["fields"]

    st.title(name)

    add_tab, records_tab = st.tabs([
        "➕ Add New",
        "📋 Records"
    ])

    with add_tab:
        with st.form(f"add_{table}"):

            values = {}

            for field, kind, required in fields:
                values[field] = render_field(
                    field,
                    kind,
                    f"add_{table}_{field}"
                )

            submitted = st.form_submit_button(
                "Save Record",
                type="primary",
                use_container_width=True
            )

        if submitted:
            error = validate_form(fields, values)

            if error:
                st.error(error)
            else:
                try:
                    insert_row(table, clean_values(values))
                    flash(f"{name} record saved.")
                    st.rerun()

                except Exception as exc:
                    st.error(f"Save failed: {exc}")

    with records_tab:
        rows = read_rows(table)

        if not rows:
            st.info("No records found.")
            return

        df = pd.DataFrame(rows)

        search = st.text_input(
            "Search records",
            key=f"search_{table}"
        )

        if search:
            mask = df.astype(str).apply(
                lambda column: column.str.contains(
                    search,
                    case=False,
                    na=False
                )
            ).any(axis=1)

            df = df[mask]

        display_df = df.drop(
            columns=["id", "created_at"],
            errors="ignore"
        ).copy()

        display_df.insert(
            0,
            "No.",
            range(1, len(display_df) + 1)
        )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        id_map = {
            str(row["id"]): row
            for row in rows
        }

        selected = st.selectbox(
            "Select record",
            [""] + list(id_map),
            format_func=lambda x:
                "Choose record..." if not x
                else record_label(id_map[x]),
            key=f"select_{table}"
        )

        if not selected:
            return

        row = id_map[selected]

        c1, c2, c3 = st.columns(3)

        if c1.button("View", key=f"view_{table}"):
            st.session_state[f"view_{table}"] = selected

        if c2.button("Edit", key=f"edit_{table}"):
            st.session_state[f"edit_{table}"] = selected

        if c3.button("Delete", key=f"delete_{table}"):
            st.session_state[f"delete_{table}"] = selected

        if st.session_state.get(f"view_{table}") == selected:
            with st.expander("Record details", expanded=True):
                st.json({
                    k: v for k, v in row.items()
                    if k != "id"
                })

        if st.session_state.get(f"edit_{table}") == selected:

            st.subheader("Edit record")

            with st.form(f"editform_{table}_{selected}"):

                updated = {}

                for field, kind, required in fields:
                    updated[field] = render_field(
                        field,
                        kind,
                        f"edit_{table}_{selected}_{field}",
                        row
                    )

                save = st.form_submit_button(
                    "Save Changes",
                    type="primary"
                )

            if save:
                error = validate_form(fields, updated)

                if error:
                    st.error(error)
                else:
                    try:
                        update_row(
                            table,
                            selected,
                            clean_values(updated)
                        )

                        st.session_state.pop(f"edit_{table}", None)

                        flash("Record updated.")
                        st.rerun()

                    except Exception as exc:
                        st.error(f"Update failed: {exc}")

        if st.session_state.get(f"delete_{table}") == selected:

            st.warning(
                "Permanent deletion may be prevented by existing "
                "foreign-key relationships."
            )

            confirm = st.checkbox(
                "Confirm permanent deletion",
                key=f"confirm_{table}_{selected}"
            )

            if st.button(
                "Confirm Delete",
                key=f"confirmdelete_{table}_{selected}"
            ):

                if not confirm:
                    st.warning("Please confirm deletion.")
                else:
                    try:
                        delete_row(table, selected)

                        st.session_state.pop(
                            f"delete_{table}",
                            None
                        )

                        flash("Record deleted.")
                        st.rerun()

                    except Exception as exc:
                        st.error(
                            f"Delete failed: {exc}"
                        )


# ============================================================
# EMPLOYEE ADVANCE BALANCE
# ============================================================

def employee_advance_balance(employee_id):
    transactions = [
        row for row in read_rows("employee_advances")
        if str(row.get("employee_id")) == str(employee_id)
    ]

    balance = Decimal("0")

    for row in transactions:
        transaction_type = str(
            row.get("transaction_type", "")
        ).lower()

        amount = decimal(row.get("amount"))

        if transaction_type in (
            "advance", "given", "issued", "credit"
        ):
            balance += amount

        elif transaction_type in (
            "deduction", "repayment", "repaid", "debit"
        ):
            balance -= amount

    return max(Decimal("0"), balance)


# ============================================================
# MONTHLY SALARY GENERATION
# ============================================================

def generate_salary_records(target_month):
    employees = [
        e for e in read_rows("employees")
        if e.get("is_active")
    ]

    records = read_rows("salary_records")

    created = 0
    errors = []

    target_month = month_start(target_month)

    for employee in employees:

        duplicate = any(
            str(row.get("employee_id")) == str(employee["id"])
            and str(row.get("salary_month", ""))[:7]
            == target_month.strftime("%Y-%m")
            for row in records
        )

        if duplicate:
            continue

        due_date = target_month.replace(
            day=monthrange(
                target_month.year,
                target_month.month
            )[1]
        )

        try:
            insert_row(
                "salary_records",
                {
                    "employee_id": employee["id"],
                    "salary_month": target_month.isoformat(),
                    "amount_due": float(
                        decimal(employee.get("monthly_salary"))
                    ),
                    "amount_paid": 0,
                    "due_date": due_date.isoformat(),
                    "status": "Unpaid",
                    "notes": "Automatically generated salary"
                }
            )

            created += 1

        except Exception as exc:
            errors.append(
                f"{record_l
