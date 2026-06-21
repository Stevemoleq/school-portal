from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('force-change-password/', views.force_change_password, name='force_change_password'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='accounts/password_reset.html'), name='password_reset'),
    path('password-reset-done/', auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html'), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'), name='password_reset_complete'),

    path('', views.dashboard_redirect, name='dashboard_redirect'),

    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('teacher-dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),

    path('manage/teachers/', views.teacher_list, name='teacher_list'),
    path('manage/teachers/new/', views.teacher_create, name='teacher_create'),
    path('manage/teachers/<int:teacher_id>/edit/', views.teacher_edit, name='teacher_edit'),
    path('manage/teachers/<int:teacher_id>/delete/', views.teacher_delete, name='teacher_delete'),
    path('manage/teachers/<int:teacher_id>/reset-password/', views.teacher_reset_password, name='teacher_reset_password'),
    path('manage/students/<int:student_id>/delete/', views.student_delete, name='student_delete'),

    path('manage/subject-assignments/', views.student_subject_search, name='student_subject_search'),
    path('manage/subject-assignments/<int:student_id>/', views.student_subject_assign, name='student_subject_assign'),

    path('profile/', views.profile, name='profile'),

    path('register-subjects/', views.register_subjects, name='register_subjects'),
    path('manage/terms/', views.admin_terms, name='admin_terms'),

    path('manage/accountants/', views.accountant_list, name='accountant_list'),
    path('manage/accountants/new/', views.accountant_create, name='accountant_create'),
    path('manage/accountants/<int:accountant_id>/delete/', views.accountant_delete, name='accountant_delete'),
]