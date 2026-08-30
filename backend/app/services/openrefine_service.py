"""OpenRefine HTTP API client.

Wraps the OpenRefine wire protocol to create projects from CSV data
and retrieve project URLs for the frontend to link to.

Wire protocol docs: https://docs.openrefine.org/technical-reference/wire-protocol
"""

import logging
from io import BytesIO

import httpx

logger = logging.getLogger(__name__)

# Default OpenRefine URL inside Docker network
OPENREFINE_URL = "http://openrefine:3333"


class OpenRefineService:
    """Thin client for OpenRefine's HTTP API."""

    def __init__(self, base_url: str = OPENREFINE_URL):
        self.base_url = base_url.rstrip("/")

    async def create_project(
        self, csv_data: bytes, project_name: str
    ) -> dict:
        """Create an OpenRefine project from CSV data.

        Args:
            csv_data: Raw CSV bytes.
            project_name: Human-readable name for the project.

        Returns:
            Dict with `project_id` and `project_url`.

        Raises:
            httpx.HTTPError: If OpenRefine is unreachable or returns an error.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {
                "project-file": ("export.csv", BytesIO(csv_data), "text/csv"),
            }
            data = {
                "project-name": project_name,
                "format": "text/line-based/*sv",
            }

            resp = await client.post(
                f"{self.base_url}/command/core/create-project-from-upload",
                files=files,
                data=data,
            )
            resp.raise_for_status()

            # OpenRefine returns JSON with {"project_id": "..."}
            result = resp.json()
            project_id = result.get("project_id")

            if not project_id:
                raise ValueError(
                    f"OpenRefine did not return a project_id: {result}"
                )

            project_url = f"{self.base_url}/project?project={project_id}"

            logger.info(
                "Created OpenRefine project %s: %s", project_id, project_name
            )

            return {
                "project_id": project_id,
                "project_url": project_url,
                "project_name": project_name,
            }

    async def get_project_rows(
        self, project_id: str
    ) -> dict:
        """Export rows from an OpenRefine project as JSON.

        Args:
            project_id: The OpenRefine project ID.

        Returns:
            The exported row data.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/command/core/export-rows",
                data={
                    "project": project_id,
                    "format": "text/line-based/*sv",
                },
            )
            resp.raise_for_status()
            return resp.text

    async def health_check(self) -> bool:
        """Check if OpenRefine is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/command/core/get-version")
                resp.raise_for_status()
                return True
        except (httpx.HTTPError, httpx.ConnectError):
            return False


# Module-level singleton
openrefine_service = OpenRefineService()
