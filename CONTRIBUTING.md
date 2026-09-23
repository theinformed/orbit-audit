# Contributing

Thanks for your interest in this project. This repository is a public release
of a research programme on satellite manoeuvre detection from two-line
element sets; contributions to the analysis code, the detection pipeline and
the test suite are welcome.

## Reporting issues

Please open a GitHub issue describing the problem or proposal. For a bug,
include the command you ran, the output you got, and what you expected. For
a proposed change to the detection logic or the false-alarm control, please
describe the change against the relevant pre-registration document in
`docs/` where one exists, since a change to the detector's decision rule
outside a registered analysis is a change to what the software claims about
itself.

## Making a change

1. Fork the repository and create a branch for your change.
2. Run the relevant test suite before opening a pull request:
   - Python: `python3 -m unittest discover -s tests -p 'test_orbit*.py'`
     (the orbit detector suite; must report `OK`).
   - TypeScript/browser application: `npm run check && npm test`.
3. Keep changes focused. Unrelated formatting or unrelated file changes make
   a pull request harder to review and are usually asked to be split out.
4. Describe what changed and why in the pull request description. If the
   change affects a numeric result reported in any of the research papers in
   `docs/`, say so explicitly; those papers are not modified by ordinary code
   contributions.

## Code style

Python code follows the conventions already used in `pipeline/` and `tools/`
(standard library where practical, explicit over implicit). TypeScript code
follows the existing `src/` conventions and is checked by `npm run check`.

## Scope

This repository does not redistribute the underlying two-line element
archive, nor any of the other bulk upstream products the analyses read; what
is published, what is not and under whose terms is set out in
[DATA.md](DATA.md). Contributions that would require committing a
redistributed archive will not be merged. Issues about the Space-Track or
CelesTrak terms of use should be raised with those services, not in this
repository.

A receipt in `docs/` records the SHA-256 of the code that produced it. If a
change alters a file some receipt pins, `tests/test_released_sources.py` will
say so; the remedy is to account for the difference in
`docs/released-source-hashes-20260923.json`, never to edit the receipt.

## License

By contributing, you agree that your contribution is licensed under this
repository's [Apache License, Version 2.0](LICENSE).
