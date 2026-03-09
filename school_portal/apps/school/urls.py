from django.urls import path
from . import views

urlpatterns = [
    # Class management (admin only)
    path('classes/', views.class_list, name='class_list'),
    path('classes/create/', views.class_create, name='class_create'),
    path('classes/<int:pk>/edit/', views.class_edit, name='class_edit'),
    path('classes/<int:pk>/delete/', views.class_delete, name='class_delete'),
    
    # Subject management (admin only)
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    path('subjects/<int:pk>/edit/', views.subject_edit, name='subject_edit'),
    path('subjects/<int:pk>/delete/', views.subject_delete, name='subject_delete'),
]