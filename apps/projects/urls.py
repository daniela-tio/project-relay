from django.urls import path
from apps.projects import views

urlpatterns = [
    #path("projects/", views.projects.as_view(), name="projects"),
    path("projects/new", views.ProjectCustomerView.as_view(), name="project_customer"),
    path("projects/new/details", views.ProjectCreateView.as_view(), name="project_create"),
    path("projects/<int:pk>/", views.ProjectDetailView.as_view(), name="project_detail"),
    path("projects/<int:pk>/status/", views.ProjectStatusView.as_view(), name="project_status"),
    path("projects/<int:pk>/edit/", views.ProjectUpdateView.as_view(), name="project_update"),
    path("projects/<int:project_pk>/milestones/new/", views.MilestoneCreateView.as_view(), name="milestone_create"),
    path("milestones/<int:pk>/edit/", views.MilestoneUpdateView.as_view(), name="milestone_update"),
    path("milestones/<int:pk>/delete/", views.MilestoneDeleteView.as_view(), name="milestone_delete"),
    path("milestones/<int:pk>/toggle/", views.MilestoneToggleView.as_view(), name="milestone_toggle"),
]