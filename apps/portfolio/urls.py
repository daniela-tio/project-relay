from django.urls import path
from apps.portfolio import views

urlpatterns = [
    path("gias/", views.GiasImportView.as_view(), name="gias_import"),
]