import streamlit as st
import pandas as pd
import smtplib
import uuid
from email.message import EmailMessage
from datetime import date, datetime, timedelta
from supabase import create_client

st.set_page_config(page_title="AGC Management System", page_icon="🏢", layout="wide")

# =========================================================
# CONFIGURATION
# =========================================================
@st.cache_resource
def connect_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = connect_supabase()

MODULES = {
    "Employees": {"table": "employees", "fields": [
        ("full_name", "text", True), ("mobile", "text", False),
        ("iqama_number", "text", False), ("iqama_expiry", "date", False),
        ("job_title", "text", False), ("monthly_salary", "number", True),
        ("monthly_iqama_expense", "number", True), ("is_active", "boolean", True),
        ("notes", "text", False)]},
    "Salary Records": {"table": "salary_records", "fields": [
        ("employee_id", "fk:employees", True), ("salary_month", "date", True),
        ("amount_due", "number", True), ("amount_paid", "number", True),
        ("due_date", "date", True), ("payment_date", "date", False),
        ("status", "select:Unpaid,Partial,Paid", True), ("notes", "text", False)]},
    "Vehicles": {"table": "vehicles", "fields": [
        ("vehicle_name", "text", True), ("plate_number", "text", True),
        ("notes", "text", False)]},
    "Drivers": {"table": "drivers", "fields": [
        ("full_name", "text", True), ("mobile", "text", False),
        ("notes", "text", False), ("is_active", "boolean", True)]},
    "Driver Advances": {"table": "driver_advances", "fields": [
        ("driver_id", "fk:drivers", True), ("vehicle_id", "fk:vehicles", False),
        ("amount", "number", True), ("advance_date", "date", True),
        ("description", "text", False)]},
    "Petty Cash Fund": {"table": "petty_cash_fund", "fields": [
        ("transaction_type", "select:IN,OUT", True), ("amount", "number", True),
        ("transaction_date", "date", True), ("description", "text", False)]},
    "Petty Cash Expenses": {"table": "petty_cash_expenses", "fields": [
        ("driver_id", "fk:drivers", False), ("vehicle_id", "fk:vehicles", False),
        ("category", "select:Maintenance,Oil Change,Tyre Change,Fuel,Other", True),
        ("amount", "number", True), ("expense_date", "date", True),
        ("description", "text", False)]},
    "Accommodations": {"table": "accommodations", "fields": [
        ("accommodation_name", "text", True), ("address", "text", False),
        ("monthly_rent", "number", True),
        ("payment_frequency", "select:Monthly,Quarterly,Half-Yearly,Yearly", True),
        ("next_due_date", "date", False), ("notes", "text", False),
        ("is_active", "boolean", True)]},
    "Rent Payments": {"table": "accommodation_rent_payments", "fields": [
        ("accommodation_id", "fk:accommodations", True), ("amount_due", "number", True),
        ("amount_paid", "number", True), ("due_date", "date", True),
        ("payment_date", "date", False), ("status", "select:Unpaid,Partial,Paid", True),
        ("notes", "text", False)]},
    "Utility Bills": {"table": "utility_bills", "fields": [
        ("accommodation_id", "fk:accommodations", False), ("bill_type", "text", True),
        ("amount", "number", True), ("bill_date", "date", False), ("due_date", "date", True),
        ("payment_date", "date", False), ("status", "select:Unpaid,Pending,Paid", True),
        ("description", "text", False)]},
    "Office Expenses": {"table": "office_expenses", "fields": [
        ("category", "text", True), ("amount", "number", True),
        ("expense_date", "date", True), ("due_date", "date", False),
        ("payment_date", "date", False), ("status", "select:Unpaid,Pending,Paid", True),
        ("description", "text", False)]},
    "Reminders": {"table": "reminders", "fields": [
        ("title", "text", True), ("message", "text", False),
        ("reminder_date", "date", True), ("related_type", "text", False),
        ("related_id", "text", False), ("is_completed", "boolean", True)]},
}

def notify_error(prefix, exc):
    st.error(f"{prefix}: {exc}")

def get_data(table, limit=2000):
    try:
        return supabase.table(table).select("*").limit(limit).execute().data or []
    except Exception as exc:
        notify_error(f"Could not read {table}", exc)
        return []

def fk_options(table):
    rows = get_data(table)
    result = {}
    for row in rows:
        if row.get("id") is not None:
            result[str(row["id"])] = row
    return result

def display_label(row, fallback):
    return str(row.get("full_name") or row.get("accommodation_name") or
               row.get("vehicle_name") or row.get("title") or
               row.get("plate_number") or fallback)

def render_field(field, kind, key, old=None):
    old = old or {}
    value = old.get(field)
    label = field.replace("_", " ").title()

    if kind == "text":
        return st.text_input(label, value="" if value is None else str(value), key=key)
    if kind == "number":
        try:
            initial = float(value or 0)
        except (TypeError, ValueError):
            initial = 0.0
        return st.number_input(label, min_value=0.0, value=initial, step=1.0, key=key)
    if kind == "date":
        try:
            initial = date.fromisoformat(str(value)[:10]) if value else date.today()
        except ValueError:
            initial = date.today()
        return st.date_input(label, value=initial, key=key)
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
            st.warning(f"No records found in {target}. Add the related record first.")
            return None
        ids = list(options.keys())
        selected = str(value) if value is not None else ""
        index = ids.index(selected) if selected in ids else 0
        chosen = st.selectbox(
            label, ids, index=index,
            format_func=lambda item: display_label(options[item], item),
            key=key
        )
        return chosen
    return None

def _flash(message, kind="success"):
    st.session_state["agc_flash"] = (kind, message)


def show_flash():
    item = st.session_state.pop("agc_flash", None)
    if item:
        kind, message = item
        getattr(st, kind, st.success)(message)


def _stable_rows(rows):
    # Keep the real database UUID untouched; show a simple serial number to users.
    return sorted(rows, key=lambda r: (str(r.get("created_at") or ""), str(r.get("id") or "")))


def module_page(name, config):
    table = config["table"]
    st.title(name)
    add_tab, records_tab = st.tabs(["Add New", "Records"])

    with add_tab:
        st.subheader(f"Add {name}")
        with st.form(f"add_form_{table}"):
            values = {}
            for field, kind, required in config["fields"]:
                values[field] = render_field(field, kind, f"add_{table}_{field}")
            submitted = st.form_submit_button("Save Record", type="primary")
        if submitted:
            missing = [f.replace("_", " ").title() for f, k, req in config["fields"]
                       if req and (values.get(f) is None or values.get(f) == "")]
            if missing:
                st.error("Please complete required fields: " + ", ".join(missing))
            else:
                try:
                    supabase.table(table).insert(values).execute()
                    _flash(f"{name} record saved successfully.")
                    st.rerun()
                except Exception as exc:
                    notify_error("Save failed", exc)

    show_flash()
    with records_tab:
        st.subheader(f"{name} Records")
        rows = _stable_rows(get_data(table))
        if not rows:
            st.info("No records found.")
            return

        # Each record is rendered as one row with actions beside it.
        header = st.columns([0.07, 0.43, 0.16, 0.16, 0.18])
        header[0].markdown("**No.**")
        header[1].markdown("**Record**")
        header[2].markdown("**View**")
        header[3].markdown("**Edit**")
        header[4].markdown("**Delete**")

        for i, row in enumerate(rows, 1):
            rid = str(row.get("id"))
            label = display_label(row, f"Record {i}")
            details = [f"{k.replace('_', ' ').title()}: {v}" for k, v in row.items()
                       if k not in ("id", "created_at", "updated_at") and v not in (None, "")]
            summary = " · ".join(details[:3])
            cells = st.columns([0.07, 0.43, 0.16, 0.16, 0.18])
            cells[0].write(str(i))
            cells[1].markdown(f"**{label}**" + (f"\n\n{summary}" if summary else ""))
            if cells[2].button("View", key=f"view_{table}_{rid}", use_container_width=True):
                st.session_state[f"viewing_{table}"] = rid
                st.session_state.pop(f"editing_{table}", None)
                st.session_state.pop(f"deleting_{table}", None)
            if cells[3].button("Edit", key=f"edit_{table}_{rid}", use_container_width=True):
                st.session_state[f"editing_{table}"] = rid
                st.session_state.pop(f"viewing_{table}", None)
                st.session_state.pop(f"deleting_{table}", None)
            if cells[4].button("Delete", key=f"delete_{table}_{rid}", use_container_width=True):
                st.session_state[f"deleting_{table}"] = rid
                st.session_state.pop(f"viewing_{table}", None)
                st.session_state.pop(f"editing_{table}", None)

            if st.session_state.get(f"viewing_{table}") == rid:
                with st.container(border=True):
                    st.markdown(f"**{name} — Record {i}: {label}**")
                    visible = {k.replace("_", " ").title(): v for k, v in row.items()
                               if k not in ("id", "created_at", "updated_at")}
                    st.json(visible)
                    if st.button("Close View", key=f"close_view_{table}_{rid}"):
                        st.session_state.pop(f"viewing_{table}", None)
                        st.rerun()

            if st.session_state.get(f"editing_{table}") == rid:
                with st.container(border=True):
                    st.markdown(f"**Edit {name} — Record {i}**")
                    with st.form(f"inline_edit_{table}_{rid}"):
                        updated = {}
                        for field, kind, required in config["fields"]:
                            updated[field] = render_field(
                                field, kind, f"inline_{table}_{rid}_{field}", row
                            )
                        save = st.form_submit_button("Save Changes", type="primary")
                    if save:
                        missing = [f.replace("_", " ").title() for f, k, req in config["fields"]
                                   if req and (updated.get(f) is None or updated.get(f) == "")]
                        if missing:
                            st.error("Please complete required fields: " + ", ".join(missing))
                        else:
                            try:
                                supabase.table(table).update(updated).eq("id", rid).execute()
                                st.session_state.pop(f"editing_{table}", None)
                                _flash(f"{name} record updated successfully.")
                                st.rerun()
                            except Exception as exc:
                                notify_error("Update failed", exc)

            if st.session_state.get(f"deleting_{table}") == rid:
                with st.container(border=True):
                    st.warning("This action permanently deletes this record. Related records may be affected by database foreign-key rules.")
                    confirm = st.checkbox("I confirm permanent deletion", key=f"confirm_{table}_{rid}")
                    if st.button("Confirm Delete", type="primary", key=f"confirm_delete_{table}_{rid}"):
                        if not confirm:
                            st.warning("Please confirm deletion first.")
                        else:
                            try:
                                supabase.table(table).delete().eq("id", rid).execute()
                                st.session_state.pop(f"deleting_{table}", None)
                                _flash(f"{name} record deleted successfully.")
                                st.rerun()
                            except Exception as exc:
                                notify_error("Delete failed", exc)

# =========================================================
# NOTIFICATIONS
# =========================================================
def as_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None

def build_notifications():
    today = date.today()
    items = []

    def add_item(title, due, detail, amount=None, status=None):
        due_date = as_date(due)
        if not due_date:
            return
        if status and str(status).lower() == "paid":
            return
        days = (due_date - today).days
        if days <= 20:
            if days > 0:
                timing = f"Due in {days} day(s)"
            elif days == 0:
                timing = "Due today"
            else:
                timing = f"Overdue by {abs(days)} day(s)"
            items.append({
                "title": title, "due_date": due_date, "days": days,
                "timing": timing, "detail": detail,
                "amount": amount
            })

    employees = get_data("employees")
    for r in employees:
        if r.get("is_active", True):
            add_item("Iqama expiry", r.get("iqama_expiry"),
                     f"Employee: {r.get('full_name', 'Employee')}")

    employee_map = {str(r.get("id")): r.get("full_name", "Employee") for r in employees}
    for r in get_data("salary_records"):
        emp = employee_map.get(str(r.get("employee_id")), "Employee")
        outstanding = max(0, float(r.get("amount_due") or 0) - float(r.get("amount_paid") or 0))
        if outstanding > 0:
            add_item("Salary payment", r.get("due_date"),
                     f"Employee: {emp}", outstanding, r.get("status"))

    accommodation_map = {
        str(r.get("id")): r.get("accommodation_name", "Accommodation")
        for r in get_data("accommodations")
    }
    for r in get_data("accommodation_rent_payments"):
        outstanding = max(0, float(r.get("amount_due") or 0) - float(r.get("amount_paid") or 0))
        if outstanding > 0:
            name = accommodation_map.get(str(r.get("accommodation_id")), "Accommodation")
            add_item("Rent payment", r.get("due_date"), name, outstanding, r.get("status"))

    for r in get_data("utility_bills"):
        if str(r.get("status", "")).lower() != "paid":
            name = accommodation_map.get(str(r.get("accommodation_id")), "Accommodation")
            add_item(f"Utility bill: {r.get('bill_type', 'Utility')}", r.get("due_date"),
                     name, r.get("amount"), r.get("status"))

    for r in get_data("office_expenses"):
        if str(r.get("status", "")).lower() != "paid":
            add_item(f"Office expense: {r.get('category', 'Expense')}", r.get("due_date"),
                     r.get("description") or "Office expense", r.get("amount"), r.get("status"))

    for r in get_data("reminders"):
        if not r.get("is_completed"):
            add_item(r.get("title", "Reminder"), r.get("reminder_date"),
                     r.get("message") or "General reminder")

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
    # A log row prevents repeat emails for the same recipient and due item.
    recipients = []
    for row in guardian_rows:
        if row.get("is_active", True) and row.get("email"):
            recipients.append(row["email"])
    if not recipients:
        return
    for item in items:
        days = item["days"]
        if days not in (20, 15, 7, 0) and days >= 0:
            continue
        body = (
            f"AGC Management System reminder\n\n"
            f"{item['title']}\n{item['detail']}\n"
            f"Due date: {item['due_date']}\nStatus: {item['timing']}\n"
            f"Amount: {item['amount'] if item['amount'] is not None else 'Not specified'} SAR\n"
        )
        for recipient in recipients:
            key = notification_key(item, recipient)
            try:
                existing = (supabase.table("notification_log").select("id")
                            .eq("event_key", key).limit(1).execute().data or [])
                if existing:
                    continue
                ok, message = send_email(f"AGC Reminder: {item['title']}", body, [recipient])
                if ok:
                    supabase.table("notification_log").insert({
                        "event_key": key, "recipient_email": recipient,
                        "event_title": item["title"], "due_date": item["due_date"].isoformat()
                    }).execute()
            except Exception:
                # Keep dashboard working even if email configuration/log table is missing.
                pass

# =========================================================
# LOGIN
# =========================================================
if "user" not in st.session_state:
    st.session_state.user = None
if "profile" not in st.session_state:
    st.session_state.profile = None

if st.session_state.user is None:
    st.title("AGC Management System")
    st.subheader("Administrator Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login", type="primary"):
        try:
            result = supabase.auth.sign_in_with_password({"email": email, "password": password})
            user = result.user
            profile = (supabase.table("profiles").select("*").eq("id", user.id)
                       .single().execute().data)
            if profile and profile.get("is_active") and profile.get("role") == "admin":
                st.session_state.user = user
                st.session_state.profile = profile
                st.rerun()
            else:
                supabase.auth.sign_out()
                st.error("Admin access only.")
        except Exception as exc:
            notify_error("Login failed", exc)

else:
    profile = st.session_state.profile or {}
    st.sidebar.title("AGC Management")
    st.sidebar.success(f"Welcome {profile.get('full_name', 'Admin')}")
    if st.sidebar.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.profile = None
        st.rerun()

    pages = ["Dashboard"] + list(MODULES.keys()) + ["Guardian Contacts"]
    page = st.sidebar.radio("Select Module", pages)

    if page == "Dashboard":
        st.title("AGC Main Dashboard")
        st.caption("Live Company Management Overview")
        employees = get_data("employees")
        salaries = get_data("salary_records")
        vehicles = get_data("vehicles")
        drivers = get_data("drivers")
        advances = get_data("driver_advances")
        expenses = get_data("petty_cash_expenses")
        rent = get_data("accommodation_rent_payments")
        utilities = get_data("utility_bills")
        office = get_data("office_expenses")

        def total(rows, field):
            return sum(float(r.get(field) or 0) for r in rows)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Employees", len(employees))
        c2.metric("Active Employees", sum(1 for r in employees if r.get("is_active")))
        c3.metric("Total Vehicles", len(vehicles))
        c4.metric("Total Drivers", len(drivers))
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Monthly Salary (SAR)", f"{total(employees, 'monthly_salary'):,.2f}")
        c6.metric("Salary Outstanding (SAR)", f"{sum(max(0, float(r.get('amount_due') or 0)-float(r.get('amount_paid') or 0)) for r in salaries):,.2f}")
        c7.metric("Driver Advances (SAR)", f"{total(advances, 'amount'):,.2f}")
        c8.metric("Petty Cash Expenses (SAR)", f"{total(expenses, 'amount'):,.2f}")
        st.subheader("Outstanding Payments")
        st.write("Rent Outstanding:", f"{sum(max(0, float(r.get('amount_due') or 0)-float(r.get('amount_paid') or 0)) for r in rent):,.2f} SAR")
        st.write("Unpaid Utility Bills:", f"{sum(float(r.get('amount') or 0) for r in utilities if r.get('status') != 'Paid'):,.2f} SAR")
        st.write("Office Expenses:", f"{total(office, 'amount'):,.2f} SAR")

        st.subheader("Notifications & Upcoming Payments")
        notifications = build_notifications()
        if notifications:
            for item in notifications:
                amount_text = f" | {item['amount']:,.2f} SAR" if item["amount"] is not None else ""
                st.warning(f"{item['timing']} — {item['title']} — {item['detail']} — Due: {item['due_date']}{amount_text}")
        else:
            st.success("No upcoming or overdue notifications.")

        st.subheader("Employee Records")
        if employees:
            st.dataframe(pd.DataFrame([
                {"Sr. No.": i, **{k: v for k, v in r.items()
                 if k not in ("id", "created_at", "updated_at")}}
                for i, r in enumerate(_stable_rows(employees), 1)
            ]), use_container_width=True, hide_index=True)
        else:
            st.info("No employee records yet.")

        # Email is sent only when the app/dashboard is opened or refreshed.
        try:
            guardians = get_data("guardian_contacts")
            if st.button("Send Due Email Notifications"):
                process_email_notifications(notifications, guardians)
                st.info("Email notification check completed. Check SMTP settings and notification_log if no email arrives.")
        except Exception:
            st.caption("Create the Guardian Contacts and Notification Log tables using the SQL setup instructions.")

    elif page == "Guardian Contacts":
        st.title("Guardian / Notification Contacts")
        st.caption("Add people who should receive AGC email reminders. They do not get application login access.")
        show_flash()
        try:
            contacts = get_data("guardian_contacts")
            with st.form("add_guardian"):
                g_name = st.text_input("Guardian Name")
                g_email = st.text_input("Email Address")
                g_active = st.checkbox("Active", value=True)
                add = st.form_submit_button("Add Guardian", type="primary")
            if add:
                if not g_name.strip() or not g_email.strip() or "@" not in g_email:
                    st.error("Enter a valid name and email address.")
                else:
                    supabase.table("guardian_contacts").insert({
                        "name": g_name.strip(), "email": g_email.strip(),
                        "is_active": g_active
                    }).execute()
                    _flash("Guardian contact saved successfully.")
                    st.rerun()
            st.subheader("Saved Guardians")
            if contacts:
                contacts = _stable_rows(contacts)
                h = st.columns([0.07, 0.43, 0.16, 0.16, 0.18])
                for cell, title in zip(h, ["**No.**", "**Guardian**", "**View**", "**Edit**", "**Delete**"]):
                    cell.markdown(title)
                for i, row in enumerate(contacts, 1):
                    rid = str(row["id"])
                    cells = st.columns([0.07, 0.43, 0.16, 0.16, 0.18])
                    cells[0].write(str(i))
                    cells[1].markdown(f"**{row.get('name', 'Guardian')}**\n\n{row.get('email', '')} · {'Active' if row.get('is_active', True) else 'Inactive'}")
                    if cells[2].button("View", key=f"guardian_view_{rid}", use_container_width=True):
                        st.session_state["guardian_view_id"] = rid
                        st.session_state.pop("guardian_edit_id", None)
                        st.session_state.pop("guardian_delete_id", None)
                    if cells[3].button("Edit", key=f"guardian_edit_{rid}", use_container_width=True):
                        st.session_state["guardian_edit_id"] = rid
                        st.session_state.pop("guardian_view_id", None)
                        st.session_state.pop("guardian_delete_id", None)
                    if cells[4].button("Delete", key=f"guardian_delete_{rid}", use_container_width=True):
                        st.session_state["guardian_delete_id"] = rid
                        st.session_state.pop("guardian_view_id", None)
                        st.session_state.pop("guardian_edit_id", None)
                    if st.session_state.get("guardian_view_id") == rid:
                        with st.container(border=True):
                            st.json({"Name": row.get("name"), "Email": row.get("email"),
                                     "Active": row.get("is_active", True)})
                    if st.session_state.get("guardian_edit_id") == rid:
                        with st.container(border=True):
                            with st.form(f"guardian_edit_form_{rid}"):
                                new_name = st.text_input("Guardian Name", value=row.get("name", ""))
                                new_email = st.text_input("Email Address", value=row.get("email", ""))
                                new_active = st.checkbox("Active", value=row.get("is_active", True))
                                save_guardian = st.form_submit_button("Save Changes", type="primary")
                            if save_guardian:
                                if not new_name.strip() or "@" not in new_email:
                                    st.error("Enter a valid name and email address.")
                                else:
                                    try:
                                        supabase.table("guardian_contacts").update({
                                            "name": new_name.strip(), "email": new_email.strip(),
                                            "is_active": new_active
                                        }).eq("id", rid).execute()
                                        st.session_state.pop("guardian_edit_id", None)
                                        _flash("Guardian contact updated successfully.")
                                        st.rerun()
                                    except Exception as exc:
                                        notify_error("Guardian update failed", exc)
                    if st.session_state.get("guardian_delete_id") == rid:
                        with st.container(border=True):
                            confirm_guardian = st.checkbox("Confirm permanent deletion", key=f"guardian_confirm_{rid}")
                            if st.button("Confirm Delete", key=f"guardian_confirm_delete_{rid}"):
                                if confirm_guardian:
                                    try:
                                        supabase.table("guardian_contacts").delete().eq("id", rid).execute()
                                        st.session_state.pop("guardian_delete_id", None)
                                        _flash("Guardian contact deleted successfully.")
                                        st.rerun()
                                    except Exception as exc:
                                        notify_error("Guardian delete failed", exc)
                                else:
                                    st.warning("Please confirm deletion first.")
                        if st.session_state.get("guardian_edit_id") == rid:
                            with st.form(f"guardian_edit_form_{rid}"):
                                new_name = st.text_input("Guardian Name", value=row.get("name", ""))
                                new_email = st.text_input("Email Address", value=row.get("email", ""))
                                new_active = st.checkbox("Active", value=row.get("is_active", True))
                                save_guardian = st.form_submit_button("Save Changes", type="primary")
                            if save_guardian:
                                if not new_name.strip() or "@" not in new_email:
                                    st.error("Enter a valid name and email address.")
                                else:
                                    try:
                                        supabase.table("guardian_contacts").update({
                                            "name": new_name.strip(), "email": new_email.strip(),
                                            "is_active": new_active
                                        }).eq("id", rid).execute()
                                        st.session_state.pop("guardian_edit_id", None)
                                        _flash("Guardian contact updated successfully.")
                                        st.rerun()
                                    except Exception as exc:
                                        notify_error("Guardian update failed", exc)
                        if st.session_state.get("guardian_delete_id") == rid:
                            confirm_guardian = st.checkbox("Confirm permanent deletion", key=f"guardian_confirm_{rid}")
                            if st.button("Confirm Delete", key=f"guardian_confirm_delete_{rid}"):
                                if confirm_guardian:
                                    try:
                                        supabase.table("guardian_contacts").delete().eq("id", rid).execute()
                                        st.session_state.pop("guardian_delete_id", None)
                                        _flash("Guardian contact deleted successfully.")
                                        st.rerun()
                                    except Exception as exc:
                                        notify_error("Guardian delete failed", exc)
                                else:
                                    st.warning("Please confirm deletion first.")
            else:
                st.info("No guardian contacts added.")
        except Exception as exc:
            st.error("Guardian tables are not ready. Run the SQL setup provided with this app.")
            st.code(str(exc))

    else:
        module_page(page, MODULES[page])
