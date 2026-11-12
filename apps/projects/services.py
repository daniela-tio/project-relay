from apps.portfolio.models import GiasEstablishment, School, Trust
from apps.portfolio.services import add_school_from_gias, trust_from_gias

class ProjectCustomer:
    
    def __init__(self, found=None, trust = None):
        self.found = found
        if trust is not None:
            self.name = trust.name
            self.dfe_number = None
            self.trust = trust
            self.trust_code = trust.gias_code
            self.trust_name = trust.name
            return
        
        self.name = found.name
        self.dfe_number = found.dfe_number
        if isinstance(found, School):
            self.trust = found.trust
            self.trust_code = found.trust.gias_code if found.trust else None
            self.trust_name = found.trust.name if found.trust else ""
        else:
            self.trust_code = found.trust_code
            self.trust = (
                Trust.objects.filter(gias_code = found.trust_code).first() if found.trust_code else None
            )
            self.trust_name = found.trust_name
    
    @property
    def is_trust(self):
        return self.found is None
    
    @property
    def formatted_dfe_number(self):
        return f"{self.dfe_number[:3]}/{self.dfe_number[3:]}"
    
    @property
    def has_trust(self):
        return bool(self.trust or self.trust_code)
    
    def school_choices(self):
        schools = {}
        if self.trust_code:
            for dfe_number, name in (
                GiasEstablishment.objects.filter(trust_code = self.trust_code)
                .exclude(status = School.Status.CLOSED)
                .values_list("dfe_number", "name")
            ):
                schools[dfe_number] = name
        if self.trust:
            for dfe_number, name in (
                self.trust.schools.exclude(status = School.Status.CLOSED).values_list("dfe_number", "name")
            ):
                schools[dfe_number] = name
        return sorted(schools.items(), key = lambda pair: pair[1])
    
    def save_trust(self):
        if self.trust:
            return self.trust
        if self.trust_code:
            return trust_from_gias(self.found)
        return None
        
    def save_school(self, dfe_number):
        school = School.objects.filter(dfe_number = dfe_number).first()
        if school:
            return school
        establishment = (
            GiasEstablishment.objects.filter(dfe_number = dfe_number)
            .exclude(status = School.Status.CLOSED)
            .first()
        )
        return add_school_from_gias(establishment)
