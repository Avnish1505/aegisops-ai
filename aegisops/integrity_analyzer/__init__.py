"""Implementation Integrity Analyzer: an isolated static-analysis toolkit.

This package loads and parses Python source independently of the
crisis-response domain (``aegisops.domain``/``application``/``infrastructure``).
Bundle 1 provides source loading, AST parsing, and the public API surface
only; integrity-detection logic is added in a later bundle.
"""
