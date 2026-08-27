from __future__ import annotations

import os

import pytest
from django.conf import settings
from django.core.mail import EmailMessage

from new_mud.apps.identity.verification import ContactInvalid, normalize_email

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SMTP_TESTS") != "1",
    reason="development SMTP smoke requires explicit RUN_SMTP_TESTS=1 opt-in",
)


def test_opt_in_163_smtp_delivery() -> None:
    recipient = os.getenv("SMTP_SMOKE_RECIPIENT", "").strip()
    assert recipient, "SMTP smoke requires an explicit SMTP_SMOKE_RECIPIENT"
    try:
        normalized_recipient = normalize_email(recipient)
    except ContactInvalid:
        pytest.fail("SMTP_SMOKE_RECIPIENT is not a supported email address", pytrace=False)

    assert settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend", (
        "SMTP smoke requires the real Django SMTP backend"
    )
    assert settings.EMAIL_HOST == "smtp.163.com", (
        "This development-only smoke is restricted to the approved 163 SMTP host"
    )
    assert settings.EMAIL_HOST_USER, "SMTP smoke requires a locally injected EMAIL_HOST_USER"
    assert os.getenv("EMAIL_HOST_PASSWORD"), (
        "SMTP smoke requires a locally injected EMAIL_HOST_PASSWORD"
    )
    assert settings.DEFAULT_FROM_EMAIL, "SMTP smoke requires DEFAULT_FROM_EMAIL"

    message = EmailMessage(
        subject="New_Mud development SMTP smoke",
        body=(
            "This is an explicitly requested development-only delivery check. "
            "It is not Public V1 provider evidence."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[normalized_recipient.delivery],
    )
    try:
        delivered = message.send(fail_silently=False)
    except Exception:
        pytest.fail(
            "Development SMTP smoke failed; provider details and recipient are suppressed",
            pytrace=False,
        )

    assert delivered == 1, "Development SMTP smoke did not report exactly one delivery"
