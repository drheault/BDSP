# BDSP — Business Development, Scheduling & Proposals

A Django + htmx web app for an engineering consultancy (tunnels and underground
structures) to write proposals, build fee estimates, lay out simple Gantt
schedules, keep client/contact records and showcase past projects.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed --demo     # defaults + sample data; creates admin / admin
python manage.py runserver
```

Open http://127.0.0.1:8000, sign in as `admin` / `admin` (change this in
`/admin/`), then go to **Company & logo** to set your firm's name, logo, colours
and proposal number prefix.

`python manage.py seed` (without `--demo`) loads only the defaults: the service
catalogue, staff roles with billing rates, and three proposal templates. It is
safe to re-run.

## What's inside

| Area | What you can do |
| --- | --- |
| **Dashboard** | Open pursuits, pipeline and weighted value, win rate, due dates, upcoming milestones |
| **Proposals** | Create from a template, edit sections inline (add / remove / reorder), placeholders such as `{{client_name}}`, status pipeline (lead → won/lost), list and Kanban board views, duplicate, delete |
| **Fee estimate** | Labour build-up by role × hours × rate, expenses with markup, manual override, weighted value |
| **Schedule** | Server-rendered SVG Gantt with phases, milestones, progress, dependencies and a today line; one-click default schedules per service type; shift tasks or the whole programme by ±7/28 days |
| **Preview & print** | Branded proposal document (logo, cover block, sections, scope, Gantt, fee table) — print to PDF from the browser |
| **Programme** | Portfolio Gantt: one bar per open proposal, plus milestones in the next 90 days |
| **Clients & contacts** | Lightweight CRM foundation with inline contact editing |
| **Project sheets** | Past projects with images, key facts and highlights; printable one-page sheet; gallery with search/filter |
| **Templates** | Editable proposal templates (Design, Construction Support, Study) — add / remove / reorder sections |
| **Services & rates** | Service catalogue (scope checklist) and staff roles with default hourly rates |
| **Metrics** | Win rate by client sector, service type and pursuit lead; submissions per month |

Everything is also editable in the Django admin at `/admin/`.

## Project layout

```
bdsp/          settings, urls
core/          company profile (logo, colours), dashboard, metrics, seed command
crm/           clients & contacts
proposals/     proposals, sections, fee lines, templates, services, roles
scheduling/    tasks + Gantt geometry (scheduling/gantt.py)
projects/      past-project sheets and images
templates/     Django templates (partials prefixed with "_" are htmx fragments)
static/        app.css design system, placeholder logo
```

htmx is loaded from unpkg; to self-host, drop `htmx.min.js` into `static/js/`
(the page falls back to it automatically if the CDN is unreachable).

## Configuration

Environment variables: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` (`1`/`0`),
`DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_DB_PATH`,
`DJANGO_TIME_ZONE`. SQLite is used by default; switch `DATABASES` in
`bdsp/settings.py` to Postgres for multi-user production use.

## Tests

```bash
python manage.py test
```

## Roadmap (designed for, not built yet)

- Timesheet integration: actual vs. estimated hours per role/phase on the Metrics page
- Collaboration: comments and review assignments on proposals for senior associates
- CRM: activity log, follow-up reminders, notifications and auto-suggestions
- Marketing: export project sheets as a brochure, pull them into proposals automatically
