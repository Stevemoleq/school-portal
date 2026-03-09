from django.urls import path
from . import views

urlpatterns = [
    # Public (authenticated users) announcement list
    path('', views.announcement_list, name='announcement_list'),
    
    # Detail view (optional)
    path('<int:pk>/', views.announcement_detail, name='announcement_detail'),
    
    # Admin/Teacher creation and management
    path('create/', views.announcement_create, name='announcement_create'),
    path('<int:pk>/edit/', views.announcement_edit, name='announcement_edit'),
    path('<int:pk>/delete/', views.announcement_delete, name='announcement_delete'),
]