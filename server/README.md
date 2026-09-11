# FloodSense backend

The backend is a Django project with Django REST Framework, GeoDjango, and a PostgreSQL/PostGIS production configuration.

Current foundation:

- Custom email-based user model
- Django administration registration for users
- JWT-ready REST Framework configuration
- Public `GET /api/v1/health/` endpoint
- Source-governance records for demonstration, pending, approved, restricted,
  and retired information
- PostGIS geographic areas and typed, source-backed area facts
- Versioned Expert System rulesets, controlled rule conditions, rainfall
  scenario options, and the four susceptibility levels
- Source-backed DSS preparedness guidance kept separate from classification
- Django Admin configuration for all of the above containers
- A separate evacuation module reserved for later verified records
- PostGIS connection configured through private environment variables

The Windows development environment has been verified against PostgreSQL 17,
PostGIS 3.6, and the installed GDAL/GEOS libraries. Use
`scripts/check_backend_bootstrap.ps1` for database-independent tests and
`scripts/verify_postgis.ps1` for the real spatial database check.

The domain containers are now in place, but the inference service and
application-facing assessment APIs are the next implementation stage. No
official Bacoor classifications or unvalidated thresholds are included.
