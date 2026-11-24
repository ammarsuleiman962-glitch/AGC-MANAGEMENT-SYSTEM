import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import date
from decimal import Decimal

st.set_page_config(
    page_title="AGC Management System",
    page_icon="🏢",
    layout="wide"
)

# =====================================
# 1. SUPABASE CONNECTION
# =====================================

@st.cache_resource
def connect_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

supabase = connect_supabase()

# =====================================
# 2. DATABASE MODULE CONFIGURATION
# =====================================

MODULES = {
    "Employees": {
        "table": "employees",
        "fields": [
            ("full_name", "text"),
            ("mobile", "text"),
            ("iqama_number", "text"),
            ("iqama_expiry", "date"),
            ("job_title", "text"),
            ("monthly_salary", "number"),
            ("monthly_iqama_expense", "number"),
            ("is_active", "boolean"),
            ("notes", "text")
        ]
    },
    "Salary Records": {
        "table": "salary_records",
        "fields": [
            ("employee_id", "fk:employees"),
            ("salary_month", "date"),
            ("amount_due", "number"),
            ("amount_paid", "number"),
            ("due_date", "date"),
            ("payment_date", "date"),
            ("status", "select:Unpaid,Partial,Paid"),
            ("notes", "text")
        ]
    },
    "Vehicles": {
        "table": "vehicles",
        "fields": [
            ("vehicle_name", "text"),
            ("plate_number", "text"),
            ("notes", "text"),
            ("is_active", "boolean")
        ]
    },
    "Drivers": {
        "table": "drivers",
        "fields": [
            ("full_name", "text"),
            ("mobile", "text"),
            ("notes", "text"),
            ("is_active", "boolean")
        ]
    },
    "Driver Advances": {
        "table": "driver_advances",
        "fields": [
            ("driver_id", "fk:drivers"),
            ("vehicle_id", "fk:vehicles"),
            ("amount", "number"),
            ("advance_date", "date"),
            ("description", "text")
        ]
    },
    "Petty Cash Fund": {
        "table": "petty_cash_fund",
        "fields": [
            ("transaction_type", "select:IN,OUT"),
            ("amount", "number"),
            ("transaction_date", "date"),
            ("description", "text")
        ]
    },
    "Petty Cash Expenses": {
        "table": "petty_cash_expenses",
        "fields": [
            ("driver_id", "fk:drivers"),
            ("vehicle_id", "fk:vehicles"),
            ("category", "select:Maintenance,Oil Change,Tyre Change,Fuel,Other"),
            ("amount", "number"),
            ("expense_date", "date"),
            ("description", "text")
        ]
    },
    "Accommodations": {
        "table": "accommodations",
        "fields": [
            ("accommodation_name", "text"),
            ("address", "text"),
            ("monthly_rent", "number"),
            ("payment_frequency", "select:Monthly,Quarterly,Half-Yearly,Yearly"),
            ("next_due_date", "date"),
            ("notes", "text"),
            ("is_active", "boolean")
        ]
    },
    "Rent Payments": {
        "table": "accommodation_rent_payments",
        "fields": [
            ("accommodation_id", "fk:accommodations"),
            ("amount_due", "number"),
            ("amount_paid", "number"),
            ("due_date", "date"),
            ("payment_date", "date"),
            ("status", "select:Unpaid,Partial,Paid"),
            ("notes", "text")
        ]
    },
    "Utility Bills": {
        "table": "utility_bills",
        "fields": [
            ("accommodation_id", "fk:accommodations"),
            ("bill_type", "text"),
            ("amount", "number"),
            ("bill_date", "date"),
            ("due_date", "date"),
            ("payment_date", "date"),
            ("status", "select:Unpaid,Pending,Paid"),
            ("description", "text")
        ]
    },
    "Office Expenses": {
        "table": "office_expenses",
        "fields": [
            ("category", "text"),
            ("amount", "number"),
            ("expense_date", "date"),
            ("due_date", "date"),
            ("payment_date", "date"),
            ("status", "select:Unpaid,Pending,Paid"),
            ("description", "text")
        ]
    },
    "Reminders": {
        "table": "reminders",
        "fields": [
            ("title", "text"),
            ("message", "text"),
            ("reminder_date", "date"),
            ("related_type", "text"),
            ("related_id", "text"),
            ("is_completed", "boolean")
        ]
    }
}

# =====================================
# 3. DATABASE FUNCTIONS
# =====================================

def get_data(table):
    try:
        return (
            supabase.table(table)
            .select("*")
            .execute().data
        )
    except Exception as e:
        st.error(f"Database Error: {e}")
        return []


def get_foreign_options(table):
    rows = get_data(table)
    return {
        str(row["id"]): row
        for row in rows
    }


def make_form_field(field, field_type, old=None):
    old = old or {}
    value = old.get(field)

    if field_type == "text":
        return st.text_input(
            field.replace("_", " ").title(),
            value=str(value or "")
        )

    elif field_type == "number":
        return st.number_input(
            field.replace("_", " ").title(),
            min_value=0.0,
            value=float(value or 0),
            step=1.0
        )

    elif field_type == "date":
        if value:
            try:
                default = date.fromisoformat(str(value)[:10])
            except ValueError:
                default = date.today()
        else:
            default = date.today()

        return st.date_input(
            field.replace("_", " ").title(),
            value=default
        )

    elif field_type == "boolean":
        return st.checkbox(
            field.replace("_", " ").title(),
            value=bool(value) if value is not None else True
        )

    elif field_type.startswith("select:"):
        options = field_type.split(":")[1].split(",")
        return st.selectbox(
            field.replace("_", " ").title(),
            options,
            index=options.index(value)
            if value in options else 0
        )

    elif field_type.startswith("fk:"):
        table = field_type.split(":")[1]
        options = get_foreign_options(table)

        if not options:
            st.warning(f"No records found in {table}.")
            return None

        ids = list(options.keys())

        labels = [
            str(
                options[x].get("full_name")
                or options[x].get("accommodation_name")
                or options[x].get("vehicle_name")
                or x
            )
            for x in ids
        ]

        selected = (
            ids.index(str(value))
            if value and str(value) in ids else 0
        )

        choice = st.selectbox(
            field.replace("_", " ").title(),
            range(len(ids)),
            format_func=lambda i: labels[i],
            index=selected
        )

        return ids[choice]


# =====================================
# 4. ADD / EDIT / DELETE MODULE
# =====================================

def module_page(name, config):

    table = config["table"]

    st.title(name)

    tab1, tab2, tab3 = st.tabs([
        "Add New",
        "View / Edit",
        "Delete"
    ])

    # ADD RECORD
    with tab1:
        st.subheader(f"Add New {name}")

        with st.form(f"add_{table}"):

            data = {}

            for field, field_type in config["fields"]:
                data[field] = make_form_field(
                    field, field_type
                )

            submitted = st.form_submit_button(
                "Save Record",
                type="primary"
            )

            if submitted:
                try:
                    if any(
                        data[f] is None
                        for f, t in config["fields"]
                        if t.startswith("fk:")
                    ):
                        st.error("Please add the required related record first.")
                    else:
                        result = (
                            supabase.table(table)
                            .insert(data)
                            .execute()
                        )

                        st.success("Record saved successfully!")
                        st.rerun()

                except Exception as e:
                    st.error(f"Save failed: {e}")

    # VIEW AND EDIT
    with tab2:

        rows = get_data(table)

        if rows:

            df = pd.DataFrame(rows)

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            ids = [str(r["id"]) for r in rows]

            selected_id = st.selectbox(
                "Select Record to Edit",
                ids,
                format_func=lambda x: (
                    next(
                        (
                            str(r.get("full_name")
                            or r.get("vehicle_name")
                            or r.get("accommodation_name")
                            or r.get("title")
                            or r["id"])
                            for r in rows
                            if str(r["id"]) == x
                        ),
                        x
                    )
                )
            )

            old = next(
                r for r in rows
                if str(r["id"]) == selected_id
            )

            with st.form(f"edit_{table}"):

                updated = {}

                for field, field_type in config["fields"]:
                    updated[field] = make_form_field(
                        field, field_type, old
                    )

                save = st.form_submit_button(
                    "Update Record",
                    type="primary"
                )

                if save:
                    try:
                        supabase.table(table).update(
                            updated
                        ).eq("id", selected_id).execute()

                        st.success("Record updated successfully!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Update failed: {e}")

        else:
            st.info("No records available yet.")

    # DELETE RECORD
    with tab3:

        rows = get_data(table)

        if rows:

            ids = [str(r["id"]) for r in rows]

            delete_id = st.selectbox(
                "Select Record to Delete",
                ids,
                key=f"delete_{table}"
            )

            if st.button(
                "Delete Record",
                type="primary",
                key=f"confirm_delete_{table}"
            ):

                try:
                    supabase.table(table).delete().eq(
                        "id", delete_id
                    ).execute()

                    st.success("Record deleted successfully!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Delete failed: {e}")

        else:
            st.info("No records available.")


# =====================================
# 5. ADMIN LOGIN
# =====================================

if "user" not in st.session_state:
    st.session_state.user = None

if "profile" not in st.session_state:
    st.session_state.profile = None


if st.session_state.user is None:

    st.title("AGC Management System")
    st.subheader("Administrator Login")

    email = st.text_input("Email")
    password = st.text_input(
        "Password",
        type="password"
    )

    if st.button("Login", type="primary"):

        try:
            result = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            user = result.user

            profile = (
                supabase.table("profiles")
                .select("*")
                .eq("id", user.id)
                .single()
                .execute()
                .data
            )

            if profile["is_active"] and profile["role"] == "admin":

                st.session_state.user = user
                st.session_state.profile = profile
                st.rerun()

            else:
                supabase.auth.sign_out()
                st.error("Admin access only.")

        except Exception as e:
            st.error(f"Login failed: {e}")


# =====================================
# 6. MAIN MANAGEMENT SYSTEM
# =====================================

else:

    profile = st.session_state.profile

    st.sidebar.title("AGC Management")
    st.sidebar.success(
        f"Welcome {profile['full_name']}"
    )

    if st.sidebar.button("Logout"):

        supabase.auth.sign_out()

        st.session_state.user = None
        st.session_state.profile = None

        st.rerun()

    page = st.sidebar.radio(
        "Select Module",
        ["Dashboard"] + list(MODULES.keys())
    )

    # =================================
    # 7. LIVE DASHBOARD
    # =================================

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

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Total Employees",
            len(employees)
        )

        c2.metric(
            "Active Employees",
            sum(
                1 for x in employees
                if x.get("is_active")
            )
        )

        c3.metric(
            "Total Vehicles",
            len(vehicles)
        )

        c4.metric(
            "Total Drivers",
            len(drivers)
        )

        def total(rows, field):
            return sum(
                float(r.get(field) or 0)
                for r in rows
            )

        c5, c6, c7, c8 = st.columns(4)

        c5.metric(
            "Monthly Salary (SAR)",
            f"{total(employees, 'monthly_salary'):,.2f}"
        )

        c6.metric(
            "Salary Outstanding (SAR)",
            f"{sum(max(0, float(r.get('amount_due') or 0) - float(r.get('amount_paid') or 0)) for r in salaries):,.2f}"
        )

        c7.metric(
            "Driver Advances (SAR)",
            f"{total(advances, 'amount'):,.2f}"
        )

        c8.metric(
            "Petty Cash Expenses (SAR)",
            f"{total(expenses, 'amount'):,.2f}"
        )

        st.subheader("Outstanding Payments")

        st.write(
            "Rent Outstanding:",
            f"{sum(max(0, float(r.get('amount_due') or 0) - float(r.get('amount_paid') or 0)) for r in rent):,.2f} SAR"
        )

        st.write(
            "Unpaid Utility Bills:",
            f"{sum(float(r.get('amount') or 0) for r in utilities if r.get('status') != 'Paid'):,.2f} SAR"
        )

        st.write(
            "Office Expenses:",
            f"{total(office, 'amount'):,.2f} SAR"
        )

        st.subheader("Employee Records")

        if employees:
            st.dataframe(
                pd.DataFrame(employees),
                use_container_width=True
            )
        else:
            st.info("No employee records yet.")

    # =================================
    # 8. ALL MODULES
    # =================================

    else:

        module_page(
            page,
            MODULES[page]
        )
