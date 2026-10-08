"""Tests for the A1 semantic controls supplement (DECISIONS B68).

Every test runs the RAW ``contract.supplement_problems``. The two contract defects lane 2a
reported (a ``class_id`` check on case documents; a ``message`` check at the trajectory document's
top level) were fixed by the lead in da73937, and the filter that once hid the first is gone.
"""
