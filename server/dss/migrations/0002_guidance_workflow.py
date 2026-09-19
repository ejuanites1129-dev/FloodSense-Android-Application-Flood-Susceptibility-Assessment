from django.db import migrations, models
from django.db.models import Q


def preserve_existing_publication_state(apps, schema_editor):
    GuidanceItem = apps.get_model("dss", "GuidanceItem")
    eligible_ids = []
    for item in GuidanceItem.objects.filter(is_enabled=True).select_related(
        "source", "susceptibility_level__source"
    ):
        source = item.source
        level = item.susceptibility_level
        level_source = level.source
        demonstration_eligible = (
            item.status == "DEMONSTRATION"
            and source.status == "DEMONSTRATION"
            and source.source_type == "DEMONSTRATION"
            and level.status == "DEMONSTRATION"
            and level.is_enabled
            and level_source.status == "DEMONSTRATION"
            and level_source.source_type == "DEMONSTRATION"
        )
        approved_eligible = (
            item.status == "APPROVED"
            and source.status == "APPROVED"
            and source.source_type != "DEMONSTRATION"
            and source.is_publicly_releasable
            and level.status == "APPROVED"
            and level.is_enabled
            and level_source.status == "APPROVED"
            and level_source.source_type != "DEMONSTRATION"
            and level_source.is_publicly_releasable
        )
        if demonstration_eligible or approved_eligible:
            eligible_ids.append(item.pk)

    GuidanceItem.objects.filter(pk__in=eligible_ids).update(
        workflow_status="PUBLISHED"
    )
    GuidanceItem.objects.filter(is_enabled=True).exclude(pk__in=eligible_ids).update(
        is_enabled=False,
        workflow_status="DRAFT",
    )


def restore_legacy_state(apps, schema_editor):
    GuidanceItem = apps.get_model("dss", "GuidanceItem")
    GuidanceItem.objects.update(is_enabled=False)


class Migration(migrations.Migration):

    dependencies = [
        ("dss", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="guidanceitem",
            name="attribution",
            field=models.TextField(
                blank=True,
                help_text="Public-facing credit or attribution required by the source.",
            ),
        ),
        migrations.AddField(
            model_name="guidanceitem",
            name="workflow_status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("IN_REVIEW", "In review"),
                    ("APPROVED", "Approved"),
                    ("PUBLISHED", "Published"),
                ],
                default="DRAFT",
                max_length=20,
            ),
        ),
        migrations.RunPython(
            preserve_existing_publication_state,
            restore_legacy_state,
        ),
        migrations.AlterModelOptions(
            name="guidanceitem",
            options={
                "ordering": (
                    "susceptibility_level__display_order",
                    "display_order",
                    "id",
                ),
                "permissions": (
                    ("approve_guidanceitem", "Can approve preparedness guidance"),
                    ("publish_guidanceitem", "Can publish preparedness guidance"),
                ),
            },
        ),
        migrations.AddConstraint(
            model_name="guidanceitem",
            constraint=models.CheckConstraint(
                condition=Q(is_enabled=False) | Q(workflow_status="PUBLISHED"),
                name="guidance_enabled_only_when_published",
            ),
        ),
    ]
