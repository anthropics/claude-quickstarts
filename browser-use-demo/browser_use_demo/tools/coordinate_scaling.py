"""
Coordinate scaling utilities for browser tool.

This module handles the scaling of coordinates from Claude's vision model
resolution to the actual browser viewport resolution.
"""


class CoordinateScaler:
    """Handles coordinate scaling between Claude's vision and actual viewport."""

    # Claude's image processing resolution for 16:9 aspect ratio
    # According to the official documentation:
    # https://docs.claude.com/en/docs/build-with-claude/vision#evaluate-image-size
    # When images exceed size thresholds, they are resized while preserving aspect ratio.
    # For 16:9 aspect ratio (like 1920x1080 screenshots), images are resized to these exact dimensions:
    CLAUDE_ACTUAL_WIDTH = 1456  # Width for 16:9 landscape (from documentation)
    CLAUDE_ACTUAL_HEIGHT = 819  # Height for 16:9 landscape (from documentation)

    # Documented maximum image sizes for different aspect ratios
    # Source: https://docs.claude.com/en/docs/build-with-claude/vision#evaluate-image-size
    DOCUMENTED_SIZES = {
        # aspect_ratio: (width, height)
        (1, 1): (1092, 1092),      # Square
        (3, 4): (951, 1268),       # Portrait
        (4, 3): (1268, 951),       # Landscape
        (2, 3): (896, 1344),       # Portrait
        (3, 2): (1344, 896),       # Landscape
        (9, 16): (819, 1456),      # Portrait (phone)
        (16, 9): (1456, 819),      # Landscape (widescreen)
        (1, 2): (784, 1568),       # Portrait (tall)
        (2, 1): (1568, 784),       # Landscape (wide)
    }

    @classmethod
    def get_documented_size_for_aspect_ratio(cls, viewport_width: int, viewport_height: int) -> tuple[int, int]:
        """
        Get the documented size for the given viewport's aspect ratio.

        Args:
            viewport_width: Actual viewport width
            viewport_height: Actual viewport height

        Returns:
            Tuple of (width, height) from documented sizes that matches the aspect ratio

        Raises:
            ValueError: If the aspect ratio doesn't match any documented sizes
        """
        viewport_ratio = viewport_width / viewport_height

        # Tolerance for aspect ratio matching (to handle minor differences)
        ASPECT_RATIO_TOLERANCE = 0.02

        # Try to find an exact or very close aspect ratio match
        for (ratio_w, ratio_h), (doc_width, doc_height) in cls.DOCUMENTED_SIZES.items():
            doc_ratio = ratio_w / ratio_h
            if abs(viewport_ratio - doc_ratio) < ASPECT_RATIO_TOLERANCE:
                return (doc_width, doc_height)

        # If no match found, raise an error with helpful information
        supported_ratios = [f"{w}:{h} ({w/h:.3f})" for (w, h) in cls.DOCUMENTED_SIZES.keys()]
        raise ValueError(
            f"Viewport aspect ratio {viewport_ratio:.3f} ({viewport_width}x{viewport_height}) "
            f"does not match any documented aspect ratios. "
            f"Supported ratios: {', '.join(supported_ratios)}. "
            f"See https://docs.claude.com/en/docs/build-with-claude/vision#evaluate-image-size"
        )

    @classmethod
    def get_scale_factors(
        cls,
        viewport_width: int,
        viewport_height: int,
        match_aspect_ratio: bool = False
    ) -> tuple[float, float]:
        """
        Calculate scale factors for converting Claude coordinates to viewport coordinates.

        Args:
            viewport_width: Actual browser viewport width
            viewport_height: Actual browser viewport height
            match_aspect_ratio: If True, match the viewport's aspect ratio to documented sizes.
                              If False (default), use 16:9 for browser scenarios.

        Returns:
            Tuple of (scale_x, scale_y) factors

        Raises:
            ValueError: If match_aspect_ratio is True and aspect ratio doesn't match documented sizes
        """
        if match_aspect_ratio:
            # Match the documented size based on aspect ratio (will raise if no match)
            base_width, base_height = cls.get_documented_size_for_aspect_ratio(viewport_width, viewport_height)
        else:
            # Use default 16:9 dimensions (typical for browser screenshots)
            base_width = cls.CLAUDE_ACTUAL_WIDTH
            base_height = cls.CLAUDE_ACTUAL_HEIGHT

        # Calculate scale factors
        scale_x = viewport_width / base_width
        scale_y = viewport_height / base_height

        return scale_x, scale_y

    @classmethod
    def scale_coordinates(
        cls,
        x: int,
        y: int,
        viewport_width: int,
        viewport_height: int,
        apply_threshold: bool = True
    ) -> tuple[int, int]:
        """
        Scale coordinates from Claude's vision to actual viewport.

        Args:
            x: X coordinate from Claude
            y: Y coordinate from Claude
            viewport_width: Actual browser viewport width
            viewport_height: Actual browser viewport height
            apply_threshold: Whether to check if coordinates need scaling

        Returns:
            Tuple of (scaled_x, scaled_y)
        """
        scale_x, scale_y = cls.get_scale_factors(viewport_width, viewport_height)

        # If scaling factors are close to 1.0, no scaling needed
        if abs(scale_x - 1.0) < 0.05 and abs(scale_y - 1.0) < 0.05:
            return x, y

        if apply_threshold:
            # Check if coordinates appear to be in Claude's resolution
            # (with 20% margin for edge cases)
            max_expected_x = cls.CLAUDE_ACTUAL_WIDTH * 1.2
            max_expected_y = cls.CLAUDE_ACTUAL_HEIGHT * 1.2

            # If coordinates are larger than expected Claude resolution,
            # they might already be in viewport coordinates
            if x > max_expected_x or y > max_expected_y:
                return x, y

        # Apply scaling
        scaled_x = int(x * scale_x)
        scaled_y = int(y * scale_y)

        # Ensure we don't exceed viewport bounds
        scaled_x = min(scaled_x, viewport_width - 1)
        scaled_y = min(scaled_y, viewport_height - 1)

        return scaled_x, scaled_y

    @classmethod
    def scale_coordinate_list(
        cls,
        coords: list | tuple,
        viewport_width: int,
        viewport_height: int
    ) -> list:
        """
        Scale a coordinate pair list/tuple.

        Args:
            coords: [x, y] coordinate pair
            viewport_width: Actual browser viewport width
            viewport_height: Actual browser viewport height

        Returns:
            Scaled [x, y] coordinate pair
        """
        if not isinstance(coords, (list, tuple)) or len(coords) != 2:
            return list(coords) if isinstance(coords, tuple) else coords

        x, y = coords[0], coords[1]
        scaled_x, scaled_y = cls.scale_coordinates(x, y, viewport_width, viewport_height)
        return [scaled_x, scaled_y]