import streamlit as st
from supabase import create_client, Client
import os

st.set_page_config(
    page_title="AGC Management System",
    page_icon="🏢",
    layout="wide"
)

# Supabase connection
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def connect_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = connect_supabase()

st.title("AGC Management System")

# Session
if "user" not in st.session_state:
    st.session_state.user = None

if "profile" not in st.session_state:
    st.session_state.profile = None

# Login
if st.session_state.user is None:
    st.subheader("Admin Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login", type="primary"):
        try:
            result = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            user = result.user

            profile_result = (
                supabase.table("profiles")
                .select("id, username, full_name, role, is_active")
                .eq("id", user.id)
                .single()
                .execute()
            )

            profile = profile_result.data

            if not profile["is_active"]:
                supabase.auth.sign_out()
                st.error("Your account is inactive.")
            elif profile["role"] != "admin":
                supabase.auth.sign_out()
                st.error("Admin access only.")
            else:
                st.session_state.user = user
                st.session_state.profile = profile
                st.rerun()

        except Exception as e:
            st.error(f"Login failed: {e}")

# Admin dashboard
else:
    profile = st.session_state.profile

    st.success(f"Welcome, {profile['full_name']}")
    st.caption("Administrator Dashboard")

    if st.sidebar.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.profile = None
        st.rerun()

    st.sidebar.title("AGC Menu")

    page = st.sidebar.radio(
        "Select Module",
        [
            "Dashboard",
            "Employees",
            "Salary Records",
            "Vehicles",
            "Drivers",
            "Driver Advances",
            "Petty Cash",
            "Accommodations",
            "Rent Payments",
            "Utility Bills",
            "Office Expenses",
            "Reminders"
        ]
    )

    if page == "Dashboard":
        st.title("Main Dashboard")
        st.write("Welcome to AGC Management System")
        st.info("Management modules will be connected here.")

    else:
        st.title(page)
        st.info(f"{page} module is ready for database integration.")
