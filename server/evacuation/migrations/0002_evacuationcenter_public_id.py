"""Backfill one stable UUID per legacy row without replacing center records."""

import uuid

from django.db import migrations, models


def backfill_public_ids(apps, schema_editor):
    center_model = apps.get_model("evacuation", "EvacuationCenter")
    centers = center_model.objects.using(schema_editor.connection.alias)
    for center in centers.filter(public_id__isnull=True).only("pk").iterator():
        centers.filter(pk=center.pk).update(public_id=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("evacuation", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="evacuationcenter",
            name="public_id",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(backfill_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="evacuationcenter",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
