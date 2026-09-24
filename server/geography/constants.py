"""Reserved identifiers and safety text for administrative reference data."""

BACOOR_REFERENCE_SOURCE_NAME = "Bacoor administrative boundaries—derived reference"
BACOOR_REFERENCE_SOURCE_VERSION = "COD-AB v03; PSA PSGC 2023-Q3"
BACOOR_REFERENCE_WARNING = "DERIVED ADMINISTRATIVE REFERENCE—NOT CITY-VERIFIED"
BACOOR_REFERENCE_LIMITATION = (
    "Administrative boundaries only; they do not indicate flood susceptibility "
    "or current conditions."
)
BACOOR_CITY_CODE = "PSGC_0402103000"
BACOOR_REFERENCE_BARANGAY_COUNT = 47

MGB_SUSCEPTIBILITY_SOURCE_NAME = "DENR-MGB Detailed Flood Susceptibility—Bacoor provisional extract"
MGB_SUSCEPTIBILITY_SOURCE_URL = (
    "https://controlmap.mgb.gov.ph/arcgis/rest/services/"
    "GeospatialDataInventory/GDI_Detailed_Flood_Susceptibility/FeatureServer/0"
)
MGB_PROVISIONAL_WARNING = "PROVISIONAL MGB-DERIVED RESEARCH INPUT—NOT BDRRMO-APPROVED"
MGB_DERIVATION_LIMITATION = (
    "The barangay baseline is the largest mapped LF/MF/HF/VHF area share; it is "
    "a FloodSense research summary, not an MGB whole-barangay classification."
)
MGB_COVERAGE_LIMITATION = (
    "MGB coverage is incomplete in parts of Bacoor; unmapped and conflicting "
    "areas remain explicit and are never assigned a hidden class."
)
