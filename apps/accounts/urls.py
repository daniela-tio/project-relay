from django.urls import path
from . import views

urlpatterns = [
    path('sign-in/', views.SignInView.as_view(), name='sign_in'),
    path('sign-out/', views.SignOutView.as_view(), name='sign_out'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/new/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/password', views.UserSetPasswordView.as_view(), name='user_set_password'),
    path('users/<int:pk>/delete', views.UserDeleteView.as_view(), name='user_delete'),
]