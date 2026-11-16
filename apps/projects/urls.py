from django.urls import path
from apps.projects import views

urlpatterns = [
    #path("projects/", views.projects.as_view(), name="projects"),
    path("projects/new", views.ProjectCustomerView.as_view(), name="project_customer"),
    path("projects/new/details", views.ProjectCreateView.as_view(), name="project_create"),
    path("projects/<int:pk>/", views.ProjectDetailView.as_view(), name="project_detail"),
    path("projects/<int:pk>/status/", views.ProjectStatusView.as_view(), name="project_status"),
]