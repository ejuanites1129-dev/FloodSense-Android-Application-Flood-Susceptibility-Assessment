from datetime import timedelta

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from dss.models import GuidanceItem
from expert.models import ScenarioOption, SusceptibilityLevel
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus

from .services.dashboard import get_dashboard_summary


class EmptyDashboardSummaryTests(TestCase):
    def test_empty_domain_has_zero_counts_and_no_invented_activity(self):
        with self.assertNumQueries(5):
            summary = get_dashboard_summary()

        for name in ("geographic_areas", "data_sources", "guidance_items", "scenario_options"):
            with self.subTest(name=name):
                self.assertEqual(summary[name]["total"], 0)
                self.assertEqual(
                    summary[name]["status_counts"],
                    {value: 0 for value, _label in PublicationStatus.choices},
                )
                self.assertEqual(
                    summary[name]["statuses"],
                    [
                        {"value": value, "label": label, "count": 0}
                        for value, label in PublicationStatus.choices
                    ],
                )
        self.assertEqual(summary["geographic_areas"]["enabled"], 0)
        self.assertTrue(all(row["count"] == 0 for row in summary["geographic_areas"]["area_types"]))
        self.assertEqual(summary["data_sources"]["approved_public"], 0)
        self.assertEqual(summary["guidance_items"]["enabled"], 0)
        self.assertEqual(summary["scenario_options"]["enabled"], 0)
        self.assertEqual(summary["scenario_options"]["enabled_intensity"], 0)
        self.assertEqual(summary["scenario_options"]["enabled_duration"], 0)
        self.assertEqual(summary["review_attention"]["total"], 0)
        self.assertEqual(summary["recent_activity"], [])
        self.assertIs(summary["activity_is_complete_audit"], False)

    def test_missing_content_type_is_not_recreated_by_read_only_service(self):
        ContentType.objects.filter(app_label="provenance", model="datasource").delete()
        ContentType.objects.clear_cache()

        with CaptureQueriesContext(connection) as queries:
            get_dashboard_summary()

        self.assertEqual(len(queries), 5)
        self.assertTrue(
            all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries)
        )
        self.assertFalse(
            ContentType.objects.filter(app_label="provenance", model="datasource").exists()
        )


class DashboardRecordSummaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Fictional isolated fixtures exercise every persisted status, including
        # enabled demonstration rows and approved rows that are not enabled.
        sources = {}
        for status in PublicationStatus.values:
            for publicly_releasable in (False, True):
                source = DataSource.objects.create(
                    name=f"Fixture source {status} {publicly_releasable}",
                    source_type=DataSource.SourceType.DEMONSTRATION,
                    status=status,
                    is_publicly_releasable=publicly_releasable,
                    notes="PRIVATE_SOURCE_NOTES",
                    permitted_use="PRIVATE_SOURCE_TERMS",
                )
                sources[(status, publicly_releasable)] = source
        cls.source = sources[(PublicationStatus.DEMONSTRATION, False)]
        level = SusceptibilityLevel.objects.create(
            code=SusceptibilityLevel.Code.LOW,
            label="Fixture classification vocabulary",
            display_order=1,
            map_color="#123456",
            definition="Fictional test vocabulary only.",
            source=cls.source,
            status=PublicationStatus.DEMONSTRATION,
        )
        geometry = MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0))), srid=4326)
        for status in PublicationStatus.values:
            for index, area_type in enumerate(GeographicArea.AreaType.values):
                GeographicArea.objects.create(
                    code=f"fixture-{status}-{area_type}",
                    name="Fictional test area",
                    area_type=area_type,
                    geometry=geometry,
                    source=cls.source,
                    status=status,
                    is_enabled=index % 2 == 0,
                )
            for enabled in (False, True):
                GuidanceItem.objects.create(
                    title="Fixture content",
                    instruction="PRIVATE_GUIDANCE_CONTENT",
                    category=GuidanceItem.Category.PREPARE,
                    susceptibility_level=level,
                    source=cls.source,
                    status=status,
                    workflow_status=(
                        GuidanceItem.WorkflowStatus.PUBLISHED
                        if enabled
                        else GuidanceItem.WorkflowStatus.DRAFT
                    ),
                    is_enabled=enabled,
                )
                for category in ScenarioOption.Category.values:
                    ScenarioOption.objects.create(
                        code=f"fixture-{status}-{category}-{enabled}",
                        label="Fixture scenario choice",
                        category=category,
                        source=cls.source,
                        status=status,
                        is_enabled=enabled,
                    )
        GeographicArea.objects.create(
            code="fixture-extra-city",
            name="Fictional test city boundary",
            area_type=GeographicArea.AreaType.CITY,
            geometry=geometry,
            source=cls.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        ScenarioOption.objects.create(
            code="fixture-extra-duration",
            label="Fixture duration choice",
            category=ScenarioOption.Category.DURATION,
            source=cls.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )

    def test_geographic_totals_statuses_and_area_types_remain_independent(self):
        areas = get_dashboard_summary()["geographic_areas"]

        self.assertEqual(areas["total"], 21)
        self.assertEqual(areas["enabled"], 11)
        self.assertEqual(
            areas["status_counts"],
            {
                value: 5 if value == PublicationStatus.DEMONSTRATION else 4
                for value in PublicationStatus.values
            },
        )
        self.assertEqual(
            areas["area_types"],
            [
                {
                    "value": value,
                    "label": label,
                    "count": 6 if value == GeographicArea.AreaType.CITY else 5,
                }
                for value, label in GeographicArea.AreaType.choices
            ],
        )

    def test_sources_require_both_approval_and_public_permission(self):
        sources = get_dashboard_summary()["data_sources"]

        self.assertEqual(sources["total"], 10)
        self.assertEqual(sources["status_counts"], dict.fromkeys(PublicationStatus.values, 2))
        self.assertEqual(sources["approved_public"], 1)
        self.assertNotIn("enabled", sources)
        self.assertEqual(
            sources["statuses"],
            [
                {"value": value, "label": label, "count": 2}
                for value, label in PublicationStatus.choices
            ],
        )

    def test_guidance_enabled_count_does_not_imply_approval(self):
        guidance = get_dashboard_summary()["guidance_items"]

        self.assertEqual(guidance["total"], 10)
        self.assertEqual(guidance["enabled"], 5)
        self.assertEqual(guidance["status_counts"], dict.fromkeys(PublicationStatus.values, 2))

    def test_scenarios_count_only_enabled_rows_in_each_category(self):
        scenarios = get_dashboard_summary()["scenario_options"]

        self.assertEqual(scenarios["total"], 21)
        self.assertEqual(scenarios["enabled"], 11)
        self.assertEqual(scenarios["enabled_intensity"], 5)
        self.assertEqual(scenarios["enabled_duration"], 6)
        self.assertEqual(
            scenarios["status_counts"],
            {
                value: 5 if value == PublicationStatus.DEMONSTRATION else 4
                for value in PublicationStatus.values
            },
        )

    def test_review_total_includes_pending_status_and_guidance_review_workflow(self):
        GuidanceItem.objects.filter(
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=False,
        ).update(workflow_status=GuidanceItem.WorkflowStatus.IN_REVIEW)
        attention = get_dashboard_summary()["review_attention"]

        self.assertEqual(attention["total"], 13)
        self.assertEqual(
            attention["modules"],
            [
                {"label": "Geographic areas", "section_slug": "map-data", "count": 4},
                {"label": "Data sources", "section_slug": "sources-content", "count": 2},
                {"label": "DSS guidance", "section_slug": "dss-content", "count": 3},
                {"label": "Scenario options", "section_slug": "assessment-parameters", "count": 4},
            ],
        )
        self.assertEqual(attention["total"], sum(row["count"] for row in attention["modules"]))

    def test_model_timestamps_do_not_fabricate_activity_or_expose_content(self):
        summary = get_dashboard_summary()

        self.assertIsNotNone(self.source.created_at)
        self.assertEqual(summary["recent_activity"], [])
        self.assertIs(summary["activity_is_complete_audit"], False)
        for marker in ("PRIVATE_SOURCE_NOTES", "PRIVATE_SOURCE_TERMS", "PRIVATE_GUIDANCE_CONTENT"):
            self.assertNotIn(marker, str(summary))

    def test_read_only_query_count_stays_constant_as_records_and_events_grow(self):
        actor = get_user_model().objects.create_user(
            email="fixture-actor@example.com", display_name="Fixture Maintainer", is_staff=True
        )
        content_type = ContentType.objects.get_for_model(DataSource)
        for number in (1, 30):
            DataSource.objects.bulk_create(
                [
                    DataSource(
                        name="Fixture extra source", source_type=DataSource.SourceType.DEMONSTRATION
                    )
                    for _ in range(number)
                ]
            )
            LogEntry.objects.bulk_create(
                [
                    LogEntry(
                        user=actor,
                        content_type=content_type,
                        action_flag=CHANGE,
                        object_repr="PRIVATE_OBJECT",
                        change_message="PRIVATE_CHANGE",
                    )
                    for _ in range(number)
                ]
            )
            ContentType.objects.clear_cache()

            with CaptureQueriesContext(connection) as queries:
                summary = get_dashboard_summary()

            self.assertEqual(len(queries), 5)
            self.assertEqual(len(summary["recent_activity"]), min(number, 5))
            for query in queries:
                sql = query["sql"].lower()
                self.assertTrue(sql.lstrip().startswith("select"))
                for field in (
                    "object_repr",
                    "change_message",
                    '"notes"',
                    '"permitted_use"',
                    '"instruction"',
                    '"geometry"',
                    '"derived_value"',
                    '"email"',
                ):
                    self.assertNotIn(field, sql)


class DashboardActivityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(
            email="fixture-history@example.com", display_name="Fixture Maintainer", is_staff=True
        )
        cls.timestamp = timezone.now()

    def _entry(self, app_label, model, *, action_flag=CHANGE, minute=0, actor=None):
        content_type, _created = ContentType.objects.get_or_create(app_label=app_label, model=model)
        return LogEntry.objects.create(
            user=actor or self.actor,
            content_type=content_type,
            object_id="fictional-deleted-object",
            object_repr="PRIVATE_RESTRICTED_OBJECT_DETAILS",
            change_message='[{"changed": {"fields": ["PRIVATE_BEFORE_AFTER"]}}]',
            action_flag=action_flag,
            action_time=self.timestamp + timedelta(minutes=minute),
        )

    def test_activity_includes_exact_model_pairs_and_known_actions_only(self):
        self._entry("geography", "geographicarea", action_flag=ADDITION, minute=-4)
        self._entry("provenance", "datasource", action_flag=CHANGE, minute=-3)
        self._entry("dss", "guidanceitem", action_flag=DELETION, minute=-2)
        self._entry("expert", "scenariooption", action_flag=ADDITION, minute=-1)
        for app_label, model in (
            ("expert", "expertrule"),
            ("expert", "expertrulecondition"),
            ("expert", "ruleset"),
            ("accounts", "user"),
            ("unrelated_app", "datasource"),
            ("provenance", "scenariooption"),
        ):
            self._entry(app_label, model)
        self._entry("provenance", "datasource", action_flag=99)
        LogEntry.objects.create(user=self.actor, content_type=None, action_flag=CHANGE)

        activity = get_dashboard_summary()["recent_activity"]

        self.assertEqual(
            [(row["action"], row["module"]) for row in activity],
            [
                ("Added", "Scenario options"),
                ("Deleted", "DSS guidance"),
                ("Changed", "Data sources"),
                ("Added", "Geographic areas"),
            ],
        )
        for row in activity:
            self.assertEqual(set(row), {"action", "module", "actor", "timestamp"})
            self.assertEqual(row["actor"], "Fixture Maintainer")
        for hidden in (
            "PRIVATE_RESTRICTED_OBJECT_DETAILS",
            "PRIVATE_BEFORE_AFTER",
            self.actor.email,
        ):
            self.assertNotIn(hidden, str(activity))
        self.assertEqual(activity[0]["timestamp"], self.timestamp - timedelta(minutes=1))

    def test_activity_is_limited_to_five_with_deterministic_newest_first_order(self):
        entries = [self._entry("provenance", "datasource", minute=minute) for minute in range(6)]
        # The final two actions share a timestamp; primary key breaks the tie.
        newest = self._entry("geography", "geographicarea", action_flag=DELETION, minute=5)

        with self.assertNumQueries(5):
            activity = get_dashboard_summary()["recent_activity"]

        self.assertEqual(len(activity), 5)
        self.assertEqual(activity[0]["module"], "Geographic areas")
        self.assertEqual(activity[0]["action"], "Deleted")
        self.assertEqual(
            [row["timestamp"] for row in activity],
            [newest.action_time, *(entry.action_time for entry in reversed(entries[2:]))],
        )

    def test_actor_fallback_does_not_disclose_an_email_address(self):
        unnamed = get_user_model().objects.create_user(
            email="fixture-unnamed@example.com", display_name="  ", is_staff=True
        )
        self._entry("dss", "guidanceitem", actor=unnamed)

        activity = get_dashboard_summary()["recent_activity"]

        self.assertEqual(activity[0]["actor"], f"Account #{unnamed.pk}")
        self.assertNotIn(unnamed.email, str(activity))
