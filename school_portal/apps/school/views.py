from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import Class, Subject
from .forms import ClassForm, SubjectForm   # you'll create these forms

@staff_member_required
def class_list(request):
    classes = Class.objects.all()
    return render(request, 'school/class_list.html', {'classes': classes})

@staff_member_required
def class_create(request):
    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Class created.')
            return redirect('class_list')
    else:
        form = ClassForm()
    return render(request, 'school/class_form.html', {'form': form})

@staff_member_required
def class_edit(request, pk):
    cls = get_object_or_404(Class, pk=pk)
    if request.method == 'POST':
        form = ClassForm(request.POST, instance=cls)
        if form.is_valid():
            form.save()
            messages.success(request, 'Class updated.')
            return redirect('class_list')
    else:
        form = ClassForm(instance=cls)
    return render(request, 'school/class_form.html', {'form': form})

@staff_member_required
def class_delete(request, pk):
    cls = get_object_or_404(Class, pk=pk)
    if request.method == 'POST':
        cls.delete()
        messages.success(request, 'Class deleted.')
        return redirect('class_list')
    return render(request, 'school/class_confirm_delete.html', {'class': cls})


# Subject views
@staff_member_required
def subject_list(request):
    subjects = Subject.objects.all()
    return render(request, 'school/subject_list.html', {'subjects': subjects})

@staff_member_required
def subject_create(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject created.')
            return redirect('subject_list')
    else:
        form = SubjectForm()
    return render(request, 'school/subject_form.html', {'form': form})

@staff_member_required
def subject_edit(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject updated.')
            return redirect('subject_list')
    else:
        form = SubjectForm(instance=subject)
    return render(request, 'school/subject_form.html', {'form': form})

@staff_member_required
def subject_delete(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        subject.delete()
        messages.success(request, 'Subject deleted.')
        return redirect('subject_list')
    return render(request, 'school/subject_confirm_delete.html', {'subject': subject})
