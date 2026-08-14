"""Reproducible evaluation harness for the Implementation Integrity Analyzer.

This package is a benchmarking/scoring layer only. It does not change, patch,
or wrap the three detector modules it measures (``scaffold_detector``,
``consistency_report`` and friends, ``wiring_checker``); it just runs them
against a labeled scenario corpus and reports how well their combined
verdicts line up with ground truth, next to a deliberately weak baseline for
context.

See ``scenarios/labels.json`` for the corpus and ``run_benchmark.py`` for the
scoring logic.
"""
