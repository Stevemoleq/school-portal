"""
PDF receipt generation for the fees module.

Uses ReportLab to produce a clean, printable, school-branded receipt
without requiring any external service.  The PDF is returned as an
``HttpResponse`` with the correct content-disposition so the browser
can either display it inline or download it.
"""
import io
import logging
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


def _format_mwk(value):
    try:
        return f"MWK {Decimal(value):,.2f}"
    except Exception:
        return "MWK 0.00"


TERM_DISPLAY = {"1st": "First Term", "2nd": "Second Term", "3rd": "Third Term"}


def render_receipt_pdf(receipt, school_config):
    """Build a PDF HttpResponse for a single receipt."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        )
    except ImportError:
        logger.error("reportlab is not installed — cannot generate PDF receipt")
        return HttpResponse(
            "PDF generation library is not available on the server.",
            status=503,
            content_type="text/plain",
        )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Receipt {receipt.receipt_number}",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                         fontSize=20, textColor=colors.HexColor("#0f172a"),
                         alignment=1, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                         fontSize=11, textColor=colors.HexColor("#475569"),
                         alignment=1, spaceAfter=14)
    label = ParagraphStyle("label", parent=styles["Normal"],
                            fontSize=9, textColor=colors.HexColor("#475569"))
    val = ParagraphStyle("val", parent=styles["Normal"],
                          fontSize=11, textColor=colors.HexColor("#0f172a"))
    body = ParagraphStyle("body", parent=styles["Normal"],
                           fontSize=10, textColor=colors.HexColor("#0f172a"),
                           leading=14)

    story = []
    school = school_config.school_name or "Nazarene Secondary School"
    motto = school_config.school_motto or ""
    address = school_config.school_address or ""
    phone = school_config.school_phone or ""
    email = school_config.school_email or ""

    story.append(Paragraph(f"<b>{school}</b>", h1))
    if motto:
        story.append(Paragraph(motto, h2))
    elif address:
        story.append(Paragraph(address, h2))
    else:
        story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(
        f'<para alignment="center"><font size="14" color="#0f172a">'
        f'<b>OFFICIAL FEE PAYMENT RECEIPT</b></font></para>',
        styles["Normal"],
    ))
    story.append(Spacer(1, 4 * mm))

    info_data = [
        [Paragraph("<b>Receipt No.</b>", label), Paragraph(receipt.receipt_number, val),
         Paragraph("<b>Date Issued</b>", label), Paragraph(receipt.date_issued.strftime("%d %b %Y %H:%M"), val)],
        [Paragraph("<b>Student ID</b>", label), Paragraph(receipt.student_id, val),
         Paragraph("<b>Term / Year</b>", label), Paragraph(f"{TERM_DISPLAY.get(receipt.term, receipt.term)} · {receipt.academic_year}", val)],
        [Paragraph("<b>Student Name</b>", label), Paragraph(receipt.student_name, val),
         Paragraph("<b>Class</b>", label), Paragraph(
            (receipt.invoice.student.current_class.name if receipt.invoice.student.current_class else "—"), val)],
        [Paragraph("<b>Bank</b>", label), Paragraph(receipt.payment.get_bank_name_display(), val),
         Paragraph("<b>Bank Ref.</b>", label), Paragraph(receipt.payment.transaction_reference, val)],
        [Paragraph("<b>Deposit Date</b>", label), Paragraph(receipt.payment.payment_date.strftime("%d %b %Y"), val),
         Paragraph("<b>Verified By</b>", label), Paragraph(
            receipt.issued_by.get_full_name() if receipt.issued_by else "—", val)],
    ]
    info = Table(info_data, colWidths=[32*mm, 50*mm, 30*mm, 50*mm])
    info.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
    ]))
    story.append(info)
    story.append(Spacer(1, 8 * mm))

    amounts = [
        ["Description", "Amount"],
        [f"Tuition Fee — {receipt.invoice.fee_structure.name}", _format_mwk(receipt.invoice.total_amount)],
        ["Total Invoice", _format_mwk(receipt.invoice.total_amount)],
        ["Previously Paid", _format_mwk(max(receipt.invoice.paid_amount - receipt.amount, Decimal('0.00')))],
        [f"Amount Paid (this receipt)", _format_mwk(receipt.amount)],
        ["Balance After Payment", _format_mwk(receipt.balance_after)],
    ]
    amt_table = Table(amounts, colWidths=[110*mm, 50*mm])
    amt_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ecfdf5")),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#10b981")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(amt_table)
    story.append(Spacer(1, 12 * mm))

    story.append(Paragraph(
        "<b>Notes:</b><br/>"
        "1. This is an official computer-generated receipt — no signature is required.<br/>"
        "2. Please retain this receipt for your records. It may be required for re-admission.<br/>"
        "3. For any queries, contact the school accountant with this receipt number.",
        body,
    ))
    story.append(Spacer(1, 16 * mm))

    # Signature lines
    sig = Table(
        [
            ["_______________________________", "_______________________________"],
            ["Accountant Signature & Date", "Principal Signature & Stamp"],
        ],
        colWidths=[80*mm, 80*mm],
    )
    sig.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#64748b")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(sig)

    story.append(Spacer(1, 6 * mm))
    contact = f"{address}" if address else ""
    if phone:
        contact += f"  ·  {phone}"
    if email:
        contact += f"  ·  {email}"
    if contact:
        story.append(Paragraph(
            f'<para alignment="center"><font size="8" color="#94a3b8">{contact}</font></para>',
            styles["Normal"],
        ))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="receipt_{receipt.receipt_number}.pdf"'
    return response
