from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q, Sum
from django_ratelimit.decorators import ratelimit
from django.contrib import messages
import json
import logging
from apps.parents.models import Parent
from .models import Student, Teacher, Class, Subject, AcademicTerm, SubjectRegistration
from apps.fees.models import Accountant
from apps.announcements.models import Announcement
from apps.results.models import Result
from apps.core.logging_utils import (
    log_user_action, log_security_event,
    log_database_operation, get_client_ip
)

logger = logging.getLogger(__name__)


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
@ratelimit(key='post:username', rate='10/h', method='POST', block=True)
def login_view(request):
    """Custom login view with rate limiting for security. Supports both Username and Email."""
    from django.contrib.auth.forms import AuthenticationForm
    from django.contrib.auth.models import User
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    form = AuthenticationForm()

    if request.method == 'POST':
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password')
        ip_address = get_client_ip(request)

        username = username_or_email
        if '@' in username_or_email:
            try:
                user_obj = User.objects.get(email__iexact=username_or_email)
                username = user_obj.username
            except User.DoesNotExist:
                pass

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            log_security_event(
                'LOGIN_SUCCESS',
                user=user,
                ip_address=ip_address,
                details={'method': 'username/email'}
            )
            logger.info(f"User ID {user.id} logged in successfully from IP {ip_address}")
            messages.success(request, f'Welcome {user.first_name or user.username}!')
            return redirect('dashboard_redirect')
        else:
            log_security_event(
                'LOGIN_FAILED',
                ip_address=ip_address,
                details={'attempted_username': username_or_email}
            )
            logger.warning(f"Failed login attempt for username '{username_or_email}' from IP {ip_address}")
            messages.error(request, 'Invalid username or password.')
            form = AuthenticationForm(data=request.POST)

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def force_change_password(request):
    """Force a student to change their password on next login."""
    try:
        student = request.user.student
    except Student.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard_redirect')

    if not student.must_change_password:
        return redirect('student_dashboard')

    from django.contrib.auth.forms import SetPasswordForm
    from django.contrib.auth import update_session_auth_hash

    if request.method == 'POST':
        form = SetPasswordForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, request.user)
            student.must_change_password = False
            student.save(update_fields=['must_change_password'])
            messages.success(request, 'Password changed successfully. Welcome!')
            return redirect('student_dashboard')
    else:
        form = SetPasswordForm(user=request.user)

    return render(request, 'accounts/force_change_password.html', {'form': form})


def landing_view(request):
    """Redirect to the dedicated login page."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    return redirect('login')


def dashboard_redirect(request):
    """Redirect user to their role-specific dashboard after login."""
    if request.user.is_authenticated:
        # Accountant check first — accountants have a dedicated portal,
        # not the admin dashboard.
        try:
            request.user.accountant
            return redirect('fees:accountant_dashboard')
        except (AttributeError, Accountant.DoesNotExist):
            pass
        if request.user.is_superuser:
            return redirect('admin_dashboard')
        try:
            request.user.teacher
            return redirect('teacher_dashboard')
        except Teacher.DoesNotExist:
            try:
                student = request.user.student
                if student.must_change_password:
                    return redirect('force_change_password')
                return redirect('student_dashboard')
            except Student.DoesNotExist:
                try:
                    request.user.parent
                    return redirect('parent_dashboard')
                except Parent.DoesNotExist:
                    logout(request)
                except AttributeError:
                    logout(request)
    return redirect('login')


@login_required
def student_dashboard(request):
    """Student dashboard: show profile, subjects grouped by category, and results per term."""
    try:
        student = request.user.student
    except Student.DoesNotExist:
        messages.error(request, 'Access denied. Student profile not found.')
        return redirect('dashboard_redirect')

    if student.must_change_password:
        return redirect('force_change_password')

    announcements = Announcement.objects.filter(
        target_audience__in=['all', 'students']
    ).select_related('author').order_by('-created_at')[:5]

    # Available terms (registrations + results)
    available_terms = student.available_terms()
    selected_term_id = request.GET.get('term')
    selected_term = None

    if selected_term_id:
        selected_term = available_terms.filter(pk=selected_term_id).first()
    if not selected_term:
        selected_term = AcademicTerm.objects.filter(is_active=True).first()
    if not selected_term:
        selected_term = available_terms.first()

    # Subjects for the selected term
    registered_subjects = list(
        student.registered_subjects_for_term(selected_term)
        if selected_term else []
    )

    if not registered_subjects and selected_term:
        # Fallback: subjects from results in that term
        result_subject_ids = list(
            Result.objects.filter(
                student=student, is_published=True,
                term=selected_term.term, session=selected_term.session,
            ).values_list('subject_id', flat=True).distinct()
        )
        if result_subject_ids:
            registered_subjects = list(
                Subject.objects.filter(id__in=result_subject_ids)
            )
        else:
            # Last fallback: permanent enrollment list
            registered_subjects = list(
                student.assigned_subjects.order_by('is_compulsory', 'name')
            )

    assigned_count = len(registered_subjects)
    compulsory_count = sum(1 for s in registered_subjects if s.is_compulsory)
    elective_count = assigned_count - compulsory_count

    category_order = ['CORE', 'SCIENCE', 'HUMANITIES', 'COMMERCIAL', 'TECHNICAL', 'OTHER']
    category_labels = dict(Subject.CATEGORY_CHOICES)
    subjects_by_category = []
    for cat_code in category_order:
        cat_subjects = [s for s in registered_subjects if s.category == cat_code]
        if cat_subjects:
            subjects_by_category.append({
                'code': cat_code,
                'label': category_labels.get(cat_code, cat_code),
                'subjects': cat_subjects,
            })

    # Results for the selected term
    term_results_map = {}
    if selected_term:
        term_results = Result.objects.filter(
            student=student, is_published=True,
            term=selected_term.term, session=selected_term.session,
        ).select_related('subject')
        for r in term_results:
            term_results_map[r.subject_id] = r

    for group in subjects_by_category:
        for s in group['subjects']:
            s.current_result = term_results_map.get(s.id)

    # "Next focus" hint for the sidebar widget — first subject in the active
    # term that does not yet have a published result. Falls back to the
    # first registered subject, or None when nothing is enrolled.
    next_subject = None
    for s in registered_subjects:
        if s.id not in term_results_map:
            next_subject = s
            break
    if not next_subject and registered_subjects:
        next_subject = registered_subjects[0]

    # Published results across ALL terms (for charts + overall stats)
    all_published = Result.objects.filter(
        student=student, is_published=True
    ).select_related('subject')

    # --- Term Performance Data (for chart) ---
    term_choices = dict(Result.TERM_CHOICES)
    raw_terms = all_published.values_list('term', flat=True).distinct().order_by('term')
    term_data = []
    for term_code in raw_terms:
        term_results = all_published.filter(term=term_code)
        avg_marks = term_results.aggregate(Avg('marks'))['marks__avg'] or 0
        term_display = term_choices.get(term_code, term_code)
        term_data.append({
            'term': term_display,
            'term_code': term_code,
            'average': round(avg_marks, 2),
            'subjects': term_results.count(),
        })

    overall_avg = all_published.aggregate(Avg('marks'))['marks__avg'] or 0
    total_subjects = all_published.values('subject').distinct().count()

    # --- Grade Distribution (all terms) ---
    grade_counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    for r in all_published:
        g = r.grade.upper()
        if g in grade_counts:
            grade_counts[g] += 1

    # --- Attendance Summary ---
    from apps.parents.models import Attendance
    att_summary = Attendance.get_student_summary(student)
    att_present_pct = att_summary['percentage']
    att_absent_pct = round(100 - att_present_pct, 1) if att_summary['total'] > 0 else 0

    # Registration status
    needs_registration = selected_term and selected_term.registration_open and not registered_subjects
    is_open = selected_term and selected_term.registration_open

    context = {
        'student': student,
        'announcements': announcements,
        'term_data': term_data,
        'term_list': term_data,
        'overall_average': round(overall_avg, 2),
        'total_subjects': total_subjects,
        'grade_dist': grade_counts,
        'att_summary': att_summary,
        'att_present_pct': att_present_pct,
        'att_absent_pct': att_absent_pct,
        'subjects_by_category': subjects_by_category,
        'assigned_count': assigned_count,
        'compulsory_count': compulsory_count,
        'elective_count': elective_count,
        'available_terms': available_terms,
        'selected_term': selected_term,
        'needs_registration': needs_registration,
        'registration_open': is_open,
        'next_subject': next_subject,
    }
    return render(request, 'accounts/student_dashboard.html', context)


@login_required
def teacher_dashboard(request):
    """Teacher dashboard: show classes/subjects taught and quick links."""
    try:
        teacher = request.user.teacher
    except Teacher.DoesNotExist:
        messages.error(request, 'Access denied. Teacher profile not found.')
        return redirect('dashboard_redirect')

    subjects = teacher.subjects.all().select_related('assigned_class')
    active_term = AcademicTerm.objects.filter(is_active=True).first()

    # Per-subject enrollment count for the active term
    subject_enrolment_counts = {}
    total_students = 0
    if active_term:
        from django.db.models import Count
        qs = SubjectRegistration.objects.filter(
            term=active_term, subject__in=subjects
        ).values('subject_id').annotate(count=Count('student_id', distinct=True))
        for row in qs:
            subject_enrolment_counts[row['subject_id']] = row['count']
        total_students = sum(subject_enrolment_counts.values())

    classes_dict = {}
    for subject in subjects:
        cls = subject.assigned_class
        if cls not in classes_dict:
            classes_dict[cls] = []
        subject.enrolled_count = subject_enrolment_counts.get(subject.id, 0)
        classes_dict[cls].append(subject)

    announcements = Announcement.objects.filter(
        target_audience__in=['all', 'teachers']
    ).select_related('author').order_by('-created_at')[:5]

    # ---- Scholarly analytics: pass rate, class performance, pending counts ----
    teacher_results = Result.objects.filter(subject__in=subjects)
    if active_term:
        teacher_results = teacher_results.filter(
            term=active_term.term, session=active_term.session
        )
    total_results = teacher_results.count()
    passed_results = teacher_results.filter(marks__gte=40).count()
    pass_rate = round((passed_results / total_results) * 100, 1) if total_results else 0
    at_risk = teacher_results.filter(marks__lt=40).count()

    # Pending results = enrolled students minus students with at least one result
    results_pending = 0
    if active_term and total_students:
        students_with_results = (
            teacher_results.values('student_id').distinct().count()
        )
        results_pending = max(total_students - students_with_results, 0)

    # Attendance pending — for the active term, no per-class attendance
    # model in the project, so we surface the count of subjects taught
    # as a proxy "sections needing attendance today".
    attendance_pending = subjects.count() if active_term else 0

    # Class performance: average mark per class for active term
    class_performance = []
    for cls, cls_subjects in classes_dict.items():
        subject_ids = [s.id for s in cls_subjects]
        avg = Result.objects.filter(
            subject_id__in=subject_ids,
        )
        if active_term:
            avg = avg.filter(term=active_term.term, session=active_term.session)
        avg = avg.aggregate(Avg('marks'))['marks__avg'] or 0
        class_performance.append({
            'name': str(cls) if cls else 'Unassigned',
            'short': (str(cls)[:8] if cls else 'N/A'),
            'average': round(avg, 1),
            'subjects': len(cls_subjects),
        })
    class_performance.sort(key=lambda x: x['name'])

    context = {
        'teacher': teacher,
        'classes_dict': classes_dict,
        'announcements': announcements,
        'total_students': total_students,
        'active_term': active_term,
        'pass_rate': pass_rate,
        'passed_results': passed_results,
        'total_results': total_results,
        'at_risk': at_risk,
        'results_pending': results_pending,
        'attendance_pending': attendance_pending,
        'class_performance': class_performance,
        'class_performance_json': json.dumps(class_performance),
    }
    return render(request, 'accounts/teacher_dashboard.html', context)


@login_required
def admin_dashboard(request):
    """Admin dashboard: summary links."""
    if not request.user.is_superuser:
        messages.error(request, 'Access denied. Superuser privileges required.')
        return redirect('dashboard_redirect')

    from apps.accounts.models import Student, Teacher
    from apps.school.models import Class, Subject
    from apps.results.models import Result
    from apps.announcements.models import Announcement
    from decimal import Decimal
    from apps.parents.models import Parent

    context = {
        'student_count': Student.objects.count(),
        'teacher_count': Teacher.objects.count(),
        'class_count': Class.objects.count(),
        'subject_count': Subject.objects.count(),
        'result_count': Result.objects.count(),
        'announcement_count': Announcement.objects.count(),
        'parent_count': Parent.objects.count(),
    }
    return render(request, 'accounts/admin_dashboard.html', context)


def _admin_required(request):
    return request.user.is_authenticated and request.user.is_superuser


@login_required
def teacher_create(request):
    """Friendly in-dashboard form to add a new teacher (admin only)."""
    if not _admin_required(request):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard_redirect')

    from .forms import TeacherCreateForm

    if request.method == 'POST':
        form = TeacherCreateForm(request.POST)
        if form.is_valid():
            teacher = form.save()
            try:
                log_user_action(
                    request.user, 'teacher_create',
                    target=teacher, request=request,
                    extra_data={'employee_id': teacher.employee_id},
                )
            except Exception:
                pass
            initial_password = getattr(teacher, '_initial_password', None)
            messages.success(
                request,
                f"Teacher {teacher.user.get_full_name()} ({teacher.employee_id}) added. "
                f"Initial password (share securely, rotate on first login): {initial_password}",
            )
            return redirect('teacher_list')
    else:
        form = TeacherCreateForm()
    return render(request, 'accounts/teacher_form.html', {'form': form, 'mode': 'create'})


@login_required
def teacher_edit(request, teacher_id):
    """Edit an existing teacher's details and subject assignments (admin only)."""
    if not _admin_required(request):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard_redirect')

    teacher = get_object_or_404(Teacher, pk=teacher_id)
    from .forms import TeacherEditForm

    if request.method == 'POST':
        form = TeacherEditForm(request.POST, instance=teacher)
        if form.is_valid():
            form.save()
            try:
                log_user_action(
                    request.user, 'teacher_edit',
                    target=teacher, request=request,
                    extra_data={'employee_id': teacher.employee_id},
                )
            except Exception:
                pass
            messages.success(
                request,
                f"Teacher {teacher.user.get_full_name()} updated successfully.",
            )
            return redirect('teacher_list')
    else:
        form = TeacherEditForm(instance=teacher)

    return render(request, 'accounts/teacher_form.html', {
        'form': form, 'mode': 'edit', 'teacher': teacher,
    })


@login_required
def teacher_list(request):
    """Friendly teacher listing (admin only)."""
    if not _admin_required(request):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard_redirect')

    from .models import Subject
    from django.db.models import Prefetch

    q = request.GET.get('q', '').strip()
    class_id = request.GET.get('class', '').strip()
    subject_id = request.GET.get('subject', '').strip()

    teachers = Teacher.objects.select_related('user').prefetch_related('subjects__assigned_class')
    if q:
        teachers = teachers.filter(
            Q(employee_id__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__email__icontains=q)
        )
    if subject_id:
        teachers = teachers.filter(subjects__id=subject_id)
    if class_id:
        teachers = teachers.filter(subjects__assigned_class_id=class_id)
    teachers = teachers.distinct().order_by('employee_id')

    from django.core.paginator import Paginator
    paginator = Paginator(teachers, 20)
    page = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page,
        'teachers': page.object_list,
        'subjects': Subject.objects.select_related('assigned_class').order_by('name'),
        'classes': Class.objects.all().order_by('name'),
        'q': q,
        'selected_class': class_id,
        'selected_subject': subject_id,
    }
    return render(request, 'accounts/teacher_list.html', context)


@login_required
def teacher_delete(request, teacher_id):
    """Delete a teacher (admin only)."""
    if not _admin_required(request):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard_redirect')

    teacher = get_object_or_404(Teacher, pk=teacher_id)
    if request.method == 'POST':
        name = teacher.user.get_full_name() or teacher.employee_id
        user = teacher.user
        # Refuse to delete a user who holds any other role — would
        # inadvertently remove the only superuser, an accountant, or
        # a parent.
        if user is not None:
            other_roles = []
            if user.is_superuser:
                other_roles.append('superuser')
            if hasattr(user, 'accountant'):
                other_roles.append('accountant')
            if hasattr(user, 'parent'):
                other_roles.append('parent')
            if other_roles:
                messages.error(
                    request,
                    f"Cannot delete {name}: this user is also a "
                    f"{', '.join(other_roles)}. Remove those roles first.",
                )
                return redirect('teacher_list')
        teacher.delete()
        if user:
            user.delete()
        messages.success(request, f"Teacher {name} deleted.")
        return redirect('teacher_list')
    return render(request, 'accounts/teacher_confirm_delete.html', {'teacher': teacher})


@login_required
@ratelimit(key='user', rate='10/h', method='POST')
def teacher_reset_password(request, teacher_id):
    """Reset a teacher's password (admin only)."""
    if not _admin_required(request):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard_redirect')

    if getattr(request, 'limited', False):
        messages.error(request, 'Too many password reset attempts. Try again later.')
        return redirect('teacher_list')

    teacher = get_object_or_404(Teacher, pk=teacher_id)

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()

        if not new_password:
            messages.error(request, 'Password is required.')
            return redirect('teacher_reset_password', teacher_id=teacher.id)

        # Enforce Django password validators
        try:
            validate_password(new_password, user=teacher.user)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return redirect('teacher_reset_password', teacher_id=teacher.id)

        teacher.user.set_password(new_password)
        teacher.user.save()
        try:
            log_user_action(
                request.user, 'teacher_reset_password',
                target=teacher, request=request,
            )
        except Exception:
            pass
        messages.success(
            request,
            f"Password reset for {teacher.user.get_full_name()} successfully.",
        )
        return redirect('teacher_list')

    return render(request, 'accounts/teacher_reset_password.html', {'teacher': teacher})


# ===== ACCOUNTANT MANAGEMENT (Admin) =====

@login_required
def accountant_list(request):
    """List all accountants (admin only)."""
    if not _admin_required(request):
        messages.error(request, 'Access denied.')
        return redirect('dashboard_redirect')

    from apps.fees.models import Accountant
    accountants = Accountant.objects.select_related('user').all().order_by('accountant_id')

    context = {
        'accountants': accountants,
    }
    return render(request, 'accounts/accountant_list.html', context)


@login_required
def accountant_create(request):
    """Create a new accountant (admin only)."""
    if not _admin_required(request):
        messages.error(request, 'Access denied.')
        return redirect('dashboard_redirect')

    from apps.fees.models import Accountant
    from apps.fees.decorators import get_or_create_accountant_group
    from django.contrib.auth.models import User, Group

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        errors = []
        if not username:
            errors.append('Username is required.')
        if not password:
            errors.append('Password is required.')
        if User.objects.filter(username__iexact=username).exists():
            errors.append(f'Username "{username}" is already taken.')

        # Validate password against Django validators
        if password:
            try:
                dummy_user = User(username=username, first_name=first_name, last_name=last_name)
                validate_password(password, user=dummy_user)
            except ValidationError as e:
                for error in e.messages:
                    errors.append(error)

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            # Accountants are NOT Django staff. They have a dedicated portal
            # at /fees/ and access only the fee-related modules. The
            # Accountant group provides the per-model permissions.

            group = get_or_create_accountant_group()
            user.groups.add(group)

            Accountant.objects.get_or_create(
                user=user,
                defaults={'phone': phone},
            )

            try:
                log_user_action(request.user, 'accountant_create', target=user, request=request)
            except Exception:
                pass

            messages.success(
                request,
                f"Accountant {first_name} {last_name} ({username}) created.",
            )
            return redirect('accountant_list')

    return render(request, 'accounts/accountant_form.html', {'mode': 'create'})


@login_required
def accountant_delete(request, accountant_id):
    """Delete an accountant (admin only)."""
    if not _admin_required(request):
        messages.error(request, 'Access denied.')
        return redirect('dashboard_redirect')

    from apps.fees.models import Accountant
    accountant = get_object_or_404(Accountant, pk=accountant_id)
    name = str(accountant)
    user = accountant.user

    if request.method == 'POST':
        # Hard-block deleting a superuser's account — that would lock
        # the operator out of the system.
        if user is not None and user.is_superuser:
            messages.error(
                request,
                f"Cannot delete {name}: this user is a superuser. "
                "Demote them first.",
            )
            return redirect('accountant_list')
        accountant.delete()
        user.delete()
        try:
            log_user_action(request.user, 'accountant_delete', target=user, request=request)
        except Exception:
            pass
        messages.success(request, f'Accountant {name} deleted.')
        return redirect('accountant_list')

    return render(request, 'accounts/accountant_confirm_delete.html', {'accountant': accountant})


@login_required
def student_delete(request, student_id):
    """Delete a student (admin only)."""
    if not _admin_required(request):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard_redirect')

    student = get_object_or_404(Student, pk=student_id)
    if request.method == 'POST':
        name = student.user.get_full_name() or student.student_id
        user = student.user
        student.delete()
        user.delete()
        messages.success(request, f"Student {name} deleted.")
        return redirect('admin_dashboard')
    return render(request, 'accounts/student_confirm_delete.html', {'student': student})


# ----------------------------------------------------------------------------
# Subject Assignment
# ----------------------------------------------------------------------------

@login_required
def student_subject_assign(request, student_id):
    """Admin interface to manage a student's subject assignments."""
    if not _admin_required(request):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard_redirect')

    from .models import StudentSubject, Subject as SubjectModel
    student = get_object_or_404(Student, pk=student_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            try:
                subject_id = int(request.POST.get('subject_id', ''))
                subject = SubjectModel.objects.get(pk=subject_id)
            except (ValueError, SubjectModel.DoesNotExist):
                messages.error(request, 'Invalid subject.')
                return redirect('student_subject_assign', student_id=student.id)

            if student.current_class_id and subject.assigned_class_id != student.current_class_id:
                messages.warning(
                    request,
                    f"Note: {subject} is registered to a different class.",
                )

            _, created = student.assign_subject(subject, is_elective=not subject.is_compulsory)
            if created:
                messages.success(
                    request,
                    f"Added {subject} to {student.user.get_full_name()}.",
                )
            else:
                messages.info(request, f"{student.user.get_full_name()} is already taking {subject}.")
            try:
                log_user_action(
                    request.user, 'student_subject_assign',
                    target=student, request=request,
                    extra_data={'subject_id': subject.id},
                )
            except Exception:
                pass

        elif action == 'remove':
            try:
                subject_id = int(request.POST.get('subject_id', ''))
                subject = SubjectModel.objects.get(pk=subject_id)
            except (ValueError, SubjectModel.DoesNotExist):
                messages.error(request, 'Invalid subject.')
                return redirect('student_subject_assign', student_id=student.id)

            ok, err = student.remove_subject(subject)
            if ok:
                messages.success(request, f"Removed {subject} from {student.user.get_full_name()}.")
                try:
                    log_user_action(
                        request.user, 'student_subject_remove',
                        target=student, request=request,
                        extra_data={'subject_id': subject.id},
                    )
                except Exception:
                    pass
            else:
                messages.error(request, err or 'Could not remove subject.')

        elif action == 'bulk':
            ids = request.POST.getlist('subject_ids')
            added = 0
            for sid in ids:
                try:
                    subject = SubjectModel.objects.get(pk=int(sid))
                    _, created = student.assign_subject(
                        subject, is_elective=not subject.is_compulsory
                    )
                    if created:
                        added += 1
                except (ValueError, SubjectModel.DoesNotExist):
                    continue
            messages.success(
                request, f"Added {added} new subject(s) to {student.user.get_full_name()}."
            )

        return redirect('student_subject_assign', student_id=student.id)

    # GET: build context
    assigned_qs = student.student_subjects.select_related('subject__assigned_class')
    assigned_subjects = [ss.subject for ss in assigned_qs]
    assigned_ids = {s.id for s in assigned_subjects}

    compulsory = [s for s in assigned_subjects if s.is_compulsory]
    electives = [s for s in assigned_subjects if not s.is_compulsory]

    # Available subjects: same class as student, not yet assigned
    available_qs = SubjectModel.objects.filter(
        assigned_class=student.current_class
    ) if student.current_class else SubjectModel.objects.none()
    available = [s for s in available_qs.order_by('is_compulsory', 'name') if s.id not in assigned_ids]

    context = {
        'student': student,
        'compulsory_subjects': compulsory,
        'elective_subjects': electives,
        'available_subjects': available,
        'total_count': len(assigned_subjects),
    }
    return render(request, 'accounts/student_subjects.html', context)


@login_required
def student_subject_search(request):
    """Search for a student to manage their subject assignments."""
    if not _admin_required(request):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard_redirect')

    q = request.GET.get('q', '').strip()
    class_id = request.GET.get('class', '').strip()

    students = Student.objects.select_related('user', 'current_class')
    if q:
        students = students.filter(
            Q(student_id__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
        )
    if class_id:
        students = students.filter(current_class_id=class_id)
    students = students.order_by('student_id')[:50]

    context = {
        'students': students,
        'q': q,
        'selected_class': class_id,
        'classes': Class.objects.all().order_by('name'),
    }
    return render(request, 'accounts/student_subject_search.html', context)


@login_required
def profile(request):
    """View and edit profile (common for all roles)."""
    from django.contrib.auth.forms import PasswordChangeForm
    from django.contrib.auth import update_session_auth_hash

    user = request.user
    teacher = None
    student = None
    role = 'unknown'

    if hasattr(user, 'teacher'):
        teacher = user.teacher
        role = 'teacher'
    elif hasattr(user, 'student'):
        student = user.student
        role = 'student'
    elif user.is_staff:
        role = 'staff'

    password_form = PasswordChangeForm(user=user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            user.email = request.POST.get('email', '').strip()

            try:
                user.save()

                if role == 'teacher' and teacher:
                    teacher.phone = request.POST.get('phone', '').strip()
                    teacher.save()
                elif role == 'student' and student:
                    address = request.POST.get('address', '').strip()
                    date_of_birth = request.POST.get('date_of_birth', '').strip()
                    student.address = address
                    if date_of_birth:
                        student.date_of_birth = date_of_birth
                    student.save()

                messages.success(request, 'Profile details updated successfully.')
            except Exception as e:
                messages.error(request, f'Failed to update profile: {str(e)}')

            return redirect('profile')

        elif action == 'change_password':
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user_obj = password_form.save()
                update_session_auth_hash(request, user_obj)
                messages.success(request, 'Your password was successfully updated!')
                return redirect('profile')
            else:
                messages.error(request, 'Please correct the errors in the password form.')

    context = {
        'user': user,
        'teacher': teacher,
        'student': student,
        'role': role,
        'password_form': password_form,
    }
    return render(request, 'accounts/profile.html', context)


# ===== TERM & SUBJECT REGISTRATION =====

@login_required
def register_subjects(request):
    """Student-facing subject registration for the current/open term."""
    try:
        student = request.user.student
    except Student.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard_redirect')

    # Fee check: student must have paid at least the minimum fee threshold
    from decimal import Decimal
    from django.conf import settings as django_settings
    from apps.parents.models import StudentInvoice
    fee_threshold = getattr(django_settings, 'FEE_REGISTRATION_THRESHOLD', 0.5)
    invoices = StudentInvoice.objects.filter(student=student)
    total_due = invoices.aggregate(s=Sum("total_amount"))["s"] or Decimal("0")
    total_paid = invoices.aggregate(s=Sum("paid_amount"))["s"] or Decimal("0")
    if total_due > 0 and total_paid < total_due * Decimal(str(fee_threshold)):
        messages.error(
            request,
            f"You must pay at least {fee_threshold*100:.0f}% of your school fees before registering for subjects. "
            "Please see the accountant.",
        )
        return redirect('student_dashboard')

    from django.utils import timezone as _tz

    open_terms = AcademicTerm.objects.filter(registration_open=True)
    # Enforce the optional deadline — if it's set and in the past, the
    # term is treated as closed even if registration_open is still True.
    open_terms = [
        t for t in open_terms
        if not t.registration_deadline or t.registration_deadline >= _tz.now()
    ]
    selected_term = None

    if request.method == 'POST':
        if not student.current_class:
            messages.error(
                request,
                "You are not assigned to a class. Please contact the school office "
                "before registering for subjects.",
            )
            return redirect('student_dashboard')

        term_id = request.POST.get('term_id')
        selected_term = get_object_or_404(AcademicTerm, pk=term_id, registration_open=True)
        if selected_term.registration_deadline and selected_term.registration_deadline < _tz.now():
            messages.error(request, "The registration deadline for this term has passed.")
            return redirect('student_dashboard')

        subject_ids = [int(x) for x in request.POST.getlist('subjects') if x.isdigit()]

        # Validate all subject IDs belong to the student's class
        valid_ids = set(
            Subject.objects.filter(
                assigned_class=student.current_class, pk__in=subject_ids
            ).values_list('pk', flat=True)
        )
        invalid = set(subject_ids) - valid_ids
        if invalid:
            messages.error(request, f"Invalid subject selection — {len(invalid)} subject(s) don't belong to your class.")
            return redirect('register_subjects')
        subject_ids = list(valid_ids)

        count = student.register_for_term(selected_term, subject_ids)
        messages.success(
            request,
            f"Registered {count} subject(s) for {selected_term.name}.",
        )
        return redirect('student_dashboard')

    # GET: show registration form for the first open term
    selected_term = open_terms[0] if open_terms else None
    if not selected_term:
        messages.info(request, 'Subject registration is not currently open.')
        return redirect('student_dashboard')

    # Subjects available for this student's class
    if student.current_class:
        class_subjects = Subject.objects.filter(
            assigned_class=student.current_class
        ).order_by('-is_compulsory', 'category', 'name')
    else:
        # Fallback: show all subjects when class is not assigned
        class_subjects = Subject.objects.all().order_by(
            '-is_compulsory', 'category', 'name'
        )

    # Already registered for this term
    registered_ids = set(
        SubjectRegistration.objects
        .filter(student=student, term=selected_term)
        .values_list('subject_id', flat=True)
    )

    # Group by category
    category_order = ['CORE', 'SCIENCE', 'HUMANITIES', 'COMMERCIAL', 'TECHNICAL', 'OTHER']
    category_labels = dict(Subject.CATEGORY_CHOICES)
    subjects_by_category = []
    for cat_code in category_order:
        cat_subjects = [s for s in class_subjects if s.category == cat_code]
        if cat_subjects:
            subjects_by_category.append({
                'code': cat_code,
                'label': category_labels.get(cat_code, cat_code),
                'subjects': cat_subjects,
                'registered_ids': registered_ids,
            })

    context = {
        'student': student,
        'selected_term': selected_term,
        'subjects_by_category': subjects_by_category,
        'registered_ids': registered_ids,
    }
    return render(request, 'accounts/subject_register.html', context)


@login_required
def admin_terms(request):
    """Admin view: list and manage academic terms."""
    if not request.user.is_superuser:
        messages.error(request, 'Access denied. Superuser privileges required.')
        return redirect('dashboard_redirect')

    terms = AcademicTerm.objects.all().order_by('-session', 'term')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            term_code = request.POST.get('term')
            session = request.POST.get('session')
            AcademicTerm.objects.create(term=term_code, session=session)
            messages.success(request, 'Term created.')

        elif action == 'toggle_active':
            term = get_object_or_404(AcademicTerm, pk=request.POST.get('term_id'))
            term.is_active = not term.is_active
            term.save()
            status = 'activated' if term.is_active else 'deactivated'
            messages.success(request, f'Term {status}.')

        elif action == 'toggle_registration':
            term = get_object_or_404(AcademicTerm, pk=request.POST.get('term_id'))
            term.registration_open = not term.registration_open
            term.save()
            status = 'opened' if term.registration_open else 'closed'
            messages.success(request, f'Registration {status} for {term.name}.')

        elif action == 'set_deadline':
            term = get_object_or_404(AcademicTerm, pk=request.POST.get('term_id'))
            from datetime import datetime
            deadline_str = request.POST.get('deadline')
            if deadline_str:
                try:
                    term.registration_deadline = datetime.fromisoformat(deadline_str)
                except (ValueError, TypeError):
                    messages.error(request, 'Invalid date format. Use YYYY-MM-DDTHH:MM.')
                    return redirect('admin_terms')
                term.save()
                messages.success(request, 'Deadline updated.')

        return redirect('admin_terms')

    context = {
        'terms': terms,
        'term_choices': AcademicTerm.TERM_CHOICES,
    }
    return render(request, 'accounts/admin_terms.html', context)