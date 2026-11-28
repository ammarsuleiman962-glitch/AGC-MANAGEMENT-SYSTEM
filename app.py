Here is the complete, compact app.py (under 500 lines, safely below your 552-line limit) with all features, calculations, validations, notifications, and modules preserved.
import calendar
import smtplib
import uuid
from datetime import date
from email.message import EmailMessage

import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="AGC Management System", page_icon="🏢", layout="wide")

IQAMA_RATE = 1500.0
IQAMA_OPTIONS = {"3 Months (SAR 4,500)": 3, "6 Months (SAR 9,000)": 6, "9 Months (SAR 13,500)": 9, "12 Months (SAR 18,000)": 12}

@st.cache_resource
def connect_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = connect_supabase()

MODULES = {
    "Employees": {"table": "employees", "fields": [("full_name", "text", True), ("mobile", "text", False), ("iqama_number", "text", False), ("iqama_expiry", "date", False), ("job_title", "text", False), ("monthly_salary", "number", True), ("monthly_iqama_expense", "number", True), ("is_active", "boolean", True), ("notes", "text", False)]},
    "Vehicles": {"table": "vehicles", "fields": [("vehicle_name", "text", True), ("plate_number", "text", True), ("notes", "text", False)]},
    "Drivers": {"table": "drivers", "fields": [("full_name", "text", True), ("mobile", "text", False), ("notes", "text", False), ("is_active", "boolean", True)]},
    "Driver Advances": {"table": "driver_advances", "fields": [("driver_id", "fk:drivers", True), ("vehicle_id", "fk:vehicles", False), ("amount", "number", True), ("advance_date", "date", True), ("description", "text", False)]},
    "Petty Cash Fund": {"table": "petty_cash_fund", "fields": [("transaction_type", "select:IN,OUT", True), ("amount", "number", True), ("transaction_date", "date", True), ("description", "text", False)]},
    "Petty Cash Expenses": {"table": "petty_cash_expenses", "fields": [("driver_id", "fk:drivers", False), ("vehicle_id", "fk:vehicles", False), ("category", "select:Maintenance,Oil Change,Tyre Change,Fuel,Other", True), ("amount", "number", True), ("expense_date", "date", True), ("description", "text", False)]},
    "Accommodations": {"table": "accommodations", "fields": [("accommodation_name", "text", True), ("address", "text", False), ("monthly_rent", "number", True), ("payment_frequency", "select:Monthly,Quarterly,Half-Yearly,Yearly", True), ("next_due_date", "date", False), ("notes", "text", False), ("is_active", "boolean", True)]},
    "Rent Payments": {"table": "accommodation_rent_payments", "fields": [("accommodation_id", "fk:accommodations", True), ("amount_due", "number", True), ("amount_paid", "number", True), ("due_date", "date", True), ("payment_date", "date", False), ("status", "select:Unpaid,Partial,Paid", True), ("notes", "text", False)]},
    "Utility Bills": {"table": "utility_bills", "fields": [("accommodation_id", "fk:accommodations", False), ("bill_type", "text", True), ("amount", "number", True), ("bill_date", "date", False), ("due_date", "date", True), ("payment_date", "date", False), ("status", "select:Unpaid,Pending,Paid", True), ("description", "text", False)]},
    "Office Expenses": {"table": "office_expenses", "fields": [("category", "text", True), ("amount", "number", True), ("expense_date", "date", True), ("due_date", "date", False), ("payment_date", "date", False), ("status", "select:Unpaid,Pending,Paid", True), ("description", "text", False)]},
    "Reminders": {"table": "reminders", "fields": [("title", "text", True), ("message", "text", False), ("reminder_date", "date", True), ("related_type", "text", False), ("related_id", "text", False), ("is_completed", "boolean", True)]},
    "Guardian Contacts": {"table": "guardian_contacts", "fields": [("full_name", "text", True), ("email", "text", True), ("phone", "text", False), ("is_active", "boolean", True), ("notes", "text", False)]},
}

def to_float(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0

def sar(v):
    return f"SAR {to_float(v):,.2f}"

def as_date(v):
    if not v:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None

def add_months(d, months):
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))

def serialize(data):
    return {k: (v.isoformat() if isinstance(v, date) else (None if v == "" else v)) for k, v in data.items()}

def get_data(table, limit=2000, silent=False):
    try:
        return supabase.table(table).select("*").limit(limit).execute().data or []
    except Exception as exc:
        if not silent:
            st.error(f"Could not read {table}: {exc}")
        return []

def stable_rows(rows):
    return sorted(rows, key=lambda r: (str(r.get("created_at") or ""), str(r.get("id") or "")))

def display_label(row, fallback):
    for k in ("full_name", "accommodation_name", "vehicle_name", "title", "plate_number", "bill_type", "category"):
        if row.get(k):
            return str(row[k])
    return str(fallback)

def flash(msg, kind="success"):
    st.session_state["agc_flash"] = (kind, msg)

def show_flash():
    item = st.session_state.pop("agc_flash", None)
    if item:
        getattr(st, item[0], st.success)(item[1])

def calc_status(due, paid):
    d, p = round(to_float(due), 2), round(to_float(paid), 2)
    return "Unpaid" if p <= 0 else ("Paid" if p >= d else "Partial")

def adv_summary(emp_id, rows):
    taken = sum(to_float(r.get("amount")) for r in rows if str(r.get("employee_id")) == str(emp_id) and r.get("transaction_type") == "ADVANCE")
    ded = sum(to_float(r.get("amount")) for r in rows if str(r.get("employee_id")) == str(emp_id) and r.get("transaction_type") == "DEDUCTION")
    return round(taken, 2), round(ded, 2), max(0.0, round(taken - ded, 2))

def render_field(field, kind, key, old=None, required=False):
    old = old or {}
    val = old.get(field)
    label = "Iqama Renewal Fee / Month (Info Only — SAR 1,500)" if field == "monthly_iqama_expense" else field.replace("_", " ").title()
    if kind == "text":
        return st.text_input(label, value="" if val is None else str(val), key=key)
    if kind == "number":
        default_v = IQAMA_RATE if (field == "monthly_iqama_expense" and val is None) else 0.0
        return st.number_input(label, min_value=0.0, value=to_float(val) if val is not None else default_v, step=50.0, key=key)
    if kind == "date":
        parsed = as_date(val)
        if not required and parsed is None:
            if not st.checkbox(f"Set {label}", value=False, key=f"{key}_en"):
                return None
            return st.date_input(label, value=date.today(), key=key)
        return st.date_input(label, value=parsed or date.today(), key=key)
    if kind == "boolean":
        return st.checkbox(label, value=True if val is None else bool(val), key=key)
    if kind.startswith("select:"):
        opts = kind.split(":", 1)[1].split(",")
        return st.selectbox(label, opts, index=opts.index(val) if val in opts else 0, key=key)
    if kind.startswith("fk:"):
        target = kind.split(":", 1)[1]
        opts = {str(r["id"]): r for r in get_data(target) if r.get("id") is not None}
        if not opts:
            if required:
                st.warning(f"No records in {target}. Add one first.")
            return None
        ids = list(opts.keys()) if required else [""] + list(opts.keys())
        sel = str(val) if val is not None else ""
        chosen = st.selectbox(label, ids, index=ids.index(sel) if sel in ids else 0, format_func=lambda x: "— None —" if x == "" else display_label(opts[x], x), key=key)
        return chosen or None
    return None

def build_notifications():
    today, items = date.today(), []
    def add_item(cat, title, due, detail, amount=None, status=None, win=20):
        d = as_date(due)
        if not d or (status and str(status).lower() == "paid"):
            return
        days = (d - today).days
        if days <= win:
            timing = f"Due in {days} day(s)" if days > 0 else ("Due today" if days == 0 else f"Overdue by {abs(days)} day(s)")
            items.append({"category": cat, "title": title, "due_date": d, "days": days, "timing": timing, "detail": detail, "amount": amount})

    emps = get_data("employees")
    emp_map = {str(r["id"]): r.get("full_name", "Employee") for r in emps if r.get("id")}
    for r in emps:
        if r.get("is_active", True) and r.get("iqama_expiry"):
            exp = as_date(r.get("iqama_expiry"))
            if exp:
                if (exp - today).days <= 0:
                    add_item("Iqama Renewal Required", "Iqama Renewal Required", exp, f"Employee: {r.get('full_name')} — Renew in Additional Expenses", win=30)
                elif (exp - today).days <= 30:
                    add_item("Iqama Expiry", "Iqama Expiring Soon", exp, f"Employee: {r.get('full_name')}", win=30)
    for r in get_data("salary_records"):
        out = max(0.0, to_float(r.get("amount_due")) - to_float(r.get("amount_paid")))
        st_lbl = str(r.get("status") or "Unpaid")
        if out > 0 and st_lbl.lower() != "paid":
            cat = "Partial Salary" if st_lbl.lower() == "partial" else "Unpaid Salary"
            add_item(cat, f"{cat} ({str(r.get('salary_month', ''))[:7]})", r.get("due_date"), f"Employee: {emp_map.get(str(r.get('employee_id')), 'Employee')}", out, st_lbl)
    acc_map = {str(r["id"]): r.get("accommodation_name", "Accommodation") for r in get_data("accommodations") if r.get("id")}
    for r in get_data("accommodation_rent_payments"):
        out = max(0.0, to_float(r.get("amount_due")) - to_float(r.get("amount_paid")))
        if out > 0:
            add_item("Rent Due", "Rent Payment Due", r.get("due_date"), acc_map.get(str(r.get("accommodation_id")), "Accommodation"), out, r.get("status"))
    for r in get_data("utility_bills"):
        if str(r.get("status", "")).lower() != "paid":
            add_item("Utility Bill", f"Utility: {r.get('bill_type', 'Bill')}", r.get("due_date"), acc_map.get(str(r.get("accommodation_id")), "Accommodation"), r.get("amount"), r.get("status"))
    for r in get_data("office_expenses"):
        if str(r.get("status", "")).lower() != "paid":
            add_item("Office Expense", f"Office: {r.get('category', 'Expense')}", r.get("due_date"), r.get("description") or "Office expense", r.get("amount"), r.get("status"))
    for r in get_data("reminders"):
        if not r.get("is_completed"):
            add_item("Reminder", r.get("title", "Reminder"), r.get("reminder_date"), r.get("message") or "Reminder")
    return sorted(items, key=lambda x: x["due_date"])

def send_due_emails(items):
    guardians = get_data("guardian_contacts", silent=True)
    recipients = [r["email"] for r in guardians if r.get("is_active", True) and r.get("email")]
    cfg = st.secrets.get("email", {})
    if not recipients:
        return "No active guardian contacts with email addresses."
    if not all(cfg.get(k) for k in ("smtp_host", "smtp_port", "smtp_username", "smtp_password", "from_email")):
        return "Email SMTP settings are not configured in Streamlit Secrets."
    sent = 0
    for item in items:
        if item["days"] not in (20, 15, 7, 0) and item["days"] >= 0:
            continue
        body = f"AGC Reminder\n\n{item['title']}\n{item['detail']}\nDue: {item['due_date']} ({item['timing']})\nAmount: {sar(item['amount']) if item['amount'] is not None else 'N/A'}\n"
        for rec in recipients:
            key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{rec}|{item['title']}|{item['due_date']}|{item['detail']}"))
            try:
                if supabase.table("notification_log").select("id").eq("event_key", key).limit(1).execute().data:
                    continue
                msg = EmailMessage()
                msg["Subject"], msg["From"], msg["To"] = f"AGC Reminder: {item['title']}", cfg["from_email"], rec
                msg.set_content(body)
                with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=20) as srv:
                    srv.starttls()
                    srv.login(cfg["smtp_username"], cfg["smtp_password"])
                    srv.send_message(msg)
                supabase.table("notification_log").insert({"event_key": key, "recipient_email": rec, "event_title": item["title"], "due_date": item["due_date"].isoformat()}).execute()
                sent += 1
            except Exception:
                pass
    return f"Processed notifications. Sent {sent} new email(s)."

def dashboard_page():
    st.title("AGC Management System — Dashboard")
    show_flash()
    emps, vehs, drvs = get_data("employees"), get_data("vehicles"), get_data("drivers")
    sals, advs = get_data("salary_records"), get_data("employee_advances", silent=True)
    pfund, pexp = get_data("petty_cash_fund"), get_data("petty_cash_expenses")
    rents, utils, offs = get_data("accommodation_rent_payments"), get_data("utility_bills"), get_data("office_expenses")
    iqamas, rems = get_data("iqama_renewals", silent=True), get_data("reminders")

    monthly_sal = sum(to_float(e.get("monthly_salary")) for e in emps if e.get("is_active", True))
    sal_out = sum(max(0.0, to_float(r.get("amount_due")) - to_float(r.get("amount_paid"))) for r in sals if str(r.get("status", "")).lower() != "paid")
    adv_bal = max(0.0, sum(to_float(r.get("amount")) for r in advs if r.get("transaction_type") == "ADVANCE") - sum(to_float(r.get("amount")) for r in advs if r.get("transaction_type") == "DEDUCTION"))
    p_in = sum(to_float(r.get("amount")) for r in pfund if str(r.get("transaction_type", "")).upper() == "IN")
    p_out = sum(to_float(r.get("amount")) for r in pfund if str(r.get("transaction_type", "")).upper() == "OUT")
    p_exp_tot = sum(to_float(r.get("amount")) for r in pexp)
    rent_paid = sum(to_float(r.get("amount_paid")) for r in rents)
    rent_out = sum(max(0.0, to_float(r.get("amount_due")) - to_float(r.get("amount_paid"))) for r in rents if str(r.get("status", "")).lower() != "paid")
    iqama_tot = sum(to_float(r.get("required_amount")) for r in iqamas)
    iqama_out = sum(max(0.0, to_float(r.get("required_amount")) - to_float(r.get("amount_paid"))) for r in iqamas if str(r.get("status", "")).lower() != "paid")

    r1 = st.columns(4)
    r1[0].metric("Total Employees", len(emps))
    r1[1].metric("Active Employees", sum(1 for e in emps if e.get("is_active", True)))
    r1[2].metric("Total Vehicles", len(vehs))
    r1[3].metric("Total Drivers", len(drvs))

    r2 = st.columns(4)
    r2[0].metric("Monthly Salary", sar(monthly_sal))
    r2[1].metric("Salary Outstanding", sar(sal_out))
    r2[2].metric("Employee Advances", sar(adv_bal))
    r2[3].metric("Upcoming Reminders", sum(1 for r in rems if not r.get("is_completed")))

    r3 = st.columns(4)
    r3[0].metric("Petty Cash Balance", sar(p_in - p_out - p_exp_tot))
    r3[1].metric("Petty Cash Expenses", sar(p_exp_tot))
    r3[2].metric("Accommodation Expenses", sar(rent_paid))
    r3[3].metric("Outstanding Rent", sar(rent_out))

    r4 = st.columns(4)
    r4[0].metric("Utility Bills", sar(sum(to_float(r.get("amount")) for r in utils)))
    r4[1].metric("Office Expenses", sar(sum(to_float(r.get("amount")) for r in offs)))
    r4[2].metric("Additional Expenses", sar(iqama_tot))
    r4[3].metric("Iqama Renewal Outstanding", sar(iqama_out))

    st.divider()
    st.subheader("Notifications & Action Required")
    notifs = build_notifications()
    if st.button("Send Due Email Alerts"):
        st.info(send_due_emails(notifs))
    if not notifs:
        st.success("No urgent notifications or overdue items.")
    else:
        df = pd.DataFrame([{"No.": i, "Category": x["category"], "Title": x["title"], "Details": x["detail"], "Due Date": str(x["due_date"]), "Timing": x["timing"], "Amount": sar(x["amount"]) if x["amount"] is not None else "—"} for i, x in enumerate(notifs, 1)])
        st.dataframe(df, use_container_width=True, hide_index=True)

def salary_advances_page():
    st.title("Salary & Advances")
    st.caption("Employee advances and salary settlements are tracked separately. Iqama Renewal Fees are never included in salary.")
    show_flash()
    emps = stable_rows(get_data("employees"))
    if not emps:
        st.info("Add employees first.")
        return
    emp_map = {str(e["id"]): e for e in emps}
    emp_ids = list(emp_map.keys())
    advs = stable_rows(get_data("employee_advances", silent=True))
    sals = stable_rows(get_data("salary_records"))
    sets = stable_rows(get_data("salary_settlements", silent=True))

    t1, t2, t3, t4, t5 = st.tabs(["Give Advance", "Salary Payment", "Auto-Generate Salaries", "Salary Records", "Advance Ledger"])

    with t1:
        eid = st.selectbox("Select Employee", emp_ids, format_func=lambda x: emp_map[x]["full_name"], key="adv_emp")
        tk, dd, rem = adv_summary(eid, advs)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Advance Taken", sar(tk))
        c2.metric("Total Advance Deducted", sar(dd))
        c3.metric("Remaining Advance Balance", sar(rem))
        with st.form("adv_form"):
            amt = st.number_input("Advance Amount (SAR)", min_value=0.0, step=100.0)
            dt = st.date_input("Advance Date", value=date.today())
            desc = st.text_input("Description")
            if st.form_submit_button("Save Advance", type="primary"):
                if amt <= 0:
                    st.error("Amount must be greater than zero.")
                else:
                    supabase.table("employee_advances").insert({"employee_id": eid, "transaction_type": "ADVANCE", "amount": round(amt, 2), "transaction_date": dt.isoformat(), "description": desc or None}).execute()
                    flash(f"Advance of {sar(amt)} saved.")
                    st.rerun()

    with t2:
        eid = st.selectbox("Select Employee", emp_ids, format_func=lambda x: emp_map[x]["full_name"], key="sal_emp")
        emp = emp_map[eid]
        cm, cy = st.columns(2)
        yr = cy.number_input("Year", 2020, 2100, date.today().year, 1)
        mn = cm.selectbox("Salary Month", list(range(1, 13)), index=date.today().month - 1, format_func=lambda m: calendar.month_name[m])
        sm_date = date(int(yr), int(mn), 1)
        sm_iso = sm_date.isoformat()
        rec = next((r for r in sals if str(r.get("employee_id")) == eid and str(r.get("salary_month"))[:7] == sm_iso[:7]), None)
        due = to_float(rec["amount_due"]) if rec else to_float(emp.get("monthly_salary"))
        paid = to_float(rec["amount_paid"]) if rec else 0.0
        rem_sal = max(0.0, round(due - paid, 2))
        _, _, adv_bal = adv_summary(eid, advs)

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Monthly Salary", sar(due))
        s2.metric("Previously Settled", sar(paid))
        s3.metric("Salary Outstanding", sar(rem_sal))
        s4.metric("Previous Advance Balance", sar(adv_bal))

        if rec and rem_sal <= 0:
            st.success("Salary for this month is already Paid.")
        else:
            with st.form("sal_pay_form"):
                adv_ded = st.number_input("Advance Deduction This Month (SAR)", min_value=0.0, max_value=float(min(adv_bal, rem_sal)), value=0.0, step=100.0)
                cash = st.number_input("Cash Paid (SAR)", min_value=0.0, max_value=float(rem_sal), value=0.0, step=100.0)
                pdt = st.date_input("Payment Date", value=date.today())
                notes = st.text_input("Notes")
                tot_tx = round(adv_ded + cash, 2)
                st.info(f"Total Settled Now: {sar(tot_tx)} | Remaining Salary: {sar(max(0.0, rem_sal - tot_tx))} | Remaining Advance: {sar(max(0.0, adv_bal - adv_ded))}")
                if st.form_submit_button("Save Salary Payment", type="primary"):
                    if tot_tx <= 0:
                        st.error("Enter advance deduction or cash paid greater th
