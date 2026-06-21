from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def parent_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('parent_login')
        try:
            request.user.parent
        except Exception:
            messages.error(request, 'Access denied. Parent account required.')
            return redirect('dashboard_redirect')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def parent_owns_student(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            parent = request.user.parent
            student_id = kwargs.get('student_id')
            if student_id:
                from apps.accounts.models import Student
                student = Student.objects.get(student_id=student_id)
                if not parent.student_relationships.filter(student=student).exists():
                    messages.error(request, 'You are not linked to this student.')
                    return redirect('parent_dashboard')
        except Exception:
            messages.error(request, 'Access denied.')
            return redirect('parent_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
