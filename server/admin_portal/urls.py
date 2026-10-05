from django.urls import path

from . import dss_views, local_testing_views, operations_views
from .views import (
    AdminLoginView,
    AdminLogoutView,
    assessment_parameters,
    audit_history,
    dashboard,
    data_source_detail,
    data_source_list,
    data_source_transition,
    evacuation_center_detail,
    evacuation_center_list,
    evacuation_center_transition,
    guidance_list,
    guidance_transition,
    map_data,
    password_help,
    rainfall_reference_detail,
    rainfall_reference_list,
    reports,
    section,
    settings_view,
)

app_name = "admin_portal"

urlpatterns = [
    path(
        "evacuation-centers/<int:record_id>/remove-temporary/",
        local_testing_views.remove_temporary,
        {"kind": "center"},
        name="remove-temporary-center",
    ),
    path(
        "sources-content/<int:record_id>/remove-temporary/",
        local_testing_views.remove_temporary,
        {"kind": "source"},
        name="remove-temporary-source",
    ),
    path("review/<slug:module>/", operations_views.review_queue, name="review-queue"),
    path("evacuation-centers/import/", operations_views.center_import, name="center-import"),
    path(
        "evacuation-centers/import/template/",
        operations_views.center_import_template,
        name="center-import-template",
    ),
    path(
        "evacuation-centers/import/<int:batch_id>/",
        operations_views.center_import_detail,
        name="center-import-detail",
    ),
    path(
        "evacuation-centers/import/<int:batch_id>/report/",
        operations_views.center_import_errors,
        name="center-import-errors",
    ),
    path(
        "sources-content/inline/new/",
        operations_views.source_editor,
        {"inline": True},
        name="source-inline-create",
    ),
    path(
        "sources-content/inline/<int:source_id>/",
        operations_views.source_editor,
        {"inline": True},
        name="source-inline-edit",
    ),
    path("login/", AdminLoginView.as_view(), name="login"),
    path("logout/", AdminLogoutView.as_view(), name="logout"),
    path("password-help/", password_help, name="password-help"),
    path("", dashboard, name="dashboard"),
    path("reports/", reports, name="reports"),
    path("map-data/", map_data, name="map-data"),
    path("settings/", settings_view, name="settings"),
    path("assessment-parameters/", assessment_parameters, name="assessment-parameters"),
    path("dss-content/", guidance_list, name="dss-content"),
    path("dss-content/flows/", dss_views.structured_flow_list, name="dss-flow-list"),
    path("dss-content/flows/new/", dss_views.structured_flow_create, name="dss-flow-create"),
    path(
        "dss-content/flows/<int:flow_id>/", dss_views.structured_flow_detail, name="dss-flow-detail"
    ),
    path(
        "dss-content/flows/<int:flow_id>/edit/",
        dss_views.structured_flow_edit,
        name="dss-flow-edit",
    ),
    path(
        "dss-content/flows/<int:flow_id>/preview/",
        dss_views.structured_flow_preview,
        name="dss-flow-preview",
    ),
    path(
        "dss-content/flows/<int:flow_id>/transition/<slug:action>/",
        dss_views.structured_flow_transition,
        name="dss-flow-transition",
    ),
    path(
        "dss-content/flows/<int:flow_id>/<slug:kind>/new/",
        dss_views.structured_node_edit,
        name="dss-node-create",
    ),
    path(
        "dss-content/flows/<int:flow_id>/<slug:kind>/<int:node_id>/edit/",
        dss_views.structured_node_edit,
        name="dss-node-edit",
    ),
    path("dss-content/new/", operations_views.guidance_editor, name="guidance-create"),
    path("dss-content/<int:item_id>/edit/", operations_views.guidance_editor, name="guidance-edit"),
    path(
        "dss-content/<int:item_id>/transition/<slug:action>/",
        guidance_transition,
        name="guidance-transition",
    ),
    path("rainfall-references/", rainfall_reference_list, name="rainfall-references"),
    path(
        "rainfall-references/<int:option_id>/",
        rainfall_reference_detail,
        name="rainfall-reference-detail",
    ),
    path("evacuation-centers/", evacuation_center_list, name="evacuation-centers"),
    path(
        "evacuation-centers/new/",
        operations_views.center_editor,
        name="evacuation-center-create",
    ),
    path(
        "evacuation-centers/<int:center_id>/",
        evacuation_center_detail,
        name="evacuation-center-detail",
    ),
    path(
        "evacuation-centers/<int:center_id>/edit/",
        operations_views.center_editor,
        name="evacuation-center-edit",
    ),
    path(
        "evacuation-centers/<int:center_id>/transition/<slug:action>/",
        evacuation_center_transition,
        name="evacuation-center-transition",
    ),
    path("sources-content/", data_source_list, name="sources-content"),
    path("sources-content/new/", operations_views.source_editor, name="data-source-create"),
    path(
        "sources-content/<int:source_id>/",
        data_source_detail,
        name="data-source-detail",
    ),
    path(
        "sources-content/<int:source_id>/edit/",
        operations_views.source_editor,
        name="data-source-edit",
    ),
    path(
        "sources-content/<int:source_id>/transition/<slug:action>/",
        data_source_transition,
        name="data-source-transition",
    ),
    path("audit-history/", audit_history, name="audit-history"),
    path("<slug:section_slug>/", section, name="section"),
]
