-- Initial database schema
-- Currency: Saudi Riyal (SAR)

create extension if not exists pgcrypto;

-- 1. User profiles and roles
create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    username text unique not null,
    full_name text not null,
    role text not null default 'employee'
        check (role in ('admin', 'employee')),
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

-- 2. Employees
create table if not exists public.employees (
    id uuid primary key default gen_random_uuid(),
    full_name text not null,
    mobile text,
    iqama_number text unique,
    iqama_expiry date,
    job_title text,
    monthly_salary numeric(12,2) not null default 0
        check (monthly_salary >= 0),
    monthly_iqama_expense numeric(12,2) not null default 0
        check (monthly_iqama_expense >= 0),
    is_active boolean not null default true,
    notes text,
    created_at timestamptz not null default now()
);

-- 3. Salary records
create table if not exists public.salary_records (
    id uuid primary key default gen_random_uuid(),
    employee_id uuid not null references public.employees(id),
    salary_month date not null,
    amount_due numeric(12,2) not null check (amount_due >= 0),
    amount_paid numeric(12,2) not null default 0
        check (amount_paid >= 0),
    due_date date not null,
    payment_date date,
    status text not null default 'Unpaid'
        check (status in ('Unpaid', 'Partial', 'Paid')),
    notes text,
    created_at timestamptz not null default now(),
    unique(employee_id, salary_month),
    check (amount_paid <= amount_due)
);

-- 4. Vehicles
create table if not exists public.vehicles (
    id uuid primary key default gen_random_uuid(),
    vehicle_name text not null,
    plate_number text unique not null,
    notes text,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

-- 5. Drivers
create table if not exists public.drivers (
    id uuid primary key default gen_random_uuid(),
    full_name text not null,
    mobile text,
    notes text,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

-- 6. Driver advances
create table if not exists public.driver_advances (
    id uuid primary key default gen_random_uuid(),
    driver_id uuid not null references public.drivers(id),
    vehicle_id uuid references public.vehicles(id),
    amount numeric(12,2) not null check (amount > 0),
    advance_date date not null default current_date,
    description text,
    created_at timestamptz not null default now()
);

-- 7. Petty cash fund transactions
create table if not exists public.petty_cash_fund (
    id uuid primary key default gen_random_uuid(),
    transaction_type text not null
        check (transaction_type in ('IN', 'OUT')),
    amount numeric(12,2) not null check (amount > 0),
    transaction_date date not null default current_date,
    description text,
    created_at timestamptz not null default now()
);

-- 8. Petty cash expenses
create table if not exists public.petty_cash_expenses (
    id uuid primary key default gen_random_uuid(),
    driver_id uuid references public.drivers(id),
    vehicle_id uuid references public.vehicles(id),
    category text not null
        check (category in (
            'Maintenance', 'Oil Change', 'Tyre Change',
            'Fuel', 'Other'
        )),
    amount numeric(12,2) not null check (amount > 0),
    expense_date date not null default current_date,
    description text,
    created_at timestamptz not null default now()
);

-- 9. Accommodations
create table if not exists public.accommodations (
    id uuid primary key default gen_random_uuid(),
    accommodation_name text not null,
    address text,
    monthly_rent numeric(12,2) not null default 0
        check (monthly_rent >= 0),
    payment_frequency text not null default 'Monthly'
        check (payment_frequency in (
            'Monthly', 'Quarterly', 'Half-Yearly', 'Yearly'
        )),
    next_due_date date,
    notes text,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

-- 10. Accommodation rent payments
create table if not exists public.accommodation_rent_payments (
    id uuid primary key default gen_random_uuid(),
    accommodation_id uuid not null
        references public.accommodations(id),
    amount_due numeric(12,2) not null check (amount_due >= 0),
    amount_paid numeric(12,2) not null default 0
        check (amount_paid >= 0),
    due_date date not null,
    payment_date date,
    status text not null default 'Unpaid'
        check (status in ('Unpaid', 'Partial', 'Paid')),
    notes text,
    created_at timestamptz not null default now(),
    check (amount_paid <= amount_due)
);

-- 11. Utility bills
create table if not exists public.utility_bills (
    id uuid primary key default gen_random_uuid(),
    accommodation_id uuid references public.accommodations(id),
    bill_type text not null,
    amount numeric(12,2) not null check (amount >= 0),
    bill_date date,
    due_date date not null,
    payment_date date,
    status text not null default 'Unpaid'
        check (status in ('Unpaid', 'Pending', 'Paid')),
    description text,
    created_at timestamptz not null default now()
);

-- 12. Office expenses
create table if not exists public.office_expenses (
    id uuid primary key default gen_random_uuid(),
    category text not null,
    amount numeric(12,2) not null check (amount >= 0),
    expense_date date not null default current_date,
    due_date date,
    payment_date date,
    status text not null default 'Paid'
        check (status in ('Unpaid', 'Pending', 'Paid')),
    description text,
    created_at timestamptz not null default now()
);

-- 13. Reminder records
create table if not exists public.reminders (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    message text,
    reminder_date date not null,
    related_type text,
    related_id uuid,
    is_completed boolean not null default false,
    created_at timestamptz not null default now()
);

-- Enable Row Level Security on all tables
alter table public.profiles enable row level security;
alter table public.employees enable row level security;
alter table public.salary_records enable row level security;
alter table public.vehicles enable row level security;
alter table public.drivers enable row level security;
alter table public.driver_advances enable row level security;
alter table public.petty_cash_fund enable row level security;
alter table public.petty_cash_expenses enable row level security;
alter table public.accommodations enable row level security;
alter table public.accommodation_rent_payments enable row level security;
alter table public.utility_bills enable row level security;
alter table public.office_expenses enable row level security;
alter table public.reminders enable row level security;

-- Initial policies: authenticated users can read records.
-- Admin-only write policies will be added after user setup.
create policy "Authenticated users can read profiles"
on public.profiles for select to authenticated
using (true);

create policy "Authenticated users can read employees"
on public.employees for select to authenticated
using (true);

create policy "Authenticated users can read salary records"
on public.salary_records for select to authenticated
using (true);

create policy "Authenticated users can read vehicles"
on public.vehicles for select to authenticated
using (true);

create policy "Authenticated users can read drivers"
on public.drivers for select to authenticated
using (true);

create policy "Authenticated users can read driver advances"
on public.driver_advances for select to authenticated
using (true);

create policy "Authenticated users can read petty cash fund"
on public.petty_cash_fund for select to authenticated
using (true);

create policy "Authenticated users can read petty cash expenses"
on public.petty_cash_expenses for select to authenticated
using (true);

create policy "Authenticated users can read accommodations"
on public.accommodations for select to authenticated
using (true);

create policy "Authenticated users can read rent payments"
on public.accommodation_rent_payments for select to authenticated
using (true);

create policy "Authenticated users can read utility bills"
on public.utility_bills for select to authenticated
using (true);

create policy "Authenticated users can read office expenses"
on public.office_expenses for select to authenticated
using (true);

create policy "Authenticated users can read reminders"
on public.reminders for select to authenticated
using (true);
