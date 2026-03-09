from django.urls import path
from . import views

urlpatterns = [
    # Student result viewing
    path('my-results/', views.student_results, name='student_results'),
]