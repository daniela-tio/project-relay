"""Copies GIAS rows into Project Relays own Trust and School records."""

from dataclasses import dataclass, field
from apps.portfolio.models import GiasEstablishment, School, Trust, GiasImport
from apps.projects.models import Project, ProjectSchool

def trust_from_gias(establishment):
    if establishment.trust_code is None:
        return None
    trust = Trust.objects.filter(gias_code=establishment.trust_code).first()
    if trust is None:
        trust = Trust.objects.create(
            name = establishment.trust_name,
            gias_code = establishment.trust_code,
            trust_type = establishment.trust_type or Trust.TrustType.MULTI_ACADEMY,
        )
    return trust

def add_school_from_gias(establishment):
    school = School.objects.filter(dfe_number = establishment.dfe_number).first()
    if school is None:
        school = School.objects.create(
            name = establishment.name,
            dfe_number = establishment.dfe_number,
            urn = establishment.urn,
            status = establishment.status,
            phase = establishment.phase,
            town = establishment.town,
            postcode = establishment.postcode,
            trust = trust_from_gias(establishment),
        )
    return school

class SchoolLookupError(Exception):
    """Raised when an entered DFE number cant be used for a new project"""
    
def find_school_for_project(dfe_number):
    """Searches for open school by DFE number"""
    
    shown = f"{dfe_number[:3]}/{dfe_number[3:]}"
    
    school = School.objects.filter(dfe_number = dfe_number).first()
    if school:
        if school.status == School.Status.CLOSED:
            raise SchoolLookupError(f"{school.name} is closed and can't be added to a project.")
        return school
    
    rows = GiasEstablishment.objects.filter(dfe_number = dfe_number)
    open_row = rows.exclude(status = School.Status.CLOSED).first()
    if open_row:
        return open_row
    closed_row = rows.first()
    if closed_row:
        closed_on = f" on {closed_row.close_date:%-d %b %Y}" if closed_row.close_date else ""
        raise SchoolLookupError(f"This school closed{closed_on}. Closed schools can't be added.")
        
    if not GiasImport.objects.filter(status = GiasImport.Status.SUCCEEDED).exists():
        raise SchoolLookupError(
            "No GIAS data has been imported yet. Add the school by hand."
        )
    raise SchoolLookupError(f"No DFE number {shown} in the latest GIAS file.")

@dataclass
class PortfolioRow:
    """One line of the portfolio"""
    
    name: str
    trust: Trust | None = None
    school: School | None = None
    active_projects: int = 0
    children: dict = field(default_factory=dict)
    
    @property
    def schools(self):
        return sorted(self.children.values(), key=lambda row: row.name.lower())
    
    @property
    def needs_attention(self):
        return bool(self.school and self.school.status == School.Status.CLOSED and self.active_projects)
    
    def matches(self, query, dfe_query):
        if query in self.name.lower():
            return True 
        if self.school:
            return self.school.dfe_number == dfe_query or query in self.school.postcode.lower()
        return self.trust.gias_code is not None and str(self.trust.gias_code) == query
    
def build_portfolio(query=""):
    """Trusts and standalone schools that have projects."""
    
    active = Project.Status.ACTIVE 
    trust_rows = {}
    standalone_rows = {}
    
    for project in Project.objects.select_related("trust"):
        if project.trust:
            row = trust_rows.setdefault(
                project.trust.pk, PortfolioRow(name = project.trust.name, trust = project.trust)
            )
            row.active_projects += project.status == active
            
    for link in ProjectSchool.objects.select_related("school", "project__trust"):
        school, project = link.school, link.project
        if project.trust:
            parent = trust_rows[project.trust.pk].children
        else:
            parent = standalone_rows
        row = parent.setdefault(school.pk, PortfolioRow(name = school.name, school = school))       
        row.active_projects += project.status == active
        
    rows = list(trust_rows.values()) + list(standalone_rows.values())
    
    query = query.strip().lower()
    if query:
        dfe_query = query.replace("/", "")
        kept = []
        for row in rows:
            if row.matches(query, dfe_query):
                kept.append(row)
            elif row.trust:
                matching = {pk: child for pk, child in row.children.items() if child.matches(query, dfe_query)} 
                if matching:
                    row.children = matching
                    kept.append(row)
        rows = kept
    return sorted(rows, key = lambda row: row.name.lower())