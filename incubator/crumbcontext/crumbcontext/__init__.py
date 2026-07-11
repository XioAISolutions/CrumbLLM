"""CrumbContext: safety-first routing for long AI context."""

from .anchors import extract_anchors, sanitize_with_anchors
from .models import Anchor, ContextBlock, Lane, RoutePlan, RoutedBlock
from .router import RouterConfig, route_blocks

__all__ = [
    "Anchor",
    "ContextBlock",
    "Lane",
    "RoutePlan",
    "RoutedBlock",
    "RouterConfig",
    "extract_anchors",
    "sanitize_with_anchors",
    "route_blocks",
]

__version__ = "0.1.0"
