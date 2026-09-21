# Establishment Census Exam Monitoring

Foundational Django dashboard for comparing the official enumerator candidate list with exam submissions. The current submission source is intentionally temporary dummy data.

## Architecture

- `monitoring.models`: candidate/master-list and temporary submission records.
- `monitoring.services.submissions`: submission retrieval boundary. Replace `DjangoSubmissionRepository` when an approved source is available.
- `monitoring.services.dashboard`: matching and dashboard summary business logic using `national_id`.
- `monitoring.services.candidate_import` and `monitoring.services.dummy_submissions`: data-loading business logic.
- `accounts.services.authentication`: staff account creation logic.
- `monitoring.views` and `templates`: presentation only.

The `accounts` app provides staff signup, login, and logout. The dashboard is protected and redirects unauthenticated users to login. New accounts are regular staff users, not administrators.

The two files under `monitoring/management/commands` are intentionally thin Django adapters. Django requires that folder location to expose custom commands, but all actual command logic lives under `monitoring/services`.

A candidate is submitted when the candidate `national_id` exists in the submission repository. Score does not determine submission status, so a score of zero is valid. There is no unknown-candidate workflow.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set the MySQL credentials. The default local fallback is SQLite, which is useful for development before MySQL is configured.
4. Create the MySQL database and user specified in `.env`.
5. Apply migrations:

   ```powershell
   python manage.py migrate
   ```

6. Import the supplied workbook:

   ```powershell
   python manage.py import_candidates_from_excel "C:\Users\user\Downloads\ALL  Lists of enumerators selected for exam at District level.xlsx" --exam-date 2026-10-01
   ```

   Use `--dry-run` to inspect the import count without changing the database.

7. Create dummy submissions:

   ```powershell
   python manage.py seed_dummy_submissions --replace
   ```

8. Run focused tests and start the server:

   ```powershell
   python manage.py test
   python manage.py runserver
   ```

Open `http://127.0.0.1:8000/` to view the dashboard.

Create a staff account at `http://127.0.0.1:8000/accounts/signup/`, then log in to access the dashboard.

## Monitoring routes

- `/` - dashboard summary with clickable district rows.
- `/sites/` - all districts/sites with progress and operational status.
- `/sites/<district>/` - district candidate status, summary cards, search, status filter, and pagination.
- `/reports/` - filtered overall, district, and candidate submission report.
- `/reports/export.csv` - authenticated CSV export using the current report filters.

To test the main workflow manually:

1. Sign up and log in.
2. From the dashboard, click a district row.
3. On the district page, select `Not Submitted` and apply the filter.
4. Use the search box with a candidate name or national ID.
5. Open `Districts / Sites`, select another district, and confirm the counts match the dashboard.
6. Open `Reports`, combine district/status/search filters, and confirm the summary and candidate table update together.
7. Use `Export CSV` and confirm it contains only the filtered candidates; use `Print Report` to open the browser print dialog.

Candidate lists use server-side pagination with 25 records per page. A candidate is submitted only when a matching `national_id` exists in submissions; score `0` remains a valid submitted result.

## Assumptions

- Each worksheet represents one district, so the worksheet name is used as the district and normalized to title case.
- The importer detects the candidate header row because the workbook has different metadata rows across sheets.
- The first ten meaningful columns are mapped to the candidate details, while extra worksheet columns are ignored.
- `registered_location` is currently stored as `sector / cell`; submission location is stored separately for later validation.
- The exam date is supplied during import because the workbook does not provide one consistent date field.

CSWeb and the real exam database are not integrated yet.
