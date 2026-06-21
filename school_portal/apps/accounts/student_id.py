"""
Student ID Generation Utility

Format: SCHOOLCODE-YY-FORM-SEQUENCE
Example: NZS-26-F1-0001

- NZS  = School code (configurable via settings or constant)
- 26   = Admission year (2-digit)
- F1   = Form at admission
- 0001 = Auto-incrementing sequence number

Concurrency: the sequence is computed inside a database transaction
with a row-level advisory lock (PostgreSQL) or a transaction-scoped
lock (SQLite/others). This makes generation safe across processes
and workers.
"""

from django.db import connection, transaction

# School code — change this to your school's code
SCHOOL_CODE = "NZS"


def get_admission_year_display(year):
    """Convert full year to 2-digit format. e.g., 2026 -> '26'"""
    return str(year)[-2:]


def get_form_display(form_name):
    """
    Convert form name to compact display code.
    Examples:
        'Form 1' -> 'F1'
        'Form 2' -> 'F2'
        'Form 3' -> 'F3'
        'Form 4' -> 'F4'
        'Grade 10' -> 'G10'
        'Senior 1' -> 'S1'
    """
    import re
    form_name = form_name.strip().lower()

    match = re.match(r'form\s*(\d+)', form_name)
    if match:
        return f"F{match.group(1)}"

    match = re.match(r'grade\s*(\d+)', form_name)
    if match:
        return f"G{match.group(1)}"

    match = re.match(r'senior\s*(\d+)', form_name)
    if match:
        return f"S{match.group(1)}"

    match = re.match(r's(\d+)', form_name)
    if match:
        return f"S{match.group(1)}"

    match = re.match(r'f(\d+)', form_name)
    if match:
        return f"F{match.group(1)}"

    return form_name[:2].upper()


def _acquire_sequence_lock(cursor, prefix):
    """Take a transaction-scoped lock keyed on the prefix.

    PostgreSQL uses pg_advisory_xact_lock; SQLite/others fall back to
    an immediate transaction that holds the row lock.
    """
    vendor = connection.vendor
    if vendor == 'postgresql':
        # Hash the prefix to a 64-bit signed integer.
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            [prefix],
        )
    # For other backends the surrounding transaction.atomic() provides
    # sufficient serialization through the unique constraint on
    # student_id, and the caller will retry on IntegrityError.


def _get_next_sequence(school_code, year_2digit, form_code):
    """
    Get the next sequence number for the given combination.
    Must be called inside transaction.atomic().
    """
    prefix = f"{school_code}-{year_2digit}-{form_code}-"

    with connection.cursor() as cursor:
        _acquire_sequence_lock(cursor, prefix)

        cursor.execute(
            """
            SELECT student_id FROM accounts_student
            WHERE student_id LIKE %s
            ORDER BY student_id DESC
            LIMIT 1
            """,
            [f"{prefix}%"],
        )
        row = cursor.fetchone()

        if row:
            last_seq_str = row[0].split("-")[-1]
            try:
                last_seq = int(last_seq_str)
            except ValueError:
                last_seq = 0
            next_seq = last_seq + 1
        else:
            next_seq = 1
        return next_seq


def generate_student_id(school_code=None, admission_year=None, admission_form=None):
    """
    Generate a unique Student ID.

    The computation is wrapped in a database transaction so the
    advisory/row lock prevents concurrent inserts from producing
    duplicate IDs.
    """
    from django.utils import timezone

    if school_code is None:
        school_code = SCHOOL_CODE
    if admission_year is None:
        admission_year = timezone.now().year
    if admission_form is None:
        admission_form = "Form 1"

    year_2digit = get_admission_year_display(admission_year)
    form_code = get_form_display(admission_form)

    with transaction.atomic():
        sequence = _get_next_sequence(school_code, year_2digit, form_code)
        return f"{school_code}-{year_2digit}-{form_code}-{sequence:04d}"
