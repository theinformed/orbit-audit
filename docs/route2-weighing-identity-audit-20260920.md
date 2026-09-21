# Route 2 identity audit — 2026-09-20, before floor results

During the first bounded extraction (226/755 objects completed; no floor table
or trend results inspected), review of the frozen selection and existing catalog
purpose fields exposed three identity problems in the LEO sample:

- 36086 POISK is an attached ISS module. The initial selector recognized names
  beginning `ISS (` but missed this separate name. It is not independent of ISS.
- 27944 LARETS is an explicitly passive metal calibration sphere. The initial
  name exclusion list omitted LARETS.
- 66906 DUPLEX has the ISS's 1998 launch date in the current catalog, while its
  purpose identifies a CubeSat funded under a 2019 program and later deployed
  from ISS. That inherited date cannot establish a pre-2015 launch.

Exclude these three from the payload floor denominators and exclude their matched
control rows from class summaries. Retain their measurements and explicit
`eligibilityExclusion` in JSONL for audit. Do not replace them or change any
normalization pool. This repairs the registered independent/old/payload eligibility
intent without selecting on a measured floor. The initial 60 LEO selections become
57 analysis-eligible selections (18 low, 20 middle, 19 high). Coverage and
strong-drag criteria remain additional independent screens.

The first extraction may finish as a disposable preliminary run. The final script
must apply these identity exclusions before floor summaries/gates; the receipt
must identify this addendum and the final script, and the report must disclose it.
