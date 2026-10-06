"""Availability policy regressions; synthetic fixtures in pytest's isolated DB."""

from datetime import timedelta

import pytest
from accounts.models import LegalDocumentVersion, OnboardingVersion
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from dss.flow_workflow import publish_dss_flow, submit_dss_flow
from dss.models import DSSFlowVersion, DSSOption, DSSOutcome, DSSQuestion
from evacuation.models import CenterImportBatch
from evacuation.services import find_nearest_eligible_centers
from evacuation.test_day2_nearest_service import center_factory as center_factory
from evacuation.test_day2_nearest_service import layer as layer
from expert.models import RuleSet, ScenarioOption, SusceptibilityLevel
from geography.models import GeographicArea
from provenance.models import DataSource

from .services.overview import get_overview_snapshot

pytestmark = pytest.mark.django_db


@pytest.fixture
def manager():
    return get_user_model().objects.create_user(
        email="overview-qa@example.test", is_staff=True, is_superuser=True
    )


def cards(snapshot):
    return {card["key"]: card for card in snapshot["cards"]}


@pytest.fixture
def flow_factory(manager):
    source = DataSource.objects.create(
        name="Synthetic Prepare source—not official",
        source_type="DEMONSTRATION",
        status="DEMONSTRATION",
        notes="PRIVATE_SOURCE_SENTINEL",
    )
    level = SusceptibilityLevel.objects.create(
        code="HIGH",
        label="Synthetic test level",
        display_order=1,
        map_color="#993333",
        definition="Test only",
        source=source,
        status="DEMONSTRATION",
        is_enabled=True,
    )

    def create(*, publish=True, **dates):
        flow = DSSFlowVersion.objects.create(
            code="preparedness",
            title="Synthetic Prepare—not official",
            version="QA-1",
            operating_mode="DEMONSTRATION",
            source=source,
            data_status="DEMONSTRATION",
            effective_date=dates.get("effective_date", timezone.localdate()),
            expires_on=dates.get("expires_on"),
            limitations="Synthetic content only",
        )
        flow.susceptibility_levels.add(level)
        question = DSSQuestion.objects.create(
            flow=flow, code="test", prompt="PRIVATE_QUESTION_SENTINEL", is_start=True
        )
        outcome = DSSOutcome.objects.create(
            flow=flow,
            code="test",
            title="Synthetic outcome",
            instruction="PRIVATE_BODY_SENTINEL",
            category="PREPARE",
            source=source,
        )
        DSSOption.objects.create(question=question, code="test", label="Test", outcome=outcome)
        reviewed = submit_dss_flow(flow_id=flow.pk, actor=manager)
        return publish_dss_flow(flow_id=flow.pk, actor=manager) if publish else reviewed

    return create


def test_published_prepare_uses_resident_validation_and_allowlisted_metadata(manager, flow_factory):
    flow_factory()
    with CaptureQueriesContext(connection) as queries:
        snapshot = get_overview_snapshot(user=manager, mode="DEMONSTRATION")
    prepare = cards(snapshot)["dss-content"]["prepare"]
    assert prepare["available"] and prepare["version"] == "QA-1"
    assert prepare["levels"] == ["HIGH"]
    assert not any(row["kind"] == "Availability problem" for row in snapshot["attention"])
    for sentinel in (
        "PRIVATE_SOURCE_SENTINEL",
        "PRIVATE_QUESTION_SENTINEL",
        "PRIVATE_BODY_SENTINEL",
    ):
        assert sentinel not in str(snapshot)
    assert all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries)


@pytest.mark.parametrize(
    "dates",
    [
        {"effective_date": timezone.localdate() + timedelta(days=1)},
        {
            "effective_date": timezone.localdate() - timedelta(days=20),
            "expires_on": timezone.localdate() - timedelta(days=1),
        },
    ],
)
def test_not_effective_prepare_is_a_problem_even_when_published(manager, flow_factory, dates):
    flow_factory(**dates)
    snapshot = get_overview_snapshot(user=manager, mode="DEMONSTRATION")
    assert not cards(snapshot)["dss-content"]["prepare"]["available"]
    assert snapshot["attention"][0]["label"] == "Published Prepare flow unavailable"
    assert "not effective or has expired" in snapshot["attention"][0]["reason"]


def test_changed_source_invalidates_published_prepare_availability(manager, flow_factory):
    flow = flow_factory()
    DataSource.objects.filter(pk=flow.source_id).update(status="RESTRICTED")
    snapshot = get_overview_snapshot(user=manager, mode="DEMONSTRATION")
    assert not cards(snapshot)["dss-content"]["prepare"]["available"]
    assert snapshot["attention"][0]["kind"] == "Availability problem"


def test_flow_only_permission_never_discloses_guidance_counts(manager, flow_factory):
    flow_factory(publish=False)
    viewer = get_user_model().objects.create_user(
        email="flow-viewer-qa@example.test", is_staff=True
    )
    viewer.user_permissions.set(Permission.objects.filter(codename="view_dssflowversion"))
    snapshot = get_overview_snapshot(user=viewer, mode="DEMONSTRATION")
    card = cards(snapshot)["dss-content"]
    assert card["metric_label"] == "structured Prepare flow"
    assert "Assessment guidance: access restricted" in card["lines"]
    assert len(snapshot["attention"]) == 1
    assert snapshot["attention"][0]["label"] == "Prepare flows awaiting review"
    assert snapshot["attention"][0]["count"] == 1


def test_centers_match_public_schema_gates_and_exclude_temporary_tests(manager, center_factory):
    center_factory()
    center_factory(name="   ")  # Stored verified row; strict public schema rejects it.
    center_factory(verified_on=None)
    temporary = DataSource.objects.create(
        name="Synthetic temporary test source", source_type="DEMONSTRATION", status="DEMONSTRATION"
    )
    center_factory(source=temporary, publication_status="DEMONSTRATION")
    snapshot = get_overview_snapshot(user=manager)
    card = cards(snapshot)["evacuation-centers"]
    assert (
        card["metric"]
        == len(find_nearest_eligible_centers(latitude=0, longitude=0)["centers"])
        == 1
    )
    assert cards(snapshot)["map-data"]["metric"] == "47 / 47"
    assert "Complete reference layer available" in cards(snapshot)["map-data"]["lines"]


def test_incomplete_reference_layer_withholds_otherwise_verified_centers(
    manager, center_factory, layer
):
    center_factory()
    GeographicArea.objects.filter(pk=layer[2][-1].pk).update(is_enabled=False)
    snapshot = get_overview_snapshot(user=manager)
    assert cards(snapshot)["map-data"]["metric"] == "46 / 47"
    assert "Reference layer unavailable" in cards(snapshot)["map-data"]["lines"]
    assert cards(snapshot)["evacuation-centers"]["metric"] == 0


def test_staged_import_attention_excludes_completed_and_unconfirmable_batches(manager, layer):
    base = {
        "source": layer[0],
        "actor": manager,
        "source_revision": layer[0].updated_at,
        "filename": "synthetic-qa.csv",
        "row_count": 3,
        "valid_count": 2,
        "invalid_count": 1,
    }
    oldest = CenterImportBatch.objects.create(**base)
    CenterImportBatch.objects.create(**base, imported_at=timezone.now(), imported_count=2)
    CenterImportBatch.objects.create(**{**base, "valid_count": 0, "invalid_count": 3})
    snapshot = get_overview_snapshot(user=manager)
    items = [row for row in snapshot["attention"] if "Staged center" in row["label"]]
    assert len(items) == 1 and items[0]["count"] == 1
    assert items[0]["url"].endswith(f"/import/{oldest.pk}/")


def test_setup_notice_follows_normal_published_configuration_not_local_bypass(manager):
    assert any(
        "Resident setup" in item["label"]
        for item in get_overview_snapshot(user=manager)["configuration"]
    )
    for kind in ("TERMS", "PRIVACY"):
        LegalDocumentVersion.objects.create(
            document_type=kind,
            version="synthetic-QA",
            title="Synthetic legal fixture",
            summary="Test only",
            status="PUBLISHED",
            effective_date=timezone.localdate(),
            published_at=timezone.now(),
        )
    OnboardingVersion.objects.create(version="synthetic-QA", status="PUBLISHED")
    assert not any(
        "Resident setup" in item["label"]
        for item in get_overview_snapshot(user=manager)["configuration"]
    )


def test_active_metadata_without_required_reference_values_never_claims_readiness(manager):
    source = DataSource.objects.create(
        name="Synthetic configuration source", source_type="DEMONSTRATION", status="DEMONSTRATION"
    )
    RuleSet.objects.create(
        name="Synthetic knowledge metadata",
        version="QA-1",
        mode="DEMONSTRATION",
        source=source,
        status="DEMONSTRATION",
        is_active=True,
    )
    for category in ("INTENSITY", "DURATION"):
        ScenarioOption.objects.create(
            category=category,
            code=f"QA-{category}",
            label="Test reference",
            source=source,
            status="DEMONSTRATION",
            is_enabled=True,
        )
    snapshot = get_overview_snapshot(user=manager, mode="DEMONSTRATION")
    assert snapshot["configuration"][0]["label"] == "Assessment configuration incomplete"
    assert "stored input values" in snapshot["configuration"][0]["reason"]
    ScenarioOption.objects.update(derived_value=1)
    snapshot = get_overview_snapshot(user=manager, mode="DEMONSTRATION")
    assert snapshot["configuration"][0]["label"] == "Assessment metadata present"
    assert "Insufficient Data" in snapshot["configuration"][0]["reason"]
    assert "ready" not in str(snapshot).lower()
