"""
DocuSeal REST API client.

Provides methods for interacting with DocuSeal's REST API including
template management, field creation, and submission handling.
"""

import os
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import time


@dataclass
class FieldArea:
    """Area definition for a field."""
    x: float
    y: float
    w: float
    h: float
    page: int
    attachment_uuid: Optional[str] = None


@dataclass
class Field:
    """Field configuration for DocuSeal template."""
    name: str
    type: str
    areas: List[FieldArea]
    required: bool = False
    default_value: Optional[str] = None
    description: Optional[str] = None
    validation_pattern: Optional[str] = None
    options: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert field to dictionary for API calls."""
        data = {
            "name": self.name,
            "type": self.type,
            "areas": [asdict(area) for area in self.areas],
        }

        if self.required:
            data["required"] = self.required
        if self.default_value is not None:
            data["default_value"] = self.default_value
        if self.description:
            data["description"] = self.description
        if self.validation_pattern:
            data["validation_pattern"] = self.validation_pattern
        if self.options:
            data["options"] = self.options

        return data


class DocuSealAPIError(Exception):
    """Exception raised for DocuSeal API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(message)


class DocuSealAPIClient:
    """Client for DocuSeal REST API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize DocuSeal API client.

        Args:
            base_url: Base URL of DocuSeal instance (default: DOCUSEAL_URL env var)
            api_key: API key for authentication (default: DOCUSEAL_API_KEY env var)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.base_url = (base_url or os.getenv("DOCUSEAL_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("DOCUSEAL_API_KEY", "")
        self.timeout = timeout
        self.max_retries = max_retries

        if not self.base_url:
            raise ValueError(
                "DocuSeal URL not configured. Set DOCUSEAL_URL environment variable "
                "or pass base_url parameter."
            )
        if not self.api_key:
            raise ValueError(
                "DocuSeal API key not configured. Set DOCUSEAL_API_KEY environment variable "
                "or pass api_key parameter."
            )

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        return {
            "X-Auth-Token": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to DocuSeal API with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data
            params: URL query parameters

        Returns:
            Response data as dictionary

        Raises:
            DocuSealAPIError: If request fails after retries
        """
        url = f"{self.base_url}/api{endpoint}"

        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    json=data,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json() if response.content else {}

            except requests.exceptions.HTTPError as e:
                error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
                if attempt == self.max_retries - 1:
                    raise DocuSealAPIError(
                        error_msg,
                        status_code=e.response.status_code,
                        response_text=e.response.text
                    )
                # Exponential backoff
                time.sleep(2 ** attempt)

            except requests.exceptions.RequestException as e:
                error_msg = f"Request failed: {str(e)}"
                if attempt == self.max_retries - 1:
                    raise DocuSealAPIError(error_msg)
                time.sleep(2 ** attempt)

        raise DocuSealAPIError("Maximum retries exceeded")

    def create_template(
        self,
        name: str,
        pdf_url: Optional[str] = None,
        pdf_file: Optional[bytes] = None,
        fields: Optional[List[Field]] = None
    ) -> Dict[str, Any]:
        """
        Create a new template.

        Args:
            name: Template name
            pdf_url: URL to PDF document
            pdf_file: PDF file bytes (alternative to pdf_url)
            fields: List of field configurations

        Returns:
            Created template data

        Raises:
            DocuSealAPIError: If template creation fails
        """
        data: Dict[str, Any] = {"name": name}

        if pdf_url:
            data["pdf_url"] = pdf_url
        elif pdf_file:
            # For file upload, would need multipart/form-data
            # This is a simplified version - actual implementation may vary
            data["pdf"] = pdf_file

        if fields:
            data["fields"] = [field.to_dict() for field in fields]

        return self._request("POST", "/templates", data=data)

    def get_template(self, template_id: str) -> Dict[str, Any]:
        """
        Get template details.

        Args:
            template_id: Template ID

        Returns:
            Template data

        Raises:
            DocuSealAPIError: If template not found or request fails
        """
        return self._request("GET", f"/templates/{template_id}")

    def list_templates(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List templates.

        Args:
            limit: Maximum number of templates to return

        Returns:
            List of template data dictionaries

        Raises:
            DocuSealAPIError: If request fails
        """
        response = self._request("GET", "/templates", params={"limit": limit})
        return response if isinstance(response, list) else []

    def update_template_fields(
        self,
        template_id: str,
        fields: List[Field]
    ) -> Dict[str, Any]:
        """
        Update template fields.

        Args:
            template_id: Template ID to update
            fields: List of field configurations

        Returns:
            Updated template data

        Raises:
            DocuSealAPIError: If update fails
        """
        data = {"fields": [field.to_dict() for field in fields]}
        return self._request("PUT", f"/templates/{template_id}", data=data)

    def add_fields(
        self,
        template_id: str,
        fields: List[Field]
    ) -> Dict[str, Any]:
        """
        Add fields to existing template (alias for update_template_fields).

        Args:
            template_id: Template ID
            fields: List of field configurations to add

        Returns:
            Updated template data
        """
        return self.update_template_fields(template_id, fields)

    def delete_template(self, template_id: str) -> Dict[str, Any]:
        """
        Delete a template.

        Args:
            template_id: Template ID to delete

        Returns:
            Deletion confirmation

        Raises:
            DocuSealAPIError: If deletion fails
        """
        return self._request("DELETE", f"/templates/{template_id}")

    def create_submission(
        self,
        template_id: str,
        submitters: List[Dict[str, str]],
        send_email: bool = True,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a submission from template.

        Args:
            template_id: Template ID to use
            submitters: List of submitter configurations
                Example: [{"email": "user@example.com", "role": "Signer"}]
            send_email: Whether to send email notifications
            message: Custom message for submitters

        Returns:
            Created submission data

        Raises:
            DocuSealAPIError: If submission creation fails
        """
        data: Dict[str, Any] = {
            "template_id": template_id,
            "submitters": submitters,
            "send_email": send_email
        }

        if message:
            data["message"] = message

        return self._request("POST", "/submissions", data=data)

    def get_submission(self, submission_id: str) -> Dict[str, Any]:
        """
        Get submission details.

        Args:
            submission_id: Submission ID

        Returns:
            Submission data including status and completion info

        Raises:
            DocuSealAPIError: If submission not found or request fails
        """
        return self._request("GET", f"/submissions/{submission_id}")

    def list_submissions(
        self,
        template_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List submissions.

        Args:
            template_id: Filter by template ID (optional)
            limit: Maximum number of submissions to return

        Returns:
            List of submission data dictionaries

        Raises:
            DocuSealAPIError: If request fails
        """
        params = {"limit": limit}
        if template_id:
            params["template_id"] = template_id

        response = self._request("GET", "/submissions", params=params)
        return response if isinstance(response, list) else []

    def get_submission_documents(self, submission_id: str) -> List[Dict[str, Any]]:
        """
        Get completed documents from submission.

        Args:
            submission_id: Submission ID

        Returns:
            List of document data with download URLs

        Raises:
            DocuSealAPIError: If request fails
        """
        return self._request("GET", f"/submissions/{submission_id}/documents")

    def archive_submission(self, submission_id: str) -> Dict[str, Any]:
        """
        Archive a submission.

        Args:
            submission_id: Submission ID to archive

        Returns:
            Archive confirmation

        Raises:
            DocuSealAPIError: If archival fails
        """
        return self._request("DELETE", f"/submissions/{submission_id}")

    def health_check(self) -> bool:
        """
        Check if DocuSeal API is accessible.

        Returns:
            True if API is accessible, False otherwise
        """
        try:
            self._request("GET", "/templates", params={"limit": 1})
            return True
        except DocuSealAPIError:
            return False
