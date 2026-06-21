from django.urls import path
from . import views

urlpatterns = [
    path('', views.announcement_list, name='announcement_list'),
    path('<int:pk>/', views.announcement_detail, name='announcement_detail'),
    path('create/', views.announcement_create, name='announcement_create'),
    path('<int:pk>/edit/', views.announcement_edit, name='announcement_edit'),
    path('<int:pk>/delete/', views.announcement_delete, name='announcement_delete'),
]