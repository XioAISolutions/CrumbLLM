"""CRUMB reading layer.

This subpackage is the *only* place CrumbLLM touches the CRUMB format. Parsing
delegates to ``crumb_core``, the single normative implementation of the
grammar, rather than to a bundled fork of it.
"""

from crumb_llm.crumb.loader import load_crumb, load_crumb_text
from crumb_llm.crumb.pack_reader import read_pack
from crumb_llm.crumb.parser_adapter import (
    CrumbFormatUnavailable,
    parse_text,
    validate_text,
)
from crumb_llm.crumb.writer import write_output

__all__ = [
    "CrumbFormatUnavailable",
    "load_crumb",
    "load_crumb_text",
    "parse_text",
    "read_pack",
    "validate_text",
    "write_output",
]
