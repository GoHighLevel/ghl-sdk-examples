"""
URL configuration for GHL Webhook App.
"""
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('install/', views.install, name='install'),
    path('oauth-callback', views.oauth_callback, name='oauth_callback'),
    path('contact', views.contact, name='contact'),
    path('refresh-token', views.refresh_token, name='refresh_token'),
    path('api/ghl/webhook', views.webhook, name='webhook'),
    path('error-page', views.error_page, name='error_page'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else None)
