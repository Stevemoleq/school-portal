# Re-export Class and Subject from accounts to avoid duplicate model definitions.
# The canonical models live in accounts.models (where migrations already exist).
from apps.accounts.models import Class, Subject  # noqa: F401
