"""
DocuSeal Controller - Hybrid automation orchestrator.

Coordinates between API-based field creation and browser automation,
intelligently choosing the best approach for each operation.
"""

import os
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import asyncio

from .api_client import DocuSealAPIClient, Field, FieldArea
from .coordinates import CoordinateConverter, NormalizedCoordinate, validate_normalized_coordinates
from .human_cursor import HumanCursor, DragDropHelper


class AutomationStrategy(Enum):
    """Strategy for field creation."""
    API_ONLY = "api"
    BROWSER_ONLY = "browser"
    HYBRID = "hybrid"


class DocuSealController:
    """
    Hybrid controller for DocuSeal automation.

    Intelligently chooses between API calls and browser automation
    based on the task requirements and available information.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        page: Optional[any] = None,  # Playwright Page object
        default_strategy: AutomationStrategy = AutomationStrategy.HYBRID
    ):
        """
        Initialize DocuSeal controller.

        Args:
            base_url: DocuSeal instance URL
            api_key: API authentication key
            page: Playwright page object for browser automation
            default_strategy: Default automation strategy
        """
        self.api_client = DocuSealAPIClient(base_url, api_key)
        self.page = page
        self.default_strategy = default_strategy

        # Coordinate converter (can be updated based on actual canvas dimensions)
        self.coord_converter = CoordinateConverter()

        # Drag-drop helper
        self.drag_helper = DragDropHelper()

    def set_page(self, page: any) -> None:
        """
        Set Playwright page object for browser automation.

        Args:
            page: Playwright page object
        """
        self.page = page

    def update_canvas_dimensions(
        self,
        page_width: int,
        page_height: int,
        canvas_offset_x: int = 200,
        canvas_offset_y: int = 100
    ) -> None:
        """
        Update canvas dimensions for coordinate conversion.

        Args:
            page_width: Canvas width in pixels
            page_height: Canvas height in pixels
            canvas_offset_x: Canvas horizontal offset
            canvas_offset_y: Canvas vertical offset
        """
        self.coord_converter = CoordinateConverter(
            page_width, page_height, canvas_offset_x, canvas_offset_y
        )

    def choose_strategy(
        self,
        has_exact_coordinates: bool,
        needs_visual_verification: bool,
        api_available: bool = True
    ) -> AutomationStrategy:
        """
        Choose automation strategy based on task requirements.

        Args:
            has_exact_coordinates: Whether exact coordinates are known
            needs_visual_verification: Whether visual verification is needed
            api_available: Whether API is accessible

        Returns:
            Recommended automation strategy
        """
        if not api_available:
            return AutomationStrategy.BROWSER_ONLY

        if has_exact_coordinates:
            if needs_visual_verification:
                return AutomationStrategy.HYBRID
            else:
                return AutomationStrategy.API_ONLY
        else:
            return AutomationStrategy.BROWSER_ONLY

    async def create_field_api(
        self,
        template_id: str,
        field_name: str,
        field_type: str,
        x: float,
        y: float,
        w: float,
        h: float,
        page: int = 1,
        required: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create field using API.

        Args:
            template_id: Template ID
            field_name: Field name
            field_type: Field type (signature, text, date, etc.)
            x, y, w, h: Normalized coordinates (0-1 range)
            page: Page number (1-indexed)
            required: Whether field is required
            **kwargs: Additional field properties

        Returns:
            API response with created field data

        Raises:
            ValueError: If coordinates are invalid
        """
        # Validate coordinates
        errors = validate_normalized_coordinates(x, y, w, h)
        if errors:
            raise ValueError(f"Invalid coordinates: {', '.join(errors)}")

        # Create field configuration
        area = FieldArea(x=x, y=y, w=w, h=h, page=page)
        field = Field(
            name=field_name,
            type=field_type,
            areas=[area],
            required=required,
            **{k: v for k, v in kwargs.items() if k in ['default_value', 'description', 'validation_pattern', 'options']}
        )

        # Create via API
        result = self.api_client.add_fields(template_id, [field])
        return result

    async def create_fields_batch_api(
        self,
        template_id: str,
        fields: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create multiple fields in a single API call.

        Args:
            template_id: Template ID
            fields: List of field configurations

        Returns:
            API response with created fields data
        """
        field_objects = []

        for field_config in fields:
            # Extract coordinates
            coords = field_config.get('coordinates', {})
            areas = []

            if 'areas' in field_config:
                # Multiple areas provided
                for area_config in field_config['areas']:
                    areas.append(FieldArea(
                        x=area_config['x'],
                        y=area_config['y'],
                        w=area_config['w'],
                        h=area_config['h'],
                        page=area_config.get('page', 1)
                    ))
            else:
                # Single area from coordinates
                areas.append(FieldArea(
                    x=coords['x'],
                    y=coords['y'],
                    w=coords['w'],
                    h=coords['h'],
                    page=coords.get('page', 1)
                ))

            # Create field object
            field = Field(
                name=field_config['name'],
                type=field_config['type'],
                areas=areas,
                required=field_config.get('required', False),
                default_value=field_config.get('default_value'),
                description=field_config.get('description'),
                validation_pattern=field_config.get('validation_pattern'),
                options=field_config.get('options')
            )
            field_objects.append(field)

        # Create all fields via API
        result = self.api_client.add_fields(template_id, field_objects)
        return result

    async def create_field_browser(
        self,
        field_type: str,
        target_x: float,
        target_y: float,
        field_palette_selector: Optional[str] = None
    ) -> bool:
        """
        Create field using browser automation.

        Args:
            field_type: Type of field to create
            target_x: Target x coordinate (normalized 0-1)
            target_y: Target y coordinate (normalized 0-1)
            field_palette_selector: CSS selector for field in palette

        Returns:
            True if successful, False otherwise
        """
        if not self.page:
            raise ValueError("Page not set. Call set_page() first.")

        # Convert normalized coordinates to pixels
        target_coord = NormalizedCoordinate(target_x, target_y, 0.2, 0.05)  # Default size
        pixel_target = self.coord_converter.center_point_pixels(target_coord)

        # Default selector if not provided
        if not field_palette_selector:
            field_palette_selector = f"[data-field-type='{field_type}']"

        # Locate field in palette
        try:
            element = await self.page.wait_for_selector(field_palette_selector, timeout=5000)
            bounding_box = await element.bounding_box()

            if not bounding_box:
                print(f"Could not get bounding box for {field_type}")
                return False

            # Calculate center of source element
            source_x = int(bounding_box['x'] + bounding_box['width'] / 2)
            source_y = int(bounding_box['y'] + bounding_box['height'] / 2)

            # Perform drag with natural motion
            success = await self.drag_helper.drag_field_with_verification(
                self.page,
                field_type,
                (source_x, source_y),
                pixel_target
            )

            return success

        except Exception as e:
            print(f"Browser automation failed: {e}")
            return False

    async def create_field_hybrid(
        self,
        template_id: str,
        field_name: str,
        field_type: str,
        x: float,
        y: float,
        w: float,
        h: float,
        page: int = 1,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create field using hybrid approach (API + visual verification).

        Args:
            template_id: Template ID
            field_name: Field name
            field_type: Field type
            x, y, w, h: Normalized coordinates
            page: Page number
            **kwargs: Additional field properties

        Returns:
            API response with verification status
        """
        # Create via API
        result = await self.create_field_api(
            template_id, field_name, field_type, x, y, w, h, page, **kwargs
        )

        # Visual verification if browser available
        if self.page:
            await asyncio.sleep(1.0)  # Wait for UI to update

            # Take screenshot for verification
            screenshot = await self.page.screenshot()

            # Could add visual verification logic here
            # For now, just return API result
            print(f"Field '{field_name}' created via API, browser verification available")

        return result

    async def navigate_to_template(self, template_id: str) -> bool:
        """
        Navigate to template builder in browser.

        Args:
            template_id: Template ID

        Returns:
            True if navigation successful
        """
        if not self.page:
            raise ValueError("Page not set. Call set_page() first.")

        try:
            url = f"{self.api_client.base_url}/templates/{template_id}"
            await self.page.goto(url, wait_until="networkidle")
            return True
        except Exception as e:
            print(f"Navigation failed: {e}")
            return False

    async def take_screenshot(self) -> Optional[bytes]:
        """
        Take screenshot of current page.

        Returns:
            Screenshot bytes or None if page not set
        """
        if not self.page:
            return None

        return await self.page.screenshot()

    def validate_template_access(self, template_id: str) -> bool:
        """
        Validate that template is accessible via API.

        Args:
            template_id: Template ID to check

        Returns:
            True if template exists and is accessible
        """
        try:
            self.api_client.get_template(template_id)
            return True
        except Exception:
            return False

    async def wait_for_field(
        self,
        field_name: str,
        timeout: int = 5000
    ) -> bool:
        """
        Wait for field to appear in UI.

        Args:
            field_name: Name of field to wait for
            timeout: Timeout in milliseconds

        Returns:
            True if field appeared, False if timeout
        """
        if not self.page:
            return False

        selector = f"[data-field-name='{field_name}']"
        return await self.drag_helper.wait_for_element(self.page, selector, timeout)

    def health_check(self) -> Dict[str, bool]:
        """
        Check health of all components.

        Returns:
            Dictionary with health status of API and browser
        """
        return {
            "api": self.api_client.health_check(),
            "browser": self.page is not None
        }
