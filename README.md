# Establishment Census Exam Monitoring

Foundational Django dashboard for comparing the expected candidate list with real exam submissions.

## Architecture

- `monitoring.models`: candidate/master-list and temporary submission records.
- `monitoring.services.submissions`: local submission retrieval boundary used by dashboard status calculations.
- `monitoring.services.external_submissions`: read-only reader for `exam_rec`, joining `level-1.id_number` through `level-1-id`.
- `monitoring.services.submission_sync`: idempotent matching and synchronization into the local `Submission` table.
- `monitoring.services.dashboard`: matching and dashboard summary business logic using `national_id`.
- `monitoring.services.candidate_import` and `monitoring.services.dummy_submissions`: data-loading business logic.
- `accounts.services.authentication`: staff account creation logic.
- `monitoring.views` and `templates`: presentation only.

The `accounts` app provides staff signup, login, and logout. The dashboard is protected and redirects unauthenticated users to login. New accounts are regular staff users, not administrators.

Management commands are thin Django adapters. Django requires their folder location to expose custom commands, while source reading and synchronization logic lives under `monitoring/services`.

A candidate is submitted when the candidate `national_id` exists in the local `Submission` table. Exam marks and exam-end time are not imported or used for status. Candidate district remains sourced from the expected candidate list.

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

7. Configure the `SUBMISSIONS_DB_*` environment variables for read-only access to the external exam database. Do not run migrations against this database.

8. Review the current matching results without changing data:

   ```powershell
   python manage.py analyze_submission_matches
   ```

   Exact National ID is primary. A corrected ID is considered only for an expected candidate without an exact match, and only when normalized name, phone, district, sector, and cell identify exactly one expected candidate and exactly one external record. Ambiguous and unmatched external rows do not create candidates. The Submission row remains keyed by the expected candidate ID and stores the source ID, source record ID, external name, phone, and resolved district/sector/cell. Repeated exact-ID rows use the highest `exam_rec-id` as the displayed source record. The bundled `monitoring/data/rwanda_admin_locations.csv` is derived from the authoritative `All_Rwanda.xls` hierarchy; conflicting code labels are not resolved.

9. Read and synchronize real submissions:

   ```powershell
   python manage.py sync_submissions
   ```

   Synchronization reads the current external rows, matches exact IDs first, then applies only unique corrected-ID matches, and updates the local `Submission` table without writing to the external database. It is safe to repeat: unchanged local rows are not rewritten, and a MySQL advisory lock skips overlapping runs. The expected candidate list remains the source of the dashboard population.

   The scheduled command should be `python manage.py sync_submissions` with no pruning option. Each run currently reads the full external set because a newly arrived row can make a previously unique corrected-ID match ambiguous, and external rows may be updated in place. A simple `exam_rec-id` high-water mark could miss those changes and would weaken matching safety. Unchanged matches do not cause local writes.

   To remove stale or dummy local rows so the local table exactly reflects current external matches, explicitly run:

   ```powershell
   python manage.py sync_submissions --prune-stale
   ```

   This option deletes unmatched rows only from the local `Submission` table; review the command summary before using it.
   Existing submissions for candidates involved in ambiguous corrected-ID matches are preserved for manual review.

10. Run focused tests and start the server:

   ```powershell
   python manage.py test
   python manage.py runserver
   ```

## Local Windows development sync

On the Windows development machine, register the one-minute current-user task with:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& .\scripts\setup_submission_sync_task.ps1
```

The task runs while that Windows user is logged in and uses the project `.venv`. It is allowed to run on battery and writes daily logs under `logs/`. The MySQL advisory lock prevents overlapping synchronization, and unchanged submissions are not rewritten. To start a run immediately, use `Start-ScheduledTask -TaskName "Establishment Census Exam Submission Sync"`. Inspect it with `Get-ScheduledTask -TaskName "Establishment Census Exam Submission Sync"` and remove it with `Unregister-ScheduledTask -TaskName "Establishment Census Exam Submission Sync" -Confirm:$false`. Do not add `--prune-stale` to the scheduled command.

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

Candidate lists use server-side pagination with 25 records per page. A candidate is submitted only when a matching `national_id` exists in the synchronized local submissions.

## Assumptions

- Each worksheet represents one district, so the worksheet name is used as the district and normalized to title case.
- The importer detects the candidate header row because the workbook has different metadata rows across sheets.
- The first ten meaningful columns are mapped to the candidate details, while extra worksheet columns are ignored.
- `registered_location` is currently stored as `sector / cell`; submission location is stored separately for later validation.
- The exam date is supplied during import because the workbook does not provide one consistent date field.

The exam database reader uses the `submissions_db` Django connection and only executes `SELECT` queries. External district codes are used for validation; the expected Candidate district is never overwritten.
