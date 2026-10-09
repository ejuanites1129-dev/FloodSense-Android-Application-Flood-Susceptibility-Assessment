# Provisional terrain sample tooling

This directory documents development-only elevation processing, not approved
terrain parameters or an adopted susceptibility methodology.

Read [the integration guide](../../../docs/SAMPLE_ELEVATION_INTEGRATION.md) before
processing or staging a sample. Preserve original metadata and unknowns, record
units/CRS/NoData/coverage/checksums, and leave all staged AreaFacts disabled and
pending validation. Do not create susceptibility classes from elevations.

Raw delivery is kept locally in the ignored `FILES/data gathered/elevation sample/`;
generated CSV/JSON are kept under ignored `tmp/elevation-sample/`. Do not add
these values to ordinary Git, promote the sample as LiPAD 1 m, or activate it
without the separately documented scientific and data-governance review.
