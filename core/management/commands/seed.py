"""Load sensible defaults for an underground-engineering consultancy.

Idempotent: safe to re-run. Use --demo to also add sample clients, proposals,
schedules and project sheets so the UI has something to show.
"""

from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import AccessRole, CompanyProfile, Currency, NewsItem, NewsSource, Office, Region
from crm.models import Client, Contact
from projects.models import PastProject, ProjectImage
from proposals.models import (
    Employee,
    FeeItem,
    FeeLine,
    Proposal,
    ProposalTemplate,
    Service,
    StaffRole,
    TemplateSection,
)
from scheduling.gantt import create_default_tasks
from timesheets.models import ActualEntry
from tags.models import Tag, TagCategory
from community.models import Profile, Skill, UserSkill
from files.models import FileRoot
from calcs.views import ensure_builtins

OFFICES = [
    # code, name, city, country, lat, lon, tz, hq, note
    ("DSP-Salzburg", "Salzburg (main office)", "Salzburg", "Austria", 47.8095, 13.0550, "Europe/Vienna", True, "Headquarters and partner location."),
    ("DSP-London", "London", "London", "United Kingdom", 51.5074, -0.1278, "Europe/London", False, "Largest office."),
    ("DSP-Washington", "Washington D.C.", "Washington", "USA", 38.9072, -77.0369, "America/New_York", False, ""),
    ("DSP-Toronto", "Toronto", "Toronto", "Canada", 43.6532, -79.3832, "America/Toronto", False, "Heavy workload: invest in local staff and senior support hiring."),
    ("DSP-TelAviv", "Tel Aviv", "Tel Aviv", "Israel", 32.0853, 34.7818, "Asia/Jerusalem", False, ""),
]

NEWS_SOURCES = [
    ("Tunnelling Journal", "https://tunnellingjournal.com/feed/"),
    ("Tunnels & Tunnelling", "https://www.tunnelsandtunnelling.com/feed/"),
    ("New Civil Engineer – Tunnelling", "https://www.newcivilengineer.com/tunnelling/feed/"),
]

TAGS = {
    # category: (weight, color, [tags])
    "Structure": (1.5, "#b8962e", ["Running tunnel", "Station cavern", "Shaft", "Cross-passage", "Cut-and-cover", "Microtunnel", "Portal", "Binocular tunnel"]),
    "Method": (1.5, "#2f80ad", ["SEM / NATM", "TBM – EPB", "TBM – slurry", "Drill & blast", "Microtunnelling", "Jet grouting", "Ground freezing", "Immersed tube"]),
    "Ground": (1.25, "#3a9d6a", ["Soft ground", "Mixed face", "Hard rock", "Glacial till", "Karst", "Squeezing ground", "High groundwater"]),
    "Sector": (1.0, "#8e6cb8", ["Metro / transit", "Rail", "Road", "Water / wastewater", "Hydropower", "Utilities", "Mining"]),
    "Service": (1.0, "#e07a1f", ["Design", "Construction support", "Peer review", "Instrumentation & monitoring", "Risk management", "Numerical modelling"]),
    "Software": (0.75, "#6b7f99", ["Plaxis", "FLAC", "RS2", "Abaqus", "Revit", "Civil 3D"]),
    "Document": (0.5, "#9aa5b1", ["Site visit report", "Photo dump", "Monitoring data", "Calculation", "Numerical model", "Presentation", "Drawing"]),
    "Phase": (0.5, "#5f6f7c", ["Feasibility", "Preliminary design", "Detailed design", "Construction", "Close-out"]),
}

SKILLS = [
    ("SEM / NATM design", "Design"), ("Segmental lining design", "Design"), ("Shaft design", "Design"), ("Cavern design", "Design"), ("Temporary works", "Design"),
    ("Settlement & building damage assessment", "Analysis"), ("Face stability", "Analysis"), ("Numerical modelling (FE/FD)", "Analysis"), ("Fibre-reinforced shotcrete", "Design"),
    ("Site engineering & inspection", "Site"), ("Instrumentation & monitoring", "Site"), ("TBM launch & logistics", "Site"), ("Ground improvement", "Design"),
    ("Plaxis", "Software"), ("FLAC3D", "Software"), ("RS2", "Software"), ("Revit / BIM", "Software"),
    ("Proposal writing", "Management"), ("Fee estimating", "Management"), ("Project management", "Management"), ("Client relations", "Management"), ("Mentoring", "Management"),
]

CURRENCIES = [
    # code, name, symbol, rate to CAD (indicative — edit under Company settings)
    ("CAD", "Canadian dollar", "CA$", "1"),
    ("USD", "US dollar", "US$", "1.38"),
    ("EUR", "Euro", "€", "1.50"),
    ("GBP", "Pound sterling", "£", "1.75"),
    ("CHF", "Swiss franc", "CHF ", "1.55"),
    ("ILS", "Israeli new shekel", "₪", "0.37"),
    ("AUD", "Australian dollar", "A$", "0.90"),
]

REGIONS = [
    ("province", [("AB", "Alberta"), ("BC", "British Columbia"), ("MB", "Manitoba"), ("NB", "New Brunswick"), ("NL", "Newfoundland and Labrador"), ("NS", "Nova Scotia"), ("NT", "Northwest Territories"), ("NU", "Nunavut"), ("ON", "Ontario"), ("PE", "Prince Edward Island"), ("QC", "Quebec"), ("SK", "Saskatchewan"), ("YT", "Yukon")]),
    ("state", [("CA", "California"), ("CO", "Colorado"), ("FL", "Florida"), ("GA", "Georgia"), ("IL", "Illinois"), ("MA", "Massachusetts"), ("MD", "Maryland"), ("NJ", "New Jersey"), ("NY", "New York"), ("OH", "Ohio"), ("PA", "Pennsylvania"), ("TX", "Texas"), ("VA", "Virginia"), ("WA", "Washington")]),
    ("country", [("AUT", "Austria"), ("AUS", "Australia"), ("CHE", "Switzerland"), ("DEU", "Germany"), ("GBR", "United Kingdom"), ("IND", "India"), ("ISR", "Israel"), ("NOR", "Norway"), ("SGP", "Singapore"), ("SWE", "Sweden")]),
]

ROLES_ACCESS = [
    # name, rank, description, capabilities
    ("Partners", 10, "Full access including costs, numbering, phases and settings.", "ALL"),
    ("Associates", 20, "Run pursuits: proposals, fees, schedules, decide won/lost, assign numbers, see costs and actuals.",
     ["view_proposals", "edit_proposals", "approve_won", "change_phase", "view_costs", "view_actuals", "edit_actuals", "view_metrics", "manage_projects_library", "use_tools", "view_projects", "edit_profiles"]),
    ("Engineers", 30, "Write proposals and estimates; no costs, no decisions.", ["view_proposals", "edit_proposals", "view_actuals", "manage_projects_library", "use_tools", "view_projects"]),
    ("Tool users", 35, "Calculation tools only (e.g. site staff, students, externals).", ["use_tools"]),
    ("HR-Global", 40, "People, rates and users across offices.", ["view_proposals", "view_costs", "edit_rates", "manage_users", "view_actuals", "edit_actuals", "edit_profiles", "view_all_offices"]),
    ("HR-Local", 45, "People and timesheets for the local office.", ["view_proposals", "edit_rates", "view_actuals", "edit_actuals", "edit_profiles"]),
    ("IT", 60, "Settings, integrations and user accounts.", ["view_proposals", "manage_settings", "manage_integrations", "manage_users", "manage_forms", "use_tools"]),
    ("Admins", 90, "Office administration: settings, users, templates.", ["view_proposals", "manage_settings", "manage_users", "manage_projects_library", "manage_forms", "edit_profiles", "use_tools", "view_projects"]),
]

REQUEST_KINDS = [
    # key, name, description, handling role
    ("access", "Access & permissions", "A role, a capability, or access to a page you cannot see.", "IT"),
    ("profile", "Profile change", "Office, title or other profile details you cannot change yourself.", "HR-Global"),
    ("data", "Data correction", "A wrong number, client, rate or project detail.", "Admins"),
    ("feature", "Feature idea", "Something TunnelVision should do.", "IT"),
    ("bug", "Bug", "Something broken, with steps to reproduce.", "IT"),
]

# Key staff from dr-sauer.com (Key Staff / Meet the Team). Email rule: first initial + last name @dr-sauer.com.
STAFF = [
    # username, first, last, title, office code, access role, staff role, superuser
    ("gsauer", "Gerhard", "Sauer", "Senior Partner", "DSP-Salzburg", "Partners", "Principal", False),
    ("jlaubbichler", "Juergen", "Laubbichler", "Managing Director & Partner", "DSP-Salzburg", "Partners", "Principal", False),
    ("gskalla", "Gerald", "Skalla", "Managing Director & Partner", "DSP-Toronto", "Partners", "Principal", False),
    ("blyons", "Brian", "Lyons", "Managing Director & Partner", "DSP-London", "Partners", "Principal", False),
    ("tschwind", "Thomas", "Schwind", "Technical Director & Partner", "DSP-London", "Partners", "Principal", False),
    ("afeiersinger", "Andreas", "Feiersinger", "Operations Director & Partner", "DSP-London", "Partners", "Principal", False),
    ("fwilhelmstoetter", "Franz", "Wilhelmstoetter", "Managing Director US & Partner", "DSP-Washington", "Partners", "Principal", False),
    ("ckarner", "Christian", "Karner", "Senior Tunnel Engineer & Partner", "DSP-Washington", "Partners", "Principal", False),
    ("psalak", "Petr", "Salak", "Managing Director Israel", "DSP-TelAviv", "Partners", "Principal", False),
    ("drheault", "David", "Rheault", "Deputy Technical Director & Senior Associate", "DSP-Toronto", "Associates", "Senior Associate", True),
]

EMPLOYEES = [
    # name, role, billing rate, cost rate (CAD/h)
    ("Maria Rivera", "Principal", 295, 140),
    ("James Chen", "Senior Associate", 245, 118),
    ("Anneke Visser", "Senior Associate", 245, 115),
    ("Tomás Herrera", "Associate", 210, 100),
    ("Priya Desai", "Senior Engineer", 185, 88),
    ("Lukas Brandt", "Senior Engineer", 185, 86),
    ("Sofia Marchetti", "Project Engineer", 155, 74),
    ("Daniel Okafor", "Engineer", 125, 60),
    ("Hannah Lee", "Geologist", 150, 72),
    ("Marc Dubois", "CAD / BIM Technician", 110, 52),
    ("Elena Petrova", "Project Controls", 120, 58),
]

SERVICES = [
    # design
    ("design", "Tunnel alignment & feasibility studies"),
    ("design", "Geotechnical interpretation & Geotechnical Baseline Report (GBR)"),
    ("design", "TBM tunnel design (segmental lining)"),
    ("design", "SEM / NATM tunnel design"),
    ("design", "Shaft & cross-passage design"),
    ("design", "Cavern & large underground station design"),
    ("design", "Cut-and-cover & deep excavation support"),
    ("design", "Ground improvement & groundwater control"),
    ("design", "Microtunnelling & trenchless design"),
    ("design", "Numerical modelling (FE/FD) & settlement assessment"),
    ("design", "Fire-life safety & ventilation coordination"),
    ("design", "Risk management & contract documentation"),
    # construction support
    ("construction", "Shop drawing & submittal review"),
    ("construction", "RFI response & design clarifications"),
    ("construction", "Resident engineering & site inspection"),
    ("construction", "Instrumentation & monitoring review"),
    ("construction", "TBM readiness & launch support"),
    ("construction", "Ground condition assessment & differing site conditions"),
    ("construction", "Record drawings & close-out"),
    # other
    ("other", "Peer review / independent design check"),
    ("other", "Expert witness & claims support"),
    ("other", "Condition assessment & rehabilitation"),
]

ROLES = [
    ("Principal", 295),
    ("Senior Associate", 245),
    ("Associate", 210),
    ("Senior Engineer", 185),
    ("Project Engineer", 155),
    ("Engineer", 125),
    ("Geologist", 150),
    ("CAD / BIM Technician", 110),
    ("Project Controls", 120),
    ("Administrative", 85),
]

DESIGN_TEMPLATE = (
    "Design Services Proposal",
    "design",
    "Standard outline for tunnel and underground structure design pursuits.",
    [
        ("Cover letter",
         "Dear {{contact_name}},\n\n{{company_name}} is pleased to submit this proposal to {{client_name}} for {{project_name}}. We have assembled a team with directly relevant experience delivering tunnels and underground structures of comparable scale and complexity, and we are committed to providing {{client_name}} with a safe, constructible and cost-effective design.\n\nWe appreciate the opportunity and look forward to discussing our approach.\n\nSincerely,\n{{owner_name}}\n{{company_name}}"),
        ("Project understanding",
         "Our understanding of {{project_name}} at {{project_location}} is summarised below.\n\n• Purpose and key drivers of the project\n• Ground and groundwater conditions anticipated along the alignment\n• Principal underground elements (running tunnels, shafts, cross-passages, caverns)\n• Interfaces with existing infrastructure and third parties\n• Schedule and procurement constraints\n\nWe have identified the following key design challenges and our approach to each:\n1. \n2. \n3. "),
        ("Scope of services",
         "{{company_name}} proposes the following scope of services:\n\nPhase 1 – Data review and site reconnaissance\nPhase 2 – Preliminary design (30%)\nPhase 3 – Detailed design (60% / 90%)\nPhase 4 – Issued-for-construction documents\n\nDeliverables at each phase will include drawings, specifications, design reports, calculations and a design risk register. Assumptions and exclusions are listed in the Basis of Proposal section."),
        ("Technical approach",
         "Our design approach is built around three principles: understanding the ground, selecting the right construction method, and designing for constructability.\n\nGround characterisation – \nConstruction method selection – \nLining and support design – \nSettlement and third-party impacts – \nRisk management – "),
        ("Project team",
         "The team proposed for {{project_name}} is led by {{owner_name}} as Project Manager, supported by senior specialists in tunnel design, geotechnical engineering and construction methods. Brief biographies and relevant project experience are provided below.\n\nProject Manager – \nLead Tunnel Engineer – \nLead Geotechnical Engineer – \nConstruction Methods Advisor – "),
        ("Relevant experience",
         "Selected projects demonstrating our capability for work of this nature:\n\n• \n• \n• \n\nProject sheets with images are appended."),
        ("Schedule",
         "The proposed schedule is presented in the Gantt chart. Key milestones are the 30%, 60% and 90% design submittals and the issued-for-construction package. We have assumed a two-week review period by {{client_name}} at each submittal."),
        ("Fee",
         "Our fee for the services described is {{fee_total}}, broken down by role and task in the fee table. Fees are based on the hourly rates shown; direct expenses are billed at cost plus the markup indicated. Invoices are submitted monthly."),
        ("Basis of proposal",
         "This proposal is based on the following assumptions:\n\n• Existing geotechnical data will be provided by {{client_name}}\n• Survey, utility and environmental information will be made available\n• Up to two rounds of comments per submittal\n• Services not listed above are excluded and can be provided under a change order\n\nThis proposal is valid for 60 days from {{date}}."),
    ],
)

CONSTRUCTION_TEMPLATE = (
    "Construction Support Services Proposal",
    "construction",
    "Design services during construction: submittal review, RFIs, site support and close-out.",
    [
        ("Cover letter",
         "Dear {{contact_name}},\n\n{{company_name}} is pleased to propose engineering services during construction for {{project_name}}. Continuity between design and construction is critical on underground projects, where ground conditions revealed during excavation must be assessed promptly against design assumptions. Our proposed team includes the engineers who understand the design intent and can respond quickly to the contractor and to {{client_name}}.\n\nSincerely,\n{{owner_name}}"),
        ("Scope of services",
         "Services during construction will include:\n\n• Review of contractor submittals and shop drawings\n• Response to requests for information (RFIs)\n• Review of instrumentation and monitoring data against trigger levels\n• Periodic site visits and inspection of critical activities\n• Assessment of encountered ground conditions and differing site condition claims\n• Preparation of record drawings and close-out documentation"),
        ("Approach & staffing",
         "We will assign a dedicated Construction Support Lead with authority to coordinate responses across disciplines. Submittals and RFIs will be logged, tracked and turned around within the contract review periods. A monthly report will summarise activity, open items and monitoring trends."),
        ("Level of effort",
         "The fee is based on an anticipated construction duration of __ months and the estimated volume of submittals and RFIs shown in the fee table. Effort is estimated by role and task; actual effort will be billed on a time-and-materials basis against the not-to-exceed amount of {{fee_total}}."),
        ("Schedule",
         "Support will be provided throughout the construction period as shown in the schedule, with the highest intensity during tunnel launch, excavation of critical structures and the first months of lining installation."),
        ("Basis of proposal",
         "• Site visits are assumed at __ per month\n• Response times are based on the contract review periods\n• Services beyond the not-to-exceed amount require written authorisation\n\nThis proposal is valid for 60 days from {{date}}."),
    ],
)

STUDY_TEMPLATE = (
    "Feasibility / Options Study",
    "other",
    "Short-form proposal for alignment studies, peer reviews and condition assessments.",
    [
        ("Introduction", "{{company_name}} is pleased to submit this proposal to {{client_name}} for {{project_name}}."),
        ("Objectives", "The study will address the following questions:\n\n1. \n2. \n3. "),
        ("Methodology", "Task 1 – Data collection and review\nTask 2 – Analysis of options\nTask 3 – Draft report and workshop\nTask 4 – Final report"),
        ("Deliverables & schedule", "A draft report will be delivered within __ weeks of notice to proceed, and the final report two weeks after receipt of comments."),
        ("Fee", "Our lump-sum fee for the study is {{fee_total}}."),
    ],
)


def _placeholder_image(label, color):
    """Generate a simple gradient placeholder so demo project sheets have covers."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:  # pragma: no cover
        return None
    w, h = 800, 600
    img = Image.new("RGB", (w, h), color)
    d = ImageDraw.Draw(img)
    for i in range(h):
        shade = tuple(max(0, c - int(i / h * 70)) for c in color)
        d.line([(0, i), (w, i)], fill=shade)
    # a stylised tunnel portal
    d.ellipse([200, 150, 600, 550], outline=(255, 255, 255), width=10)
    d.rectangle([200, 350, 600, 550], fill=color)
    d.rectangle([150, 540, 650, 560], fill=(255, 255, 255))
    d.text((24, 24), label, fill=(255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return ContentFile(buf.getvalue(), name=f"{label.lower().replace(' ', '-')}.jpg")


class Command(BaseCommand):
    help = "Seed the database with default services, rates, templates and (optionally) demo data."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Also create sample clients, proposals and project sheets.")
        parser.add_argument("--no-admin", action="store_true", help="Skip creating the default admin user.")

    def handle(self, *args, **opts):
        User = get_user_model()
        company = CompanyProfile.get_solo()
        if not company.logo:
            from django.conf import settings as dj
            from django.core.files import File

            logo = dj.BASE_DIR / "static" / "img" / "logo-drsauer.png"
            if logo.exists():
                with open(logo, "rb") as f:
                    company.logo.save("logo-drsauer.png", File(f), save=False)
                company.primary_color, company.accent_color = "#1b3a5c", "#e3a725"
                company.save()
        self.stdout.write(f"Company profile: {company.name}")

        if not opts["no_admin"] and not User.objects.exists():
            User.objects.create_superuser("admin", "admin@example.com", "admin", first_name="Admin")
            self.stdout.write(self.style.WARNING("Created superuser admin / admin — change this password!"))

        for i, (code, name, symbol, rate) in enumerate(CURRENCIES):
            Currency.objects.get_or_create(code=code, defaults={"name": name, "symbol": symbol, "rate_to_base": rate, "sort_order": i})
        if not company.default_currency_id:
            company.default_currency = Currency.objects.get(code="CAD")
            company.save()
        self.stdout.write(f"Currencies: {Currency.objects.count()} (default {company.default_currency})")

        country_of = {"province": "canada", "state": "usa", "country": None}
        for kind, rows in REGIONS:
            for code, name in rows:
                Region.objects.get_or_create(code=code, defaults={"name": name, "kind": kind, "country": country_of[kind] or name.lower().replace(" ", "-")})
        from core.models import CAPABILITY_KEYS

        for name, rank, desc, caps in ROLES_ACCESS:
            role, created = AccessRole.objects.get_or_create(name=name, defaults={"rank": rank, "description": desc, "capabilities": CAPABILITY_KEYS if caps == "ALL" else caps, "is_system": True})
            if not created and caps == "ALL":
                role.capabilities = CAPABILITY_KEYS
                role.save()
        from tickets.models import RequestKind

        for i, (key, name, desc, role_name) in enumerate(REQUEST_KINDS):
            RequestKind.objects.get_or_create(key=key, defaults={"name": name, "description": desc, "handled_by": AccessRole.objects.filter(name=role_name).first(), "order": i})
        self.stdout.write(f"Regions: {Region.objects.count()}, access roles: {AccessRole.objects.count()}")

        for i, (cat, (weight, color, names)) in enumerate(TAGS.items()):
            c, _ = TagCategory.objects.get_or_create(name=cat, defaults={"weight": weight, "color": color, "order": i})
            for n in names:
                Tag.objects.get_or_create(name=n, category=c)
        for name, cat in SKILLS:
            Skill.objects.get_or_create(name=name, defaults={"category": cat})
        for i, (code, name, city, country, lat, lon, tz_, hq, note) in enumerate(OFFICES):
            Office.objects.get_or_create(code=code, defaults={"name": name, "city": city, "country": country, "latitude": lat, "longitude": lon, "timezone": tz_, "is_hq": hq, "notes": note, "order": i})
        for name, url in NEWS_SOURCES:
            NewsSource.objects.get_or_create(url=url, defaults={"name": name})
        self.stdout.write(f"Offices: {Office.objects.count()}, news sources: {NewsSource.objects.count()}")

        ensure_builtins()
        from calcs.models import Tool as _Tool
        from calcs.spec import EXAMPLE_SPEC

        _Tool.objects.get_or_create(key="waler-udl", defaults={"name": "Waler under uniform load", "kind": "spec", "category": "Temporary works", "summary": "Example no-code tool: moment and shear for a simply supported waler.", "description": "Built with the tool builder: M = wL²/8, V = wL/2. Edit it or copy it as a starting point.", "spec": EXAMPLE_SPEC, "version": "1.0"})
        for name, purpose, phases, path, tpl, order in (
            ("Projects (dc120)", "projects", "CDE", r"\\dc120\projects", "{country}/{project_number}", 0),
            ("Business development (dc120)", "bd", "B", r"\\dc120\Business Development", "{country}/B-{region}/B-{region}{seq4}", 1),
            ("Printed material · project sheets (dc120)", "sheets", "", r"\\dc120\Administration\canada\printed material\project sheets", "", 2),
        ):
            FileRoot.objects.get_or_create(name=name, defaults={"purpose": purpose, "phases": phases, "kind": "smb", "path": path, "project_folder_template": tpl, "order": order})
        self.stdout.write(f"Tags: {Tag.objects.count()} in {TagCategory.objects.count()} categories, skills: {Skill.objects.count()}, tools: {__import__('calcs.models', fromlist=['Tool']).Tool.objects.count()}")

        # tag the service catalogue
        for svc in Service.objects.all():
            n = svc.name.lower()
            names = []
            if "tbm" in n: names += ["TBM – EPB", "Running tunnel"]
            if "sem" in n or "natm" in n: names += ["SEM / NATM"]
            if "shaft" in n: names += ["Shaft", "Cross-passage"]
            if "cavern" in n or "station" in n: names += ["Station cavern"]
            if "cut-and-cover" in n: names += ["Cut-and-cover"]
            if "microtunnel" in n: names += ["Microtunnel", "Microtunnelling"]
            if "numerical" in n or "settlement" in n: names += ["Numerical modelling"]
            if "monitoring" in n: names += ["Instrumentation & monitoring"]
            if "risk" in n: names += ["Risk management"]
            if "review" in n: names += ["Peer review"]
            names.append("Design" if svc.category == "design" else "Construction support" if svc.category == "construction" else "Peer review")
            svc.set_tags(names)

        for i, (cat, name) in enumerate(SERVICES):
            Service.objects.get_or_create(name=name, defaults={"category": cat, "sort_order": i})
        for i, (title, rate) in enumerate(ROLES):
            StaffRole.objects.get_or_create(title=title, defaults={"default_rate": rate, "sort_order": i})
        roles = {r.title: r for r in StaffRole.objects.all()}
        office_cycle = ["DSP-Toronto", "DSP-Toronto", "DSP-London", "DSP-Toronto", "DSP-Salzburg", "DSP-London", "DSP-Toronto", "DSP-Toronto", "DSP-Washington", "DSP-Toronto", "DSP-London"]
        for i, (name, role, rate, cost) in enumerate(EMPLOYEES):
            Employee.objects.get_or_create(name=name, defaults={"role": roles[role], "rate": rate, "cost_rate": cost, "office": Office.objects.filter(code=office_cycle[i % len(office_cycle)]).first()})
        self.stdout.write(f"Services: {Service.objects.count()}, roles: {StaffRole.objects.count()}, employees: {Employee.objects.count()}")

        role_objs = {r.title: r for r in StaffRole.objects.all()}
        created_staff = 0
        for username, first, last, title, office_code, access, staff_role, su in STAFF:
            email = f"{first[0].lower()}{last.lower()}@dr-sauer.com"
            u, created = User.objects.get_or_create(username=username, defaults={"first_name": first, "last_name": last, "email": email, "is_staff": su, "is_superuser": su})
            if created:
                u.set_password("changeme")
                u.save()
                created_staff += 1
            office = Office.objects.filter(code=office_code).first()
            Profile.objects.update_or_create(user=u, defaults={"title": title, "office": office})
            AccessRole.objects.get(name=access).users.add(u)
            emp, _ = Employee.objects.get_or_create(name=f"{first} {last}", defaults={"role": role_objs[staff_role], "rate": role_objs[staff_role].default_rate, "email": email, "office": office, "user": u})
            if not emp.user_id:
                emp.user = u
                emp.save(update_fields=["user"])
        if created_staff:
            self.stdout.write(self.style.WARNING(f"Created {created_staff} staff accounts from dr-sauer.com with password 'changeme' — change them under Roles & users."))

        for name, stype, desc, sections in (DESIGN_TEMPLATE, CONSTRUCTION_TEMPLATE, STUDY_TEMPLATE):
            t, created = ProposalTemplate.objects.get_or_create(
                name=name, defaults={"service_type": stype, "description": desc, "is_default": stype == "design"}
            )
            if created:
                for i, (title, body) in enumerate(sections):
                    TemplateSection.objects.create(template=t, order=i, title=title, body=body)
        self.stdout.write(f"Templates: {ProposalTemplate.objects.count()}")

        if opts["demo"]:
            self._demo(User)

        self.stdout.write(self.style.SUCCESS("Seed complete."))

    # ------------------------------------------------------------------
    def _demo(self, User):
        if Proposal.objects.exists():
            self.stdout.write("Demo data already present; skipping.")
            return
        today = timezone.localdate()
        lead1 = User.objects.get(username="gskalla")   # Partner, London
        lead2 = User.objects.get(username="drheault")  # Senior Associate, Toronto
        eng, _ = User.objects.get_or_create(username="demo.engineer", defaults={"first_name": "Demo", "last_name": "Engineer", "email": "demo.engineer@example.com"})
        if not eng.password:
            eng.set_password("password")
            eng.save()
        AccessRole.objects.get(name="Engineers").users.add(eng)
        on, bc, ny = Region.objects.get(code="ON"), Region.objects.get(code="BC"), Region.objects.get(code="NY")
        tor, lon_, slz = Office.objects.get(code="DSP-Toronto"), Office.objects.get(code="DSP-London"), Office.objects.get(code="DSP-Salzburg")
        AccessRole.objects.get(name="Partners").capabilities = AccessRole.objects.get(name="Partners").capabilities  # noqa
        for u, title, office, have, learning in (
            (lead1, None, tor, [("SEM / NATM design", 5), ("Cavern design", 5), ("Proposal writing", 5), ("Client relations", 5), ("Mentoring", 4)], []),
            (lead2, None, tor, [("Segmental lining design", 4), ("Fee estimating", 4), ("Numerical modelling (FE/FD)", 4), ("Plaxis", 4), ("Project management", 4)], ["Cavern design"]),
            (eng, "Engineer (demo account)", tor, [("Numerical modelling (FE/FD)", 2), ("Plaxis", 3), ("Settlement & building damage assessment", 2)], ["SEM / NATM design", "Fee estimating", "Face stability"]),
        ):
            prof, _ = Profile.objects.get_or_create(user=u)
            prof.office = office
            if title:
                prof.title = title
            prof.save()
            for name, lvl in have:
                UserSkill.objects.update_or_create(user=u, skill=Skill.objects.get(name=name), defaults={"self_level": lvl, "is_learning": False})
            for name in learning:
                UserSkill.objects.update_or_create(user=u, skill=Skill.objects.get(name=name), defaults={"self_level": 1, "is_learning": True})

        transit, _ = Client.objects.get_or_create(name="Metro Transit Authority", defaults={"sector": "public", "website": "https://example.org"})
        water, _ = Client.objects.get_or_create(name="Regional Water District", defaults={"sector": "utility"})
        jv, _ = Client.objects.get_or_create(name="Northstar–Keller Joint Venture", defaults={"sector": "contractor"})
        c1 = Contact.objects.create(client=transit, name="Dana Whitfield", title="Director of Capital Programs", email="dwhitfield@example.org", is_primary=True)
        c2 = Contact.objects.create(client=water, name="Luis Ortega", title="Chief Engineer", email="lortega@example.org", is_primary=True)
        c3 = Contact.objects.create(client=jv, name="Priya Natarajan", title="Project Director", email="pnatarajan@example.com", is_primary=True)

        design_t = ProposalTemplate.objects.get(name=DESIGN_TEMPLATE[0])
        cs_t = ProposalTemplate.objects.get(name=CONSTRUCTION_TEMPLATE[0])
        emps = {e.name.split()[0]: e for e in Employee.objects.all()}
        cad = Currency.objects.get(code="CAD")
        usd = Currency.objects.get(code="USD")

        def wbs(p, items):
            """items: [(code, name, kind, [(employee_first_name | ('expense', kind, desc, qty, unit, markup)), hours), ...]), ...]"""
            for i, (code, name, kind, lines) in enumerate(items):
                item = FeeItem.objects.create(proposal=p, code=code, name=name, kind=kind, order=i)
                for j, spec in enumerate(lines):
                    if spec[0] == "expense":
                        _, lk, desc, qty, unit, mk = spec
                        FeeLine.objects.create(item=item, kind=lk, description=desc, quantity=qty, unit_cost=unit, markup_percent=mk, order=j)
                    else:
                        who, hours = spec
                        FeeLine.objects.create(item=item, kind="labour", employee=emps[who], hours=hours, order=j)

        p1 = Proposal.objects.create(
            title="Eastside Extension – Twin-Bore Running Tunnels Final Design", client=transit, contact=c1,
            service_type="design", owner=lead2, status="drafting", due_date=today + timedelta(days=18),
            probability=60, location="Downtown to Eastside, 4.2 km", currency=cad, contingency_percent=5, region=on,
            summary="Final design of 4.2 km twin-bore EPB TBM tunnels (6.5 m ID) with six cross-passages and two ventilation shafts in mixed-face glacial soils beneath an urban corridor.",
        )
        p1.apply_template(design_t)
        p1.services.set(Service.objects.filter(category="design")[:7])
        p1.set_tags(["Running tunnel", "TBM – EPB", "Cross-passage", "Shaft", "Glacial till", "Mixed face", "Metro / transit", "Design", "Detailed design"])
        wbs(p1, [
            ("1", "Project management & QA", "pm", [("Maria", 160), ("James", 420), ("Elena", 200), ("expense", "travel", "Client meetings, 12 trips", 12, 650, 0)]),
            ("2", "Geotechnical interpretation & GBR", "report", [("Hannah", 420), ("Lukas", 120), ("Daniel", 160)]),
            ("3", "Segmental lining design", "task", [("Priya", 520), ("Daniel", 400), ("expense", "software", "FE analysis licence, 6 months", 6, 1800, 0)]),
            ("4", "Cross-passage & shaft design", "task", [("Lukas", 460), ("Sofia", 600), ("Daniel", 300)]),
            ("5", "Design drawings (IFC set, ~180 sheets)", "drawing", [("Marc", 1400), ("Sofia", 300)]),
            ("6", "Design reports & calculations", "report", [("Priya", 240), ("Lukas", 200), ("James", 80)]),
            ("7", "Settlement & third-party impact assessment", "calc", [("Tomás", 300), ("expense", "sub", "Building condition survey (subconsultant)", 1, 42000, 10)]),
        ])
        create_default_tasks(p1, today + timedelta(days=45))

        p2 = Proposal.objects.create(
            title="Northern Interceptor Tunnel – Engineering Services During Construction", client=water, contact=c2,
            service_type="construction", owner=lead2, status="submitted", due_date=today - timedelta(days=12),
            probability=70, location="North Basin", currency=cad, region=bc,
            summary="Construction-phase engineering support for a 3.1 km, 3.6 m ID segmentally lined sewer tunnel driven by slurry TBM, including three drop shafts.",
        )
        p2.apply_template(cs_t)
        p2.services.set(Service.objects.filter(category="construction"))
        p2.set_tags(["Running tunnel", "TBM – slurry", "Shaft", "Water / wastewater", "Construction support", "Instrumentation & monitoring", "Construction"])
        wbs(p2, [
            ("1", "Construction support lead & reporting", "pm", [("James", 420)]),
            ("2", "Submittal & shop drawing review", "site", [("Priya", 600), ("Daniel", 300)]),
            ("3", "RFI responses", "site", [("Lukas", 400), ("Sofia", 300)]),
            ("4", "Instrumentation & monitoring review", "site", [("Sofia", 400), ("Hannah", 120)]),
            ("5", "Site inspections", "site", [("Daniel", 600), ("expense", "travel", "Site visits, 40 days", 40, 420, 0)]),
            ("6", "Ground condition assessments", "report", [("Hannah", 300)]),
        ])
        create_default_tasks(p2, today + timedelta(days=30))

        p3 = Proposal.objects.create(
            title="Harbour Crossing – Immersed vs. Bored Tunnel Options Study", client=transit, contact=c1,
            service_type="other", owner=lead2, status="lead", due_date=today + timedelta(days=40), probability=35,
            location="Harbour crossing, 1.8 km", manual_value=185000, currency=cad, region=on,
            summary="Comparative study of immersed-tube and bored tunnel options for the harbour crossing, covering constructability, cost, schedule and risk.",
        )
        p3.apply_template(ProposalTemplate.objects.get(name=STUDY_TEMPLATE[0]))

        p4 = Proposal.objects.create(
            title="Central Station Cavern – Design-Build Design Services", client=jv, contact=c3,
            service_type="both", owner=lead2, status="won", due_date=today - timedelta(days=90), region=ny, sequence=603, phase="D",
            probability=100, location="Central Business District", currency=usd, contingency_percent=7.5,
            summary="Design of a 24 m span, 230 m long SEM mined station cavern with twin entrance shafts, for a design-build joint venture.",
        )
        p4.apply_template(design_t)
        p4.set_tags(["Station cavern", "SEM / NATM", "Shaft", "Metro / transit", "Design", "Construction support", "Numerical modelling", "Plaxis"])
        p4.services.set(Service.objects.filter(category="design")[:6])
        wbs(p4, [
            ("1", "Project management & QA", "pm", [("Maria", 300), ("James", 700), ("Elena", 240)]),
            ("2", "Geotechnical interpretation & GBR", "report", [("Hannah", 380), ("Lukas", 100)]),
            ("3", "Cavern support & SEM sequence design", "task", [("Priya", 900), ("Lukas", 700), ("Daniel", 500), ("expense", "software", "3D FE licence, 12 months", 12, 1900, 0)]),
            ("4", "Numerical modelling", "calc", [("Tomás", 800), ("Daniel", 500)]),
            ("5", "Design drawings (IFC set)", "drawing", [("Marc", 2000), ("Sofia", 500)]),
            ("6", "Design reports & calculations", "report", [("Priya", 300), ("James", 120)]),
            ("7", "Settlement & third-party impact assessment", "calc", [("Tomás", 240), ("expense", "sub", "Building condition survey", 1, 38000, 10)]),
        ])
        create_default_tasks(p4, today - timedelta(days=60))
        # booked time on the won project: roughly 55% through, drawings running hot
        import random

        rnd = random.Random(7)
        for item in p4.items.all():
            factor = {"5": 0.75, "3": 0.6, "1": 0.5, "2": 0.95, "4": 0.55, "6": 0.3, "7": 0.5}.get(item.code, 0.5)
            for line in item.lines.filter(kind="labour"):
                booked = float(line.hours) * factor * rnd.uniform(0.85, 1.25)
                weeks = 8
                for w in range(weeks):
                    ActualEntry.objects.create(proposal=p4, item=item, employee=line.employee, date=today - timedelta(days=7 * (weeks - w)), hours=round(booked / weeks * rnd.uniform(0.7, 1.3), 1), source="csv", description="Weekly timesheet")
        for t in p4.tasks.all():
            if t.end < today:
                t.percent_complete = 100
            elif t.start < today:
                t.percent_complete = 50
            t.save()

        Proposal.objects.create(
            title="Westfield Stormwater Tunnel Preliminary Design", client=water, contact=c2, service_type="design",
            owner=lead2, status="lost", due_date=today - timedelta(days=150), probability=0, manual_value=640000, currency=cad, region=bc, sequence=601,
            summary="Preliminary design of a 2.4 km stormwater storage tunnel.", notes="Lost on price; incumbent retained.",
        )
        Proposal.objects.create(
            title="Airport People-Mover Cut-and-Cover Peer Review", client=transit, service_type="other",
            owner=lead2, status="won", due_date=today - timedelta(days=200), probability=100, manual_value=95000, currency=cad, region=on, sequence=602, phase="E", project_status="complete",
        )
        # assign B numbers to the live pursuits and log history
        for p in (p1, p2):
            p.assign_project_number(user=lead2)
        from proposals.models import PhaseChange, ProjectRecord

        for ph, note in (("B", "Number assigned"), ("C", "Contract signed"), ("D", "Design development started")):
            PhaseChange.objects.create(proposal=p4, phase=ph, note=note, by=lead2)
        exec_p = Proposal.objects.get(sequence=602)
        for i, (kind, title, val, unit) in enumerate([
            ("site_visit", "Site visit report #12 — cut-and-cover box, east wall", None, ""),
            ("photos", "Photo dump — strut installation level 2", None, ""),
            ("monitoring", "Inclinometer I-04 weekly readings", 6.2, "mm"),
            ("progress", "Excavation advance, week 31", 2.8, "m/day"),
            ("progress", "Excavation advance, week 32", 3.1, "m/day"),
        ]):
            ProjectRecord.objects.create(proposal=exec_p, kind=kind, date=today - timedelta(days=30 - i * 6), title=title, value=val, unit=unit, path=f"{exec_p.smb_path}\\{kind}\\", created_by=lead2)

        projects = [
            ("Riverside Transit Tunnels", transit, "tunnel", "Lead designer", 2022, 410_000_000, "Twin 6.0 m ID EPB TBM tunnels, 3.8 km, 28 m deep", (15, 61, 94),
             "Twin-bore EPB TBM running tunnels beneath a dense downtown corridor, with four cross-passages and two ventilation shafts in glacial till and water-bearing sands.",
             "Mixed-face conditions at the river crossing; 6 m clearance beneath a 1920s masonry viaduct; a 7-week launch window dictated by a traffic diversion.",
             "Segmental lining optimised with 3D FE; face-pressure windows tied to monitoring triggers; cross-passages designed for ground freezing with a 30% shorter freeze programme.",
             "Lining thickness reduced from 350 mm to 300 mm (8% of lining cost); settlement under the viaduct held to 9 mm against a 25 mm limit; launch achieved inside the window.",
             ["Running tunnel", "TBM – EPB", "Cross-passage", "Shaft", "Glacial till", "Mixed face", "Metro / transit", "Design", "Numerical modelling", "Plaxis"], ["TBM tunnel design (segmental lining)", "Shaft & cross-passage design", "Numerical modelling (FE/FD) & settlement assessment", "Instrumentation & monitoring review"]),
            ("Lakeview Pumping Station Cavern", water, "cavern", "Engineer of record", 2020, 185_000_000, "22 m span × 18 m high × 120 m long SEM cavern", (224, 122, 31),
             "A 22 m span pumping-station cavern excavated by SEM in shale with a 35 m rock cover, connected to a 3.6 m ID inflow tunnel and two 10 m shafts.",
             "Bedding-parallel shear zones crossing the crown; strict vibration limits beside a hospital; permanent dry conditions required for the equipment hall.",
             "Top-heading/bench sequence with fibre-reinforced shotcrete and spiling through the shear zones; drill-and-blast vibration design per round; waterproofed secondary lining.",
             "Cavern delivered 3 months early; no vibration exceedance across 410 blasts; shotcrete lining saved an estimated 2,100 m³ of cast concrete.",
             ["Station cavern", "SEM / NATM", "Drill & blast", "Hard rock", "Water / wastewater", "Design", "Construction support", "Fibre-reinforced shotcrete" if False else "Design"], ["SEM / NATM tunnel design", "Cavern & large underground station design", "Resident engineering & site inspection"]),
            ("Harbourfront Access Shafts", jv, "shaft", "Design-build designer", 2023, 62_000_000, "Three 14 m ID diaphragm-wall shafts, 42 m deep", (46, 110, 140),
             "Three 14 m internal-diameter shafts, 42 m deep, as TBM launch and reception structures on reclaimed fill over marine clay and glacial till.",
             "Artesian pressure in the till; a live rail corridor 9 m from the nearest shaft; TBM reception through a diaphragm wall under 3 bar.",
             "Diaphragm-wall shafts with a jet-grout plug and relief wells; soft-eye design with GFRP reinforcement; staged dewatering tied to rail monitoring.",
             "Rail settlement limited to 6 mm; reception completed without intervention; design-build partner's programme shortened by 5 weeks.",
             ["Shaft", "Cut-and-cover", "High groundwater", "Soft ground", "Metro / transit", "Design", "Jet grouting"], ["Shaft & cross-passage design", "Ground improvement & groundwater control", "TBM readiness & launch support"]),
            ("Old Town Interceptor Microtunnel", water, "micro", "Lead designer & CM support", 2019, 28_000_000, "1.8 m ID, 1.2 km microtunnel under historic district", (58, 157, 106),
             "A 1.8 m ID microtunnelled interceptor sewer, 1.2 km in four drives beneath a protected historic district, with five 8 m shafts.",
             "Heritage foundations within 3 m of the alignment; cobbles and boulders in the glacial outwash; night-only working in two blocks.",
             "Slurry microtunnelling with a crusher head; shaft locations negotiated with the heritage authority; real-time settlement dashboards for the contractor.",
             "No damage claims from 34 heritage properties; drives completed 11% under the contractor's estimate; the dashboard became the client's standard.",
             ["Microtunnel", "Microtunnelling", "Soft ground", "Water / wastewater", "Design", "Construction support", "Instrumentation & monitoring"], ["Microtunnelling & trenchless design", "Resident engineering & site inspection"]),
        ]
        for name, client, kind, role, year, value, dims, color, desc, chal, contrib, val, tags, svcs in projects:
            pr = PastProject.objects.create(
                name=name, client=client, kind=kind, role=role, year_completed=year, construction_value=value, duration_months={"tunnel": 42, "cavern": 30, "shaft": 24, "micro": 18}[kind],
                key_dimensions=dims, location="Metro region", is_featured=kind in ("tunnel", "cavern"),
                description=desc, challenges=chal, contribution=contrib, value_added=val,
                highlights="Delivered on schedule with no lost-time incidents\nSettlement kept within limits beneath sensitive structures\nValue-engineered design saved construction cost",
                source_path=f"\\\\fileserver\\Projects\\Execution\\{name.replace(' ', '')}",
            )
            pr.set_tags(tags)
            pr.services.set(Service.objects.filter(name__in=svcs))
            img = _placeholder_image(name, color)
            if img:
                ProjectImage.objects.create(project=pr, image=img, caption=f"{name} — placeholder image", order=0)
        # offices on proposals (owner's office), and a London pursuit for the office breakdown
        for pr_ in Proposal.objects.all():
            if not pr_.office_id:
                pr_.office = tor
                pr_.save(update_fields=["office"])
        Proposal.objects.create(title="Thames Tideway East – Secondary Lining Peer Review", client=transit, service_type="other", owner=lead1, status="submitted", due_date=today - timedelta(days=3), probability=55, manual_value=120000, currency=Currency.objects.get(code="GBP"), office=lon_, region=Region.objects.get(code="GBR"))
        for i, (title, src) in enumerate([
            ("TBM breakthrough completes twin-bore drive beneath city centre", "Tunnelling Journal"), ("Fibre-reinforced segmental linings: lessons from three recent metro projects", "Tunnels & Tunnelling"),
            ("Ground freezing adopted for cross-passages on harbour crossing", "Tunnelling Journal"), ("NCE Tunnelling Festival shortlist announced", "New Civil Engineer – Tunnelling"),
        ]):
            NewsItem.objects.get_or_create(url=f"https://example.com/news/{i+1}", defaults={"title": title, "summary": "Example item — real items arrive from the configured feeds once fetch_news runs on the office network.", "published_at": timezone.now() - timedelta(days=i * 3), "source": NewsSource.objects.filter(name=src).first()})
        # attach the two most relevant sheets to the live design pursuit
        from proposals.models import ProposalAttachment

        for i, s_ in enumerate(p1.suggested_sheets(limit=2)):
            ProposalAttachment.objects.get_or_create(proposal=p1, project=s_["sheet"], defaults={"kind": "sheet", "order": i})

        self.stdout.write(f"Demo: {Client.objects.count()} clients, {Proposal.objects.count()} proposals, {PastProject.objects.count()} project sheets.")
        self.stdout.write(self.style.WARNING("Demo engineer account demo.engineer has password 'password'."))
