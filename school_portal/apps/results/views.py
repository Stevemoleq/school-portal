from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg
import json
from .models import Result
from apps.accounts.models import Student

@login_required
def student_results(request):
    try:
        student = request.user.student
    except Student.DoesNotExist:
        messages.error(request, 'Access denied. Student profile not found.')
        return redirect('dashboard_redirect')

    # Get all published results for this student
    all_results = Result.objects.filter(student=student, is_published=True)\
        .select_related('subject', 'student__student_class')\
        .order_by('student__student_class', 'term', 'subject__name')

    if not all_results.exists():
        context = {
            'results_by_form_term': [],
            'all_results': [],
            'forms': [],
            'terms': [],
            'chart_data': '{}',
        }
        return render(request, 'results/student_results.html', context)

    # Get unique forms and terms for filter dropdowns
    forms = sorted(set(
        r.student.student_class.name if r.student.student_class else "No Form"
        for r in all_results
    ))
    
    term_display = dict(Result.TERM_CHOICES)
    term_codes = sorted(set(r.term for r in all_results), key=lambda x: ['1st', '2nd', '3rd'].index(x) if x in ['1st', '2nd', '3rd'] else 999)
    terms = [(code, term_display.get(code, code)) for code in term_codes]

    # Get selected filters from GET parameters
    selected_form = request.GET.get('form', '')
    selected_term = request.GET.get('term', '')
    
    # If no term selected, default to the first available term
    if not selected_term and terms:
        selected_term = terms[0][0]  # Get the first term code

    # Filter results based on selections
    filtered_results = all_results
    if selected_form:
        filtered_results = filtered_results.filter(student__student_class__name=selected_form)
    if selected_term:
        filtered_results = filtered_results.filter(term=selected_term)

    # Group filtered results by Form and Term
    form_term_groups = {}
    
    for result in filtered_results:
        form_name = result.student.student_class.name if result.student.student_class else "No Form"
        term_code = result.term
        term_name = term_display.get(term_code, term_code)
        
        # Create a unique key for Form + Term
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
    
    # Calculate average for each Form + Term group
    results_by_form_term = []
    for key, group in form_term_groups.items():
        if group['results']:
            avg_marks = sum(r.marks for r in group['results']) / len(group['results'])
            group['average'] = round(avg_marks, 2)
            results_by_form_term.append(group)
    
    # Sort by form and term
    results_by_form_term.sort(key=lambda x: (x['form'], ['1st', '2nd', '3rd'].index(x['term_code']) if x['term_code'] in ['1st', '2nd', '3rd'] else 999))

    # Prepare chart data - average per term (across ALL results, not filtered)
    term_averages = {}
    for result in all_results:
        term_code = result.term
        term_name = term_display.get(term_code, term_code)
        
        if term_code not in term_averages:
            term_averages[term_code] = {'marks': [], 'name': term_name}
        
        term_averages[term_code]['marks'].append(result.marks)
    
    # Calculate and sort chart data by term (all terms, not filtered)
    chart_labels = []
    chart_data = []
    for code in ['1st', '2nd', '3rd']:
        if code in term_averages:
            marks = term_averages[code]['marks']
            avg = round(sum(marks) / len(marks), 2)
            chart_labels.append(term_averages[code]['name'])
            chart_data.append(avg)
    
    chart_data_json = json.dumps({
        'labels': chart_labels,
        'data': chart_data,
    })

    context = {
        'results_by_form_term': results_by_form_term,
        'all_results': all_results,
        'forms': forms,
        'terms': terms,
        'selected_form': selected_form,
        'selected_term': selected_term,
        'chart_data': chart_data_json,
    }
    return render(request, 'results/student_results.html', context)