from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Announcement
from .forms import AnnouncementForm   # you'll create this form

@login_required
def announcement_list(request):
    """Show announcements based on user role."""
    user = request.user
    if user.is_staff:
        # Staff see all
        announcements = Announcement.objects.all().order_by('-created_at')
    else:
        try:
            user.student
            audience_filter = ['all', 'students']
        except:
            try:
                user.teacher
                audience_filter = ['all', 'teachers']
            except:
                audience_filter = ['all']
        announcements = Announcement.objects.filter(
            target_audience__in=audience_filter
        ).order_by('-created_at')
    
    return render(request, 'announcements/announcement_list.html', {'announcements': announcements})

@login_required
def announcement_detail(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    # Optionally check audience permissions
    return render(request, 'announcements/announcement_detail.html', {'announcement': announcement})

@login_required
def announcement_create(request):
    if not (request.user.is_staff or hasattr(request.user, 'teacher')):
        messages.error(request, 'You are not authorised to create announcements.')
        return redirect('announcement_list')
    
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            ann = form.save(commit=False)
            ann.author = request.user
            ann.save()
            messages.success(request, 'Announcement created.')
            return redirect('announcement_detail', pk=ann.pk)
    else:
        form = AnnouncementForm()
    return render(request, 'announcements/announcement_form.html', {'form': form})

@login_required
def announcement_edit(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    # Only author or admin can edit
    if request.user != announcement.author and not request.user.is_staff:
        messages.error(request, 'You cannot edit this announcement.')
        return redirect('announcement_list')
    
    if request.method == 'POST':
        form = AnnouncementForm(request.POST, instance=announcement)
        if form.is_valid():
            form.save()
            messages.success(request, 'Announcement updated.')
            return redirect('announcement_detail', pk=announcement.pk)
    else:
        form = AnnouncementForm(instance=announcement)
    return render(request, 'announcements/announcement_form.html', {'form': form})

@login_required
def announcement_delete(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    if request.user != announcement.author and not request.user.is_staff:
        messages.error(request, 'You cannot delete this announcement.')
        return redirect('announcement_list')
    
    if request.method == 'POST':
        announcement.delete()
        messages.success(request, 'Announcement deleted.')
        return redirect('announcement_list')
    return render(request, 'announcements/announcement_confirm_delete.html', {'announcement': announcement})

# Create your views here.
