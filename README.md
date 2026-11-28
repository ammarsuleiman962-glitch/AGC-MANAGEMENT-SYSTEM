# AGC Management System — Android (Flutter)

Native Android app for the existing AGC Supabase project. Online-only, single administrator login.

## Features included
- Supabase email/password authentication and `profiles` admin/active check
- Dashboard summaries for employees, salary, vehicles, drivers, advances, petty cash, rent, utilities and office expenses
- Add, view, edit and delete for all 12 tables/modules from the existing Streamlit app
- PDF export of the selected module
- Online Supabase data access; no local database or offline mode

## Supabase configuration
`lib/app_config.dart` contains the Supabase project URL and **publishable** client key supplied by the owner. Publishable keys are intended for client apps. Never replace it with a `service_role` or secret key. All access must be protected by Supabase Row Level Security (RLS).

## Required database assumptions
The app expects the tables and columns in the existing `agc_updated_app.py`, including `profiles`, `employees`, `salary_records`, `vehicles`, `drivers`, `driver_advances`, `petty_cash_fund`, `petty_cash_expenses`, `accommodations`, `accommodation_rent_payments`, `utility_bills`, `office_expenses`, and `reminders`. It expects each business table to have an `id` column. The app expects a `created_at` column for ordering; if a table does not have one, remove `.order('created_at', ascending: false)` in `lib/main.dart`.

The admin's `profiles` row must have `role = 'admin'` and `is_active = true`. Existing RLS policies must permit the signed-in admin to select/insert/update/delete these tables. Never disable RLS just to make the app work.

## Build the APK free using GitHub Actions
1. Create a free GitHub repository named `agc-management-android`.
2. Upload the contents of this folder to the repository root (not the folder itself).
3. Open the repository's **Actions** tab and enable workflows if prompted.
4. Select **Build AGC Android APK** → **Run workflow**.
5. When complete, open the successful workflow run, scroll to **Artifacts**, and download `AGC-Management-Android-APK`.
6. Extract the ZIP on your Android phone and install `app-release.apk`. Android may ask permission to install unknown apps.

The APK is built by GitHub's free hosted runner within the free account's usage limits. This workspace does not contain Flutter/Android SDK, so the APK is not precompiled here.

## Local build (optional)
Install Flutter stable and Android Studio/Android SDK, then run:
```bash
flutter pub get
flutter build apk --release
```
APK output: `build/app/outputs/flutter-apk/app-release.apk`.

## Important limitations / next integration pass
- Email notifications require a secure server-side Supabase Edge Function or another email provider; do not place SMTP passwords in the APK. This first Android build includes reminder records in the dashboard but does not send emails.
- Confirm actual SQL column types, RLS policies and foreign-key relationships in the live project before production use. Do not use a service-role key in the client.
