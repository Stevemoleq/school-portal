from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Q
from django.urls import reverse
import json
import csv
import io
import logging
from .models import Result
from apps.accounts.models import Student
from apps.core.logging_utils import log_user_action, get_client_ip

logger = logging.getLogger(__name__)


@login_required
def student_results(request):
    try:
        student = request.user.student
    except Student.DoesNotExist:
        logger.warning(
            f"Access denied: User {request.user.username} attempted to access results without student profile"
        )
        messages.error(request, 'Access denied. Student profile not found.')
        return redirect('dashboard_redirect')

    log_user_action(
        'Viewed student results',
        user=request.user,
        details={'student_id': student.student_id},
        level=10,  # DEBUG — high-volume endpoint
    )

    # Only include results for subjects the student is enrolled in.
    assigned_subject_ids = list(
        student.student_subjects.values_list('subject_id', flat=True)
    )

    base_qs = Result.objects.filter(
        student=student, is_published=True
    ).select_related(
        'subject', 'student__current_class'
    ).order_by(
        'student__current_class', 'term', 'subject__name'
    )
    if assigned_subject_ids:
        base_qs = base_qs.filter(subject_id__in=assigned_subject_ids)
    all_results = base_qs

    assigned_subjects = list(student.assigned_subjects.order_by('is_compulsory', 'name'))

    if not all_results.exists():
        logger.debug(f"No published results found for student {student.student_id}")
        context = {
            'student': student,
            'results_by_form_term': [],
            'all_results': [],
            'forms': [],
            'terms': [],
            'search_query': '',
            'chart_data': {},
            'assigned_subjects': assigned_subjects,
            'compulsory_subjects': [s for s in assigned_subjects if s.is_compulsory],
            'elective_subjects': [s for s in assigned_subjects if not s.is_compulsory],
        }
        return render(request, 'results/student_results.html', context)

    forms = list(
        all_results.values_list('student__current_class__name', flat=True).distinct()
    )

    term_display = dict(Result.TERM_CHOICES)
    term_codes = list(
        all_results.values_list('term', flat=True).distinct()
    )
    terms = [(code, term_display.get(code, code)) for code in term_codes]

    selected_form = request.GET.get('form', '')
    selected_term = request.GET.get('term', '')
    search_query = request.GET.get('search', '').strip()

    if not selected_term and terms:
        selected_term = terms[0][0]

    filtered_results = all_results
    if selected_form:
        filtered_results = filtered_results.filter(student__current_class__name=selected_form)
    if selected_term:
        filtered_results = filtered_results.filter(term=selected_term)
    if search_query:
        filtered_results = filtered_results.filter(
            Q(subject__name__icontains=search_query)
        )

    form_term_groups = {}

    for result in filtered_results:
        form_name = result.student.current_class.name if result.student.current_class else "No Form"
        term_code = result.term
        term_name = term_display.get(term_code, term_code)

        key = f"{form_name}_{term_code}"

        if key not in form_term_groups:
            form_term_groups[key] = {
                'form': form_name,
                'term': term_name,
                'term_code': term_code,
                'results': [],
                'average': 0,
            }

        form_term_groups[key]['results'].append(result)

    results_by_form_term = []
    for key, group in form_term_groups.items():
        if group['results']:
            avg_marks = sum(r.marks for r in group['results']) / len(group['results'])
            group['average'] = round(avg_marks, 2)
            results_by_form_term.append(group)

    results_by_form_term.sort(
        key=lambda x: (
            x['form'],
            ['1st', '2nd', '3rd'].index(x['term_code'])
            if x['term_code'] in ['1st', '2nd', '3rd'] else 999
        )
    )

    current_group = None
    if results_by_form_term:
        current_group = results_by_form_term[0]
        current_group['results'] = sorted(
            current_group['results'], key=lambda r: r.subject.name
        )
        if current_group['results']:
            marks_list = [r.marks for r in current_group['results']]
            current_group['highest_marks'] = max(marks_list)
            current_group['lowest_marks'] = min(marks_list)
            highest_result = max(current_group['results'], key=lambda r: r.marks)
            current_group['highest_subject'] = highest_result.subject.name
            current_group['highest_grade'] = highest_result.grade
            lowest_result = min(current_group['results'], key=lambda r: r.marks)
            current_group['lowest_subject'] = lowest_result.subject.name
            current_group['lowest_grade'] = lowest_result.grade
            passed = sum(1 for r in current_group['results'] if r.marks >= 50)
            current_group['passed_count'] = passed
            current_group['failed_count'] = len(current_group['results']) - passed

    term_averages = {}
    for result in all_results:
        term_code = result.term
        term_name = term_display.get(term_code, term_code)

        if term_code not in term_averages:
            term_averages[term_code] = {'marks': [], 'name': term_name}

        term_averages[term_code]['marks'].append(result.marks)

    chart_labels = []
    chart_data = []
    for code in ['1st', '2nd', '3rd']:
        if code in term_averages:
            marks = term_averages[code]['marks']
            avg = round(sum(marks) / len(marks), 2)
            chart_labels.append(term_averages[code]['name'])
            chart_data.append(avg)

    chart_data_dict = {
        'labels': chart_labels,
        'data': chart_data,
    }

    context = {
        'student': student,
        'current_group': current_group,
        'results_by_form_term': results_by_form_term,
        'all_results': all_results,
        'forms': forms,
        'terms': terms,
        'selected_form': selected_form,
        'selected_term': selected_term,
        'search_query': search_query,
        'chart_data': chart_data_dict,
        'assigned_subjects': assigned_subjects,
        'compulsory_subjects': [s for s in assigned_subjects if s.is_compulsory],
        'elective_subjects': [s for s in assigned_subjects if not s.is_compulsory],
    }
    return render(request, 'results/student_results.html', context)


@login_required
def manage_results(request, subject_id):
    from apps.school.models import Subject
    from apps.accounts.models import SubjectRegistration, StudentSubject, AcademicTerm
    from django.db import transaction

    if not hasattr(request.user, 'teacher'):
        messages.error(request, 'Access denied. Only teachers can manage results.')
        return redirect('dashboard_redirect')

    teacher = request.user.teacher
    subject = get_object_or_404(Subject, pk=subject_id)

    if subject not in teacher.subjects.all():
        messages.error(request, 'Access denied. You are not assigned to this subject.')
        return redirect('dashboard_redirect')

    # Determine term: use GET param or fall back to active term
    selected_term_code = request.GET.get('term', '')
    selected_session = request.GET.get('session', '')
    selected_term = None

    if selected_term_code and selected_session:
        selected_term = AcademicTerm.objects.filter(
            term=selected_term_code, session=selected_session
        ).first()
        if not selected_term:
            messages.error(request, "The selected term/session combination is not valid.")
            return redirect('teacher_dashboard')
    if not selected_term:
        selected_term = AcademicTerm.objects.filter(is_active=True).first()
    if selected_term:
        selected_term_code = selected_term.term
        selected_session = selected_term.session

    # Only show students registered for this subject in the selected term
    student_class = subject.assigned_class
    if selected_term:
        enrolled_ids = SubjectRegistration.objects.filter(
            subject=subject, term=selected_term
        ).values_list('student_id', flat=True)

        # Fallback: if no term registrations exist, use permanent enrollment
        if not enrolled_ids:
            enrolled_ids = StudentSubject.objects.filter(
                subject=subject
            ).values_list('student_id', flat=True)
    else:
        enrolled_ids = []

    if student_class:
        students = student_class.students.filter(
            id__in=enrolled_ids
        ).select_related('user').order_by(
            'user__first_name', 'user__last_name'
        )
    else:
        students = Student.objects.filter(
            id__in=enrolled_ids
        ).select_related('user').order_by(
            'user__first_name', 'user__last_name'
        )

    existing_results = Result.objects.filter(
        subject=subject,
        term=selected_term_code,
        session=selected_session
    ).select_related('student')

    results_map = {res.student_id: res for res in existing_results}

    if request.method == 'POST':
        # Confirm-delete is required for any row whose marks field is blank
        # AND has a stored result. Prevents a teacher from accidentally
        # (or maliciously) wiping marks with a single stray click.
        confirm_delete = request.POST.get('confirm_delete', '')

        changes = {'created': [], 'updated': [], 'deleted': [], 'published': []}
        with transaction.atomic():
            for student in students:
                marks_raw = request.POST.get(f'marks_{student.id}')
                is_published = request.POST.get(f'publish_{student.id}') == 'on'
                existing = results_map.get(student.id)

                if marks_raw != '' and marks_raw is not None:
                    try:
                        marks = float(marks_raw)
                    except ValueError:
                        messages.warning(
                            request,
                            f"Invalid marks format for {student.user.get_full_name()}.",
                        )
                        continue
                    if not (0 <= marks <= 100):
                        messages.warning(
                            request,
                            f"Marks for {student.user.get_full_name()} must be between 0 and 100.",
                        )
                        continue

                    result_obj, created = Result.objects.get_or_create(
                        student=student,
                        subject=subject,
                        term=selected_term_code,
                        session=selected_session,
                        defaults={'marks': marks, 'is_published': is_published},
                    )
                    if created:
                        changes['created'].append(
                            (student.student_id, marks, is_published)
                        )
                    else:
                        if result_obj.marks != marks:
                            changes['updated'].append(
                                (student.student_id, float(result_obj.marks), marks)
                            )
                        if result_obj.is_published != is_published:
                            changes['published'].append(
                                (student.student_id, result_obj.is_published, is_published)
                            )
                        result_obj.marks = marks
                        result_obj.is_published = is_published
                        result_obj.save()
                else:
                    if existing is not None:
                        if not confirm_delete:
                            messages.warning(
                                request,
                                f"Blank marks for {student.user.get_full_name()} ignored — "
                                f"tick 'Confirm deletions' to remove existing results.",
                            )
                            continue
                        changes['deleted'].append(
                            (student.student_id, float(existing.marks), existing.is_published)
                        )
                        existing.delete()

        # Audit log (one entry per change category).
        ip = get_client_ip(request)
        for sid, marks, published in changes['created']:
            log_user_action(
                f"Created result for student {sid}: {marks} (published={published}) "
                f"in {subject} {selected_term} {selected_session}",
                user=request.user,
                details={
                    'action': 'create_result',
                    'student_id': sid,
                    'subject_id': subject.id,
                    'marks': marks,
                    'is_published': published,
                    'term': selected_term,
                    'session': selected_session,
                    'ip': ip,
                },
                level=20,
            )
        for sid, old, new in changes['updated']:
            log_user_action(
                f"Updated result for student {sid}: {old} -> {new} in {subject}",
                user=request.user,
                details={
                    'action': 'update_result',
                    'student_id': sid,
                    'subject_id': subject.id,
                    'old_marks': old,
                    'new_marks': new,
                    'ip': ip,
                },
                level=20,
            )
        for sid, old_marks, was_published in changes['deleted']:
            log_user_action(
                f"DELETED result for student {sid} (was {old_marks}, "
                f"published={was_published}) in {subject}",
                user=request.user,
                details={
                    'action': 'delete_result',
                    'student_id': sid,
                    'subject_id': subject.id,
                    'old_marks': old_marks,
                    'was_published': was_published,
                    'ip': ip,
                },
                level=30,
            )
        for sid, old_pub, new_pub in changes['published']:
            log_user_action(
                f"Changed publish state for student {sid} in {subject}: "
                f"{old_pub} -> {new_pub}",
                user=request.user,
                details={
                    'action': 'change_publish',
                    'student_id': sid,
                    'subject_id': subject.id,
                    'old': old_pub,
                    'new': new_pub,
                    'ip': ip,
                },
                level=25,
            )

        messages.success(
            request,
            f"Results updated. {len(changes['created'])} created, "
            f"{len(changes['updated'])} updated, {len(changes['deleted'])} deleted, "
            f"{len(changes['published'])} publish-state changes.",
        )
        base_url = reverse('manage_results', args=[subject_id])
        return redirect(f"{base_url}?term={selected_term_code}&session={selected_session}")

    student_data = []
    for student in students:
        res = results_map.get(student.id)
        student_data.append({
            'student': student,
            'marks': res.marks if res else '',
            'grade': res.grade if res else '—',
            'is_published': res.is_published if res else False,
        })

    available_terms = AcademicTerm.objects.all().order_by('-session', 'term')

    context = {
        'subject': subject,
        'student_class': student_class,
        'student_data': student_data,
        'selected_term': selected_term_code,
        'selected_session': selected_session,
        'term_choices': Result.TERM_CHOICES,
        'available_terms': available_terms,
    }
    return render(request, 'results/manage_results.html', context)


@login_required
def upload_grades_csv(request, subject_id):
    from apps.school.models import Subject
    from apps.accounts.models import SubjectRegistration, StudentSubject, AcademicTerm
    from django.db import transaction

    if not hasattr(request.user, 'teacher'):
        messages.error(request, 'Access denied. Only teachers can manage results.')
        return redirect('dashboard_redirect')

    teacher = request.user.teacher
    subject = get_object_or_404(Subject, pk=subject_id)

    if subject not in teacher.subjects.all():
        messages.error(request, 'Access denied. You are not assigned to this subject.')
        return redirect('dashboard_redirect')

    selected_term_code = request.GET.get('term', '')
    selected_session = request.GET.get('session', '')
    selected_term = None

    if selected_term_code and selected_session:
        selected_term = AcademicTerm.objects.filter(
            term=selected_term_code, session=selected_session
        ).first()
    if not selected_term:
        selected_term = AcademicTerm.objects.filter(is_active=True).first()
    if selected_term:
        selected_term_code = selected_term.term
        selected_session = selected_term.session

    student_class = subject.assigned_class
    if selected_term:
        enrolled_ids = SubjectRegistration.objects.filter(
            subject=subject, term=selected_term
        ).values_list('student_id', flat=True)
        if not enrolled_ids:
            enrolled_ids = StudentSubject.objects.filter(
                subject=subject
            ).values_list('student_id', flat=True)
    else:
        enrolled_ids = []

    if student_class:
        enrolled_students = student_class.students.filter(
            id__in=enrolled_ids
        ).select_related('user')
    else:
        enrolled_students = Student.objects.filter(
            id__in=enrolled_ids
        ).select_related('user')

    enrolled_map = {s.registration_number: s for s in enrolled_students}

    if request.method != 'POST':
        base_url = reverse('manage_results', args=[subject_id])
        return redirect(f"{base_url}?term={selected_term_code}&session={selected_session}")

    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        messages.error(request, 'No file uploaded.')
        base_url = reverse('manage_results', args=[subject_id])
        return redirect(f"{base_url}?term={selected_term_code}&session={selected_session}")

    if not csv_file.name.endswith('.csv'):
        messages.error(request, 'Please upload a CSV file.')
        base_url = reverse('manage_results', args=[subject_id])
        return redirect(f"{base_url}?term={selected_term_code}&session={selected_session}")

    try:
        decoded = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
    except UnicodeDecodeError:
        messages.error(request, 'Could not read the file. Please ensure it is UTF-8 encoded.')
        base_url = reverse('manage_results', args=[subject_id])
        return redirect(f"{base_url}?term={selected_term_code}&session={selected_session}")

    required_cols = {'registration_number', 'marks'}
    if not required_cols.issubset(set(reader.fieldnames or [])):
        messages.error(
            request,
            'CSV must have columns: registration_number, marks. '
            'Optional column: published (TRUE/FALSE).'
        )
        base_url = reverse('manage_results', args=[subject_id])
        return redirect(f"{base_url}?term={selected_term_code}&session={selected_session}")

    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors = []

    ip = get_client_ip(request)

    with transaction.atomic():
        for i, row in enumerate(reader, start=2):
            reg_number = row.get('registration_number', '').strip()
            marks_raw = row.get('marks', '').strip()
            published_raw = row.get('published', '').strip().upper()

            if not reg_number:
                errors.append(f"Row {i}: missing registration_number")
                skipped_count += 1
                continue

            student = enrolled_map.get(reg_number)
            if not student:
                errors.append(f"Row {i}: {reg_number} not enrolled in this subject")
                skipped_count += 1
                continue

            if marks_raw == '':
                errors.append(f"Row {i}: {reg_number} has no marks")
                skipped_count += 1
                continue

            try:
                marks = float(marks_raw)
            except ValueError:
                errors.append(f"Row {i}: {reg_number} has invalid marks '{marks_raw}'")
                skipped_count += 1
                continue

            if not (0 <= marks <= 100):
                errors.append(f"Row {i}: {reg_number} marks {marks} must be 0-100")
                skipped_count += 1
                continue

            is_published = published_raw in ('TRUE', '1', 'YES', 'Y') if published_raw else False

            result_obj, created = Result.objects.get_or_create(
                student=student,
                subject=subject,
                term=selected_term_code,
                session=selected_session,
                defaults={'marks': marks, 'is_published': is_published},
            )
            if created:
                created_count += 1
                log_user_action(
                    f"CSV import: Created result for {reg_number}: {marks} (published={is_published}) "
                    f"in {subject} {selected_term} {selected_session}",
                    user=request.user,
                    details={
                        'action': 'csv_create_result',
                        'student_id': reg_number,
                        'subject_id': subject.id,
                        'marks': marks,
                        'is_published': is_published,
                        'ip': ip,
                    },
                    level=20,
                )
            else:
                old_marks = result_obj.marks
                result_obj.marks = marks
                result_obj.is_published = is_published
                result_obj.save()
                updated_count += 1
                log_user_action(
                    f"CSV import: Updated result for {reg_number}: {old_marks} -> {marks} "
                    f"in {subject} {selected_term} {selected_session}",
                    user=request.user,
                    details={
                        'action': 'csv_update_result',
                        'student_id': reg_number,
                        'subject_id': subject.id,
                        'old_marks': old_marks,
                        'new_marks': marks,
                        'ip': ip,
                    },
                    level=20,
                )

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
            f"CSV import complete: {created_count} created, {updated_count} updated, "
            f"{skipped_count} skipped."
        )

    base_url = reverse('manage_results', args=[subject_id])
    return redirect(f"{base_url}?term={selected_term_code}&session={selected_session}")


@login_required
def download_grades_template(request, subject_id):
    from apps.school.models import Subject
    from apps.accounts.models import SubjectRegistration, StudentSubject, AcademicTerm
    from django.http import HttpResponse

    if not hasattr(request.user, 'teacher'):
        messages.error(request, 'Access denied.')
        return redirect('dashboard_redirect')

    teacher = request.user.teacher
    subject = get_object_or_404(Subject, pk=subject_id)

    if subject not in teacher.subjects.all():
        messages.error(request, 'Access denied.')
        return redirect('dashboard_redirect')

    selected_term_code = request.GET.get('term', '')
    selected_session = request.GET.get('session', '')
    selected_term = None

    if selected_term_code and selected_session:
        selected_term = AcademicTerm.objects.filter(
            term=selected_term_code, session=selected_session
        ).first()
    if not selected_term:
        selected_term = AcademicTerm.objects.filter(is_active=True).first()
    if selected_term:
        selected_term_code = selected_term.term
        selected_session = selected_term.session

    student_class = subject.assigned_class
    if selected_term:
        enrolled_ids = SubjectRegistration.objects.filter(
            subject=subject, term=selected_term
        ).values_list('student_id', flat=True)
        if not enrolled_ids:
            enrolled_ids = StudentSubject.objects.filter(
                subject=subject
            ).values_list('student_id', flat=True)
    else:
        enrolled_ids = []

    if student_class:
        enrolled_students = student_class.students.filter(
            id__in=enrolled_ids
        ).select_related('user').order_by('registration_number')
    else:
        enrolled_students = Student.objects.filter(
            id__in=enrolled_ids
        ).select_related('user').order_by('registration_number')

    existing_results = Result.objects.filter(
        subject=subject, term=selected_term_code, session=selected_session
    ).select_related('student')
    results_map = {res.student_id: res for res in existing_results}

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="{subject.code}_grades_template.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(['registration_number', 'marks', 'published'])
    for student in enrolled_students:
        res = results_map.get(student.id)
        existing_marks = res.marks if res else ''
        existing_pub = 'TRUE' if res and res.is_published else 'FALSE'
        writer.writerow([student.registration_number, existing_marks, existing_pub])

    return response