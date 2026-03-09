from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login
from django.db.models import Avg, Count
from django_ratelimit.decorators import ratelimit
from django.contrib import messages
import json
from .models import Student, Teacher
from apps.announcements.models import Announcement
from apps.results.models import Result

# Rate limit: 5 login attempts per minute per IP
@ratelimit(key='ip', rate='5/m', method='POST')
def login_view(request):
    """Custom login view with rate limiting for security."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome {user.first_name or user.username}!')
            return redirect('dashboard_redirect')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'accounts/login.html')

def dashboard_redirect(request):
    """Redirect user to their role‑specific dashboard after login."""
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return redirect('admin_dashboard')
        try:
            request.user.teacher
            return redirect('teacher_dashboard')
        except Teacher.DoesNotExist:
            try:
                request.user.student
                return redirect('student_dashboard')
            except Student.DoesNotExist:
                # Fallback (should not happen)
                logout(request)
                return redirect('login')
    return redirect('login')

@login_required
def student_dashboard(request):
    """Student dashboard: show profile summary and recent announcements."""
    # Authorization check: ensure user is a student
    try:
        student = request.user.student
    except Student.DoesNotExist:
        messages.error(request, 'Access denied. Student profile not found.')
        return redirect('dashboard_redirect')
    
    # Fetch latest announcements for students (all or targeted)
    announcements = Announcement.objects.filter(
        target_audience__in=['all', 'students']
    ).order_by('-created_at')[:5]
    
    # Fetch student performance across terms
    published_results = Result.objects.filter(student=student, is_published=True)
    
    # Get unique terms for this student
    terms = published_results.values_list('term', flat=True).distinct().order_by('term')
    term_choices = dict(Result.TERM_CHOICES)
    
    # Calculate performance data for chart
    term_data = []
    for term in terms:
        term_results = published_results.filter(term=term)
        avg_marks = term_results.aggregate(Avg('marks'))['marks__avg'] or 0
        term_display = term_choices.get(term, term)
        term_data.append({
            'term': term_display,
            'average': round(avg_marks, 2),
            'subjects': term_results.count()
        })
    
    # Get overall statistics
    overall_avg = published_results.aggregate(Avg('marks'))['marks__avg'] or 0
    total_subjects = published_results.values('subject').distinct().count()
    
    context = {
        'student': student,
        'announcements': announcements,
        'term_data': json.dumps(term_data),  # For JavaScript
        'term_list': term_data,  # For template display
        'overall_average': round(overall_avg, 2),
        'total_subjects': total_subjects,
    }
    return render(request, 'accounts/student_dashboard.html', context)

@login_required
def teacher_dashboard(request):
    """Teacher dashboard: show classes/subjects taught and quick links."""
    # Authorization check: ensure user is a teacher
    try:
        teacher = request.user.teacher
    except Teacher.DoesNotExist:
        messages.error(request, 'Access denied. Teacher profile not found.')
        return redirect('dashboard_redirect')
    
    # Get subjects taught by this teacher
    subjects = teacher.subjects.all().select_related('class_id')
    # Group by class for display
    classes_dict = {}
    for subject in subjects:
        cls = subject.class_id
        if cls not in classes_dict:
            classes_dict[cls] = []
        classes_dict[cls].append(subject)
    
    announcements = Announcement.objects.filter(
        target_audience__in=['all', 'teachers']
    ).order_by('-created_at')[:5]
    
    context = {
        'teacher': teacher,
        'classes_dict': classes_dict,
        'announcements': announcements,
    }
    return render(request, 'accounts/teacher_dashboard.html', context)

@login_required
def admin_dashboard(request):
    """Admin dashboard: summary links (or use Django admin)."""
    # Authorization check: ensure user is admin/staff
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard_redirect')
    
    # Quick counts
    from apps.accounts.models import Student, Teacher
    from apps.school.models import Class, Subject
    from apps.results.models import Result
    from apps.announcements.models import Announcement
    
    context = {
        'student_count': Student.objects.count(),
        'teacher_count': Teacher.objects.count(),
        'class_count': Class.objects.count(),
        'subject_count': Subject.objects.count(),
        'result_count': Result.objects.count(),
        'announcement_count': Announcement.objects.count(),
    }
    return render(request, 'accounts/admin_dashboard.html', context)

@login_required
def profile(request):
    """View and edit profile (common for all roles)."""
    # You can extend this to handle both student and teacher profiles
    user = request.user
    try:
        teacher = user.teacher
        role = 'teacher'
    except Teacher.DoesNotExist:
        try:
            student = user.student
            role = 'student'
        except Student.DoesNotExist:
            role = 'staff' if user.is_staff else 'unknown'
    
    context = {
        'user': user,
        'role': role,
    }
    return render(request, 'accounts/profile.html', context)