"""Operational checks for the Space Environment Explorer.

Nothing in this package contacts celestrak.org or space-track.org. Every module
here reads local files, local systemd journals, and — over the private link —
the same kinds of files on the VPS. That is deliberate: an operations page you
are afraid to refresh is an operations page nobody refreshes.
"""
