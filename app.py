import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from supabase import create_client

st.set_page_config(page_title="AGC Management System", page_icon="🏢", layout="wide")

# -------------------------------------------------------------------
# Supabase connection
# .streamlit/secrets.toml:
# SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
# SUPABASE_KEY = "YOUR_SERVER_SIDE_KEY"
# -------------------------------------------------------------------
@st.cache_resource
def connect_supabase():
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Add SUPABASE_URL and SUPABASE_KEY to .streamlit/secrets.toml")
    return create_client(url, key)

try:
    supabase = connect_supabase()
except Exception as exc:
    st.error(f"Supabase connection error: {exc}")
    st.stop()

# field tuple: database column, widget type, required
MODULES = {
    "Employees": {"table": "employees", "fields": [
        ("full_name", "text", True), ("mobile", "text", False),
        ("iqama_number", "text", False), ("iqama_expiry", "optional_date", False),
        ("job_title", "text", False), ("monthly_salary", "number", True),
        ("monthly_iqama_expense", "number", True), ("is_active", "boolean", True),
        ("notes", "textarea", False)]},
    "Salary Records": {"table": "salary_records", "fields": [
        ("employee_id", "fk:employees", True), ("salary_month", "date", True),
        ("amount_due", "number", True), ("amount_paid", "number", True),
        ("due_date", "date", True), ("payment_date", "optional_date", False),
        ("status", "select:Unpaid,Partial,Paid", True), ("notes", "textarea", False)]},
    "Vehicles": {"table": "vehicles", "fields": [
        ("vehicle_name", "text", True), ("plate_number", "text", True),
        ("notes", "textarea", False)]},
    "Drivers": {"table": "drivers", "fields": [
        ("full_name", "text", True), ("mobile", "text", False),
        ("notes", "textarea", False), ("is_active", "boolean", True)]},
    "Driver Advances": {"table": "driver_advances", "fields": [
        ("driver_id", "fk:drivers", True), ("vehicle_id", "fk:vehicles", False),
        ("amount", "number", True), ("advance_date", "date", True),
        ("description", "textarea", False)]},
    "Petty Cash Fund": {"table": "petty_cash_fund", "fields": [
        ("transaction_type", "select:IN,OUT", True), ("amount", "number", True),
        ("transaction_date", "date", True), ("description", "textarea", False)]},
    "Petty Cash Expenses": {"table": "petty_cash_expenses", "fields": [
        ("driver_id", "fk:drivers", False), ("vehicle_id", "fk:vehicles", False),
        ("category", "select:Maintenance,Oil Change,Tyre Change,Fuel,Other", True),
        ("amount", "number", True), ("expense_date", "date", True),
        ("description", "textarea", False)]},
    "Accommodations": {"table": "accommodations", "fields": [
        ("accommodation_name", "text", True), ("address", "text", False),
        ("monthly_rent", "number", True),
        ("payment_frequency", "select:Monthly,Quarterly,Half-Yearly,Yearly", True),
        ("next_due_date", "optional_date", False), ("notes", "textarea", False),
        ("is_active", "boolean", True)]},
    "Rent Payments": {"table": "accommodation_rent_payments", "fields": [
        ("accommodation_id", "fk:accommodations", True), ("amount_due", "number", True),
        ("amount_paid", "number", True), ("due_date", "date", True),
        ("payment_date", "optional_date", False),
        ("status", "select:Unpaid,Partial,Paid", True), ("notes", "textarea", False)]},
    "Utility Bills": {"table": "utility_bills", "fields": [
        ("accommodation_id", "fk:accommodations", False), ("bill_type", "text", True),
        ("amount", "number", True), ("bill_date", "optional_date", False),
        ("due_date", "date", True), ("payment_date", "optional_date", False),
        ("status", "select:Unpaid,Pending,Paid", True), ("description", "textarea", False)]},
    "Office Expenses": {"table": "office_expenses", "fields": [
        ("category", "text", True), ("amount", "number", True),
        ("expense_date", "date", True), ("due_date", "optional_date", False),
        ("payment_date", "optional_date", False),
        ("status", "select:Unpaid,Pending,Paid", True), ("description", "textarea", False)]},
    "Reminders": {"table": "reminders", "fields": [
        ("title", "text", True), ("message", "textarea", False),
        ("reminder_date", "date", True), ("related_type", "text", False),
        ("related_id", "text", False), ("is_completed", "boolean", True)]},
}

def flash(message, kind="success"):
    st.session_state["agc_flash"] = (kind, message)

def show_flash():
    item = st.session_state.pop("agc_flash", None)
    if item:
        kind, message = item
        getattr(st, kind, st.success)(message)

def read_rows(table, limit=5000):
    try:
        response = supabase.table(table).select("*").limit(limit).execute()
        return response.data or []
    except Exception as exc:
        st.error(f"Could not read {table}: {exc}")
        return []

def as_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None

def money(value):
    try:
        return f"SAR {float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "SAR 0.00"

def display_label(row, fallback="Record"):
    return str(row.get("full_name") or row.get("accommodation_name") or
                row.get("vehicle_name") or row.get("title") or
                row.get("plate_number") or fallback)

def fk_map(table):
    rows = read_rows(table)
    return {str(r["id"]): r for r in rows if r.get("id")}

def field_label(field):
    return field.replace("_", " ").title()

def render_field(field, kind, key, old=None):
    old = old or {}
    value = old.get(field)
    label = field_label(field)

    if kind == "text":
        return st.text_input(label, value="" if value is None else str(value), key=key)
    if kind == "textarea":
        return st.text_area(label, value="" if value is None else str(value), key=key)
    if kind == "number":
        try:
            initial = float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            initial = 0.0
        return st.number_input(label, min_value=0.0, value=initial, step=1.0, format="%.2f", key=key)
    if kind == "date":
        initial = as_date(value) or date.today()
        return st.date_input(label, value=initial, key=key)
    if kind == "optional_date":
        current = as_date(value)
        enabled = st.checkbox(f"Set {label.lower()}", value=current is not None, key=f"{key}_enabled")
        if not enabled:
            return None
        return st.date_input(label, value=current or date.today(), key=key)
    if kind == "boolean":
        return st.checkbox(label, value=True if value is None else bool(value), key=key)
    if kind.startswith("select:"):
        choices = kind.split(":", 1)[1].split(",")
        selected = str(value) if value is not None else choices[0]
        index = choices.index(selected) if selected in choices else 0
        return st.selectbox(label, choices, index=index, key=key)
    if kind.startswith("fk:"):
        target = kind.split(":", 1)[1]
        options = fk_map(target)
        if not options:
            st.warning(f"No records found in {target}. Add the related record first.")
            return None
        ids = list(options)
        optional = not any(x[0] == field and x[2] for x in [])
        choices = ([""] + ids) if field in ("vehicle_id", "driver_id", "accommodation_id") else ids
        old_id = str(value) if value else ""
        index = choices.index(old_id) if old_id in choices else 0
        selected = st.selectbox(
            label, choices, index=index,
            format_func=lambda item: "— None —" if item == "" else display_label(options[item], item),
            key=key
        )
        return selected or None
    return None

def serialize_values(values):
    result = {}
    for key, value in values.items():
        if isinstance(value, (date, datetime)):
            result[key] = value.isoformat()
        elif value == "":
            result[key] = None
        else:
            result[key] = value
    return result

def validate_values(fields, values):
    missing = [field_label(f) for f, _, required in fields
               if required and (values.get(f) is None or values.get(f) == "")]
    if missing:
        return "Please complete required fields: " + ", ".join(missing)
    if "amount_due" in values and "amount_paid" in values:
        if float(values["amount_paid"] or 0) > float(values["amount_due"] or 0):
            return "Amount paid cannot be greater than amount due."
    return None

def module_page(name, config):
    table = config["table"]
    st.title(name)
    add_tab, records_tab = st.tabs(["➕ Add New", "📋 Records"])

    with add_tab:
        with st.form(f"add_form_{table}"):
            values = {}
            for field, kind, required in config["fields"]:
                values[field] = render_field(field, kind, f"add_{table}_{field}")
            submitted = st.form_submit_button("Save Record", type="primary", use_container_width=True)
        if submitted:
            error = validate_values(config["fields"], values)
            if error:
                st.error(error)
            else:
                try:
                    supabase.table(table).insert(serialize_values(values)).execute()
                    flash(f"{name} record saved.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Save failed: {exc}")

    show_flash()
    with records_tab:
        rows = read_rows(table)
        if not rows:
            st.info("No records found.")
            return

        df = pd.DataFrame(rows)
        if "created_at" in df:
            df = df.sort_values("created_at", ascending=False, na_position="last")
        st.caption(f"{len(df)} record(s)")
        search = st.text_input("Search records", key=f"search_{table}")
        if search:
            mask = df.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
            df = df[mask]
        display_df = df.drop(columns=[c for c in ("id", "created_at") if c in df.columns], errors="ignore")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        id_to_row = {str(r["id"]): r for r in rows}
        selected_id = st.selectbox(
            "Select a record for actions",
            options=[""] + list(id_to_row),
            format_func=lambda rid: "Choose a record..." if not rid else
                f"{display_label(id_to_row[rid], 'Record')} · {rid[:8]}",
            key=f"action_select_{table}"
        )
        if not selected_id:
            return

        row = id_to_row[selected_id]
        view_col, edit_col, delete_col = st.columns(3)
        with view_col:
            if st.button("View details", key=f"view_{table}_{selected_id}", use_container_width=True):
                st.session_state[f"show_view_{table}"] = selected_id
        with edit_col:
            if st.button("Edit record", key=f"edit_{table}_{selected_id}", use_container_width=True):
                st.session_state[f"show_edit_{table}"] = selected_id
        with delete_col:
            if st.button("Delete record", key=f"delete_{table}_{selected_id}", use_container_width=True):
                st.session_state[f"show_delete_{table}"] = selected_id

        if st.session_state.get(f"show_view_{table}") == selected_id:
            with st.expander("Record details", expanded=True):
                st.json({k: v for k, v in row.items() if k != "id"})

        if st.session_state.get(f"show_edit_{table}") == selected_id:
            st.subheader("Edit selected record")
            with st.form(f"edit_form_{table}_{selected_id}"):
                updated = {}
                for field, kind, required in config["fields"]:
                    updated[field] = render_field(
                        field, kind, f"edit_{table}_{selected_id}_{field}", row
                    )
                save = st.form_submit_button("Save Changes", type="primary")
            if save:
                error = validate_values(config["fields"], updated)
                if error:
                    st.error(error)
                else:
                    try:
                        supabase.table(table).update(serialize_values(updated)).eq("id", selected_id).execute()
                        st.session_state.pop(f"show_edit_{table}", None)
                        flash(f"{name} record updated.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Update failed: {exc}")

        if st.session_state.get(f"show_delete_{table}") == selected_id:
            st.warning("This permanently deletes the selected record. Related records may prevent deletion.")
            confirm = st.checkbox("I understand and confirm permanent deletion", key=f"confirm_{table}_{selected_id}")
            if st.button("Confirm Delete", type="primary", key=f"confirm_delete_{table}_{selected_id}"):
                if not confirm:
                    st.warning("Please tick the confirmation box.")
                else:
                    try:
                        supabase.table(table).delete().eq("id", selected_id).execute()
                        st.session_state.pop(f"show_delete_{table}", None)
                        flash(f"{name} record deleted.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Delete failed: {exc}. Check whether other records reference this record.")

def build_notifications():
    today = date.today()
    notices = []

    def add(title, due_value, detail, status=None):
        due = as_date(due_value)
        if not due or (status and str(status).lower() == "paid"):
            return
        days = (due - today).days
        if days < 0:
            label = f"OVERDUE by {abs(days)} day(s)"
            priority = 0
        elif days == 0:
            label, priority = "Due today", 1
        elif days <= 7:
            label, priority = f"Due in {days} day(s)", 2
        else:
            return
        notices.append({"Priority": priority, "Item": title, "Due date": due.isoformat(),
                        "Status": label, "Details": detail})

    for r in read_rows("salary_records"):
        add("Salary payment", r.get("due_date"),
            f"Employee ID: {str(r.get('employee_id', ''))[:8]} · {money(r.get('amount_due'))}",
            r.get("status"))
    for r in read_rows("accommodation_rent_payments"):
        add("Accommodation rent", r.get("due_date"),
            f"Accommodation ID: {str(r.get('accommodation_id', ''))[:8]} · {money(r.get('amount_due'))}",
            r.get("status"))
    for r in read_rows("utility_bills"):
        add(r.get("bill_type") or "Utility bill", r.get("due_date"),
            money(r.get("amount")), r.get("status"))
    for r in read_rows("office_expenses"):
        if str(r.get("status", "")).lower() != "paid":
            add(r.get("category") or "Office expense", r.get("due_date"),
                money(r.get("amount")), r.get("status"))
    for r in read_rows("reminders"):
        if not r.get("is_completed"):
            add(r.get("title") or "Reminder", r.get("reminder_date"),
                r.get("message") or "General reminder")
    return sorted(notices, key=lambda x: (x["Priority"], x["Due date"]))

def dashboard():
    st.title("🏢 AGC Management Dashboard")
    today = date.today()
    employee = read_rows("employees")
    drivers = read_rows("drivers")
    salary = read_rows("salary_records")
    rent = read_rows("accommodation_rent_payments")
    utilities = read_rows("utility_bills")
    office = read_rows("office_expenses")
    advances = read_rows("driver_advances")
    petty = read_rows("petty_cash_expenses")
    fund = read_rows("petty_cash_fund")

    def total(rows, field, condition=None):
        return sum(float(r.get(field) or 0) for r in rows if condition is None or condition(r))

    outstanding_salary = total(salary, "amount_due") - total(salary, "amount_paid")
    outstanding_rent = total(rent, "amount_due") - total(rent, "amount_paid")
    unpaid_utilities = total(utilities, "amount") - total(utilities, "amount") if False else total(
        utilities, "amount", lambda r: str(r.get("status", "")).lower() != "paid")
    unpaid_office = total(office, "amount", lambda r: str(r.get("status", "")).lower() != "paid")
    cash_in = total(fund, "amount", lambda r: str(r.get("transaction_type", "")).upper() == "IN")
    cash_out = total(fund, "amount", lambda r: str(r.get("transaction_type", "")).upper() == "OUT")
    cash_balance = cash_in - cash_out

    metrics = [
        ("Active employees", sum(bool(r.get("is_active")) for r in employee)),
        ("Active drivers", sum(bool(r.get("is_active")) for r in drivers)),
        ("Salary outstanding", money(outstanding_salary)),
        ("Rent outstanding", money(outstanding_rent)),
        ("Unpaid utilities", money(unpaid_utilities)),
        ("Unpaid office expenses", money(unpaid_office)),
        ("Driver advances", money(total(advances, "amount"))),
        ("Petty cash balance", money(cash_balance)),
    ]
    cols = st.columns(4)
    for i, (label, value) in enumerate(metrics):
        cols[i % 4].metric(label, value)

    st.subheader("Payment overview")
    overview = pd.DataFrame([
        {"Category": "Salaries", "Outstanding (SAR)": max(0, outstanding_salary)},
        {"Category": "Rent", "Outstanding (SAR)": max(0, outstanding_rent)},
        {"Category": "Utilities", "Outstanding (SAR)": unpaid_utilities},
        {"Category": "Office expenses", "Outstanding (SAR)": unpaid_office},
    ])
    st.bar_chart(overview.set_index("Category"))

    st.subheader("Upcoming and overdue items")
    notices = build_notifications()
    if notices:
        st.dataframe(pd.DataFrame(notices).drop(columns=["Priority"]), use_container_width=True, hide_index=True)
    else:
        st.success("No payments or reminders are due within the next 7 days.")

    st.caption(f"Dashboard date: {today.isoformat()} · Amounts are shown in SAR.")

# -------------------------------------------------------------------
# Navigation
# -------------------------------------------------------------------
st.sidebar.title("AGC Management")
page = st.sidebar.radio("Navigation", ["Dashboard", "Notifications"] + list(MODULES.keys()))
if page == "Dashboard":
    dashboard()
elif page == "Notifications":
    st.title("🔔 Notifications")
    notices = build_notifications()
    if notices:
        st.dataframe(pd.DataFrame(notices).drop(columns=["Priority"]), use_container_width=True, hide_index=True)
    else:
        st.success("No upcoming or overdue items.")
else:
    module_page(page, MODULES[page])
