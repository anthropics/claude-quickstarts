#!/usr/bin/env python3
"""
DocuSeal Coordinate Validator

Validates normalized coordinates (0-1 range) for DocuSeal template fields.
Ensures fields fit within page boundaries and have reasonable dimensions.

Usage:
    python coordinate_validator.py --x 0.5 --y 0.8 --w 0.2 --h 0.05
    python coordinate_validator.py --x 0.5 --y 0.8 --w 0.2 --h 0.05 --page 2
"""

import sys
import argparse
from typing import Tuple, List


def validate_coordinates(
    x: float,
    y: float,
    w: float,
    h: float,
    page: int = 1
) -> Tuple[bool, List[str]]:
    """
    Validate DocuSeal normalized coordinates.

    Args:
        x: Horizontal position (0=left, 1=right)
        y: Vertical position (0=top, 1=bottom)
        w: Width as decimal (0.2 = 20% of page width)
        h: Height as decimal (0.05 = 5% of page height)
        page: Page number (1-indexed)

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Validate x coordinate
    if not (0 <= x <= 1):
        errors.append(f"x={x} is outside valid range [0, 1]")

    # Validate y coordinate
    if not (0 <= y <= 1):
        errors.append(f"y={y} is outside valid range [0, 1]")

    # Validate width
    if not (0 < w <= 1):
        errors.append(f"w={w} is outside valid range (0, 1]")

    # Validate height
    if not (0 < h <= 1):
        errors.append(f"h={h} is outside valid range (0, 1]")

    # Check if field exceeds page width
    if x + w > 1.0:
        errors.append(f"x + w = {x + w:.4f} exceeds page width (max 1.0)")

    # Check if field exceeds page height
    if y + h > 1.0:
        errors.append(f"y + h = {y + h:.4f} exceeds page height (max 1.0)")

    # Validate page number
    if page < 1:
        errors.append(f"page={page} must be >= 1")

    # Check for unreasonably small dimensions
    MIN_DIMENSION = 0.01  # 1% minimum
    if w < MIN_DIMENSION:
        errors.append(f"w={w} is too small (minimum recommended: {MIN_DIMENSION})")
    if h < MIN_DIMENSION:
        errors.append(f"h={h} is too small (minimum recommended: {MIN_DIMENSION})")

    # Check for unreasonably large dimensions
    MAX_DIMENSION = 0.9  # 90% maximum for single field
    if w > MAX_DIMENSION:
        errors.append(f"w={w} is too large (maximum recommended: {MAX_DIMENSION})")
    if h > MAX_DIMENSION:
        errors.append(f"h={h} is too large (maximum recommended: {MAX_DIMENSION})")

    return (len(errors) == 0, errors)


def validate_margin_compliance(x: float, y: float, w: float, h: float) -> List[str]:
    """
    Check if field respects recommended margins.

    Recommended margins:
    - Left: 5% (x >= 0.05)
    - Right: 5% (x + w <= 0.95)
    - Top: 5% (y >= 0.05)
    - Bottom: 5% (y + h <= 0.95)

    Returns:
        List of warnings (empty if all margins are respected)
    """
    warnings = []

    LEFT_MARGIN = 0.05
    RIGHT_MARGIN = 0.95
    TOP_MARGIN = 0.05
    BOTTOM_MARGIN = 0.95

    if x < LEFT_MARGIN:
        warnings.append(f"Field too close to left edge (x={x}, recommended >= {LEFT_MARGIN})")

    if x + w > RIGHT_MARGIN:
        warnings.append(f"Field too close to right edge (x+w={x+w:.4f}, recommended <= {RIGHT_MARGIN})")

    if y < TOP_MARGIN:
        warnings.append(f"Field too close to top edge (y={y}, recommended >= {TOP_MARGIN})")

    if y + h > BOTTOM_MARGIN:
        warnings.append(f"Field too close to bottom edge (y+h={y+h:.4f}, recommended <= {BOTTOM_MARGIN})")

    return warnings


def print_field_info(x: float, y: float, w: float, h: float, page: int):
    """Print helpful field information."""
    print("\n📍 Field Information:")
    print(f"   Position: ({x:.4f}, {y:.4f})")
    print(f"   Size: {w:.4f} × {h:.4f}")
    print(f"   Page: {page}")
    print(f"   Bounds: x={x:.4f} to {x+w:.4f}, y={y:.4f} to {y+h:.4f}")

    # Calculate percentages for easier understanding
    print(f"\n📊 As Percentages:")
    print(f"   Position: {x*100:.1f}% from left, {y*100:.1f}% from top")
    print(f"   Size: {w*100:.1f}% wide, {h*100:.1f}% tall")


def main():
    """Main entry point for coordinate validation."""
    parser = argparse.ArgumentParser(
        description="Validate DocuSeal normalized coordinates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Validate signature box coordinates
    python coordinate_validator.py --x 0.5 --y 0.85 --w 0.3 --h 0.05

    # Validate text field on page 2
    python coordinate_validator.py --x 0.1 --y 0.2 --w 0.4 --h 0.03 --page 2

    # Show warnings about margins
    python coordinate_validator.py --x 0.02 --y 0.1 --w 0.2 --h 0.03 --show-warnings
        """
    )

    parser.add_argument("--x", type=float, required=True,
                       help="Horizontal position (0=left, 1=right)")
    parser.add_argument("--y", type=float, required=True,
                       help="Vertical position (0=top, 1=bottom)")
    parser.add_argument("--w", type=float, required=True,
                       help="Width as decimal (0.2 = 20%% of page width)")
    parser.add_argument("--h", type=float, required=True,
                       help="Height as decimal (0.05 = 5%% of page height)")
    parser.add_argument("--page", type=int, default=1,
                       help="Page number (default: 1)")
    parser.add_argument("--show-warnings", action="store_true",
                       help="Show margin compliance warnings")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed field information")

    args = parser.parse_args()

    # Validate coordinates
    is_valid, errors = validate_coordinates(args.x, args.y, args.w, args.h, args.page)

    # Show field info if verbose
    if args.verbose:
        print_field_info(args.x, args.y, args.w, args.h, args.page)

    # Check margin compliance if requested
    if args.show_warnings:
        warnings = validate_margin_compliance(args.x, args.y, args.w, args.h)
        if warnings:
            print("\n⚠️  Margin Warnings:")
            for warning in warnings:
                print(f"   - {warning}")

    # Report validation results
    if is_valid:
        print("\n✅ Coordinates are valid!")
        sys.exit(0)
    else:
        print("\n❌ INVALID COORDINATES:", file=sys.stderr)
        for error in errors:
            print(f"   - {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
