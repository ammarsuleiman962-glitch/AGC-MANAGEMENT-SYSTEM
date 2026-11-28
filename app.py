import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import date, datetime
from calendar import monthrange

# ---------------- CONFIG ----------------
st.set_page_config(page_title="AGC Management", layout="wide")

@st.cache_resource
def get_db():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

db = get_db()

TABLES = [
    "employees", "salary_records", "employee_advances",
    "salary_settlements", "vehicles", "drivers", "driver_advances",
    "petty_cash_fund", "petty_cash_expenses", "accommodations",
    "accommodation_rent_payments", "utility_bills", "office_expenses",
    "iqama_renewals", "iqama_renewal_payments", "reminders",
    "guardian_contacts"
]

def get_data(table):
    try:
        return db.table(table).select("*").execute().data or []
    except Exception as e:
        st.error(f"{table}: {e}")
        return []

def insert(table, data):
    try:
        db.table(table).insert(data).execute()
        st.success("Saved successfully")
        st.rerun()
    except Exception as e:
        st.error(str(e))

def update(table, row_id, data):
    try:
        db.table(table).update(data).eq("id", row_id).execute()
        st.success("Updated successfully")
        st.rerun()
    except Exception as e:
        st.error(str(e))

def delete(table, row_id):
    try:
        db.table(table).delete().eq("id", row_id).execute()
        st.success("Deleted")
        st.rerun()
    except Exception as e:
        st.error(f"Cannot delete this record: {e}")

def frame(table):
    return pd.DataFrame(get_data(table))

def money(value):
    return f"SAR {float(value or 0):,.2f}"

# ---------------- SIDEBAR ----------------
st.sidebar.title("AGC Management")
page = st.sidebar.radio("Menu", [
    "Dashboard",
    "Employees",
    "Salary & Advances",
    "Additional Expenses - Iqama",
    "Other Modules"
])

# ---------------- DASHBOARD ----------------
if page == "Dashboard":
    st.title("Management Dashboard")

    employees = frame("employees")
    salaries = frame("salary_records")
    advances = frame("employee_advances")
    renewals = frame("iqama_renewals")
    vehicles = frame("vehicles")
    drivers = frame("drivers")
    rent = frame("accommodation_rent_payments")
    utilities = frame("utility_bills")
    office = frame("office_expenses")
    reminders = frame("reminders")

    def total(df, col):
        return pd.to_numeric(df[col], errors="coerce").fillna(0).sum() if col in df else 0

    active = employees[
        employees["is_active"] == True
    ] if not employees.empty and "is_active" in employees else employees

    salary_due = total(salaries, "amount_due")
    salary_paid = total(salaries, "amount_paid")
    salary_outstanding = max(0, salary_due - salary_paid)

    advance_total = total(advances, "amount")
    iqama_outstanding = total(renewals, "outstanding_amount")

    rent_outstanding = (
        total(rent, "amount_due") - total(rent, "amount_paid")
    )
    utility_outstanding = total(
        utilities[utilities["status"] != "Paid"], "amount"
    ) if not utilities.empty and "status" in utilities else 0

    office_outstanding = total(
        office[office["status"] != "Paid"], "amount"
    ) if not office.empty and "status" in office else 0

    cols = st.columns(4)
    cols[0].metric("Employees", len(employees))
    cols[1].metric("Active Employees", len(active))
    cols[2].metric("Vehicles", len(vehicles))
    cols[3].metric("Drivers", len(drivers))

    cols = st.columns(4)
    cols[0].metric("Monthly Salary", money(total(active, "monthly_salary")))
    cols[1].metric("Salary Outstanding", money(salary_outstanding))
    cols[2].metric("Employee Advances", money(advance_total))
    cols[3].metric("Iqama Outstanding", money(iqama_outstanding))

    cols = st.columns(4)
    cols[0].metric("Rent Outstanding", money(rent_outstanding))
    cols[1].metric("Utility Bills", money(utility_outstanding))
    cols[2].metric("Office Expenses Outstanding", money(office_outstanding))
    cols[3].metric("Reminders", len(reminders))

    st.subheader("Recent Salary Records")
    st.dataframe(salaries.tail(10), use_container_width=True)

# ---------------- EMPLOYEES ----------------
elif page == "Employees":
    st.title("Employee Management")
    df = frame("employees")

    with st.expander("Add Employee"):
        with st.form("employee_form"):
            name = st.text_input("Full Name")
            mobile = st.text_input("Mobile")
            iqama = st.text_input("Iqama Number")
            expiry = st.date_input("Iqama Expiry", value=None)
            job = st.text_input("Job Title")
            salary = st.number_input("Monthly Salary", min_value=0.0)
            iqama_cost = st.number_input("Monthly Iqama Expense", min_value=0.0)
            notes = st.text_area("Notes")
            active = st.checkbox("Active", value=True)

            if st.form_submit_button("Save Employee"):
                if name.strip():
                    insert("employees", {
                        "full_name": name,
                        "mobile": mobile,
                        "iqama_number": iqama,
                        "iqama_expiry": str(expiry) if expiry else None,
                        "job_title": job,
                        "monthly_salary": salary,
                        "monthly_iqama_expense": iqama_cost,
                        "notes": notes,
                        "is_active": active
                    })
                else:
                    st.warning("Enter employee name")

    st.subheader("Employee List")
    st.dataframe(df, use_container_width=True)

    if not df.empty:
        selected = st.selectbox(
            "Select Employee",
            df.to_dict("records"),
            format_func=lambda x: x["full_name"]
        )
        with st.expander("Edit / Delete Employee"):
            new_name = st.text_input("Name", selected["full_name"])
            new_mobile = st.text_input("Mobile", selected.get("mobile") or "")
            new_salary = st.number_input(
                "Monthly Salary",
                min_value=0.0,
                value=float(selected.get("monthly_salary") or 0)
            )
            if st.button("Update Employee"):
                update("employees", selected["id"], {
                    "full_name": new_name,
                    "mobile": new_mobile,
                    "monthly_salary": new_salary
                })
            if st.button("Delete Employee"):
                st.warning("Deletion may be blocked if related records exist.")
                if st.checkbox("Confirm employee deletion"):
                    delete("employees", selected["id"])

# ---------------- SALARY & ADVANCES ----------------
elif page == "Salary & Advances":
    st.title("Salary & Employee Advances")

    employees = get_data("employees")
    if not employees:
        st.warning("Add employees first.")
        st.stop()

    emp = st.selectbox(
        "Employee",
        employees,
        format_func=lambda x: x["full_name"]
    )

    st.subheader("Give Employee Advance")
    with st.form("advance_form"):
        amount = st.number_input("Advance Amount", min_value=0.01)
        adv_date = st.date_input("Advance Date")
        description = st.text_input("Description")
        if st.form_submit_button("Save Advance"):
            insert("employee_advances", {
                "employee_id": emp["id"],
                "transaction_type": "ADVANCE",
                "amount": amount,
                "transaction_date": str(adv_date),
                "description": description
            })

    st.subheader("Create Monthly Salary Record")
    with st.form("salary_form"):
        month = st.date_input("Salary Month", value=date.today().replace(day=1))
        due = st.number_input(
            "Salary Due",
            min_value=0.0,
            value=float(emp.get("monthly_salary") or 0)
        )
        due_date = st.date_input("Payment Due Date")
        if st.form_submit_button("Create Salary"):
            month_start = month.replace(day=1)
            existing = db.table("salary_records").select("id").eq(
                "employee_id", emp["id"]
            ).eq("salary_month", str(month_start)).execute().data

            if existing:
                st.warning("Salary record already exists for this month.")
            else:
                insert("salary_records", {
                    "employee_id": emp["id"],
                    "salary_month": str(month_start),
                    "amount_due": due,
                    "amount_paid": 0,
                    "due_date": str(due_date),
                    "status": "Unpaid"
                })

    st.subheader("Salary Payment")
    salaries = db.table("salary_records").select("*").eq(
        "employee_id", emp["id"]
    ).execute().data

    if salaries:
        salary = st.selectbox(
            "Select Salary Record",
            salaries,
            format_func=lambda x: f"{x['salary_month']} - {money(x['amount_due'])}"
        )

        with st.form("settlement_form"):
            advance_deducted = st.number_input("Advance Deduction", min_value=0.0)
            cash_paid = st.number_input("Cash Paid", min_value=0.0)
            payment_date = st.date_input("Payment Date")
            notes = st.text_input("Notes")

            if st.form_submit_button("Settle Salary"):
                total_paid = advance_deducted + cash_paid
                remaining = float(salary["amount_due"]) - float(salary["amount_paid"])

                if total_paid <= 0 or total_paid > remaining:
                    st.error(f"Payment must be greater than zero and not exceed {money(remaining)}.")
                else:
                    new_paid = float(salary["amount_paid"]) + total_paid
                    status = "Paid" if new_paid >= float(salary["amount_due"]) else "Partial"

                    try:
                        db.table("salary_settlements").insert({
                            "salary_record_id": salary["id"],
                            "employee_id": emp["id"],
                            "advance_deducted": advance_deducted,
                            "cash_paid": cash_paid,
                            "total_settled": total_paid,
                            "payment_date": str(payment_date),
                            "notes": notes
                        }).execute()

                        db.table("salary_records").update({
                            "amount_paid": new_paid,
                            "payment_date": str(payment_date),
                            "status": status
                        }).eq("id", salary["id"]).execute()

                        if advance_deducted > 0:
                            db.table("employee_advances").insert({
                                "employee_id": emp["id"],
                                "transaction_type": "DEDUCTION",
                                "amount": advance_deducted,
                                "transaction_date": str(payment_date),
                                "salary_record_id": salary["id"],
                                "description": "Salary advance deduction"
                            }).execute()

                        st.success("Salary payment recorded")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Payment could not be completed: {e}")

    st.subheader("Employee Advance History")
    st.dataframe(
        frame("employee_advances").query(
            "employee_id == @emp['id']"
        ) if not frame("employee_advances").empty else pd.DataFrame(),
        use_container_width=True
    )

# ---------------- IQAMA ADDITIONAL EXPENSES ----------------
elif page == "Additional Expenses - Iqama":
    st.title("Iqama Renewals")
    st.info("Iqama fee is SAR 1,500 per month. It is separate from employee salary.")

    employees = get_data("employees")
    if not employees:
        st.warning("Add employees first.")
        st.stop()

    emp = st.selectbox(
        "Employee",
        employees,
        format_func=lambda x: x["full_name"]
    )

    months = st.selectbox("Renewal Period", [3, 6, 9, 12])
    rate = 1500
    required = months * rate

    st.metric("Required Iqama Fee", money(required))

    with st.form("iqama_form"):
        renewal_date = st.date_input("Renewal Date")
        paid = st.number_input("Amount Paid", min_value=0.0, max_value=float(required))
        notes = st.text_input("Notes")

        if st.form_submit_button("Save Renewal"):
            old_expiry = emp.get("iqama_expiry")
            base = old_expiry if old_expiry and date.fromisoformat(old_expiry) > renewal_date else str(renewal_date)
            base_date = date.fromisoformat(base)

            new_month = base_date.month - 1 + months
            year = base_date.year + new_month // 12
            month = new_month % 12 + 1
            day = min(base_date.day, monthrange(year, month)[1])
            new_expiry = date(year, month, day)

            outstanding = required - paid
            status = "Paid" if outstanding == 0 else ("Partial" if paid > 0 else "Unpaid")

            try:
                renewal = db.table("iqama_renewals").insert({
                    "employee_id": emp["id"],
                    "renewal_months": months,
                    "monthly_rate": rate,
                    "required_amount": required,
                    "amount_paid": paid,
                    "outstanding_amount": outstanding,
                    "renewal_date": str(renewal_date),
                    "old_iqama_expiry": old_expiry,
                    "new_iqama_expiry": str(new_expiry),
                    "status": status,
                    "notes": notes
                }).execute().data[0]

                if paid > 0:
                    db.table("iqama_renewal_payments").insert({
                        "renewal_id": renewal["id"],
                        "employee_id": emp["id"],
                        "amount_paid": paid,
                        "payment_date": str(renewal_date),
                        "notes": notes
                    }).execute()

                db.table("employees").update({
                    "iqama_expiry": str(new_expiry)
                }).eq("id", emp["id"]).execute()

                st.success(f"Iqama renewal saved. New expiry: {new_expiry}")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    st.subheader("Record Additional Iqama Payment")
    renewals = db.table("iqama_renewals").select("*").eq(
        "employee_id", emp["id"]
    ).execute().data

    if renewals:
        renewal = st.selectbox(
            "Select Renewal",
            renewals,
            format_func=lambda x: f"{x['renewal_date']} - Outstanding {money(x['outstanding_amount'])}"
        )

        with st.form("iqama_payment"):
            payment = st.number_input("Payment Amount", min_value=0.01)
            payment_date = st.date_input("Payment Date")
            if st.form_submit_button("Record Payment"):
                outstanding = float(renewal["outstanding_amount"] or 0)
                if payment > outstanding:
                    st.error("Payment exceeds outstanding amount.")
                else:
                    new_paid = float(renewal["amount_paid"]) + payment
                    new_outstanding = outstanding - payment
                    status = "Paid" if new_outstanding == 0 else "Partial"

                    try:
                        db.table("iqama_renewal_payments").insert({
                            "renewal_id": renewal["id"],
                            "employee_id": emp["id"],
                            "amount_paid": payment,
                            "payment_date": str(payment_date)
                        }).execute()

                        db.table("iqama_renewals").update({
                            "amount_paid": new_paid,
                            "outstanding_amount": new_outstanding,
                            "status": status
                        }).eq("id", renewal["id"]).execute()

                        st.success("Payment saved")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    st.subheader("Renewal History")
    st.dataframe(pd.DataFrame(renewals), use_container_width=True)

# ---------------- OTHER EXISTING MODULES ----------------
elif page == "Other Modules":
    st.title("Other Management Modules")

    table = st.selectbox("Select Module", TABLES)
    data = get_data(table)
    df = pd.DataFrame(data)

    st.subheader(table.replace("_", " ").title())
    st.dataframe(df, use_container_width=True)

    st.caption("Add records below. Use the table's existing column names.")

    if table not in ["employees", "salary_records", "employee_advances",
                     "salary_settlements", "iqama_renewals",
                     "iqama_renewal_payments"]:
        with st.expander("Add Record"):
            if not df.empty:
                columns = [c for c in df.columns if c not in ["id", "created_at"]]
            else:
                st.warning("No existing rows found to detect columns. Add records through the dedicated module or configure table fields.")
                columns = []

            values = {}
            for col in columns:
                value = st.text_input(col)
                if value.strip():
                    values[col] = value

            if st.button("Save Record"):
                if values:
                    insert(table, values)
                else:
                    st.warning("Enter at least one value.")

    if not df.empty and "id" in df.columns:
        selected_id = st.selectbox("Record ID", df["id"].tolist())
        if st.button("Delete Selected Record"):
            st.warning("Only delete records you are sure are not needed.")
            if st.checkbox("Confirm deletion"):
                delete(table, selected_id)
