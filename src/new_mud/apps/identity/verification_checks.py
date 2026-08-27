from __future__ import annotations

from django.core.checks import Error, Tags, register

from .verification_config import authentication_baseline_configuration_issue


@register(Tags.security)
def check_verification_configuration(app_configs, **kwargs):
    issue = authentication_baseline_configuration_issue()
    if issue is None:
        return []
    return [Error(issue.check_message, id=issue.check_id)]
