from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Announcement
from .forms import AnnouncementForm


@login_required
def announcement_list(request):
    """Show announcements based on user role with search & filter support."""
    user = request.user
    if user.is_superuser or user.is_staff:
        base_qs = Announcement.objects.select_related('author')
        audience_filter = None
    else:
        audience_filter = _audience_filter_for(user) or ['all']
        base_qs = Announcement.objects.filter(
            target_audience__in=audience_filter
        ).select_related('author')

    search_query = request.GET.get('search', '').strip()
    audience_q = request.GET.get('audience', '').strip()

    if search_query:
        base_qs = base_qs.filter(
            Q(title__icontains=search_query) | Q(content__icontains=search_query)
        )
    if audience_q and (user.is_superuser or user.is_staff):
        base_qs = base_qs.filter(target_audience=audience_q)

    base_qs = base_qs.order_by('-created_at')

    paginator = Paginator(base_qs, 10)
    page_number = request.GET.get('page')
    announcements = paginator.get_page(page_number)

    return render(request, 'announcements/announcement_list.html', {
        'announcements': announcements,
        'search_query': search_query,
        'audience_filter': audience_q,
    })


def _audience_filter_for(user):
    if user.is_superuser or user.is_staff:
        return None  # no restriction
    if hasattr(user, 'student'):
        return ['all', 'students']
    if hasattr(user, 'teacher'):
        return ['all', 'teachers']
    if hasattr(user, 'parent'):
        return ['all', 'parents']
    return ['all']


@login_required
def announcement_detail(request, pk):
    user = request.user
    qs = Announcement.objects.select_related('author')
    allowed = _audience_filter_for(user)
    if allowed is not None:
        qs = qs.filter(target_audience__in=allowed)
    announcement = get_object_or_404(qs, pk=pk)
    return render(request, 'announcements/announcement_detail.html', {'announcement': announcement})


@login_required
def announcement_create(request):
    if not (request.user.is_superuser or request.user.is_staff or hasattr(request.user, 'teacher')):
        messages.error(request, 'You are not authorised to create announcements.')
        return redirect('announcement_list')

    is_teacher_only = (
        not request.user.is_superuser
        and not request.user.is_staff
        and hasattr(request.user, 'teacher')
    )

    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            target_audience = form.cleaned_data.get('target_audience')
            # Teachers can only target students/all. Staff/superusers
            # can target any audience.
            if is_teacher_only and target_audience == 'parents':
                messages.error(
                    request,
                    'Teachers can only publish announcements to students or everyone.',
                )
            else:
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
