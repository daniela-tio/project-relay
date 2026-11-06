from django.shortcuts import render
from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

def health(request):
    # Report if the app and its database are reachable
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return HttpResponse("Database not available", status=503, content_type="text/plain")
    return HttpResponse("OK", content_type="text/plain")

@login_required
def home(request):
    """Placeholder homepage until dashboards are ready"""
    return render(request, "core/home.html")