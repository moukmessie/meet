"""Give existing rooms the organization of their owners.

A room gets an organization only when all its owners with a known organization
share the same one. Otherwise it is left empty: with
TRUSTED_ACCESS_SAME_ORGANIZATION, nobody benefits from its trusted access
level except users holding a role on it.
"""

from django.db import migrations


def backfill_room_organization_id(apps, schema_editor):
    """Copy the owners' organization to rooms without one."""
    Room = apps.get_model("core", "Room")
    ResourceAccess = apps.get_model("core", "ResourceAccess")

    organizations_by_room = {}
    owner_accesses = ResourceAccess.objects.filter(
        role="owner",
        user__organization_id__isnull=False,
        resource__room__organization_id__isnull=True,
    ).values_list("resource_id", "user__organization_id")
    for room_id, organization_id in owner_accesses.iterator():
        organizations_by_room.setdefault(room_id, set()).add(organization_id)

    for room_id, organizations in organizations_by_room.items():
        if len(organizations) == 1:
            Room._default_manager.filter(
                pk=room_id, organization_id__isnull=True
            ).update(organization_id=organizations.pop())


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0031_room_organization_id"),
    ]

    operations = [
        migrations.RunPython(backfill_room_organization_id, migrations.RunPython.noop),
    ]
