from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('upload/', views.upload_invoice, name='upload_invoice'),
    path('gst-verification/', views.gst_verification, name='gst_verification'),
    path('api/request-captcha/', views.request_captcha, name='request_captcha'),
    path('api/verify-gst/', views.verify_gst, name='verify_gst'),
]