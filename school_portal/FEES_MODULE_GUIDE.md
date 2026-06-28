# Tuition Fees Management — Implementation Guide

A complete, bank-based fees workflow for the Nazarene School Portal.

## Overview

```
┌─────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌──────────────┐
│   ADMIN     │    │   PARENT   │    │  ACCOUNTANT│    │   STUDENT  │    │  AUDIT LOG   │
│  creates    │───▶│ deposits   │───▶│  verifies  │───▶│  views     │    │ (immutable)  │
│ FeeStructure│    │ at bank +  │    │  & credits │    │  receipt & │    │              │
│ + invoices  │    │ uploads slip│    │  invoice   │    │  balance   │    │              │
└─────────────┘    └────────────┘    └────────────┘    └──────────────┘    └──────────────┘
```

## Step 1 — Apply migrations

```bash
python manage.py migrate
```

This creates four tables: `Accountant`, `Receipt`, `AuditLog`, `FeeConfiguration`.

## Step 2 — Create an Accountant user

The system uses a `createaccountant` management command:

```bash
python manage.py createaccountant \
    --username=finance \
    --password=secure-password \
    --email=finance@school.com \
    --first-name=Jane \
    --last-name=Banda \
    --phone="+265 999 111 222"
```

What this does:
1. Creates a Django `User` with `is_staff=True` and the `Accountant` group
2. Creates an `Accountant` profile (auto-generates `ACC-0001`, `ACC-0002`, …)
3. (optional) Also creates a `StaffProfile` if `--staff` is passed

The user is auto-added to the "Accountant" group via signals, and removed
from it if the `Accountant` profile is deleted.

## Step 3 — Configure the school (one-time)

Open the Django admin and go to **Fees → Fee Configuration**. Set:
- School name (printed on every receipt)
- School motto
- School phone, email, address (printed on receipts)
- Receipt prefix (default: `RCP`)

There's only ever one `FeeConfiguration` row (singleton pattern).

## Step 4 — Create a fee structure

Two options:

### Option A — Via admin
Admin → Fees → Fee structures → Add fee structure
- Name: "Term 1 Tuition 2026"
- Amount: 100,000.00
- Target class: Form 1A
- Term: First Term
- Session: 2026

### Option B — Custom admin page
Navigate to **Admin → Fees → Fee Structures** (the new fees admin page) to
batch-create structures with auto-invoice generation.

## Step 5 — Generate invoices for a class

The `generate_invoices` view auto-creates one `StudentInvoice` per active
student in the target class. Triggered from:
- Admin → Fee structure detail page → "Generate invoices for this class"
- Or programmatically via `StudentInvoice.objects.bulk_create(...)`

## Step 6 — Parent submits bank deposit slip

1. Parent logs in
2. Sidebar → "Fees & Invoices" (or per-child "Fees" button on dashboard)
3. Clicks "Upload Bank Deposit Slip" on an unpaid invoice
4. Fills the form (bank, reference, amount, date, image)
5. Slips are saved with `status="pending"`

The parent's sidebar shows the per-child view with summary cards, all
invoices, and pending slips.

## Step 7 — Accountant verifies the slip

1. Accountant logs in (auto-redirected to fees dashboard)
2. Sidebar → "Verify Payments" shows pending slips
3. Clicks a slip → sees bank details, depositor, amount, image
4. Approves → invoice is credited, Receipt issued, PDF available
5. Or rejects with required reason → parent is notified

## Step 8 — Student/Parent views the receipt

- Student sidebar → "My Fees" → see invoices + receipts, download PDF
- Parent sidebar → "Fees & Invoices" → click child's "Fees" button →
  per-child view with all receipts, each with PDF download

## Step 9 — Reports

Accountant sidebar → "Reports":
- Filter by period (today, week, month, year)
- See total collected, per-bank, per-term, per-class breakdowns
- Top outstanding students list

## Step 10 — Audit log

Accountant sidebar → "Audit Log":
- Filter by action type and actor
- See every approval, rejection, recording, slip submission
- IP addresses, timestamps, immutable

## Roles & Permissions

| Role        | Permissions                                                  |
|-------------|--------------------------------------------------------------|
| Admin       | All + configure fee structures, generate invoices, view logs |
| Accountant  | Verify/record payments, view reports, view audit log         |
| Teacher     | No fees access                                               |
| Parent      | Read-only own children; submit slips                         |
| Student     | Read-only own fees & receipts                                |

Enforced by:
- `@accountant_required` decorator (returns 302→login or 403)
- View-level checks for student/parent ownership
- `fees_tags.is_accountant` template filter for sidebar rendering

## Models added

### `Accountant`
- One-to-one with `User`
- Auto-generates `accountant_id` (ACC-0001, …)
- Signals auto-add to "Accountant" group on save

### `Receipt`
- One-to-one with `BankPaymentReceipt` (the approved bank slip)
- `receipt_number` auto-generated as `RCP-YYYYMMDD-XXXXXX`
- Stores snapshot of student name, ID, amount, balance-after, term, year

### `AuditLog`
- Append-only trail of `action`, `actor`, `description`, `metadata`
- IP address, user agent, timestamp
- Never updated or deleted by app code

### `FeeConfiguration`
- Singleton — `FeeConfiguration.get_solo()`
- School branding for receipts

## Files

```
apps/fees/
├── __init__.py
├── apps.py                       # FeesConfig
├── decorators.py                 # accountant_required, get_or_create_accountant_group
├── forms.py                      # StudentSearchForm, VerifyPaymentForm, FeeStructureForm, AccountantForm
├── models.py                     # Accountant, Receipt, AuditLog, FeeConfiguration
├── signals.py                    # Auto add/remove from Accountant group
├── pdf.py                        # reportlab receipt generator
├── urls.py                       # 15 routes
├── views.py                      # 13 views
├── admin.py                      # Django admin registration
├── tests.py                      # 14 tests (all pass)
├── migrations/0001_initial.py
├── templatetags/fees_tags.py     # is_accountant filter
├── templates/fees/               # 12 templates
└── management/commands/createaccountant.py
```

## URLs

| URL                                                     | View                  | Who        |
|---------------------------------------------------------|-----------------------|------------|
| `/fees/accountant/`                                     | accountant_dashboard  | accountant |
| `/fees/accountant/search/`                              | search_student        | accountant |
| `/fees/accountant/student/<id>/`                        | student_fee_detail    | accountant |
| `/fees/accountant/verify/`                              | verify_payment_list   | accountant |
| `/fees/accountant/verify/<id>/`                         | verify_payment        | accountant |
| `/fees/accountant/record/<id>/`                         | record_payment        | accountant |
| `/fees/accountant/reports/`                             | reports               | accountant |
| `/fees/accountant/audit/`                               | audit_log             | accountant |
| `/fees/accountant/profile/`                             | accountant_profile    | accountant |
| `/fees/accountant/invoices/<id>/generate/`              | generate_invoices     | admin      |
| `/fees/my-fees/`                                        | student_fees          | student    |
| `/fees/parent/child/<id>/`                              | parent_child_fees     | parent     |
| `/fees/receipt/<num>/`                                  | receipt_detail        | owner      |
| `/fees/receipt/<num>/pdf/`                              | receipt_pdf           | owner      |

## Tests

67 tests pass (`python manage.py test apps.accounts apps.announcements
apps.parents apps.results apps.fees`), including:

- 14 fees tests covering: decorator access, payment approval + Receipt
  creation, rejection (with/without reason), balance auto-update,
  partial-payment status, direct payment recording, receipt number
  uniqueness, fee-structure invoice auto-generation, student access,
  PDF generation
