"""
Coordinate conversion and validation utilities for DocuSeal.

Handles conversion between normalized coordinates (0-1 range) and pixel coordinates,
with validation to ensure fields fit within page boundaries.
"""

from typing import Tuple, List, Dict, Any
from dataclasses import dataclass


@dataclass
class NormalizedCoordinate:
    """Normalized coordinate (0-1 range) for DocuSeal fields."""
    x: float
    y: float
    w: float
    h: float
    page: int = 1

    def __post_init__(self):
        """Validate coordinates after initialization."""
        errors = validate_normalized_coordinates(self.x, self.y, self.w, self.h)
        if errors:
            raise ValueError(f"Invalid coordinates: {', '.join(errors)}")


@dataclass
class PixelCoordinate:
    """Pixel coordinate for browser automation."""
    x: int
    y: int
    w: int
    h: int


class CoordinateConverter:
    """Convert between normalized and pixel coordinates."""

    def __init__(
        self,
        page_width: int = 1000,
        page_height: int = 1200,
        canvas_offset_x: int = 200,
        canvas_offset_y: int = 100
    ):
        """
        Initialize coordinate converter.

        Args:
            page_width: Width of the document canvas in pixels
            page_height: Height of the document canvas in pixels
            canvas_offset_x: Horizontal offset of canvas from screen left edge
            canvas_offset_y: Vertical offset of canvas from screen top edge
        """
        self.page_width = page_width
        self.page_height = page_height
        self.canvas_offset_x = canvas_offset_x
        self.canvas_offset_y = canvas_offset_y

    def normalized_to_pixels(
        self,
        x: float,
        y: float,
        w: float,
        h: float
    ) -> PixelCoordinate:
        """
        Convert normalized coordinates to pixel coordinates.

        Args:
            x: Normalized horizontal position (0-1)
            y: Normalized vertical position (0-1)
            w: Normalized width (0-1)
            h: Normalized height (0-1)

        Returns:
            PixelCoordinate with pixel positions and dimensions
        """
        pixel_x = self.canvas_offset_x + int(x * self.page_width)
        pixel_y = self.canvas_offset_y + int(y * self.page_height)
        pixel_w = int(w * self.page_width)
        pixel_h = int(h * self.page_height)

        return PixelCoordinate(pixel_x, pixel_y, pixel_w, pixel_h)

    def pixels_to_normalized(
        self,
        x: int,
        y: int,
        w: int,
        h: int
    ) -> NormalizedCoordinate:
        """
        Convert pixel coordinates to normalized coordinates.

        Args:
            x: Pixel horizontal position
            y: Pixel vertical position
            w: Pixel width
            h: Pixel height

        Returns:
            NormalizedCoordinate with values in 0-1 range
        """
        # Remove canvas offset
        canvas_x = x - self.canvas_offset_x
        canvas_y = y - self.canvas_offset_y

        # Convert to normalized
        norm_x = canvas_x / self.page_width
        norm_y = canvas_y / self.page_height
        norm_w = w / self.page_width
        norm_h = h / self.page_height

        # Clamp to valid range
        norm_x = max(0.0, min(1.0, norm_x))
        norm_y = max(0.0, min(1.0, norm_y))
        norm_w = max(0.01, min(1.0, norm_w))
        norm_h = max(0.01, min(1.0, norm_h))

        return NormalizedCoordinate(norm_x, norm_y, norm_w, norm_h)

    def center_point(self, coord: NormalizedCoordinate) -> Tuple[float, float]:
        """
        Get the center point of a normalized coordinate.

        Args:
            coord: Normalized coordinate

        Returns:
            Tuple of (center_x, center_y) in normalized coordinates
        """
        center_x = coord.x + (coord.w / 2)
        center_y = coord.y + (coord.h / 2)
        return (center_x, center_y)

    def center_point_pixels(self, coord: NormalizedCoordinate) -> Tuple[int, int]:
        """
        Get the center point in pixel coordinates.

        Args:
            coord: Normalized coordinate

        Returns:
            Tuple of (center_x, center_y) in pixel coordinates
        """
        pixel_coord = self.normalized_to_pixels(coord.x, coord.y, coord.w, coord.h)
        center_x = pixel_coord.x + (pixel_coord.w // 2)
        center_y = pixel_coord.y + (pixel_coord.h // 2)
        return (center_x, center_y)


def validate_normalized_coordinates(
    x: float,
    y: float,
    w: float,
    h: float,
    min_dimension: float = 0.01,
    max_dimension: float = 0.9
) -> List[str]:
    """
    Validate normalized coordinates.

    Args:
        x: Horizontal position (should be 0-1)
        y: Vertical position (should be 0-1)
        w: Width (should be 0-1)
        h: Height (should be 0-1)
        min_dimension: Minimum allowed dimension (default: 1%)
        max_dimension: Maximum allowed dimension (default: 90%)

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Validate position ranges
    if not (0 <= x <= 1):
        errors.append(f"x={x} outside valid range [0, 1]")
    if not (0 <= y <= 1):
        errors.append(f"y={y} outside valid range [0, 1]")

    # Validate dimension ranges
    if not (0 < w <= 1):
        errors.append(f"w={w} outside valid range (0, 1]")
    if not (0 < h <= 1):
        errors.append(f"h={h} outside valid range (0, 1]")

    # Check boundary violations
    if x + w > 1.0:
        errors.append(f"x + w = {x + w:.4f} exceeds page width")
    if y + h > 1.0:
        errors.append(f"y + h = {y + h:.4f} exceeds page height")

    # Check minimum dimensions
    if w < min_dimension:
        errors.append(f"w={w} too small (minimum: {min_dimension})")
    if h < min_dimension:
        errors.append(f"h={h} too small (minimum: {min_dimension})")

    # Check maximum dimensions
    if w > max_dimension:
        errors.append(f"w={w} too large (maximum: {max_dimension})")
    if h > max_dimension:
        errors.append(f"h={h} too large (maximum: {max_dimension})")

    return errors


def check_margin_compliance(
    x: float,
    y: float,
    w: float,
    h: float,
    left_margin: float = 0.05,
    right_margin: float = 0.95,
    top_margin: float = 0.05,
    bottom_margin: float = 0.95
) -> List[str]:
    """
    Check if coordinates respect recommended margins.

    Args:
        x, y, w, h: Normalized coordinates
        left_margin: Minimum x value (default: 5%)
        right_margin: Maximum x+w value (default: 95%)
        top_margin: Minimum y value (default: 5%)
        bottom_margin: Maximum y+h value (default: 95%)

    Returns:
        List of warning messages (empty if all margins respected)
    """
    warnings = []

    if x < left_margin:
        warnings.append(f"Field too close to left edge (x={x:.3f}, recommended >= {left_margin})")

    if x + w > right_margin:
        warnings.append(
            f"Field too close to right edge (x+w={x+w:.3f}, recommended <= {right_margin})"
        )

    if y < top_margin:
        warnings.append(f"Field too close to top edge (y={y:.3f}, recommended >= {top_margin})")

    if y + h > bottom_margin:
        warnings.append(
            f"Field too close to bottom edge (y+h={y+h:.3f}, recommended <= {bottom_margin})"
        )

    return warnings


def get_field_type_dimensions(field_type: str) -> Tuple[float, float]:
    """
    Get recommended dimensions for a field type.

    Args:
        field_type: Type of field (signature, text, date, etc.)

    Returns:
        Tuple of (width, height) as normalized values
    """
    dimensions = {
        "signature": (0.20, 0.05),
        "initials": (0.08, 0.04),
        "text": (0.25, 0.03),
        "text_short": (0.15, 0.03),
        "text_long": (0.40, 0.03),
        "date": (0.15, 0.03),
        "number": (0.10, 0.03),
        "checkbox": (0.02, 0.02),
        "radio": (0.02, 0.02),
        "select": (0.20, 0.03),
        "image": (0.15, 0.15),
        "file": (0.25, 0.04),
        "payment": (0.30, 0.05),
    }

    return dimensions.get(field_type, (0.20, 0.03))


def get_common_positions(position_name: str) -> Dict[str, float]:
    """
    Get coordinates for common field positions.

    Args:
        position_name: Name of position (e.g., 'signature_bottom_left')

    Returns:
        Dictionary with x, y coordinates
    """
    positions = {
        # Signature positions
        "signature_bottom_left": {"x": 0.10, "y": 0.85},
        "signature_bottom_center": {"x": 0.40, "y": 0.85},
        "signature_bottom_right": {"x": 0.65, "y": 0.85},

        # Date positions (near signatures)
        "date_bottom_left": {"x": 0.10, "y": 0.92},
        "date_bottom_right": {"x": 0.65, "y": 0.92},

        # Header positions
        "header_left": {"x": 0.10, "y": 0.10},
        "header_center": {"x": 0.40, "y": 0.10},
        "header_right": {"x": 0.70, "y": 0.10},

        # Body positions (two-column)
        "body_left_col": {"x": 0.10, "y": 0.25},
        "body_right_col": {"x": 0.55, "y": 0.25},

        # Footer positions
        "footer_left": {"x": 0.10, "y": 0.90},
        "footer_right": {"x": 0.70, "y": 0.90},

        # Page corner (for initials)
        "page_corner": {"x": 0.85, "y": 0.92},
    }

    return positions.get(position_name, {"x": 0.10, "y": 0.25})


def calculate_multi_column_positions(
    num_columns: int,
    row_y: float,
    field_width: float = 0.35,
    column_spacing: float = 0.10
) -> List[Dict[str, float]]:
    """
    Calculate positions for multi-column layout.

    Args:
        num_columns: Number of columns
        row_y: Y position for the row
        field_width: Width of each field
        column_spacing: Space between columns

    Returns:
        List of position dictionaries with x, y coordinates
    """
    positions = []
    left_margin = 0.05
    available_width = 0.90  # 5% margin on each side

    # Calculate actual spacing to fit all columns
    total_field_width = field_width * num_columns
    total_spacing = available_width - total_field_width
    spacing = total_spacing / (num_columns - 1) if num_columns > 1 else 0

    for col in range(num_columns):
        x = left_margin + (col * (field_width + spacing))
        positions.append({"x": x, "y": row_y})

    return positions
