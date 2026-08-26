from __future__ import annotations

import os

import django
from django.core.management import call_command


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "new_mud.settings.development")
    django.setup()
    call_command("migrate", interactive=False, verbosity=1)
    call_command("runserver", "127.0.0.1:8000", noreload=True)


if __name__ == "__main__":
    main()
