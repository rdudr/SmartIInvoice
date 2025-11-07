from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('upload/', views.upload_invoice, name='upload_invoice'),
    path('gst-verification/', views.gst_verification, name='gst_verification'),
    path('gst-cache/', views.gst_cache_management, name='gst_cache'),
    path('invoice/<int:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    path('invoice/<int:invoice_id>/manual-entry/', views.manual_entry, name='manual_entry'),
    path('invoice/<int:invoice_id>/submit-manual-entry/', views.submit_manual_entry, name='submit_manual_entry'),
    path('profile/', views.user_profile, name='user_profile'),
    path('settings/', views.settings, name='settings'),
    path('api/check-gst-cache/', views.check_gst_cache, name='check_gst_cache'),
    path('api/request-captcha/', views.request_captcha, name='request_captcha'),
    path('api/verify-gst/', views.verify_gst, name='verify_gst'),
    path('api/refresh-gst-cache/', views.refresh_gst_cache_entry, name='refresh_gst_cache_entry'),
    path('api/bulk-upload/', views.bulk_upload_invoices, name='bulk_upload_invoices'),
    path('api/batch-status/<str:batch_id>/', views.get_batch_status, name='get_batch_status'),
    path('api/dashboard-analytics/', views.dashboard_analytics_api, name='dashboard_analytics_api'),
    path('api/delete-profile-picture/', views.delete_profile_picture, name='delete_profile_picture'),
    path('export/invoices/', views.export_invoices, name='export_invoices'),
    path('export/gst-cache/', views.export_gst_cache, name='export_gst_cache'),
    path('export/my-data/', views.export_my_data, name='export_my_data'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path('coming-soon/', views.coming_soon, name='coming_soon'),
]