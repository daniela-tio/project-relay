"""Copies GIAS rows into Project Relays own Trust and School records."""

from apps.portfolio.models import GiasEstablishment, School, Trust

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

def open_schools_in_trust(trust):
    schools = {}
    if trust.gias_code is not None:
        for dfe_number, name in (
            GiasEstablishment.objects.filter(trust_code = trust.gias_code)
            .exclude(status = School.Status.CLOSED)
            .values_list("dfe_number", "name")
        ):
            schools[dfe_number] = name
    for dfe_number, name in (
        trust.schools.exclude(status = School.Status.CLOSED).values_list("dfe_number", "name")
    ):
        schools[dfe_number] = name
    return sorted(schools.items(), key = lambda pair: pair[1])