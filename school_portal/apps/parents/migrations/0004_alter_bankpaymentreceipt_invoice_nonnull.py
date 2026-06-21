"""Make BankPaymentReceipt.invoice non-nullable.

Any existing rows with NULL invoice are deleted (safe for dev).
"""
from django.db import migrations, models
import django.db.models.deletion


def remove_null_invoice_receipts(apps, schema_editor):
    BankPaymentReceipt = apps.get_model("parents", "BankPaymentReceipt")
    BankPaymentReceipt.objects.filter(invoice__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("parents", "0003_alter_bankpaymentreceipt_invoice"),
    ]

    operations = [
        migrations.RunPython(remove_null_invoice_receipts, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name="bankpaymentreceipt",
            name="invoice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="receipts",
                to="parents.studentinvoice",
            ),
        ),
    ]
