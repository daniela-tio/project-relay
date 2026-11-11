from django.urls import path
from apps.portfolio import views

urlpatterns = [
    path("gias/", views.GiasImportView.as_view(), name="gias_import"),
    path("schools/new/", views.SchoolCreateView.as_view(), name="school_create"),
    path("trusts/new/", views.TrustCreateView.as_view(), name="trust_create"),
]