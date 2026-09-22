from django.contrib.admin.models import CHANGE, LogEntry
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import DSSFlowVersion
from .services import validate_dss_flow


@transaction.atomic
def submit_dss_flow(*, flow_id: int, actor) -> DSSFlowVersion:
    if not actor.has_perm("dss.review_dssflowversion"):
        raise PermissionDenied
    flow = DSSFlowVersion.objects.select_for_update().get(pk=flow_id)
    if flow.workflow_status != DSSFlowVersion.WorkflowStatus.DRAFT:
        raise ValidationError("Only a draft DSS flow can be submitted for review.")
    flow.workflow_status = DSSFlowVersion.WorkflowStatus.IN_REVIEW
    flow.save(update_fields=("workflow_status", "updated_at"))
    LogEntry.objects.log_actions(
        user_id=actor.pk,
        queryset=[flow],
        action_flag=CHANGE,
        change_message="Submitted structured DSS flow version for review.",
        single_object=True,
    )
    return flow


@transaction.atomic
def publish_dss_flow(*, flow_id: int, actor) -> DSSFlowVersion:
    if not actor.has_perm("dss.publish_dssflowversion"):
        raise PermissionDenied
    flow = (
        DSSFlowVersion.objects.select_for_update()
        .select_related("source")
        .get(pk=flow_id)
    )
    if flow.workflow_status != DSSFlowVersion.WorkflowStatus.IN_REVIEW:
        raise ValidationError("Only an in-review flow can be published.")
    validate_dss_flow(flow)
    flow.workflow_status = DSSFlowVersion.WorkflowStatus.PUBLISHED
    flow.published_at = timezone.now()
    flow.full_clean()
    flow.save(update_fields=("workflow_status", "published_at", "updated_at"))
    LogEntry.objects.log_actions(
        user_id=actor.pk,
        queryset=[flow],
        action_flag=CHANGE,
        change_message="Published validated structured DSS flow version.",
        single_object=True,
    )
    return flow
