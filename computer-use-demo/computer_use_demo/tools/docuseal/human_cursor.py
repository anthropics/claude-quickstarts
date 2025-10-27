"""
Human-like cursor movement simulation.

Provides natural mouse movement patterns using Bezier curves and randomization
to avoid detection as bot activity and provide more reliable drag-and-drop operations.
"""

import random
import math
from typing import List, Tuple
import asyncio


class HumanCursor:
    """Simulate human-like cursor movements."""

    @staticmethod
    def bezier_curve(
        start: Tuple[int, int],
        end: Tuple[int, int],
        control_points: int = 2,
        steps: int = 20
    ) -> List[Tuple[int, int]]:
        """
        Generate Bezier curve points for natural movement.

        Args:
            start: Starting (x, y) position
            end: Ending (x, y) position
            control_points: Number of control points (default: 2 for cubic)
            steps: Number of points in the curve

        Returns:
            List of (x, y) coordinates along the curve
        """
        points = []

        # Generate control points with random deviation
        controls = []
        for i in range(control_points):
            t = (i + 1) / (control_points + 1)
            # Linear interpolation with random offset
            x = start[0] + (end[0] - start[0]) * t
            y = start[1] + (end[1] - start[1]) * t

            # Add random deviation perpendicular to the line
            distance = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
            max_deviation = min(distance * 0.2, 100)  # Max 20% of distance or 100px

            # Random deviation
            deviation = random.uniform(-max_deviation, max_deviation)
            angle = math.atan2(end[1] - start[1], end[0] - start[0]) + math.pi / 2

            x += deviation * math.cos(angle)
            y += deviation * math.sin(angle)

            controls.append((x, y))

        # Generate curve points using cubic Bezier (with 2 control points)
        if len(controls) >= 2:
            for i in range(steps + 1):
                t = i / steps

                # Cubic Bezier formula
                x = (
                    (1 - t)**3 * start[0] +
                    3 * (1 - t)**2 * t * controls[0][0] +
                    3 * (1 - t) * t**2 * controls[1][0] +
                    t**3 * end[0]
                )
                y = (
                    (1 - t)**3 * start[1] +
                    3 * (1 - t)**2 * t * controls[0][1] +
                    3 * (1 - t) * t**2 * controls[1][1] +
                    t**3 * end[1]
                )

                points.append((int(x), int(y)))
        else:
            # Fallback to linear interpolation
            for i in range(steps + 1):
                t = i / steps
                x = start[0] + (end[0] - start[0]) * t
                y = start[1] + (end[1] - start[1]) * t
                points.append((int(x), int(y)))

        return points

    @staticmethod
    def add_natural_jitter(
        points: List[Tuple[int, int]],
        jitter_amount: int = 2
    ) -> List[Tuple[int, int]]:
        """
        Add small random jitter to points for more natural movement.

        Args:
            points: List of (x, y) coordinates
            jitter_amount: Maximum pixel deviation (default: 2)

        Returns:
            List of jittered coordinates
        """
        jittered = []
        for x, y in points:
            jitter_x = random.randint(-jitter_amount, jitter_amount)
            jitter_y = random.randint(-jitter_amount, jitter_amount)
            jittered.append((x + jitter_x, y + jitter_y))
        return jittered

    @staticmethod
    def calculate_timing(
        points: List[Tuple[int, int]],
        min_delay_ms: int = 10,
        max_delay_ms: int = 30
    ) -> List[int]:
        """
        Calculate timing for each point in movement.

        Args:
            points: List of (x, y) coordinates
            min_delay_ms: Minimum delay between points
            max_delay_ms: Maximum delay between points

        Returns:
            List of delay values in milliseconds
        """
        delays = []
        for i in range(len(points)):
            # Vary speed - faster in middle, slower at start/end
            progress = i / max(len(points) - 1, 1)
            # Sine wave for smooth acceleration/deceleration
            speed_factor = math.sin(progress * math.pi)

            base_delay = min_delay_ms + (max_delay_ms - min_delay_ms) * speed_factor
            # Add random variation
            delay = int(base_delay + random.uniform(-5, 5))
            delays.append(max(min_delay_ms, min(delay, max_delay_ms)))

        return delays

    @staticmethod
    async def drag_with_natural_motion(
        page: any,  # Playwright Page object
        start: Tuple[int, int],
        end: Tuple[int, int],
        steps: int = 20,
        jitter: int = 2
    ) -> None:
        """
        Perform drag operation with natural cursor movement.

        Args:
            page: Playwright page object
            start: Starting (x, y) position
            end: Ending (x, y) position
            steps: Number of interpolation steps
            jitter: Amount of random jitter
        """
        # Generate curve
        curve_points = HumanCursor.bezier_curve(start, end, steps=steps)

        # Add jitter
        if jitter > 0:
            curve_points = HumanCursor.add_natural_jitter(curve_points, jitter)

        # Calculate timing
        delays = HumanCursor.calculate_timing(curve_points)

        # Perform the drag
        await page.mouse.move(start[0], start[1])
        await page.mouse.down()

        # Follow the curve
        for (x, y), delay in zip(curve_points, delays):
            await page.mouse.move(x, y)
            await asyncio.sleep(delay / 1000.0)  # Convert to seconds

        await page.mouse.up()

    @staticmethod
    async def move_to_with_natural_motion(
        page: any,  # Playwright Page object
        target: Tuple[int, int],
        steps: int = 15
    ) -> None:
        """
        Move cursor to target with natural movement.

        Args:
            page: Playwright page object
            target: Target (x, y) position
            steps: Number of interpolation steps
        """
        # Get current position (approximate - Playwright doesn't expose this)
        # Assume starting from center of viewport
        viewport = page.viewport_size
        start = (viewport['width'] // 2, viewport['height'] // 2)

        # Generate curve
        curve_points = HumanCursor.bezier_curve(start, target, steps=steps)
        curve_points = HumanCursor.add_natural_jitter(curve_points, jitter=2)

        # Calculate timing
        delays = HumanCursor.calculate_timing(curve_points)

        # Move along curve
        for (x, y), delay in zip(curve_points, delays):
            await page.mouse.move(x, y)
            await asyncio.sleep(delay / 1000.0)

    @staticmethod
    def random_pause() -> float:
        """
        Generate random pause duration for human-like behavior.

        Returns:
            Pause duration in seconds
        """
        # Most pauses are short, occasional longer pauses
        if random.random() < 0.9:
            return random.uniform(0.1, 0.5)
        else:
            return random.uniform(0.5, 2.0)

    @staticmethod
    async def click_with_natural_motion(
        page: any,  # Playwright Page object
        target: Tuple[int, int],
        double_click: bool = False
    ) -> None:
        """
        Move to target and click with natural motion.

        Args:
            page: Playwright page object
            target: Target (x, y) position
            double_click: Whether to double-click
        """
        # Move to target naturally
        await HumanCursor.move_to_with_natural_motion(page, target)

        # Small pause before clicking
        await asyncio.sleep(random.uniform(0.05, 0.15))

        # Click
        if double_click:
            await page.mouse.click(target[0], target[1], click_count=2)
        else:
            await page.mouse.click(target[0], target[1])

        # Small pause after clicking
        await asyncio.sleep(random.uniform(0.05, 0.1))


class DragDropHelper:
    """Helper for drag-and-drop operations with retry logic."""

    def __init__(self, max_retries: int = 3):
        """
        Initialize drag-drop helper.

        Args:
            max_retries: Maximum number of retry attempts
        """
        self.max_retries = max_retries

    async def drag_field_with_verification(
        self,
        page: any,
        field_type: str,
        source_position: Tuple[int, int],
        target_position: Tuple[int, int],
        verification_callback = None
    ) -> bool:
        """
        Drag field with automatic verification and retry.

        Args:
            page: Playwright page object
            field_type: Type of field being dragged
            source_position: Starting position (field palette)
            target_position: Target position on canvas
            verification_callback: Optional callback to verify success

        Returns:
            True if drag was successful, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                # Perform drag with natural motion
                await HumanCursor.drag_with_natural_motion(
                    page,
                    source_position,
                    target_position
                )

                # Wait for UI to update
                await asyncio.sleep(0.5)

                # Verify if callback provided
                if verification_callback:
                    if await verification_callback(page):
                        return True
                    else:
                        if attempt < self.max_retries - 1:
                            print(f"Drag attempt {attempt + 1} failed verification, retrying...")
                            await asyncio.sleep(1.0)
                else:
                    # No verification, assume success
                    return True

            except Exception as e:
                print(f"Drag attempt {attempt + 1} failed with error: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1.0)

        return False

    @staticmethod
    async def wait_for_element(
        page: any,
        selector: str,
        timeout: int = 5000
    ) -> bool:
        """
        Wait for element to appear.

        Args:
            page: Playwright page object
            selector: CSS selector
            timeout: Timeout in milliseconds

        Returns:
            True if element appeared, False if timeout
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False
