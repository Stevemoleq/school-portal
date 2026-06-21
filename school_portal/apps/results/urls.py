from django.urls import path
from . import views

urlpatterns = [
    path('my-results/', views.student_results, name='student_results'),
    path('manage/<int:subject_id>/', views.manage_results, name='manage_results'),
    path('manage/<int:subject_id>/upload-csv/', views.upload_grades_csv, name='upload_grades_csv'),
    path('manage/<int:subject_id>/download-template/', views.download_grades_template, name='download_grades_template'),
]