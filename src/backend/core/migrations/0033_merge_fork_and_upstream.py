"""Merge the fork organization migrations with the upstream user email ones."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0032_backfill_room_organization_id"),
        ("core", "0032_user_email_idx"),
    ]

    operations = []
