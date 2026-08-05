"""Implementation Integrity Analyzer: an isolated static-analysis toolkit.

This package loads and parses Python source independently of the
crisis-response domain (``aegisops.domain``/``application``/``infrastructure``).
Bundle 1 provided source loading, AST parsing, and the public API surface.
Bundle 2 adds detection of scaffolded functions (bodies that are only
``pass``, ``...``, a lone docstring, or ``raise NotImplementedError()``).
"""
