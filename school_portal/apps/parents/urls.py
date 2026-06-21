from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.parent_login, name='parent_login'),
    path('', views.parent_dashboard, name='parent_dashboard'),
    path('child/<str:student_id>/results/', views.parent_child_results, name='parent_child_results'),
    path('child/<str:student_id>/attendance/', views.parent_child_attendance, name='parent_child_attendance'),
    path('child/<str:student_id>/report-card/', views.parent_child_report_card, name='parent_child_report_card'),
    path('announcements/', views.parent_announcements, name='parent_announcements'),
    path('announcements/<int:pk>/', views.parent_announcement_detail, name='parent_announcement_detail'),
    path('profile/', views.parent_profile, name='parent_profile'),
    path('notifications/', views.parent_notifications, name='parent_notifications'),
    path('notifications/<int:pk>/read/', views.parent_notification_read, name='parent_notification_read'),
    path('invoices/', views.parent_invoices, name='parent_invoices'),
    path('invoices/<int:invoice_id>/pay/', views.submit_bank_payment, name='submit_bank_payment'),
    path('upload-receipt/', views.upload_receipt, name='upload_receipt'),
    path('attendance/manage/<int:subject_id>/', views.teacher_take_attendance, name='teacher_take_attendance'),
    path('attendance/manage/<int:subject_id>/upload-csv/', views.upload_attendance_csv, name='upload_attendance_csv'),
]
