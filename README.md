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
| **Project numbers & phases** | `B-ON601` in business development → `601C` consulting → `601D` design development → `601E` execution. Region codes (2-letter province/state, 3-letter country) and the sequence counter are managed in settings; the number is assigned once and the letter changes with the phase. Required before a proposal can be marked won; every change is logged |
| **Records & files** | Per project: the file-server folder path (from a template) and a register of site-visit reports, photo dumps, monitoring data and progress rates with their SMB paths. Progress rates are averaged to feed future estimates |
| **Roles & users** | Partners, Associates, Engineers, HR-Global, HR-Local, IT, Admins seeded; create, edit or delete roles and tick capabilities (see costs, approve won, change phase, manage settings…). Pages, buttons and columns follow the capabilities |
| **Project sheets v2** | Services provided, cost, duration, description, challenges, our contribution, value added, highlights, reference, file-server source path, tags. One-page PDF with a fixed template. Comments and "used in proposals" |
| **Attachments** | Per proposal: project sheets ranked by relevance (shared tags weighted by category, services, client/sector, structure type, keywords) with checkboxes and previews; files (PDFs merge into the export); saved calculations. Standard attachments: fee breakdown, schedule, terms & validity, capabilities |
| **Document structure** | Main body = cover, project description, your sections, fee summary, closing words, signature, validity line. Attachments follow in order |
| **Calculations** | Six built-in tools with formulas shown: tunnel face stability, settlement & building damage, beam analysis, RC section, M–N capacity curves, fibre-reinforced shotcrete. Save runs against proposals; upload your own tools; likes, ratings and discussion rank them |
| **Tags** | One vocabulary for services, project sheets, proposals, records, tools and skills, organised in weighted categories with aliases for auto-tagging |
| **People & skills** | Profiles with avatars, self-rated skills, peer endorsements with context, mentor suggestions and mentoring requests; comments and likes on anything |
| **File server** | Browse, upload and download on mounted or SMB shares; index a project folder into records |
| **Form builder** | Hide, require, relabel and reorder inputs on each form; add custom fields (text, number, date, yes/no, choice) that print on documents |
| **Appearance** | Four built-in styles, each with dark and light palettes (dark by default; users switch in their account menu); Engineering slate carries the Dr. Sauer anthracite-and-gold palette. Collapsible, resizable sidebar. Apply one for all users, copy and customise colours/fonts with a live preview, add custom CSS, import/export themes as JSON. Per-user text-size control in the account menu |
| **Integrations** | Office Timesheets sync: watched export folder or HTTP endpoint, phase filter, duplicate protection, run history, "Sync now" and a schedulable command. HCL Notes placeholder |
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

1. **Sync** (now): under *Integrations*, point the connector at the folder
   where Office Timesheets drops its scheduled export (or at an HTTP export
   URL), choose which phases may receive hours (default C, D, E) and press
   *Sync now*. Schedule `python manage.py sync_timesheets` hourly or nightly
   with cron / Task Scheduler for hands-off operation. Each run is logged with
   files, rows created, duplicates skipped and errors. Rows are matched by
   project number, employee name / external ID, and work-item name or code.
   One-off files can still be imported on a proposal's *Actuals* tab or with
   `python manage.py import_timesheets export.xlsx --source ots`. CSV and Excel
   exports are both accepted; if the report's column names differ from the
   built-in aliases, map them once in the connector's *Column map* field.
2. **Adopt**: staff book time directly in BDSP against work items.
3. **Replace**: retire the connector.

## Where legal text goes

The validity sentence is printed in the main body right under the fee summary,
because it is the line a client reads. The full terms (basis, invoicing,
liability, confidentiality) are an attachment so they never crowd the
narrative. Both come from *Company settings → Proposal documents*.

## Interface principles

Large readable type, high contrast, few visible controls. Secondary actions
sit behind a "…" menu on each row or card; add-forms open on request; Export
is one menu. Every colour, font and size is a CSS variable set by the active
theme (`core/themes.py` holds the presets), so the look can change without
touching templates.

## Permissions

Capabilities are granted through access roles (Roles & users). A user's
capabilities are the union of their roles; superusers have all of them. Views
are protected with `@require_cap("…")` (`core/permissions.py`) and templates
hide controls with `{% if can.capability %}`. Seeded roles: Partners (all),
Associates, Engineers, HR-Global, HR-Local, IT, Admins — edit freely or add
your own.

Demo logins after `seed --demo`: `admin`/`admin` (superuser), `mrivera`
(Partners), `jchen` (Associates), `dokafor` (Engineers), all with password
`password` except admin.

## Configuration

Environment variables: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` (`1`/`0`),
`DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`,
`DJANGO_DB_PATH` (SQLite fallback), `DJANGO_TIME_ZONE`.

## Tests

```bash
python manage.py test
```

## Public site

`/` is a landing page for tunnelvision.ca when signed out and the dashboard
when signed in. Set `DJANGO_ALLOWED_HOSTS=tunnelvision.ca,www.tunnelvision.ca`
and `DJANGO_CSRF_TRUSTED_ORIGINS=https://tunnelvision.ca` for deployment.

## Roadmap (designed for, not built yet)

- Office Timesheets "adopt" phase: book time in BDSP and push back
- LAN agent that indexes the project folders (site reports, photos, monitoring
  exports) into project records automatically
- Learned cost suggestions once enough won projects carry actuals (today: similarity on item names)
- Collaboration: comments and review assignments on proposals for senior associates
- CRM: activity log, follow-up reminders, notifications
- Marketing: export project sheets as a brochure, pull them into proposals automatically
- HCL Notes lookup to reconcile project numbers with the live register (placeholder connector in place)
