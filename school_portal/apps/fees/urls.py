from django.urls import path
from . import views

app_name = "fees"

urlpatterns = [
    # Accountant
    path("accountant/", views.accountant_dashboard, name="accountant_dashboard"),
    path("accountant/search/", views.search_student, name="search_student"),
    path("accountant/student/<str:student_id>/", views.student_fee_detail, name="student_fee_detail"),
    path("accountant/verify/", views.verify_payment_list, name="accountant_verify_list"),
    path("accountant/verify/<int:receipt_id>/", views.verify_payment, name="verify_payment"),
    path("accountant/record/<str:student_id>/", views.record_payment, name="record_payment"),
    path("accountant/reports/", views.reports, name="reports"),
    path("accountant/audit/", views.audit_log, name="audit_log"),
    path("accountant/profile/", views.accountant_profile, name="accountant_profile"),
    path("accountant/invoices/<int:fee_structure_id>/generate/", views.generate_invoices, name="generate_invoices"),
    path("accountant/fee-structures/", views.fee_structure_list, name="fee_structure_list"),
    path("accountant/fee-structures/new/", views.fee_structure_create, name="fee_structure_create"),

    # Student
    path("my-fees/", views.student_fees, name="student_fees"),

    # Parent
    path("parent/child/<str:student_id>/", views.parent_child_fees, name="parent_child_fees"),

    # Receipts
    path("receipt/<str:receipt_number>/", views.receipt_detail, name="receipt_detail"),
    path("receipt/<str:receipt_number>/pdf/", views.receipt_pdf, name="receipt_pdf"),
]
