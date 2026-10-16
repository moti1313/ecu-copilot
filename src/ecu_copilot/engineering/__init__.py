"""Deterministic engineering layer (no LLM).

Pure functions over test results (the twin's JSON shape) and the machine-readable specification.
They produce compact, checked evidence - validity per measurement, change points, lot concentration,
signal descriptors - that the agent reads instead of raw result lists. Every function is unit-tested;
the agent is told to call these before it talks about validity, trends or lots.
"""
