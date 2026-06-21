"""
Tuition Fees Management Views
==============================

This module provides the views for all fee-related workflows:

* Accountant (financial role): dashboard, search, verify payments, reports, receipt.
* Student: read-only view of own balance and receipts.
* Parent: read-only view of children's balance and payment history.
* PDF receipt generation (downloadable).
"""
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.models import Student
from apps.core.logging_utils import log_user_action, get_client_ip
from apps.parents.decorators import parent_required, parent_owns_student
from apps.parents.models import (
    BankPaymentReceipt, FeeStructure, Parent, StudentInvoice,
)

from .decorators import accountant_required, user_is_accountant
from .forms import StudentSearchForm, VerifyPaymentForm, FeeStructureForm, AccountantForm
from .models import Accountant, AuditLog, FeeConfiguration, Receipt
from .pdf import render_receipt_pdf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _actor_role(user):
    if user.is_superuser:
        return "superuser"
    if hasattr(user, "accountant"):
        return "accountant"
    if hasattr(user, "teacher"):
        return "teacher"
    if hasattr(user, "student"):
        return "student"
    if hasattr(user, "parent"):
        return "parent"
    if user.is_staff:
        return "staff"
    return "user"


def _write_audit(*, action, request, description, target_model="", target_id="", metadata=None):
    """Persist an AuditLog entry.  Never raises."""
    try:
        AuditLog.objects.create(
            action=action,
            actor=request.user if request.user.is_authenticated else None,
            actor_role=_actor_role(request.user) if request.user.is_authenticated else "anonymous",
            target_model=target_model,
            target_id=str(target_id) if target_id else "",
            description=description,
            metadata=metadata or {},
            ip_address=get_client_ip(request),
        )
    except Exception as exc:
        logger.exception("Failed to write audit log: %s", exc)


def _balance_for_invoice(invoice):
    """Return the current outstanding balance for a StudentInvoice."""
    invoice.refresh_from_db()
    return invoice.balance


def _generate_invoices_for_structure(fee_structure, request=None):
    """Auto-generate StudentInvoice rows for every active student.

    If the ``target_class`` is set, only students in that class are billed.
    Otherwise, all students are billed (the school-wide fee).

    Returns the number of invoices created.
    """
    qs = Student.objects.select_related("user", "current_class").filter(user__is_active=True)
    if fee_structure.target_class_id:
        qs = qs.filter(current_class=fee_structure.target_class)
    created = 0
    for student in qs:
        _, was_created = StudentInvoice.objects.get_or_create(
            student=student,
            fee_structure=fee_structure,
            defaults={
                "total_amount": fee_structure.amount,
                "paid_amount": Decimal("0.00"),
                "balance": fee_structure.amount,
                "status": "unpaid",
            },
        )
        if was_created:
            created += 1
    if request is not None and created:
        log_user_action(
            f"Auto-generated {created} invoice(s) for fee structure {fee_structure}",
            user=request.user,
            details={"fee_structure_id": fee_structure.pk, "count": created},
        )
    return created


# ---------------------------------------------------------------------------
# Accountant dashboard
# ---------------------------------------------------------------------------

@login_required
@accountant_required
def accountant_dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    last_30 = today - timedelta(days=30)

    pending = BankPaymentReceipt.objects.filter(status="pending").count()
    approved_today = BankPaymentReceipt.objects.filter(
        status="approved", verified_at__date=today
    ).count()
    approved_month = BankPaymentReceipt.objects.filter(
        status="approved", verified_at__date__gte=month_start
    )
    collected_today = BankPaymentReceipt.objects.filter(
        status="approved", verified_at__date=today
    ).aggregate(s=Sum("amount_paid"))["s"] or Decimal("0.00")
    collected_month = approved_month.aggregate(s=Sum("amount_paid"))["s"] or Decimal("0.00")

    total_outstanding = StudentInvoice.objects.exclude(status="paid").aggregate(
        s=Sum("balance")
    )["s"] or Decimal("0.00")

    total_students = Student.objects.count()
    paid_count = StudentInvoice.objects.filter(status="paid").values("student").distinct().count()
    partial_count = StudentInvoice.objects.filter(status="partially_paid").values("student").distinct().count()
    unpaid_count = max(total_students - paid_count - partial_count, 0)

    recent_payments = BankPaymentReceipt.objects.filter(
        status="approved"
    ).select_related(
        "invoice__student__user", "invoice__fee_structure", "verified_by", "receipt",
        "student__user",
    ).order_by("-verified_at")[:8]

    recent_pending = BankPaymentReceipt.objects.filter(
        status="pending"
    ).select_related(
        "invoice__student__user", "invoice__fee_structure",
        "student__user",
    ).order_by("-created_at")[:8]

    # Last 7 days income for sparkline
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        total = BankPaymentReceipt.objects.filter(
            status="approved", verified_at__date=d
        ).aggregate(s=Sum("amount_paid"))["s"] or 0
        chart_labels.append(d.strftime("%a"))
        chart_data.append(float(total))

    context = {
        "pending": pending,
        "approved_today": approved_today,
        "collected_today": collected_today,
        "collected_month": collected_month,
        "total_outstanding": total_outstanding,
        "paid_count": paid_count,
        "partial_count": partial_count,
        "unpaid_count": unpaid_count,
        "total_students": total_students,
        "recent_payments": recent_payments,
        "recent_pending": recent_pending,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
    }
    _write_audit(
        action="view_report", request=request,
        description="Viewed accountant dashboard",
        target_model="fees.Dashboard", target_id="accountant",
    )
    return render(request, "fees/accountant_dashboard.html", context)


# ---------------------------------------------------------------------------
# Student search (Accountant)
# ---------------------------------------------------------------------------

@login_required
@accountant_required
def search_student(request):
    form = StudentSearchForm(request.GET or None)
    students = Student.objects.select_related("user", "current_class").order_by("student_id")
    if form.is_valid():
        q = (form.cleaned_data.get("q") or "").strip()
        cls = form.cleaned_data.get("class_level")
        if q:
            students = students.filter(
                Q(student_id__icontains=q)
                | Q(user__first_name__icontains=q)
                | Q(user__last_name__icontains=q)
                | Q(registration_number__icontains=q)
            )
        if cls:
            students = students.filter(current_class=cls)

    paginator = Paginator(students, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {"form": form, "page_obj": page_obj, "q": request.GET.get("q", "")}
    return render(request, "fees/search_student.html", context)


# ---------------------------------------------------------------------------
# Student fee detail (Accountant view)
# ---------------------------------------------------------------------------

@login_required
@accountant_required
def student_fee_detail(request, student_id):
    student = get_object_or_404(Student, student_id=student_id)
    invoices = (
        StudentInvoice.objects.filter(student=student)
        .select_related("fee_structure", "student__user")
        .order_by("-created_at")
    )
    from django.db.models import Q
    receipts = (
        BankPaymentReceipt.objects.filter(Q(student=student) | Q(invoice__student=student))
        .select_related("invoice__fee_structure", "verified_by", "student__user")
        .order_by("-created_at")
    )

    # Summary
    total_due = invoices.aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")
    total_paid = invoices.aggregate(s=Sum("paid_amount"))["s"] or Decimal("0.00")
    total_balance = invoices.aggregate(s=Sum("balance"))["s"] or Decimal("0.00")

    # Per-term breakdown
    per_term = {}
    for inv in invoices:
        key = f"{inv.fee_structure.term} · {inv.fee_structure.session}"
        bucket = per_term.setdefault(key, {"due": Decimal("0.00"), "paid": Decimal("0.00"), "balance": Decimal("0.00"), "term": inv.fee_structure.term, "session": inv.fee_structure.session})
        bucket["due"] += inv.total_amount
        bucket["paid"] += inv.paid_amount
        bucket["balance"] += inv.balance

    context = {
        "student": student,
        "invoices": invoices,
        "receipts": receipts,
        "total_due": total_due,
        "total_paid": total_paid,
        "total_balance": total_balance,
        "per_term": sorted(per_term.values(), key=lambda b: b["session"] + b["term"]),
    }
    return render(request, "fees/student_fee_detail.html", context)


# ---------------------------------------------------------------------------
# Verify a pending payment
# ---------------------------------------------------------------------------

@login_required
@accountant_required
@require_http_methods(["GET", "POST"])
def verify_payment(request, receipt_id):
    if request.method == "GET":
        receipt = get_object_or_404(
            BankPaymentReceipt.objects.select_related(
                "invoice__student__user", "invoice__fee_structure", "verified_by"
            ),
            pk=receipt_id,
        )
        if receipt.status == "approved" and not request.GET.get("force"):
            messages.info(request, "This payment has already been approved.")
            return redirect("fees:accountant_verify_list")
        form = VerifyPaymentForm(instance=receipt)
        context = {"receipt": receipt, "form": form}
        return render(request, "fees/verify_payment.html", context)

    # POST — use select_for_update to prevent double-approval race.
    # `of=("self",)` locks only the BankPaymentReceipt row, NOT the
    # joined invoice — necessary because the invoice FK is nullable
    # and PostgreSQL refuses FOR UPDATE on the nullable side of an
    # outer join.
    receipt = get_object_or_404(
        BankPaymentReceipt.objects.select_related(
            "invoice__student__user", "invoice__fee_structure"
        ),
        pk=receipt_id,
    )
    form = VerifyPaymentForm(request.POST, instance=receipt)
    if form.is_valid():
        new_status = form.cleaned_data["status"]
        new_rejection_reason = form.cleaned_data.get("rejection_reason", "")
        with transaction.atomic():
            receipt_locked = BankPaymentReceipt.objects.select_for_update(
                skip_locked=True, of=("self",)
            ).select_related(
                "invoice__student__user", "invoice__fee_structure"
            ).get(pk=receipt_id)

            if receipt_locked.status == "approved":
                messages.info(request, "This payment was just approved by another user.")
                return redirect("fees:accountant_verify_list")

            receipt_locked.verified_by = request.user
            receipt_locked.verified_at = timezone.now()
            receipt_locked.status = new_status
            receipt_locked.rejection_reason = "" if new_status != "rejected" else new_rejection_reason
            receipt_locked.save()

            # On approval: credit the invoice & issue a receipt
            if new_status == "approved":
                invoice = receipt_locked.invoice
                student = receipt_locked.student or (invoice.student if invoice else None)

                if invoice is not None:
                    invoice.paid_amount = (invoice.paid_amount or Decimal("0.00")) + receipt_locked.amount_paid
                    invoice.save()  # auto-computes balance & status

                default_student_name = student.user.get_full_name() or student.student_id if student else "Unknown"
                default_student_id = student.student_id if student else "N/A"

                Receipt.objects.get_or_create(
                    payment=receipt_locked,
                    defaults={
                        "invoice": invoice,
                        "student_name": default_student_name,
                        "student_id": default_student_id,
                        "amount": receipt_locked.amount_paid,
                        "balance_after": invoice.balance if invoice else Decimal("0.00"),
                        "term": invoice.fee_structure.term if invoice else "",
                        "academic_year": invoice.fee_structure.session if invoice else "",
                        "issued_by": request.user,
                    },
                )
                _write_audit(
                    action="approve_payment", request=request,
                    description=f"Approved bank payment {receipt_locked.transaction_reference}",
                    target_model="BankPaymentReceipt", target_id=receipt_locked.pk,
                    metadata={"amount": float(receipt_locked.amount_paid), "student_id": default_student_id},
                )
                messages.success(
                    request,
                    f"Payment of MWK {receipt_locked.amount_paid:,.2f} approved — receipt issued.",
                )
            else:
                _write_audit(
                    action="reject_payment", request=request,
                    description=f"Rejected bank payment {receipt_locked.transaction_reference}",
                    target_model="BankPaymentReceipt", target_id=receipt_locked.pk,
                    metadata={"reason": receipt_locked.rejection_reason},
                )
                messages.warning(request, "Payment rejected. Parent has been notified.")
        return redirect("fees:accountant_verify_list")
    else:
        messages.error(request, "Please correct the errors below.")

    context = {"receipt": receipt, "form": form}
    return render(request, "fees/verify_payment.html", context)


@login_required
@accountant_required
def verify_payment_list(request):
    status_filter = request.GET.get("status", "pending")
    qs = BankPaymentReceipt.objects.select_related(
        "invoice__student__user", "invoice__fee_structure", "verified_by", "receipt",
        "student__user",
    )
    if status_filter in ("pending", "approved", "rejected"):
        qs = qs.filter(status=status_filter)
    qs = qs.order_by("-created_at")

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    counts = {
        "pending": BankPaymentReceipt.objects.filter(status="pending").count(),
        "approved": BankPaymentReceipt.objects.filter(status="approved").count(),
        "rejected": BankPaymentReceipt.objects.filter(status="rejected").count(),
    }
    return render(request, "fees/verify_list.html", {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "counts": counts,
    })


# ---------------------------------------------------------------------------
# Direct recording (no bank slip) — accountant records cash/exception
# ---------------------------------------------------------------------------

@login_required
@accountant_required
@require_http_methods(["GET", "POST"])
def record_payment(request, student_id):
    student = get_object_or_404(Student, student_id=student_id)
    invoices = (
        StudentInvoice.objects.filter(student=student)
        .exclude(status="paid")
        .select_related("fee_structure")
        .order_by("fee_structure__session", "fee_structure__term")
    )

    if request.method == "POST":
        invoice_id = request.POST.get("invoice") or None
        amount_raw = request.POST.get("amount")
        bank_name = (request.POST.get("bank_name") or "").strip()
        reference = (request.POST.get("transaction_reference") or "").strip()
        payment_date_raw = request.POST.get("payment_date") or date.today().isoformat()

        # Validate payment_date strictly — bad input previously caused 500s.
        try:
            parsed_date = date.fromisoformat(payment_date_raw)
        except (TypeError, ValueError):
            messages.error(request, "Invalid payment date. Use the date picker.")
            return redirect("fees:record_payment", student_id=student_id)
        if parsed_date > date.today():
            messages.error(request, "Payment date cannot be in the future.")
            return redirect("fees:record_payment", student_id=student_id)

        try:
            amount = Decimal(amount_raw)
        except Exception:
            amount = Decimal("0.00")
        if amount <= 0:
            messages.error(request, "Amount must be greater than zero.")
            return redirect("fees:record_payment", student_id=student_id)
        if not reference:
            messages.error(request, "A bank reference / transaction number is required.")
            return redirect("fees:record_payment", student_id=student_id)
        if BankPaymentReceipt.objects.filter(transaction_reference=reference).exists():
            messages.error(request, "A payment with this reference already exists. Use a different reference.")
            return redirect("fees:record_payment", student_id=student_id)

        if not invoice_id:
            messages.error(request, "Please select an invoice for this payment.")
            return redirect("fees:record_payment", student_id=student_id)
        # Reject any POST that targets an already-paid or wrong-student
        # invoice, even if the dropdown was bypassed.
        invoice = get_object_or_404(
            StudentInvoice,
            pk=invoice_id,
            student=student,
        )
        if invoice.status == "paid":
            messages.error(
                request,
                "This invoice is already fully paid. A new receipt cannot be issued.",
            )
            return redirect("fees:record_payment", student_id=student_id)
        outstanding = Decimal(str(invoice.balance or 0))
        if amount > outstanding:
            messages.error(
                request,
                f"Amount MWK {amount:,.2f} exceeds the outstanding balance "
                f"of MWK {outstanding:,.2f}.",
            )
            return redirect("fees:record_payment", student_id=student_id)

        with transaction.atomic():
            receipt = BankPaymentReceipt.objects.create(
                invoice=invoice,
                bank_name=bank_name or "other",
                depositor_name=(student.user.get_full_name() or student.student_id),
                transaction_reference=reference,
                amount_paid=amount,
                payment_date=parsed_date,
                status="approved",
                verified_by=request.user,
                verified_at=timezone.now(),
            )
            current_paid = Decimal(str(invoice.paid_amount or 0))
            invoice.paid_amount = current_paid + amount
            invoice.save()

            Receipt.objects.create(
                payment=receipt,
                invoice=invoice,
                student_name=invoice.student.user.get_full_name() or invoice.student.student_id,
                student_id=invoice.student.student_id,
                amount=amount,
                balance_after=invoice.balance,
                term=invoice.fee_structure.term,
                academic_year=invoice.fee_structure.session,
                issued_by=request.user,
            )
            _write_audit(
                action="record_payment", request=request,
                description=f"Recorded direct payment {reference}",
                target_model="StudentInvoice",
                target_id=invoice.pk,
                metadata={"amount": float(amount), "reference": reference, "student_id": student.student_id},
            )
            messages.success(request, f"Payment of MWK {amount:,.2f} recorded and receipt issued.")
        return redirect("fees:student_fee_detail", student_id=student_id)

    context = {"student": student, "invoices": invoices}
    return render(request, "fees/record_payment.html", context)


# ---------------------------------------------------------------------------
# Receipt download (PDF)
# ---------------------------------------------------------------------------

@login_required
def receipt_detail(request, receipt_number):
    receipt = get_object_or_404(
        Receipt.objects.select_related(
            "payment", "invoice__student__user", "invoice__fee_structure", "issued_by"
        ),
        receipt_number=receipt_number,
    )
    if not _user_can_view_receipt(request.user, receipt):
        return HttpResponseForbidden("You are not allowed to view this receipt.")
    _write_audit(
        action="download_receipt", request=request,
        description=f"Viewed receipt {receipt.receipt_number}",
        target_model="Receipt", target_id=receipt.pk,
        metadata={"student_id": receipt.student_id},
    )
    return render(request, "fees/receipt.html", {"receipt": receipt})


@login_required
def receipt_pdf(request, receipt_number):
    receipt = get_object_or_404(
        Receipt.objects.select_related(
            "payment", "invoice__student__user", "invoice__fee_structure", "issued_by"
        ),
        receipt_number=receipt_number,
    )
    if not _user_can_view_receipt(request.user, receipt):
        return HttpResponseForbidden("You are not allowed to download this receipt.")
    config = FeeConfiguration.get_solo()
    _write_audit(
        action="download_receipt", request=request,
        description=f"Downloaded PDF receipt {receipt.receipt_number}",
        target_model="Receipt", target_id=receipt.pk,
    )
    return render_receipt_pdf(receipt, config)


def _user_can_view_receipt(user, receipt):
    if user.is_superuser or user_is_accountant(user):
        return True
    if hasattr(user, "student"):
        return user.student.student_id == receipt.student_id
    if hasattr(user, "parent"):
        if receipt.invoice:
            return receipt.invoice.student.parent_relationships.filter(parent=user.parent).exists()
        return False
    return False


# ---------------------------------------------------------------------------
# Student fee portal (read-only)
# ---------------------------------------------------------------------------

@login_required
def student_fees(request):
    if not hasattr(request.user, "student"):
        messages.error(request, "Only students can view their fee portal here.")
        return redirect("dashboard_redirect")
    from django.db.models import Q
    student = request.user.student
    invoices = (
        StudentInvoice.objects.filter(student=student)
        .select_related("fee_structure")
        .order_by("-created_at")
    )
    receipts = (
        Receipt.objects.filter(Q(invoice__student=student) | Q(payment__student=student))
        .select_related("invoice__fee_structure", "payment__student__user")
        .order_by("-date_issued")
    )
    pending_slips = (
        BankPaymentReceipt.objects.filter(
            Q(student=student) | Q(invoice__student=student),
            status="pending",
        )
        .select_related("invoice__fee_structure", "student__user")
        .order_by("-created_at")
    )
    total_due = invoices.aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")
    total_paid = invoices.aggregate(s=Sum("paid_amount"))["s"] or Decimal("0.00")
    total_balance = invoices.aggregate(s=Sum("balance"))["s"] or Decimal("0.00")

    return render(request, "fees/student_fees.html", {
        "student": student,
        "invoices": invoices,
        "receipts": receipts,
        "pending_slips": pending_slips,
        "total_due": total_due,
        "total_paid": total_paid,
        "total_balance": total_balance,
    })


# ---------------------------------------------------------------------------
# Parent: per-child fee portal
# ---------------------------------------------------------------------------

@login_required
@parent_required
@parent_owns_student
def parent_child_fees(request, student_id):
    from django.db.models import Q
    student = get_object_or_404(Student, student_id=student_id)
    invoices = (
        StudentInvoice.objects.filter(student=student)
        .select_related("fee_structure")
        .order_by("-created_at")
    )
    receipts = (
        Receipt.objects.filter(Q(invoice__student=student) | Q(payment__student=student))
        .select_related("invoice__fee_structure", "payment__student__user")
        .order_by("-date_issued")
    )
    pending_slips = (
        BankPaymentReceipt.objects.filter(
            Q(student=student) | Q(invoice__student=student),
            status="pending",
        )
        .select_related("invoice__fee_structure", "student__user")
        .order_by("-created_at")
    )
    total_due = invoices.aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")
    total_paid = invoices.aggregate(s=Sum("paid_amount"))["s"] or Decimal("0.00")
    total_balance = invoices.aggregate(s=Sum("balance"))["s"] or Decimal("0.00")
    return render(request, "fees/parent_child_fees.html", {
        "student": student,
        "invoices": invoices,
        "receipts": receipts,
        "pending_slips": pending_slips,
        "total_due": total_due,
        "total_paid": total_paid,
        "total_balance": total_balance,
    })


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@login_required
@accountant_required
def reports(request):
    today = timezone.localdate()
    period = request.GET.get("period", "month")
    if period == "today":
        start = today
    elif period == "week":
        start = today - timedelta(days=7)
    elif period == "year":
        start = today.replace(month=1, day=1)
    else:
        start = today.replace(day=1)
        period = "month"

    payments_qs = BankPaymentReceipt.objects.filter(
        status="approved", verified_at__date__gte=start
    )
    total_collected = payments_qs.aggregate(s=Sum("amount_paid"))["s"] or Decimal("0.00")

    # Per-bank
    per_bank = (
        payments_qs.values("bank_name")
        .annotate(total=Sum("amount_paid"), count=Count("id"))
        .order_by("-total")
    )

    # Per-term
    per_term = (
        payments_qs.values("invoice__fee_structure__term", "invoice__fee_structure__session")
        .annotate(total=Sum("amount_paid"), count=Count("id"))
        .order_by("-total")
    )

    # Class summary
    per_class_qs = (
        StudentInvoice.objects.values("fee_structure__target_class__name")
        .annotate(
            due=Sum("total_amount"),
            paid=Sum("paid_amount"),
            balance=Sum("balance"),
        ).order_by("fee_structure__target_class__name")
    )

    # Outstanding (top 20)
    outstanding = (
        StudentInvoice.objects.exclude(status="paid")
        .select_related("student__user", "fee_structure")
        .order_by("-balance")[:20]
    )

    _write_audit(
        action="view_report", request=request,
        description=f"Viewed financial report ({period})",
        target_model="fees.Report", target_id=period,
    )

    context = {
        "period": period,
        "period_choices": [("today", "Today"), ("week", "Last 7 days"), ("month", "This month"), ("year", "This year")],
        "start": start,
        "end": today,
        "total_collected": total_collected,
        "per_bank": per_bank,
        "per_term": per_term,
        "per_class": per_class_qs,
        "outstanding": outstanding,
        "total_outstanding": StudentInvoice.objects.exclude(status="paid").aggregate(s=Sum("balance"))["s"] or Decimal("0.00"),
    }
    return render(request, "fees/reports.html", context)


# ---------------------------------------------------------------------------
# Audit log — restricted to superusers because it exposes internal
# staff usernames and IP addresses.
# ---------------------------------------------------------------------------

@login_required
def audit_log(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. Superuser privileges required.")
        return redirect("dashboard_redirect")

    qs = AuditLog.objects.select_related("actor").order_by("-timestamp")
    action = request.GET.get("action")
    if action:
        qs = qs.filter(action=action)
    actor = request.GET.get("actor")
    if actor:
        qs = qs.filter(actor__username__icontains=actor)

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "fees/audit_log.html", {
        "page_obj": page_obj,
        "actions": AuditLog.ACTION_CHOICES,
        "selected_action": action,
        "selected_actor": actor,
    })


# ---------------------------------------------------------------------------
# Invoice generator (admin/accountant)
# ---------------------------------------------------------------------------

@login_required
@accountant_required
@require_http_methods(["POST"])
def generate_invoices(request, fee_structure_id):
    fee_structure = get_object_or_404(FeeStructure, pk=fee_structure_id)
    count = _generate_invoices_for_structure(fee_structure, request=request)
    if count:
        messages.success(request, f"Generated {count} invoice(s) for {fee_structure}.")
    else:
        messages.info(request, "All matching students already have invoices for this fee structure.")
    _write_audit(
        action="create_invoice", request=request,
        description=f"Generated invoices for fee structure {fee_structure}",
        target_model="FeeStructure", target_id=fee_structure.pk,
        metadata={"count": count},
    )
    return redirect("fees:fee_structure_list")


# ---------------------------------------------------------------------------
# Fee structure management (accountant portal)
# ---------------------------------------------------------------------------

@login_required
@accountant_required
def fee_structure_list(request):
    structures = FeeStructure.objects.all().select_related("target_class").order_by("-session", "term", "name")
    return render(request, "fees/fee_structure_list.html", {"structures": structures})


@login_required
@accountant_required
def fee_structure_create(request):
    from .forms import FeeStructureForm
    if request.method == "POST":
        form = FeeStructureForm(request.POST)
        if form.is_valid():
            fs = form.save()
            _write_audit(
                action="create_fee_structure", request=request,
                description=f"Created fee structure '{fs.name}' ({fs.session} {fs.term})",
                target_model="FeeStructure", target_id=fs.pk,
                metadata={"amount": float(fs.amount)},
            )
            messages.success(request, f"Fee structure '{fs.name}' created.")
            return redirect("fees:fee_structure_list")
    else:
        form = FeeStructureForm()
    return render(request, "fees/fee_structure_form.html", {"form": form})


# ---------------------------------------------------------------------------
# Accountant profile
# ---------------------------------------------------------------------------

@login_required
@accountant_required
def accountant_profile(request):
    accountant, _ = Accountant.objects.get_or_create(user=request.user)
    from .forms import AccountantForm
    if request.method == "POST":
        form = AccountantForm(request.POST, instance=accountant, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("fees:accountant_profile")
    else:
        form = AccountantForm(instance=accountant, user=request.user)
    return render(request, "fees/accountant_profile.html", {"form": form, "accountant": accountant})
