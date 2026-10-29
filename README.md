# BDSP — Business Development, Scheduling & Proposals

A Django + htmx web app for Dr. Sauer & Partners (tunnels and underground
structures) to write proposals, build granular fee estimates, lay out Gantt
schedules, track estimate vs. actual on won work, keep client/contact records
and showcase past projects.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed --demo     # defaults + sample data; creates admin / admin
python manage.py runserver
```

Open http://127.0.0.1:8000, sign in as `admin` / `admin` (change this in
`/admin/`), then go to **Company settings** to upload the logo, pick the default
currency, and set the project-number format.

`python manage.py seed` (without `--demo`) loads only the defaults: currencies
(CAD default, USD, EUR, GBP, CHF, ILS, AUD), the service catalogue, role rate
card, eleven example employees with rates, and three proposal templates. It is
safe to re-run.

### Postgres

```bash
docker compose up -d                      # local Postgres 16
export DATABASE_URL=postgres://bdsp:bdsp@localhost:5432/bdsp
python manage.py migrate && python manage.py seed
```

Without `DATABASE_URL` the app falls back to SQLite. See `.env.example` for
the production variables.

## What's inside

| Area | What you can do |
| --- | --- |
| **Dashboard** | Open pursuits, pipeline and weighted value, win rate, due dates, upcoming milestones |
| **Proposals** | Create from a template, edit sections inline (add / remove / reorder), placeholders such as `{{client_name}}`, status pipeline (lead → won/lost), list and Kanban board views, duplicate, delete |
| **Fee estimate** | Work-breakdown items (drawings, reports, design tasks, meetings…) each holding granular lines: named employee or role × hours × rate, expenses, software licences, subconsultants, travel with markup. Roll-ups by item, cost type and person; contingency; manual override; weighted value |
| **Currencies** | Price each proposal in CAD, USD, EUR, ILS… (add any). Rate card is in the base currency and converts automatically; dashboard totals convert back to base |
| **Project numbers** | Official project number validated against a configurable pattern (your file-server / HCL Notes classification); required before a proposal can be marked won |
| **Suggestions** | While naming a work item, similar items from won projects appear with their estimated and booked hours; one click creates the item re-priced at current rates |
| **Actuals** | Per won project: estimate vs. booked hours and cost by work item and by person; manual time entries; CSV import (Office Timesheets export format) |
| **Export** | Word (.docx) and PDF downloads of the full proposal with logo, sections, scope, Gantt image and fee table |
| **Schedule** | Server-rendered SVG Gantt with phases, milestones, progress, dependencies and a today line; one-click default schedules per service type; shift tasks or the whole programme by ±7/28 days |
| **Preview & print** | Branded on-screen proposal document; also printable from the browser |
| **Programme** | Portfolio Gantt: one bar per open proposal, plus milestones in the next 90 days |
| **Clients & contacts** | Lightweight CRM foundation with inline contact editing |
| **Project sheets** | Past projects with images, key facts and highlights; printable one-page sheet; gallery with search/filter |
| **Templates** | Editable proposal templates (Design, Construction Support, Study) — add / remove / reorder sections |
| **Services & rates** | Service catalogue (scope checklist) and staff roles with default hourly rates |
| **Metrics** | Win rate by client sector, service type and pursuit lead; submissions per month; estimate accuracy (hours and cost variance) on won projects |

Everything is also editable in the Django admin at `/admin/`.

## Project layout

```
bdsp/          settings, urls
core/          company profile (logo, colours), dashboard, metrics, seed command
crm/           clients & contacts
proposals/     proposals, sections, fee items/lines, employees, templates, services, roles
               suggestions.py (estimates from past projects), export.py (DOCX/PDF)
scheduling/    tasks + Gantt geometry (scheduling/gantt.py)
projects/      past-project sheets and images
timesheets/    actual entries, CSV importer, Office Timesheets connector stub
templates/     Django templates (partials prefixed with "_" are htmx fragments)
static/        app.css design system, placeholder logo
```

htmx is loaded from unpkg; to self-host, drop `htmx.min.js` into `static/js/`
(the page falls back to it automatically if the CDN is unreachable).

## Money model

- **Rate card** (Services, people & rates): employees have an individual billing
  rate and optional internal cost rate; roles have a default rate. Both in the
  base currency.
- **Fee lines** store the rate in the proposal's currency at the time the line
  is added (converted via the currency's rate-to-base), so a past proposal's
  numbers don't drift when exchange rates are updated.
- **Actuals** store cost in the base currency (hours × employee rate unless a
  cost is supplied) and are converted to the proposal currency for comparison.

## Timesheets: sync → adopt → replace

1. **Sync** (now): export from Office Timesheets to CSV and import on a won
   proposal's *Actuals* tab, or run
   `python manage.py import_timesheets export.csv --source ots`. Rows are
   matched by project number, employee name / external ID, and work-item name
   or code. `timesheets/connector.py` holds the API stub for scheduled pulls.
2. **Adopt**: staff book time directly in BDSP against work items.
3. **Replace**: retire the connector.

## Configuration

Environment variables: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` (`1`/`0`),
`DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`,
`DJANGO_DB_PATH` (SQLite fallback), `DJANGO_TIME_ZONE`.

## Tests

```bash
python manage.py test
```

## Roadmap (designed for, not built yet)

- Office Timesheets API sync on a schedule (connector stub in place)
- Learned cost suggestions once enough won projects carry actuals (today: similarity on item names)
- Collaboration: comments and review assignments on proposals for senior associates
- CRM: activity log, follow-up reminders, notifications
- Marketing: export project sheets as a brochure, pull them into proposals automatically
- HCL Notes / file-server lookup to validate project numbers against the live register
