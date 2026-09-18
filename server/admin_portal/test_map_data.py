"""Read-only geographic review, including the controlled test-database import."""

import json
from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import connection
from django.test import Client, RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import escape
from geography.constants import BACOOR_REFERENCE_SOURCE_NAME
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus

from .services.map_data import VERSION_NOT_RECORDED, get_map_data
from .test_dashboard import DashboardHTML
from .views import map_data


class MapDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="map-staff@example.com",
            display_name="Test Reviewer",
            is_staff=True,
        )

    def setUp(self):
        self.client.force_login(self.staff)
        self.url = reverse("admin_portal:map-data")

    def source(self, **changes):
        values = {
            "name": BACOOR_REFERENCE_SOURCE_NAME,
            "organization": "Test source organization",
            "source_type": DataSource.SourceType.AGENCY_DATASET,
            "status": PublicationStatus.PENDING_VALIDATION,
            "is_publicly_releasable": True,
            "notes": "PRIVATE_NOTES_SENTINEL",
            "permitted_use": "PRIVATE_LICENSE_SENTINEL",
        }
        return DataSource.objects.create(**(values | changes))

    def area(self, source=None, **changes):
        values = {
            "code": "TEST_REFERENCE",
            "name": "Test reference area",
            "area_type": GeographicArea.AreaType.BARANGAY,
            "geometry": MultiPolygon(Polygon.from_bbox((120.95, 14.4, 120.96, 14.41)), srid=4326),
            "source": source or self.source(),
            "status": PublicationStatus.PENDING_VALIDATION,
            "is_enabled": True,
        }
        return GeographicArea.objects.create(**(values | changes))

    def demo(self, **changes):
        source = self.source(
            name="Synthetic test source",
            source_type=DataSource.SourceType.DEMONSTRATION,
            status=PublicationStatus.DEMONSTRATION,
            is_publicly_releasable=False,
        )
        return self.area(
            source,
            **(
                {
                    "code": "TEST_DEMO",
                    "name": "Synthetic zone",
                    "area_type": GeographicArea.AreaType.DEMO_ZONE,
                    "status": PublicationStatus.DEMONSTRATION,
                }
                | changes
            ),
        )

    def test_anonymous_is_redirected(self):
        self.assertRedirects(
            Client().get(self.url),
            f"{reverse('admin_portal:login')}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_nonstaff_is_forbidden(self):
        resident = get_user_model().objects.create_user(email="map-resident@example.com")
        self.client.force_login(resident)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_inactive_staff_is_forbidden_before_queries(self):
        request = RequestFactory().get(self.url)
        self.staff.is_active = False
        request.user = self.staff
        with self.assertNumQueries(0), self.assertRaises(PermissionDenied):
            map_data(request)

    def test_staff_empty_state_and_existing_navigation_route(self):
        response = self.client.get(self.url)
        self.assertContains(response, "No reviewable geographic records are available.")
        self.assertContains(response, "No administrative reference boundaries are available")
        self.assertEqual(
            response.context["map_data"]["counts"],
            {
                "total": 0,
                "enabled": 0,
                "barangays": 0,
                "pending": 0,
                "demonstration": 0,
                "disabled": 0,
            },
        )
        self.assertEqual(
            self.url, reverse("admin_portal:section", kwargs={"section_slug": "map-data"})
        )
        html = DashboardHTML(response)
        self.assertEqual(len(html.select("h1")), 1)
        self.assertTrue(html.select("a", href=self.url, **{"aria-current": "page"}))
        for layer in ("mgb", "approved"):
            self.assertIn("disabled", html.select("input", id=f"layer-{layer}")[0]["attrs"])

    def test_counts_and_layers_are_separate_and_database_backed(self):
        area = self.area()
        self.area(area.source, code="TEST_CITY", area_type=GeographicArea.AreaType.CITY)
        self.area(area.source, code="TEST_DISABLED", is_enabled=False)
        demo = self.demo()
        data = get_map_data()
        self.assertEqual(
            data["counts"],
            {
                "total": 4,
                "enabled": 3,
                "barangays": 1,
                "pending": 3,
                "demonstration": 1,
                "disabled": 1,
            },
        )
        self.assertEqual(data["administrative_mapped"], 2)
        self.assertEqual(data["demonstration_mapped"], 1)
        self.assertEqual(
            data["payload"]["layers"]["demonstration"]["features"][0]["id"], str(demo.pk)
        )
        self.assertNotIn(
            str(demo.pk),
            [item["id"] for item in data["payload"]["layers"]["administrative"]["features"]],
        )

    def test_excludes_unrelated_restricted_retired_and_misidentified_sources(self):
        valid = self.area()
        source_changes = (
            {"name": "Unrelated source"},
            {"name": BACOOR_REFERENCE_SOURCE_NAME + " copy"},
            {"status": PublicationStatus.RESTRICTED},
            {"status": PublicationStatus.RETIRED},
            {"status": PublicationStatus.APPROVED},
            {"source_type": DataSource.SourceType.DEMONSTRATION},
            {"is_publicly_releasable": False},
        )
        for index, changes in enumerate(source_changes):
            self.area(
                self.source(**changes), code=f"EXCLUDED_SOURCE_{index}", name="Excluded sentinel"
            )
        for status in (
            PublicationStatus.RESTRICTED,
            PublicationStatus.RETIRED,
            PublicationStatus.APPROVED,
        ):
            self.area(
                valid.source, code=f"EXCLUDED_{status}", status=status, name="Excluded sentinel"
            )
        for kind in (GeographicArea.AreaType.OTHER, GeographicArea.AreaType.DEMO_ZONE):
            self.area(
                valid.source, code=f"EXCLUDED_{kind}", area_type=kind, name="Excluded sentinel"
            )
        response = self.client.get(self.url)
        self.assertEqual(response.context["map_data"]["counts"]["total"], 1)
        self.assertNotContains(response, "Excluded sentinel")
        self.assertNotContains(response, "EXCLUDED_")

    def test_demonstration_requires_matching_record_source_status_and_type(self):
        valid = self.demo()
        for index, changes in enumerate(
            (
                {"status": PublicationStatus.PENDING_VALIDATION},
                {"area_type": GeographicArea.AreaType.BARANGAY},
            )
        ):
            self.area(
                valid.source,
                code=f"WRONG_DEMO_{index}",
                **(
                    {
                        "status": PublicationStatus.DEMONSTRATION,
                        "area_type": GeographicArea.AreaType.DEMO_ZONE,
                    }
                    | changes
                ),
            )
        for index, source_changes in enumerate(
            (
                {"status": PublicationStatus.RESTRICTED},
                {"source_type": DataSource.SourceType.AGENCY_DATASET},
            )
        ):
            source = self.source(
                **(
                    {
                        "source_type": DataSource.SourceType.DEMONSTRATION,
                        "status": PublicationStatus.DEMONSTRATION,
                    }
                    | source_changes
                )
            )
            self.area(
                source,
                code=f"WRONG_DEMO_SOURCE_{index}",
                status=PublicationStatus.DEMONSTRATION,
                area_type=GeographicArea.AreaType.DEMO_ZONE,
            )
        self.assertEqual([row["id"] for row in get_map_data()["records"]], [str(valid.pk)])

    def test_geojson_is_valid_and_has_only_neutral_allowlisted_properties(self):
        self.area()
        collection = get_map_data()["payload"]["layers"]["administrative"]
        self.assertEqual(collection["type"], "FeatureCollection")
        for feature in collection["features"]:
            self.assertTrue(GEOSGeometry(json.dumps(feature["geometry"]), srid=4326).valid)
            self.assertEqual(feature["geometry"]["type"], "MultiPolygon")
            self.assertEqual(
                set(feature["properties"]), {"record_id", "name", "code", "area_type", "layer_kind"}
            )
            for forbidden in (
                "classification",
                "risk_score",
                "hazard_score",
                "flood_color",
                "inference_result",
                "susceptibility",
            ):
                self.assertNotIn(forbidden, feature["properties"])

    def test_details_and_server_selection_show_truthful_source_status_and_version(self):
        self.area()
        selected = self.demo(name="Selected synthetic area")
        source = selected.source
        source.coverage_description = "Synthetic test extent"
        source.record_period_start = date(2023, 1, 1)
        source.reviewed_on = date(2026, 9, 18)
        source.reviewed_by = self.staff
        source.save()
        response = self.client.get(self.url, {"area": selected.pk})
        record = response.context["map_data"]["selected"]
        self.assertEqual(record["id"], str(selected.pk))
        fields = {field["key"]: field["value"] for field in record["details"]}
        self.assertEqual(fields["source_name"], source.name)
        self.assertEqual(fields["organization"], source.organization)
        self.assertEqual(fields["status"], PublicationStatus.DEMONSTRATION.label)
        self.assertEqual(fields["source_status"], PublicationStatus.DEMONSTRATION.label)
        self.assertEqual(fields["reviewer"], "Test Reviewer")
        self.assertEqual(fields["review_date"], "2026-09-18")
        self.assertEqual(fields["period_start"], "2023-01-01")
        self.assertEqual(fields["period_end"], "Not recorded")
        self.assertEqual(fields["public_release"], "No")
        self.assertEqual(fields["version"], VERSION_NOT_RECORDED)
        self.assertEqual(fields["spatial_reference"], "EPSG:4326")
        self.assertContains(response, VERSION_NOT_RECORDED)
        self.assertNotContains(response, "PRIVATE_NOTES_SENTINEL")
        self.assertNotContains(response, "PRIVATE_LICENSE_SENTINEL")
        # Reviewer email is not serialized (the logged-in shell has a display name).
        self.assertNotContains(response, self.staff.email)

    def test_missing_reviewer_name_never_falls_back_to_email(self):
        self.staff.display_name = ""
        self.staff.save(update_fields=["display_name"])
        self.area(self.source(reviewed_by=self.staff))
        payload = json.dumps(get_map_data()["payload"])
        self.assertNotIn(self.staff.email, payload)
        self.assertIn("Recorded reviewer (name unavailable)", payload)

    def test_unavailable_selection_cannot_disclose_an_excluded_record(self):
        hidden = self.area(status=PublicationStatus.RESTRICTED, name="PRIVATE_AREA_SENTINEL")
        response = self.client.get(self.url, {"area": hidden.pk})
        self.assertContains(response, "The requested record is unavailable")
        self.assertNotContains(response, hidden.name)
        self.assertIsNone(response.context["map_data"]["selected"])

    def test_disabled_and_empty_geometry_are_reviewable_but_not_mapped(self):
        disabled = self.area(is_enabled=False)
        empty = self.area(disabled.source, code="EMPTY_GEOMETRY", geometry=MultiPolygon(srid=4326))
        data = get_map_data(selected_id=str(empty.pk))
        self.assertEqual(data["counts"]["total"], 2)
        self.assertEqual(data["administrative_mapped"], 0)
        self.assertFalse(data["selected"]["mapped"])
        self.assertTrue(any("Geometry is empty" in value for value in data["selected"]["warnings"]))

    def test_html_and_embedded_json_escape_untrusted_names_and_source_fields(self):
        attack = '</script><img src=x onerror="window.mapXss=true">'
        area = self.demo(name=attack)
        area.source.name = attack
        area.source.organization = attack
        area.source.coverage_description = attack
        area.source.save()
        response = self.client.get(self.url)
        self.assertContains(response, escape(attack))
        self.assertNotContains(response, attack)
        html = DashboardHTML(response)
        self.assertFalse(html.select("img"))
        script = html.select("script", id="map-data-payload", type="application/json")[0]
        payload = json.loads("".join(script["text"]))
        self.assertEqual(payload["records"][0]["name"], attack)
        self.assertEqual(len(html.select("button", **{"data-record-id": str(area.pk)})), 1)

    def test_two_queries_without_private_columns_n_plus_one_or_rule_access(self):
        area = self.area(self.source(reviewed_by=self.staff))
        for index in range(8):
            self.area(area.source, code=f"TEST_{index}")
        with self.assertNumQueries(2), CaptureQueriesContext(connection) as queries:
            get_map_data()
        for query in queries:
            sql = query["sql"].lower()
            self.assertTrue(sql.startswith("select"))
            for forbidden in (
                "notes",
                "permitted_use",
                "email",
                "password",
                "expert_",
                "geography_areafact",
            ):
                self.assertNotIn(forbidden, sql)

    def test_all_non_get_methods_are_rejected_without_writes(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"):
            with self.subTest(method=method), CaptureQueriesContext(connection) as queries:
                response = self.client.generic(method, self.url)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.headers["Allow"], "GET")
            self.assertTrue(
                all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries)
            )

    def test_get_only_reads_and_does_not_import_missing_boundaries(self):
        with CaptureQueriesContext(connection) as queries:
            self.client.get(self.url)
        self.assertTrue(
            all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries)
        )
        self.assertFalse(GeographicArea.objects.exists())
        self.assertFalse(DataSource.objects.exists())


class ImportedMapDataTests(TestCase):
    def test_controlled_import_exposes_47_barangays_and_one_city_without_classifications(self):
        # This runs only in pytest/Django's isolated test database, never the developer DB.
        call_command("import_bacoor_boundaries", stdout=StringIO())
        data = get_map_data()
        self.assertEqual(data["counts"]["barangays"], 47)
        self.assertEqual(data["counts"]["pending"], 48)
        features = data["payload"]["layers"]["administrative"]["features"]
        self.assertEqual(len(features), 48)
        self.assertEqual(
            sum(feature["properties"]["area_type"] == "BARANGAY" for feature in features), 47
        )
        self.assertEqual(data["demonstration_mapped"], 0)
        for feature in features:
            self.assertEqual(
                set(feature["properties"]), {"record_id", "name", "code", "area_type", "layer_kind"}
            )
            self.assertTrue(GEOSGeometry(json.dumps(feature["geometry"])).valid)
