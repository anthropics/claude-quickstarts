"""
DocuSeal integration tools for Claude Computer Use.

This package provides tools for automating DocuSeal template builder operations,
including API-based field creation, coordinate management, and browser automation.
"""

from .api_client import DocuSealAPIClient
from .controller import DocuSealController
from .coordinates import CoordinateConverter, validate_normalized_coordinates
from .human_cursor import HumanCursor

__all__ = [
    "DocuSealAPIClient",
    "DocuSealController",
    "CoordinateConverter",
    "validate_normalized_coordinates",
    "HumanCursor",
]

__version__ = "1.0.0"
