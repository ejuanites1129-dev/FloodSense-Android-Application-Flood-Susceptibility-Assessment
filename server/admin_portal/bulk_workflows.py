"""Preview each normal transition in a rolled-back savepoint, then apply a snapshot.

The confirmation explicitly names rejected records. The eligible subset is one
transaction: a stale record or failed validation rolls back ALL applied changes.
"""

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from dss.flow_workflow import (
    publish_dss_flow,
    retire_dss_flow,
    return_dss_flow_to_draft,
    submit_dss_flow,
)
from dss.models import DSSFlowVersion, GuidanceItem
from dss.workflow import TRANSITIONS as GUIDANCE_ACTIONS
from dss.workflow import transition_guidance
from evacuation.models import EvacuationCenter
from evacuation.workflow import TRANSITIONS as CENTER_ACTIONS
from evacuation.workflow import transition_center
from provenance.models import DataSource
from provenance.workflow import TRANSITIONS as SOURCE_ACTIONS
from provenance.workflow import transition_source

from .record_workflows import require_fresh, require_permission

FLOW_ACTIONS = {
    "submit": ("review_dssflowversion", "Submit for review", submit_dss_flow),
    "return": ("review_dssflowversion", "Return to draft", return_dss_flow_to_draft),
    "publish": ("publish_dssflowversion", "Publish reviewed flow", publish_dss_flow),
    "retire": ("publish_dssflowversion", "Retire / unpublish", retire_dss_flow),
}
MODELS = {
    "centers": EvacuationCenter,
    "sources": DataSource,
    "guidance": GuidanceItem,
    "flows": DSSFlowVersion,
}
ACTION_MAPS = {"centers": CENTER_ACTIONS, "sources": SOURCE_ACTIONS, "guidance": GUIDANCE_ACTIONS}
SALT = "floodsense-bulk-review-v1"
LIMIT = 1000


def permitted_actions(module, actor):
    if module == "flows":
        return [
            (a, spec[1]) for a, spec in FLOW_ACTIONS.items() if actor.has_perm("dss." + spec[0])
        ]
    return [
        (a, spec.label)
        for a, spec in ACTION_MAPS[module].items()
        if actor.has_perm(spec.permission)
    ]


def view_permission(module):
    model = MODELS[module]
    return f"{model._meta.app_label}.view_{model._meta.model_name}"


def _apply(module, record, action, actor, verified_on=None):
    if module == "centers":
        return transition_center(
            center_id=record.pk,
            action=action,
            actor=actor,
            expected_status=record.verification_status,
            verified_on=verified_on,
        )
    if module == "sources":
        return transition_source(
            source_id=record.pk,
            action=action,
            actor=actor,
            expected_status=record.status,
            expected_public=record.is_publicly_releasable,
        )
    if module == "guidance":
        return transition_guidance(
            item_id=record.pk, action=action, actor=actor, expected_status=record.workflow_status
        )
    return FLOW_ACTIONS[action][2](
        flow_id=record.pk, actor=actor, expected_updated_at=record.updated_at
    )


def _dependencies(record):
    # Source revocation/correction invalidates a previously reviewed snapshot.
    result = {}
    if getattr(record, "source_id", None):
        result[str(record.source_id)] = record.source.updated_at.isoformat()
    if isinstance(record, DSSFlowVersion):
        for source in DataSource.objects.filter(
            pk__in=list(record.outcomes.values_list("source_id", flat=True))
            + list(record.content_blocks.values_list("source_id", flat=True))
        ):
            result[str(source.pk)] = source.updated_at.isoformat()
    return result


@transaction.atomic
def preview_bulk(*, module, ids, action, actor, verified_on=None):
    require_permission(actor, view_permission(module))
    if action not in dict(permitted_actions(module, actor)):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    if not ids or len(set(ids)) > LIMIT:
        raise ValidationError("Select 1 through 1,000 records. Refine larger matching sets.")
    records = list(MODELS[module].objects.filter(pk__in=ids).order_by("pk"))
    if len(records) != len(set(ids)):
        raise ValidationError("A selected record no longer exists. Refresh the list.")
    eligible, rejected, snapshots = [], [], []
    for record in records:
        snapshot = {
            "id": record.pk,
            "revision": record.updated_at.isoformat(),
            "sources": _dependencies(record),
        }
        try:
            with transaction.atomic():
                _apply(module, record, action, actor, verified_on)
                transaction.set_rollback(True)
        except ValidationError as error:
            rejected.append({"id": record.pk, "label": str(record), "reasons": error.messages})
        else:
            eligible.append({"id": record.pk, "label": str(record)})
        snapshots.append(snapshot)
    token = signing.dumps(
        {
            "actor": actor.pk,
            "module": module,
            "action": action,
            "snapshots": snapshots,
            "eligible": [r["id"] for r in eligible],
            "verified_on": verified_on.isoformat() if verified_on else None,
        },
        salt=SALT,
    )
    return {
        "eligible": eligible,
        "rejected": rejected,
        "token": token,
        "total": len(records),
        "action_label": dict(permitted_actions(module, actor))[action],
    }


@transaction.atomic
def execute_bulk(*, token, actor):
    from datetime import date

    try:
        data = signing.loads(token, salt=SALT, max_age=1800)
    except signing.BadSignature as error:
        raise ValidationError(
            "Review confirmation expired or is invalid. Preview again."
        ) from error
    if data["actor"] != actor.pk:
        raise ValidationError("This review belongs to another administrator.")
    module = data["module"]
    require_permission(actor, view_permission(module))
    sources = {}
    for snapshot in data["snapshots"]:
        sources.update(snapshot["sources"])
    for source in DataSource.objects.select_for_update().filter(pk__in=sources).order_by("pk"):
        require_fresh(source, sources[str(source.pk)])
    ids = [s["id"] for s in data["snapshots"]]
    records = {
        r.pk: r
        for r in MODELS[module].objects.select_for_update().filter(pk__in=ids).order_by("pk")
    }
    if len(records) != len(ids):
        raise ValidationError("A selected record was removed. No changes applied.")
    for snapshot in data["snapshots"]:
        require_fresh(records[snapshot["id"]], snapshot["revision"])
    verified_on = date.fromisoformat(data["verified_on"]) if data["verified_on"] else None
    for record_id in data["eligible"]:
        _apply(module, records[record_id], data["action"], actor, verified_on)
    return len(data["eligible"]), len(ids) - len(data["eligible"])
