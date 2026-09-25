from django.urls import path
from . import views
app_name = 'accounts'
urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('auth/login/', views.login, name='login'),
    path('auth/register/', views.register, name='register'),
    path('auth/verify/', views.verify, name='verify'),
    path('auth/resend/', views.resend, name='resend'),
    path('auth/recover/', views.recover, name='recover'),
    path('auth/reset/', views.reset, name='reset'),
    path('auth/mfa/', views.mfa, name='mfa'),
    path('auth/invitation/', views.invitation, name='invitation'),
    path('auth/status/', views.status, name='status'),
    path('auth/logout/', views.logout, name='logout'),
    path('auth/revoke/', views.revoke_sessions, name='revoke'),
    path('auth/session/', views.session_info, name='session'),
    path('auth/help/', views.help_page, name='help'),
    path('auth/privacy/', views.privacy, name='privacy'),
    path('auth/terms/', views.terms, name='terms'),
]
