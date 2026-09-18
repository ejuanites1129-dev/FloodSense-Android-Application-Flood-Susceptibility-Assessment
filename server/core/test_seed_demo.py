from decimal import Decimal
from io import StringIO

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from dss.models import GuidanceItem
from expert.models import (
    ExpertRule,
    ExpertRuleCondition,
    RuleSet,
    ScenarioOption,
    SusceptibilityLevel,
)
from geography.constants import BACOOR_REFERENCE_SOURCE_NAME
from geography.models import AreaFact, GeographicArea
from provenance.models import DataSource, PublicationStatus

from .management.commands.seed_demo import SOURCE_NAME


def geometry():
    polygon = Polygon(((10, 10), (10, 11), (11, 11), (11, 10), (10, 10)))
    return MultiPolygon(polygon, srid=4326)


class SeedDemoCommandTests(TestCase):
    def _seed(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        return output.getvalue()

    def test_creates_complete_clearly_labeled_demonstration_dataset(self):
        output = self._seed()

        self.assertIn("DEMONSTRATION DATA—NOT OFFICIAL", output)
        self.assertIn("Imported 1 Bacoor City boundary and 47 current barangay boundaries", output)
        self.assertEqual(DataSource.objects.filter(name=SOURCE_NAME).count(), 1)
        self.assertEqual(
            DataSource.objects.filter(name=BACOOR_REFERENCE_SOURCE_NAME).count(),
            1,
        )
        self.assertEqual(SusceptibilityLevel.objects.count(), 4)
        self.assertEqual(ScenarioOption.objects.count(), 10)
        self.assertEqual(GeographicArea.objects.count(), 52)
        self.assertEqual(
            GeographicArea.objects.filter(
                source__name=BACOOR_REFERENCE_SOURCE_NAME,
                area_type=GeographicArea.AreaType.BARANGAY,
            ).count(),
            47,
        )
        self.assertEqual(AreaFact.objects.count(), 4)
        self.assertEqual(RuleSet.objects.count(), 1)
        self.assertEqual(ExpertRule.objects.count(), 4)
        self.assertEqual(ExpertRuleCondition.objects.count(), 12)
        self.assertEqual(GuidanceItem.objects.count(), 4)
        self.assertFalse(DataSource.objects.get(name=SOURCE_NAME).is_publicly_releasable)

    def test_running_twice_is_idempotent(self):
        self._seed()
        ids_before = {
            "areas": set(GeographicArea.objects.values_list("id", flat=True)),
            "rules": set(ExpertRule.objects.values_list("id", flat=True)),
            "guidance": set(GuidanceItem.objects.values_list("id", flat=True)),
        }

        self._seed()

        self.assertEqual(
            set(GeographicArea.objects.values_list("id", flat=True)),
            ids_before["areas"],
        )
        self.assertEqual(
            set(ExpertRule.objects.values_list("id", flat=True)),
            ids_before["rules"],
        )
        self.assertEqual(
            set(GuidanceItem.objects.values_list("id", flat=True)),
            ids_before["guidance"],
        )
        self.assertEqual(ExpertRuleCondition.objects.count(), 12)

    def test_polygons_are_multipolygons_in_4326_and_do_not_overlap(self):
        self._seed()
        areas = list(GeographicArea.objects.filter(source__name=SOURCE_NAME).order_by("code"))

        self.assertEqual([area.code for area in areas], [f"DEMO_ZONE_{x}" for x in "ABCD"])
        for area in areas:
            self.assertEqual(area.geometry.geom_type, "MultiPolygon")
            self.assertEqual(area.geometry.srid, 4326)
        for index, area in enumerate(areas):
            for other in areas[index + 1 :]:
                self.assertFalse(area.geometry.intersects(other.geometry))

    def test_seed_owned_demonstration_values_are_safely_refreshed(self):
        self._seed()
        option = ScenarioOption.objects.get(code="DEMO_HEAVY")
        option.derived_value = 99
        option.save(update_fields=("derived_value",))
        area = GeographicArea.objects.get(code="DEMO_ZONE_A")
        area.name = "Temporary local edit"
        area.save(update_fields=("name",))
        guidance = GuidanceItem.objects.get(susceptibility_level__code="LOW")
        guidance.title = "Temporary local title"
        guidance.save(update_fields=("title",))

        self._seed()

        option.refresh_from_db()
        area.refresh_from_db()
        guidance.refresh_from_db()
        self.assertEqual(option.derived_value, 3)
        self.assertEqual(area.name, "Demo Zone A")
        self.assertEqual(guidance.title, "Review basic preparedness supplies")

    def test_unrelated_non_demonstration_records_are_preserved(self):
        source = DataSource.objects.create(
            name="Approved unrelated source",
            source_type=DataSource.SourceType.AGENCY_DATASET,
            status=PublicationStatus.APPROVED,
            is_publicly_releasable=True,
        )
        unrelated = GeographicArea.objects.create(
            code="APPROVED_TEST_AREA",
            name="Approved unrelated test area",
            area_type=GeographicArea.AreaType.OTHER,
            geometry=geometry(),
            source=source,
            status=PublicationStatus.APPROVED,
            is_enabled=False,
        )

        self._seed()

        unrelated.refresh_from_db()
        self.assertEqual(unrelated.name, "Approved unrelated test area")
        self.assertEqual(unrelated.status, PublicationStatus.APPROVED)

    def test_unsafe_stable_code_conflict_aborts_atomically(self):
        source = DataSource.objects.create(
            name="Approved conflict source",
            source_type=DataSource.SourceType.AGENCY_DATASET,
            status=PublicationStatus.APPROVED,
            is_publicly_releasable=True,
        )
        conflicting = GeographicArea.objects.create(
            code="DEMO_ZONE_A",
            name="Protected conflicting record",
            area_type=GeographicArea.AreaType.OTHER,
            geometry=geometry(),
            source=source,
            status=PublicationStatus.APPROVED,
            is_enabled=False,
        )

        with self.assertRaises(CommandError):
            self._seed()

        conflicting.refresh_from_db()
        self.assertEqual(conflicting.name, "Protected conflicting record")
        self.assertFalse(DataSource.objects.filter(name=SOURCE_NAME).exists())

    def test_boundary_code_conflict_rolls_back_the_combined_seed(self):
        source = DataSource.objects.create(
            name="Approved boundary conflict source",
            source_type=DataSource.SourceType.AGENCY_DATASET,
            status=PublicationStatus.APPROVED,
            is_publicly_releasable=True,
        )
        GeographicArea.objects.create(
            code="PSGC_0402103000",
            name="Protected city record",
            area_type=GeographicArea.AreaType.CITY,
            geometry=geometry(),
            source=source,
            status=PublicationStatus.APPROVED,
            is_enabled=False,
        )

        with self.assertRaises(CommandError):
            self._seed()

        self.assertFalse(DataSource.objects.filter(name=SOURCE_NAME).exists())
        self.assertFalse(DataSource.objects.filter(name=BACOOR_REFERENCE_SOURCE_NAME).exists())
        self.assertEqual(GeographicArea.objects.count(), 1)

    def test_foreign_demonstration_stable_code_conflict_aborts_atomically(self):
        source = DataSource.objects.create(
            name="Foreign demonstration source",
            source_type=DataSource.SourceType.DEMONSTRATION,
            status=PublicationStatus.DEMONSTRATION,
        )
        conflicting = ScenarioOption.objects.create(
            category=ScenarioOption.Category.INTENSITY,
            code="DEMO_LIGHT",
            label="Foreign fictional light option",
            derived_value=Decimal("9"),
            source=source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=False,
        )

        with self.assertRaises(CommandError):
            self._seed()

        conflicting.refresh_from_db()
        self.assertEqual(conflicting.derived_value, Decimal("9"))
        self.assertEqual(conflicting.source, source)
        self.assertFalse(DataSource.objects.filter(name=SOURCE_NAME).exists())

    def test_foreign_active_demonstration_ruleset_is_not_disabled(self):
        source = DataSource.objects.create(
            name="Unrelated demonstration source",
            source_type=DataSource.SourceType.DEMONSTRATION,
            status=PublicationStatus.DEMONSTRATION,
        )
        ruleset = RuleSet.objects.create(
            name="Unrelated active demonstration rules",
            version="9",
            mode=RuleSet.Mode.DEMONSTRATION,
            source=source,
            status=PublicationStatus.DEMONSTRATION,
            is_active=True,
        )

        with self.assertRaises(CommandError):
            self._seed()

        ruleset.refresh_from_db()
        self.assertTrue(ruleset.is_active)
        self.assertFalse(DataSource.objects.filter(name=SOURCE_NAME).exists())
