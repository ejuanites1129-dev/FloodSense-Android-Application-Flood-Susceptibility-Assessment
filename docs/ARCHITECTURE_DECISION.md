# Architecture decision: Django rather than FastAPI

## Decision

FloodSense will use Django as its single backend framework. Django REST Framework will expose the Flutter API, GeoDjango will perform spatial operations, and Django Admin will provide the initial trusted administration interface.

## Reason

FloodSense requires more than an API: it needs authentication, roles, database migrations, internal administration, spatial models, rule and DSS maintenance, and audit-ready records. Django provides these responsibilities in one framework and avoids a separate FastAPI service or separate administration backend.

## Boundary

The Android application never connects directly to PostgreSQL. Flutter calls the authenticated Django REST API. The custom Expert System remains an ordinary Python service module inside the Django project.

