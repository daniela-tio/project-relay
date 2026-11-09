import csv
import io 
import re 
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from apps.portfolio.models import GiasEstablishment, School, Trust, GiasImport

REQUIRED_COLUMNS = [
    "URN", "LA (code)", "EstablishmentNumber", "EstablishmentName", "EstablishmentStatus (name)", "CloseDate", "PhaseOfEducation (name)",
    "Town", "Postcode", "Trusts (code)", "Trusts (name)", "TrustSchoolFlag (name)",
]

STATUS_MAP = {
    "Open": School.Status.OPEN,
    "Closed": School.Status.CLOSED,
    "Open, but proposed to close": School.Status.PROPOSED_TO_CLOSE,
    "Proposed to open": School.Status.PROPOSED_TO_OPEN,
}

TRUST_TYPE_MAP = {
    "Supported by a multi-academy trust": Trust.TrustType.MULTI_ACADEMY,
    "Supported by a single-academy trust": Trust.TrustType.SINGLE_ACADEMY,
    "Supported by a trust": Trust.TrustType.FOUNDATION,
}

BATCH_SIZE = 1000

class GiasFileError(Exception):
    """The uploaded file is not usable."""
    
def file_date_from_name(file_name):
    """Read the date from the name of the CSV"""
    
    match = re.search(r"(\d{8})", file_name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None
    
def parse_close_date(value):
    return datetime.strptime(value, "%d-%m-%Y").date() if value else None

def row_to_establishment(row):
    """Turn CSV row into a GIASEstablishment or none to skip it"""
    
    if not row["EstablishmentNumber"]:
        return None
    return GiasEstablishment(
        urn = int(row["URN"]),
        dfe_number = row["LA (code)"] + row["EstablishmentNumber"],
        name = row["EstablishmentName"],
        status = STATUS_MAP[row["EstablishmentStatus (name)"]],
        close_date = parse_close_date(row["CloseDate"]),
        phase = row["Town"],
        postcode = row["Postcode"],
        trust_code = int(row["Trusts (code)"]) if row["Trusts (code)"] else None,
        trust_name = row["Trusts (name)"],
        trust_type = TRUST_TYPE_MAP.get(row["TrustSchoolFlag (name)"], ""),
    )
    
def load_establishments(binary_file):
    """Replace the GIAS table with the files rows."""
    
    text = io.TextIOWrapper(binary_file, encoding = "cp1252", newline = "")
    reader = csv.DictReader(text)
    
    for column in REQUIRED_COLUMNS:
        if column not in (reader.fieldnames or []):
            raise GiasFileError(
                f'Something does not look right with the file: missing column "{column}".' 
            )
    
    rows_read = 0
    batch = []
    with transaction.atomic():
        GiasEstablishment.objects.all().delete()
        for row in reader:
            rows_read += 1
            try: 
                establishment = row_to_establishment(row)
            except (KeyError, ValueError) as error:
                raise GiasFileError(
                    f"Could't read row {rows_read + 1} of the file: {error}."
                )
            if establishment:
                batch.append(establishment)
            if len(batch) >= BATCH_SIZE:
                GiasEstablishment.objects.bulk_create(batch)
                batch = []
        GiasEstablishment.objects.bulk_create(batch)
    return rows_read

def run_import(binary_file, file_name, user=None):
    """Run import and record it in the import history."""
    
    record = GiasImport.objects.create(
        file_name = file_name,
        file_date = file_date_from_name(file_name),
        uploaded_by = user,
    )
    try:
        record.rows_read = load_establishments(binary_file)
        record.status = GiasImport.Status.SUCCEEDED
    except GiasFileError as error:
        record.status = GiasImport.Status.FAILED
        record.error_summary = str(error)
    except Exception:
        record.status = GiasImport.Status.FAILED
        record.error_summary = "The import stopped because of an unexpected error."
        raise
    finally:
        record.finished_at = timezone.now()
        record.save()
    return record