# Supplemental external audit protocol

Recorded while arm 0 is running, before running any three-arm outcomes. The
original registration hash remains unchanged. This adds a second external
classification source after discovering that the local CelesTrak mirror is
strictly operational-only; it does not change cohort thresholds or test margins.

Use ESA's *Classification of Geosynchronous Objects*, issue 21 (19 July 2019),
status at 1 January 2019, publicly available as an [ESA-authored PDF mirror](https://astronomer.ru/data/0128/Classification_of_Geosynchronous_Objects_I21R0.pdf).
Extract only records explicitly marked `TLEs` and join their S-ID to NORAD.
Vimpel/ISON identifiers are NOT NORAD numbers and must never be joined as such.
Retain source PDF hash, page, classification, orbit epoch and geometry.

For raises earlier than the ESA reference date: C1/C2/C4 subsequently controlled
status contradicts a terminal-retirement interpretation; D plus perigee more
than 235 km above GEO supports an inactive elevated orbit, but cannot confirm
the date or intent of the raise. Other categories and missing records remain
unknown. A current CelesTrak operational contradiction takes precedence over a
historical supporting geometry (reactivation remains a possible explanation).

ESA's explicitly named 2018 disposal list can confirm the **year** of a detected
2018 raise on the same COSPAR object. It cannot confirm the day or validate a
day-precision cessation lead. Dates outside that year are not silently moved.
This source is an external classification/curation check, not an independent
sensor experiment: many ESA classifications use the same USSTRATCOM TLE family.
Keep CelesTrak-only and supplemented agreement rates separately; list every
contradiction and every unknown. Report operator-dated evidence separately.

Sources or classifications must not be selected based on pre-cessation outcomes.
Documentary review may address classification disputes, but does not alter the
frozen analysis cohorts or optimize a raise endpoint to improve an outcome.
