# FloodSense backend

The backend is a Django project with Django REST Framework, GeoDjango, and a PostgreSQL/PostGIS production configuration.

Current foundation:

- Custom email-based user model
- Django administration registration for users
- JWT-ready REST Framework configuration
- Public `GET /api/v1/health/` endpoint
- Separate application modules for geography, Expert System, DSS, evacuation resources, and provenance
- PostGIS connection configured through private environment variables

The Windows development environment has been verified against PostgreSQL 17,
PostGIS 3.6, and the installed GDAL/GEOS libraries. Use
`scripts/check_backend_bootstrap.ps1` for database-independent tests and
`scripts/verify_postgis.ps1` for the real spatial database check.
