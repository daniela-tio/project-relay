"""Copies GIAS rows into Project Relays own Trust and School records."""

from apps.portfolio.models import GiasEstablishment, School, Trust, GiasImport

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
        raise SchoolLookupError(f"This school closed {closed_on}. Closed schools can't be added.")
        
    if not GiasImport.objects.filter(status = GiasImport.Status.SUCCEEDED).exists():
        raise SchoolLookupError(
            "No GIAS data has been imported yet. Add the school by hand."
        )
    raise SchoolLookupError(f"No with DFE number {shown} in the latest GIAS file.")