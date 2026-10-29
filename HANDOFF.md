# TunnelVision (BDSP) — Handoff

Branch: `claude/bd-proposal-scheduling-app-oya2k8` · Django 5.2 · htmx · SQLite locally, Postgres via `DATABASE_URL`
Owner: David Rheault (drheault@dr-sauer.com), Dr. Sauer & Partners, Toronto. Target domain: tunnelvision.ca (Linode Nanode).

## 1. What this is

An internal platform for an underground-engineering consultancy:
business development (proposals, fees, schedules, project sheets), project
execution data (timesheet actuals, file-server records), engineering
calculation tools, and a people/skills/requests layer. Every office sees its
own numbers; partners see everything.

Run locally: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python manage.py migrate && python manage.py seed --demo && python manage.py runserver`.
Sign in as `drheault` / `changeme` (superuser). Tests: `python manage.py test` (46 tests).

## 2. Current state (what works)

| Area | State |
| --- | --- |
| Proposals | Numbered pursuits, templates with placeholders, htmx section editor, status pipeline (lead → shortlisted → won/lost), board view, duplicate |
| Project numbering | `B-{region}{seq}` in phase B → `{seq}C/D/E`; regions with country folder; sequence counter; required before won; phase log |
| Fee build-up | Work items × lines (employee or role × hours × rate; expense, software, sub, travel with markup); multi-currency; contingency; roll-ups; suggestions from won projects |
| Schedule | Server-rendered SVG Gantt, default schedules per service type, shift/cascade, programme overview |
| Exports | PDF (ReportLab) and Word (python-docx): main body (cover, description, sections, fee summary, closing, signature, validity) + ordered attachments (fee breakdown, schedule, terms, project sheets, files, calculations, capabilities) |
| Project sheets | v2 fields (services, cost, challenges, contribution, value added…), one-page PDF, tags, comments, relevance-ranked attachment picker |
| Actuals | Timesheet entries, CSV/XLSX import with column map, Office Timesheets sync (watched folder or HTTP), estimate vs actual, phase filter |
| File server | Rule-based locations (purpose, phases, folder template), mounted or SMB (smbprotocol), browse/upload/download, index folder → records, friendly unreachable page |
| Calculations | 6 built-in engines (face stability, settlement & damage, beam, RC section, M–N curves, FRS), live recalculation with sliders, autosaved state, shared **project parameters**, no-code **spec tools** (safe expression evaluator), ratings/likes/comments |
| Community | Profiles (avatar, office, title), skills with self-rating + endorsements, mentor matching, comments/reactions on anything |
| Requests | Register with kinds → handling group, triage, events, in-app + email notifications, profile-change requests apply automatically |
| Dashboard | Widget registry, role defaults, per-user customisation, office scoping, offices breakdown, hours, news (RSS), weather (Open-Meteo in browser) |
| Admin UX | Roles & capabilities, users, form builder (hide/require/relabel/custom fields) + pencils on forms, configuration panel (edit mode, costs, density, preview-as-role), appearance themes (dark/light, import/export), sidebar collapse/resize, text size |
| Landing | Internal landing with selectable visual (FE mesh → contours → drawing → photo; shotcrete; advancing rings; drawing→photo) and dark login |

Seeded data: offices (Salzburg HQ, London, Washington, Toronto, Tel Aviv),
key staff from dr-sauer.com (password `changeme`), roles, tags, skills,
services, rates, templates, request kinds, news sources, dc120 file locations.

## 3. Decisions made

- **Palette**: logo gold `#E3A725`, logo grey `#74787D`, dark blue `#1B3A5C` (unconfirmed), black for dark mode. Light mode default; users switch.
- **Numbering** follows the file server: `B-ON0604` folder in BD (4-digit), `604C` in projects. Sequence starts at 601; digits configurable.
- **Legal text**: validity line in the main body under the fee summary; full terms as an attachment. Both in Company settings.
- **Permissions** are capability-based (`core/permissions.py`, `AccessRole.capabilities`), not Django permissions. Views use `@require_cap`, templates `{% if can.x %}`. Preview-as-role is server-side so previews are faithful.
- **Office scoping**: `Scope` in `core/widgets.py`; `view_all_offices` lifts it. Own proposals always visible.
- **User tools are not arbitrary Django apps.** For safety they are JSON specs evaluated by `calcs/spec.py` (AST-whitelisted maths). Code plugins need review + deployment (see next steps).
- **File server**: locations are rules, never hard-coded paths; SharePoint to be added as another `FileRoot.kind`.
- **Dependencies** in `requirements.txt` are pure Python; cairo (Word Gantt image) and psycopg are optional.
- **Email**: console backend by default; `DJANGO_EMAIL_*` env vars for SMTP.

## 4. Open issues / known gaps

- dr-sauer.com is unreachable from the build session: staff list covers leadership only; dark-blue hex unconfirmed; landing photo slot is empty (upload under Company settings).
- Office Timesheets: importer built, but never run against real exports (column names, report variants). Needs sample files.
- SharePoint: not implemented (placeholder in file locations).
- HCL Notes: placeholder only (settings + "test" button).
- News feeds: URLs seeded as guesses; verify and run `manage.py fetch_news` on the LAN.
- Weather needs browser internet; shows a message otherwise.
- Word export has no Gantt image unless `rlPyCairo` is installed.
- Form builder covers 8 forms; `extra` JSON only on Proposal, Client, Employee, PastProject.
- No per-user **widget layouts for the landing page** itself (landing is public; personalisation is the dashboard).
- Engineers role currently includes `edit_proposals`; tighten if needed.
- No automated backups, no HTTPS config, no gunicorn/nginx files yet.
- Tests are broad but shallow in places (exports, SMB backend untested against a real share).

## 5. Next steps (suggested order)

1. **Deployment**: Linode Nanode, Ubuntu, Postgres, gunicorn + nginx, Let's Encrypt, `DJANGO_*` env, `collectstatic`, cron for `sync_timesheets` and `fetch_news`, nightly `pg_dump`. Add `deploy/` with a systemd unit and nginx site.
2. **Timesheets**: load real exports, fix the column map, enable the folder sync, validate phase filtering and employee matching.
3. **Calculation platform**: parameter sets per tool version, comparison of saved runs (overlay charts), units handling, more engines (lining bedded-beam, shaft ring, settlement for twin tunnels), a reviewed "code plugin" path (git submodule + review) for Python tools that outgrow specs.
4. **Project data flywheel**: index execution folders, auto-tag records, feed progress rates into estimates; estimate-accuracy learning for suggestions.
5. **People**: skills map for partners, hiring needs per office, mentoring tracking; LDAP/Entra sign-in if the firm has it.
6. **Documents**: brochure/capability export from project sheets; template library per office/language.
7. **Hardening**: CSP/HSTS, rate limiting on login, audit log for phase changes and rate edits, 2FA for partners.

## 6. Where things live

```
bdsp/settings.py           env-driven settings (DATABASE_URL, EMAIL, SITE_URL)
core/                      company profile, regions, roles/capabilities, themes, form builder, offices, news, dashboard widgets, landing visuals
proposals/                 proposals, fee items/lines, employees, templates, attachments, export.py (PDF/DOCX), suggestions.py
projects/                  project sheets + one-page PDF
scheduling/                tasks + gantt.py
timesheets/                actuals, importer (CSV/XLSX), Office Timesheets sync, integrations page
files/                     file locations, backends (mount/SMB), browse/upload/sync
calcs/                     engines.py (built-in), spec.py (no-code), params.py (shared parameters), live run
community/                 profiles, skills, endorsements, mentoring, comments, reactions
tickets/                   requests register + notifications
tags/                      tag vocabulary + Taggable mixin
templates/, static/css/app.css   htmx partials prefixed "_"; themeable CSS variables
core/management/commands/seed.py  idempotent defaults + --demo data
```
