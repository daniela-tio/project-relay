from pathlib import Path 
from django.core.management.base import BaseCommand, CommandError
from apps.portfolio.gias import run_import
from apps.portfolio.models import GiasImport

class Command(BaseCommand):
    help = "Import the GIAS all-establishments CSV into the GIAS table."
    
    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to the edubasealldata CSV file")
        
    def handle(self, *args, csv_path, **options):
        path = Path(csv_path)
        if not path.exists():
            raise CommandError(f"No file at {path}")
        
        with path.open("rb") as csv_file:
            record = run_import(csv_file, path.name)
            
        if record.status == GiasImport.Status.FAILED:
            raise CommandError(record.error_summary)
        
        seconds = (record.finished_at - record.started_at).total_seconds()
        self.stdout.write(self.style.SUCCESS(
            f"Imported {record.rows_read:,} rows in {seconds:.0f} s."
        ))