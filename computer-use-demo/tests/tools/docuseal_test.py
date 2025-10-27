"""
Unit tests for DocuSeal integration tools.

Tests coordinate validation, conversion, API client, and controller functionality.
"""

import pytest
from computer_use_demo.tools.docuseal.coordinates import (
    CoordinateConverter,
    NormalizedCoordinate,
    validate_normalized_coordinates,
    check_margin_compliance,
    get_field_type_dimensions,
    get_common_positions,
)


class TestCoordinateValidation:
    """Test coordinate validation functions."""

    def test_valid_coordinates(self):
        """Test that valid coordinates pass validation."""
        errors = validate_normalized_coordinates(0.5, 0.5, 0.2, 0.1)
        assert len(errors) == 0

    def test_invalid_x_coordinate(self):
        """Test that invalid x coordinate is caught."""
        errors = validate_normalized_coordinates(1.5, 0.5, 0.2, 0.1)
        assert len(errors) > 0
        assert any("x=" in err for err in errors)

    def test_invalid_y_coordinate(self):
        """Test that invalid y coordinate is caught."""
        errors = validate_normalized_coordinates(0.5, -0.1, 0.2, 0.1)
        assert len(errors) > 0
        assert any("y=" in err for err in errors)

    def test_invalid_width(self):
        """Test that invalid width is caught."""
        errors = validate_normalized_coordinates(0.5, 0.5, 0, 0.1)
        assert len(errors) > 0
        assert any("w=" in err for err in errors)

    def test_invalid_height(self):
        """Test that invalid height is caught."""
        errors = validate_normalized_coordinates(0.5, 0.5, 0.2, 1.5)
        assert len(errors) > 0
        assert any("h=" in err for err in errors)

    def test_exceeds_page_width(self):
        """Test that coordinates exceeding page width are caught."""
        errors = validate_normalized_coordinates(0.9, 0.5, 0.2, 0.1)
        assert len(errors) > 0
        assert any("page width" in err for err in errors)

    def test_exceeds_page_height(self):
        """Test that coordinates exceeding page height are caught."""
        errors = validate_normalized_coordinates(0.5, 0.95, 0.2, 0.1)
        assert len(errors) > 0
        assert any("page height" in err for err in errors)

    def test_too_small_dimensions(self):
        """Test that too small dimensions are caught."""
        errors = validate_normalized_coordinates(0.5, 0.5, 0.001, 0.001)
        assert len(errors) > 0

    def test_too_large_dimensions(self):
        """Test that too large dimensions are caught."""
        errors = validate_normalized_coordinates(0.05, 0.05, 0.95, 0.95)
        assert len(errors) > 0


class TestMarginCompliance:
    """Test margin compliance checking."""

    def test_compliant_coordinates(self):
        """Test coordinates that respect margins."""
        warnings = check_margin_compliance(0.1, 0.1, 0.3, 0.2)
        assert len(warnings) == 0

    def test_left_margin_violation(self):
        """Test left margin violation."""
        warnings = check_margin_compliance(0.02, 0.1, 0.3, 0.2)
        assert len(warnings) > 0
        assert any("left edge" in warn for warn in warnings)

    def test_right_margin_violation(self):
        """Test right margin violation."""
        warnings = check_margin_compliance(0.8, 0.1, 0.3, 0.2)
        assert len(warnings) > 0
        assert any("right edge" in warn for warn in warnings)

    def test_top_margin_violation(self):
        """Test top margin violation."""
        warnings = check_margin_compliance(0.1, 0.02, 0.3, 0.2)
        assert len(warnings) > 0
        assert any("top edge" in warn for warn in warnings)

    def test_bottom_margin_violation(self):
        """Test bottom margin violation."""
        warnings = check_margin_compliance(0.1, 0.85, 0.3, 0.2)
        assert len(warnings) > 0
        assert any("bottom edge" in warn for warn in warnings)


class TestNormalizedCoordinate:
    """Test NormalizedCoordinate dataclass."""

    def test_valid_coordinate_creation(self):
        """Test creating valid normalized coordinate."""
        coord = NormalizedCoordinate(0.5, 0.5, 0.2, 0.1, page=1)
        assert coord.x == 0.5
        assert coord.y == 0.5
        assert coord.w == 0.2
        assert coord.h == 0.1
        assert coord.page == 1

    def test_invalid_coordinate_raises_error(self):
        """Test that invalid coordinates raise ValueError."""
        with pytest.raises(ValueError):
            NormalizedCoordinate(1.5, 0.5, 0.2, 0.1)

    def test_default_page_number(self):
        """Test that page defaults to 1."""
        coord = NormalizedCoordinate(0.5, 0.5, 0.2, 0.1)
        assert coord.page == 1


class TestCoordinateConverter:
    """Test coordinate conversion between normalized and pixels."""

    def test_normalized_to_pixels(self):
        """Test conversion from normalized to pixel coordinates."""
        converter = CoordinateConverter(
            page_width=1000,
            page_height=1200,
            canvas_offset_x=200,
            canvas_offset_y=100
        )

        pixel_coord = converter.normalized_to_pixels(0.5, 0.5, 0.2, 0.1)

        # Expected: x=200+(0.5*1000)=700, y=100+(0.5*1200)=700
        assert pixel_coord.x == 700
        assert pixel_coord.y == 700
        assert pixel_coord.w == 200  # 0.2 * 1000
        assert pixel_coord.h == 120  # 0.1 * 1200

    def test_pixels_to_normalized(self):
        """Test conversion from pixel to normalized coordinates."""
        converter = CoordinateConverter(
            page_width=1000,
            page_height=1200,
            canvas_offset_x=200,
            canvas_offset_y=100
        )

        norm_coord = converter.pixels_to_normalized(700, 700, 200, 120)

        # Should be close to original normalized values
        assert abs(norm_coord.x - 0.5) < 0.01
        assert abs(norm_coord.y - 0.5) < 0.01
        assert abs(norm_coord.w - 0.2) < 0.01
        assert abs(norm_coord.h - 0.1) < 0.01

    def test_center_point(self):
        """Test calculating center point of coordinate."""
        converter = CoordinateConverter()
        coord = NormalizedCoordinate(0.1, 0.2, 0.3, 0.4)

        center_x, center_y = converter.center_point(coord)

        # Center should be at (0.1 + 0.3/2, 0.2 + 0.4/2) = (0.25, 0.4)
        assert center_x == 0.25
        assert center_y == 0.4

    def test_center_point_pixels(self):
        """Test calculating center point in pixels."""
        converter = CoordinateConverter(
            page_width=1000,
            page_height=1000,
            canvas_offset_x=0,
            canvas_offset_y=0
        )
        coord = NormalizedCoordinate(0.4, 0.4, 0.2, 0.2)

        center_x, center_y = converter.center_point_pixels(coord)

        # Expected: center at (0.5*1000, 0.5*1000) = (500, 500)
        assert center_x == 500
        assert center_y == 500


class TestFieldTypeDimensions:
    """Test field type dimension helpers."""

    def test_signature_dimensions(self):
        """Test signature field dimensions."""
        w, h = get_field_type_dimensions("signature")
        assert w == 0.20
        assert h == 0.05

    def test_text_dimensions(self):
        """Test text field dimensions."""
        w, h = get_field_type_dimensions("text")
        assert w == 0.25
        assert h == 0.03

    def test_checkbox_dimensions(self):
        """Test checkbox dimensions."""
        w, h = get_field_type_dimensions("checkbox")
        assert w == 0.02
        assert h == 0.02

    def test_unknown_field_type(self):
        """Test that unknown field types return defaults."""
        w, h = get_field_type_dimensions("unknown_type")
        assert w > 0
        assert h > 0


class TestCommonPositions:
    """Test common field position helpers."""

    def test_signature_bottom_left(self):
        """Test signature bottom left position."""
        pos = get_common_positions("signature_bottom_left")
        assert pos["x"] == 0.10
        assert pos["y"] == 0.85

    def test_header_positions(self):
        """Test header positions."""
        pos_left = get_common_positions("header_left")
        pos_center = get_common_positions("header_center")
        pos_right = get_common_positions("header_right")

        assert pos_left["x"] < pos_center["x"] < pos_right["x"]
        assert pos_left["y"] == pos_center["y"] == pos_right["y"]

    def test_body_columns(self):
        """Test body column positions."""
        pos_left = get_common_positions("body_left_col")
        pos_right = get_common_positions("body_right_col")

        assert pos_left["x"] < pos_right["x"]
        assert pos_left["y"] == pos_right["y"]

    def test_unknown_position(self):
        """Test unknown position returns default."""
        pos = get_common_positions("unknown_position")
        assert "x" in pos
        assert "y" in pos


# Integration tests would require actual API access and browser
# These are placeholder tests for structure

class TestDocuSealAPIClient:
    """Test DocuSeal API client (requires mocking or actual API)."""

    def test_client_initialization_with_env_vars(self, monkeypatch):
        """Test client initializes with environment variables."""
        monkeypatch.setenv("DOCUSEAL_URL", "https://test.docuseal.com")
        monkeypatch.setenv("DOCUSEAL_API_KEY", "test_key")

        from computer_use_demo.tools.docuseal.api_client import DocuSealAPIClient
        client = DocuSealAPIClient()

        assert client.base_url == "https://test.docuseal.com"
        assert client.api_key == "test_key"

    def test_client_initialization_without_url_raises_error(self):
        """Test client raises error without URL."""
        from computer_use_demo.tools.docuseal.api_client import DocuSealAPIClient

        with pytest.raises(ValueError, match="DocuSeal URL not configured"):
            DocuSealAPIClient(base_url="", api_key="test")

    def test_client_initialization_without_key_raises_error(self):
        """Test client raises error without API key."""
        from computer_use_demo.tools.docuseal.api_client import DocuSealAPIClient

        with pytest.raises(ValueError, match="API key not configured"):
            DocuSealAPIClient(base_url="https://test.com", api_key="")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
