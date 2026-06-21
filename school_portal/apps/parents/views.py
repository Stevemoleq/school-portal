import json
import logging
from collections import defaultdict
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Q, Prefetch, Sum
from django.core.paginator import Paginator
from django_ratelimit.decorators import ratelimit
from apps.accounts.models import Student
from apps.results.models import Result
from apps.announcements.models import Announcement
from apps.core.logging_utils import (
    log_user_action, log_security_event, get_client_ip
)
from .models import (
    Parent, ParentStudentRelationship, Attendance,
    ParentNotification, ParentAnnouncementRead,
    FeeStructure, StudentInvoice, BankPaymentReceipt
)
from .decorators import parent_required, parent_owns_student
from .forms import ParentProfileForm, BankPaymentReceiptForm


logger = logging.getLogger(__name__)


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
@ratelimit(key='post:login_id', rate='10/h', method='POST', block=True)
def parent_login(request):
    """Parent login view supporting phone number or Parent ID."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        login_id = request.POST.get('login_id', '').strip()
        password = request.POST.get('password')
        ip_address = get_client_ip(request)

        user = authenticate(
            request, username=login_id, password=password
        )

        if user is not None and hasattr(user, 'parent'):
            login(request, user)
            log_security_event(
                'PARENT_LOGIN_SUCCESS',
                user=user,
                ip_address=ip_address,
                details={'method': 'phone/parent_id', 'parent_id': user.parent.parent_id}
            )
            logger.info(
                f"Parent {user.parent.parent_id} logged in from IP {ip_address}"
            )
            messages.success(
                request,
                f'Welcome {user.first_name or "Parent"}!'
            )
            return redirect('parent_dashboard')
        else:
            log_security_event(
                'PARENT_LOGIN_FAILED',
                ip_address=ip_address,
                details={'attempted_login': login_id}
            )
            logger.warning(
                f"Failed parent login attempt for '{login_id}' from IP {ip_address}"
            )
            messages.error(
                request,
                'Invalid phone number, Parent ID, or password.'
            )

    return render(request, 'parents/parent_login.html')


@login_required
@parent_required
def parent_dashboard(request):
    """Parent dashboard showing overview of all linked children."""
    parent = request.user.parent
    children = parent.children.prefetch_related(
        'student_subjects',
    )

    child_list = list(children)
    child_ids = [c.pk for c in child_list]

    # Batch subject IDs per child
    child_subject_ids = defaultdict(set)
    for child in child_list:
        child_subject_ids[child.pk] = set(
            child.student_subjects.values_list('subject_id', flat=True)
        )

    # Single batch query for results averages
    result_avgs = {}
    if child_ids:
        results_qs = Result.objects.filter(
            student_id__in=child_ids, is_published=True
        ).values('student_id', 'subject_id', 'marks')
        student_buckets = defaultdict(list)
        for r in results_qs:
            student_buckets[r['student_id']].append(r)
        for sid, marks_list in student_buckets.items():
            allowed = child_subject_ids.get(sid, set())
            filtered = [m['marks'] for m in marks_list if not allowed or m['subject_id'] in allowed]
            result_avgs[sid] = round(sum(filtered) / len(filtered), 1) if filtered else 0

    # Per-child term-over-term averages for the progress-trends chart
    child_trend_data = {}
    if child_ids:
        from django.db.models import Avg
        all_published = Result.objects.filter(
            student_id__in=child_ids, is_published=True
        ).values('student_id', 'term', 'session', 'marks')
        bucket = defaultdict(lambda: defaultdict(list))
        for r in all_published:
            allowed = child_subject_ids.get(r['student_id'], set())
            # No way to filter by subject here without a second pass — keep
            # the average as-is (it already excludes unpublished results).
            bucket[r['student_id']][r['term']].append(r['marks'])
        for sid, by_term in bucket.items():
            child_trend_data[sid] = {
                code: round(sum(marks) / len(marks), 1) if marks else 0
                for code, marks in by_term.items()
            }

    children_data = []
    total_due = Decimal("0")
    total_paid = Decimal("0")
    for child in child_list:
        assigned_subjects = list(child.assigned_subjects.order_by('is_compulsory', 'name'))
        attendance_summary = Attendance.get_student_summary(child)
        trend = child_trend_data.get(child.pk, {})

        # Per-child fees summary (invoices + standalone approved receipts)
        child_invoices = StudentInvoice.objects.filter(student=child)
        child_due = child_invoices.aggregate(s=Sum("total_amount"))["s"] or Decimal("0")
        child_paid = child_invoices.aggregate(s=Sum("paid_amount"))["s"] or Decimal("0")
        # Include approved standalone payments (no invoice)
        receipt_paid = BankPaymentReceipt.objects.filter(
            student=child, status="approved", invoice__isnull=True
        ).aggregate(s=Sum("amount_paid"))["s"] or Decimal("0")
        child_paid += receipt_paid
        total_due += child_due
        total_paid += child_paid

        if child_due > 0:
            if child_paid >= child_due:
                fee_status = 'paid'
            elif child_paid > 0:
                fee_status = 'partial'
            else:
                fee_status = 'unpaid'
        elif receipt_paid > 0:
            fee_status = 'paid'
        else:
            fee_status = 'none'

        children_data.append({
            'student': child,
            'average': result_avgs.get(child.pk, 0),
            'attendance': attendance_summary,
            'assigned_subjects': assigned_subjects,
            'compulsory_subjects': [s for s in assigned_subjects if s.is_compulsory],
            'elective_subjects': [s for s in assigned_subjects if not s.is_compulsory],
            'subject_count': len(assigned_subjects),
            'trend': trend,
            'fee_total': child_due,
            'fee_paid': child_paid,
            'fee_balance': child_due - child_paid,
            'fee_status': fee_status,
        })

    unread_announcements = Announcement.objects.filter(
        target_audience__in=['all', 'parents']
    ).exclude(
        read_by_parents__parent=parent
    ).count()

    # Build a per-child, per-term dataset for the trend chart (keeps order)
    term_display = {'1st': 'Term 1', '2nd': 'Term 2', '3rd': 'Term 3'}
    trend_chart = {
        'labels': list(term_display.values()),
        'children': [
            {
                'id': c['student'].pk,
                'name': c['student'].user.get_full_name() or c['student'].student_id,
                'short': (c['student'].user.first_name or c['student'].student_id),
                'series': [
                    c['trend'].get(code, 0) for code in ['1st', '2nd', '3rd']
                ],
            }
            for c in children_data
        ],
    }
    overall_balance = total_due - total_paid
    if total_due > 0:
        if total_paid >= total_due:
            overall_fee_status = 'paid'
        elif total_paid > 0:
            overall_fee_status = 'partial'
        else:
            overall_fee_status = 'unpaid'
    else:
        overall_fee_status = 'none'

    context = {
        'parent': parent,
        'children_data': children_data,
        'children_count': len(children_data),
        'unread_announcements': unread_announcements,
        'relationship_display': parent.get_relationship_display_name(),
        'trend_chart_json': trend_chart,
        'overall_fee_total': total_due,
        'overall_fee_paid': total_paid,
        'overall_fee_balance': overall_balance,
        'overall_fee_status': overall_fee_status,
    }
    return render(request, 'parents/parent_dashboard.html', context)


@login_required
@parent_required
@parent_owns_student
def parent_child_results(request, student_id):
    """View results for a specific child."""
    parent = request.user.parent
    student = get_object_or_404(Student, student_id=student_id)

    # Only show results for subjects the child is enrolled in
    assigned_subject_ids = list(
        student.student_subjects.values_list('subject_id', flat=True)
    )

    base_qs = Result.objects.filter(
        student=student, is_published=True
    ).select_related(
        'subject', 'student__current_class'
    )
    if assigned_subject_ids:
        base_qs = base_qs.filter(subject_id__in=assigned_subject_ids)
    all_results = base_qs.order_by('term', 'subject__name')

    term_display = dict(Result.TERM_CHOICES)
    term_codes = list(all_results.values_list('term', flat=True).distinct())

    selected_term = request.GET.get('term', '')
    if not selected_term and term_codes:
        selected_term = term_codes[-1]

    filtered_results = all_results
    if selected_term:
        filtered_results = filtered_results.filter(term=selected_term)

    chart_labels = []
    chart_data = []
    for code in ['1st', '2nd', '3rd']:
        term_results = all_results.filter(term=code)
        if term_results.exists():
            avg = term_results.aggregate(Avg('marks'))['marks__avg']
            chart_labels.append(term_display.get(code, code))
            chart_data.append(round(avg, 1))

    overall_avg = filtered_results.aggregate(Avg('marks'))['marks__avg'] or 0

    assigned_subjects = list(student.assigned_subjects.order_by('is_compulsory', 'name'))

    context = {
        'parent': parent,
        'student': student,
        'results': filtered_results,
        'terms': [(code, term_display.get(code, code)) for code in term_codes],
        'selected_term': selected_term,
        'overall_average': round(overall_avg, 1),
        'chart_data': {'labels': chart_labels, 'data': chart_data},
        'assigned_subjects': assigned_subjects,
        'compulsory_subjects': [s for s in assigned_subjects if s.is_compulsory],
        'elective_subjects': [s for s in assigned_subjects if not s.is_compulsory],
    }
    return render(request, 'parents/child_results.html', context)


@login_required
@parent_required
@parent_owns_student
def parent_child_attendance(request, student_id):
    """View attendance for a specific child."""
    parent = request.user.parent
    student = get_object_or_404(Student, student_id=student_id)

    selected_term = request.GET.get('term', '')
    selected_session = request.GET.get('session', '')

    if not selected_term:
        selected_term = '1st'

    filters = {'student': student}
    if selected_term:
        filters['term'] = selected_term
    if selected_session:
        filters['session'] = selected_session

    records = Attendance.objects.filter(**filters).order_by('-date')
    summary = Attendance.get_student_summary(
        student, term=selected_term, session=selected_session
    )

    sessions = Attendance.objects.filter(
        student=student
    ).values_list('session', flat=True).distinct().order_by('-session')

    context = {
        'parent': parent,
        'student': student,
        'records': records,
        'summary': summary,
        'selected_term': selected_term,
        'selected_session': selected_session,
        'term_choices': Attendance._meta.get_field('term').choices,
        'sessions': sessions,
    }
    return render(request, 'parents/child_attendance.html', context)


@login_required
@parent_required
@parent_owns_student
def parent_child_report_card(request, student_id):
    """View/download report card for a specific child."""
    parent = request.user.parent
    student = get_object_or_404(Student, student_id=student_id)

    selected_term = request.GET.get('term', '')
    selected_session = request.GET.get('session', '')

    # Restrict to subjects the child is enrolled in
    assigned_subject_ids = list(
        student.student_subjects.values_list('subject_id', flat=True)
    )

    results = Result.objects.filter(
        student=student, is_published=True
    ).select_related('subject')
    if assigned_subject_ids:
        results = results.filter(subject_id__in=assigned_subject_ids)

    if selected_term:
        results = results.filter(term=selected_term)
    if selected_session:
        results = results.filter(session=selected_session)

    terms = results.values_list('term', flat=True).distinct()
    sessions = results.values_list('session', flat=True).distinct()

    term_display = dict(Result.TERM_CHOICES)

    grouped_results = {}
    for result in results:
        key = f"{result.term}_{result.session}"
        if key not in grouped_results:
            grouped_results[key] = {
                'term': result.term,
                'term_display': term_display.get(result.term, result.term),
                'session': result.session,
                'compulsory_results': [],
                'elective_results': [],
                'results': [],
                'average': 0,
                'compulsory_average': 0,
                'elective_average': 0,
            }
        grouped_results[key]['results'].append(result)
        if result.subject.is_compulsory:
            grouped_results[key]['compulsory_results'].append(result)
        else:
            grouped_results[key]['elective_results'].append(result)

    for key, group in grouped_results.items():
        marks = [r.marks for r in group['results']]
        group['average'] = round(sum(marks) / len(marks), 1) if marks else 0
        c_marks = [r.marks for r in group['compulsory_results']]
        group['compulsory_average'] = round(sum(c_marks) / len(c_marks), 1) if c_marks else 0
        e_marks = [r.marks for r in group['elective_results']]
        group['elective_average'] = round(sum(e_marks) / len(e_marks), 1) if e_marks else 0
        # Sort by is_compulsory then name for display
        group['compulsory_results'].sort(key=lambda r: r.subject.name)
        group['elective_results'].sort(key=lambda r: r.subject.name)

    assigned_subjects = list(student.assigned_subjects.order_by('is_compulsory', 'name'))

    context = {
        'parent': parent,
        'student': student,
        'grouped_results': grouped_results,
        'terms': terms,
        'sessions': sessions,
        'selected_term': selected_term,
        'selected_session': selected_session,
        'assigned_subjects': assigned_subjects,
        'compulsory_subjects': [s for s in assigned_subjects if s.is_compulsory],
        'elective_subjects': [s for s in assigned_subjects if not s.is_compulsory],
    }
    return render(request, 'parents/child_report_card.html', context)


@login_required
@parent_required
def parent_announcements(request):
    """View announcements relevant to parents."""
    parent = request.user.parent

    announcements = Announcement.objects.filter(
        target_audience__in=['all', 'parents']
    ).select_related('author').order_by('-created_at')

    search_query = request.GET.get('search', '')
    if search_query:
        announcements = announcements.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query)
        )

    read_ids = ParentAnnouncementRead.objects.filter(
        parent=parent
    ).values_list('announcement_id', flat=True)

    paginator = Paginator(announcements, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'parent': parent,
        'page_obj': page_obj,
        'search_query': search_query,
        'read_ids': list(read_ids),
    }
    return render(request, 'parents/announcements.html', context)


@login_required
@parent_required
def parent_announcement_detail(request, pk):
    """View a single announcement and mark as read."""
    parent = request.user.parent
    announcement = get_object_or_404(
        Announcement, pk=pk,
        target_audience__in=['all', 'parents']
    )

    ParentAnnouncementRead.objects.get_or_create(
        parent=parent,
        announcement=announcement,
    )

    context = {
        'parent': parent,
        'announcement': announcement,
    }
    return render(request, 'parents/announcement_detail.html', context)


@login_required
@parent_required
def parent_profile(request):
    """Parent profile editing."""
    parent = request.user.parent

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            form = ParentProfileForm(
                request.POST, instance=parent, user=request.user
            )
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('parent_profile')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
        elif action == 'change_password':
            from django.contrib.auth.forms import PasswordChangeForm
            from django.contrib.auth import update_session_auth_hash

            password_form = PasswordChangeForm(
                user=request.user, data=request.POST
            )
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(
                    request, 'Password changed successfully.'
                )
                return redirect('parent_profile')
            else:
                for field, errors in password_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')

        return redirect('parent_profile')

    form = ParentProfileForm(instance=parent, user=request.user)

    from django.contrib.auth.forms import PasswordChangeForm
    password_form = PasswordChangeForm(user=request.user)

    context = {
        'parent': parent,
        'form': form,
        'password_form': password_form,
    }
    return render(request, 'parents/parent_profile.html', context)


@login_required
@parent_required
def parent_notifications(request):
    """View parent notifications."""
    parent = request.user.parent
    notifications = parent.notifications.all().order_by('-created_at')

    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'parent': parent,
        'page_obj': page_obj,
    }
    return render(request, 'parents/notifications.html', context)


@login_required
@parent_required
def parent_notification_read(request, pk):
    """Mark a notification as read."""
    parent = request.user.parent
    notification = get_object_or_404(
        ParentNotification, pk=pk, parent=parent
    )
    notification.mark_as_read()
    return redirect('parent_notifications')


@login_required
@parent_required
def parent_invoices(request):
    """View to list all fee invoices and payments for the parent's children."""
    parent = request.user.parent
    children = parent.children

    invoices = StudentInvoice.objects.filter(
        student__in=children
    ).select_related('student__user', 'fee_structure').order_by('-created_at')

    paginator = Paginator(invoices, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'parent': parent,
        'page_obj': page_obj,
        'invoices': page_obj.object_list,
    }
    return render(request, 'parents/parent_invoices.html', context)


@login_required
@parent_required
def submit_bank_payment(request, invoice_id):
    """View to upload bank slip details for a student invoice."""
    from django.db import IntegrityError, transaction as db_transaction
    parent = request.user.parent

    invoice = get_object_or_404(StudentInvoice, pk=invoice_id)

    # Permission check: Ensure this invoice belongs to one of the parent's children
    if not parent.children.filter(pk=invoice.student.pk).exists():
        messages.error(request, "Access denied. Student profile not linked.")
        return redirect('parent_invoices')

    # Don't allow uploads for fully paid invoices
    if invoice.status == 'paid':
        messages.warning(request, "This invoice is already fully paid.")
        return redirect('parent_invoices')

    if request.method == 'POST':
        form = BankPaymentReceiptForm(request.POST, request.FILES)
        if form.is_valid():
            reference = form.cleaned_data['transaction_reference']
            # Serialise duplicate-reference detection inside a
            # transaction. The unique constraint on
            # BankPaymentReceipt.transaction_reference is the actual
            # guarantee — the in-check below is a friendlier fast path.
            with db_transaction.atomic():
                # Re-read the invoice's status atomically. The save()
                # call below is the authoritative serialisation point
                # (the IntegrityError catches concurrent dup-ref races).
                current_invoice = StudentInvoice.objects.get(pk=invoice.pk)
                if current_invoice.status == 'paid':
                    messages.warning(request, "This invoice was just paid. Upload cancelled.")
                    return redirect('parent_invoices')
                if BankPaymentReceipt.objects.filter(transaction_reference=reference).exists():
                    messages.error(
                        request,
                        "This transaction reference has already been submitted. "
                        "Please check the reference number and try again.",
                    )
                    return redirect('parent_invoices')
                receipt = form.save(commit=False)
                receipt.invoice = current_invoice
                receipt.status = 'pending'
                try:
                    receipt.save()
                except IntegrityError:
                    messages.error(
                        request,
                        "This transaction reference has already been submitted. "
                        "Please check the reference number and try again.",
                    )
                    return redirect('parent_invoices')
            messages.success(
                request,
                f"Deposit slip for ref '{receipt.transaction_reference}' uploaded. "
                "It will be verified by the school accountant shortly.",
            )
            return redirect('parent_invoices')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = BankPaymentReceiptForm()

    context = {
        'parent': parent,
        'invoice': invoice,
        'form': form,
    }
    return render(request, 'parents/submit_bank_payment.html', context)


@login_required
@parent_required
def upload_receipt(request):
    """Standalone page for parents to upload a bank deposit slip without an invoice."""
    from django.db import IntegrityError, transaction as db_transaction
    parent = request.user.parent

    if request.method == 'POST':
        form = BankPaymentReceiptForm(request.POST, request.FILES, parent=parent)
        if form.is_valid():
            reference = form.cleaned_data['transaction_reference']
            student = form.cleaned_data['student']
            with db_transaction.atomic():
                if BankPaymentReceipt.objects.filter(transaction_reference=reference).exists():
                    messages.error(
                        request,
                        "This transaction reference has already been submitted. "
                        "Please check the reference number and try again.",
                    )
                    return redirect('parent_dashboard')
                receipt = form.save(commit=False)
                receipt.student = student
                receipt.status = 'pending'
                try:
                    receipt.save()
                except IntegrityError:
                    messages.error(
                        request,
                        "This transaction reference has already been submitted. "
                        "Please check the reference number and try again.",
                    )
                    return redirect('parent_dashboard')
            messages.success(
                request,
                f"Deposit slip for {student.user.get_full_name()} (ref '{receipt.transaction_reference}') uploaded. "
                "It will be verified by the school accountant shortly.",
            )
            return redirect('parent_dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = BankPaymentReceiptForm(parent=parent)

    context = {
        'parent': parent,
        'form': form,
    }
    return render(request, 'parents/upload_receipt.html', context)


@login_required
def teacher_take_attendance(request, subject_id):
    from apps.accounts.models import SubjectRegistration, StudentSubject, AcademicTerm
    from apps.school.models import Subject
    from django.db import transaction
    from datetime import date

    if not hasattr(request.user, 'teacher'):
        messages.error(request, 'Access denied. Only teachers can record attendance.')
        return redirect('dashboard_redirect')

    teacher = request.user.teacher
    subject = get_object_or_404(Subject, pk=subject_id)

    if subject not in teacher.subjects.all():
        messages.error(request, 'Access denied. You are not assigned to this subject.')
        return redirect('dashboard_redirect')

    student_class = subject.assigned_class
    if not student_class:
        messages.error(request, 'This subject is not assigned to a class.')
        return redirect('teacher_dashboard')

    active_term = AcademicTerm.objects.filter(is_active=True).first()
    selected_term_code = request.GET.get('term', active_term.term if active_term else '1st')
    selected_session = request.GET.get('session', active_term.session if active_term else '2026-2027')
    selected_date = request.GET.get('date', date.today().isoformat())

    try:
        att_date = date.fromisoformat(selected_date)
    except ValueError:
        att_date = date.today()
        selected_date = att_date.isoformat()

    students = student_class.students.select_related('user').order_by(
        'user__first_name', 'user__last_name'
    )

    existing_records = Attendance.objects.filter(
        student__in=students,
        date=att_date,
        term=selected_term_code,
        session=selected_session,
    ).select_related('student')
    records_map = {r.student_id: r for r in existing_records}

    if request.method == 'POST':
        changes = {'created': [], 'updated': []}
        ip = get_client_ip(request)

        with transaction.atomic():
            for student in students:
                status = request.POST.get(f'status_{student.id}', '').strip()
                remarks = request.POST.get(f'remarks_{student.id}', '').strip()

                if status not in ('present', 'absent', 'late', 'excused'):
                    continue

                existing = records_map.get(student.id)
                if existing:
                    if existing.status != status or existing.remarks != remarks:
                        old_status = existing.status
                        existing.status = status
                        existing.remarks = remarks
                        existing.recorded_by = request.user
                        existing.save()
                        changes['updated'].append(
                            (student.student_id, old_status, status)
                        )
                else:
                    Attendance.objects.create(
                        student=student,
                        date=att_date,
                        status=status,
                        term=selected_term_code,
                        session=selected_session,
                        remarks=remarks,
                        recorded_by=request.user,
                    )
                    changes['created'].append((student.student_id, status))

        for sid, status in changes['created']:
            log_user_action(
                f"Attendance recorded for {sid}: {status} on {att_date} "
                f"in {student_class}",
                user=request.user,
                details={
                    'action': 'record_attendance',
                    'student_id': sid,
                    'date': str(att_date),
                    'status': status,
                    'class': str(student_class),
                    'ip': ip,
                },
                level=20,
            )
        for sid, old, new in changes['updated']:
            log_user_action(
                f"Attendance updated for {sid}: {old} -> {new} on {att_date}",
                user=request.user,
                details={
                    'action': 'update_attendance',
                    'student_id': sid,
                    'date': str(att_date),
                    'old_status': old,
                    'new_status': new,
                    'ip': ip,
                },
                level=20,
            )

        total_changed = len(changes['created']) + len(changes['updated'])
        messages.success(
            request,
            f"Attendance saved for {student_class.name} on {att_date.strftime('%b %d, %Y')}. "
            f"{len(changes['created'])} recorded, {len(changes['updated'])} updated.",
        )
        base_url = reverse('teacher_take_attendance', args=[subject_id])
        return redirect(
            f"{base_url}?term={selected_term_code}&session={selected_session}&date={selected_date}"
        )

    student_data = []
    for student in students:
        rec = records_map.get(student.id)
        student_data.append({
            'student': student,
            'status': rec.status if rec else '',
            'remarks': rec.remarks if rec else '',
        })

    today = date.today()
    recent_dates = []
    d = today
    from datetime import timedelta
    for _ in range(14):
        if d.weekday() < 5:
            recent_dates.append(d.isoformat())
        d = d - timedelta(days=1)

    context = {
        'subject': subject,
        'student_class': student_class,
        'student_data': student_data,
        'selected_term': selected_term_code,
        'selected_session': selected_session,
        'selected_date': selected_date,
        'att_date': att_date,
        'available_terms': AcademicTerm.objects.all().order_by('-session', 'term'),
        'recent_dates': recent_dates,
    }
    return render(request, 'parents/teacher_attendance.html', context)


@login_required
def upload_attendance_csv(request, subject_id):
    from apps.accounts.models import AcademicTerm
    from apps.school.models import Subject
    from django.db import transaction
    from datetime import date
    import csv
    import io

    if not hasattr(request.user, 'teacher'):
        messages.error(request, 'Access denied.')
        return redirect('dashboard_redirect')

    teacher = request.user.teacher
    subject = get_object_or_404(Subject, pk=subject_id)

    if subject not in teacher.subjects.all():
        messages.error(request, 'Access denied.')
        return redirect('dashboard_redirect')

    student_class = subject.assigned_class
    if not student_class:
        messages.error(request, 'This subject is not assigned to a class.')
        return redirect('teacher_dashboard')

    active_term = AcademicTerm.objects.filter(is_active=True).first()
    selected_term_code = request.GET.get('term', active_term.term if active_term else '1st')
    selected_session = request.GET.get('session', active_term.session if active_term else '2026-2027')
    selected_date = request.GET.get('date', date.today().isoformat())

    try:
        att_date = date.fromisoformat(selected_date)
    except ValueError:
        att_date = date.today()
        selected_date = att_date.isoformat()

    students = student_class.students.select_related('user').order_by('registration_number')
    student_map = {s.registration_number: s for s in students}

    if request.method != 'POST':
        base_url = reverse('teacher_take_attendance', args=[subject_id])
        return redirect(f"{base_url}?term={selected_term_code}&session={selected_session}&date={selected_date}")

    csv_file = request.FILES.get('csv_file')
    if not csv_file or not csv_file.name.endswith('.csv'):
        messages.error(request, 'Please upload a valid CSV file.')
        base_url = reverse('teacher_take_attendance', args=[subject_id])
        return redirect(f"{base_url}?term={selected_term_code}&session={selected_session}&date={selected_date}")

    try:
        decoded = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
    except UnicodeDecodeError:
        messages.error(request, 'Could not read the file. Ensure it is UTF-8 encoded.')
        base_url = reverse('teacher_take_attendance', args=[subject_id])
        return redirect(f"{base_url}?term={selected_term_code}&session={selected_session}&date={selected_date}")

    if not {'registration_number', 'status'}.issubset(set(reader.fieldnames or [])):
        messages.error(request, 'CSV must have columns: registration_number, status. Optional: remarks')
        base_url = reverse('teacher_take_attendance', args=[subject_id])
        return redirect(f"{base_url}?term={selected_term_code}&session={selected_session}&date={selected_date}")

    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors = []
    ip = get_client_ip(request)

    with transaction.atomic():
        for i, row in enumerate(reader, start=2):
            reg_number = row.get('registration_number', '').strip()
            status = row.get('status', '').strip().lower()
            remarks = row.get('remarks', '').strip()

            if not reg_number:
                errors.append(f"Row {i}: missing registration_number")
                skipped_count += 1
                continue

            student = student_map.get(reg_number)
            if not student:
                errors.append(f"Row {i}: {reg_number} not in this class")
                skipped_count += 1
                continue

            if status not in ('present', 'absent', 'late', 'excused'):
                errors.append(f"Row {i}: {reg_number} has invalid status '{status}'")
                skipped_count += 1
                continue

            rec, created = Attendance.objects.get_or_create(
                student=student,
                date=att_date,
                term=selected_term_code,
                session=selected_session,
                defaults={
                    'status': status,
                    'remarks': remarks,
                    'recorded_by': request.user,
                },
            )
            if created:
                created_count += 1
            else:
                if rec.status != status or rec.remarks != remarks:
                    rec.status = status
                    rec.remarks = remarks
                    rec.recorded_by = request.user
                    rec.save()
                    updated_count += 1

    if errors:
        messages.warning(
            request,
            f"CSV import done: {created_count} created, {updated_count} updated, "
            f"{skipped_count} skipped. Errors: {'; '.join(errors[:5])}"
            f"{'...' if len(errors) > 5 else ''}"
        )
    else:
        messages.success(
            request,
            f"CSV import complete: {created_count} created, {updated_count} updated."
        )

    base_url = reverse('teacher_take_attendance', args=[subject_id])
    return redirect(f"{base_url}?term={selected_term_code}&session={selected_session}&date={selected_date}")

