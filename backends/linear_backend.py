"""Linear.app backend for work tracking.

This backend integrates with Linear.app for work item management.
It uses the Linear GraphQL API to create and manage issues.

Linear is particularly useful for:
- Team visibility into agent progress
- Integration with existing Linear workflows
- Rich issue management features (labels, cycles, projects)

Environment Variables:
    LINEAR_API_KEY: Linear API key for authentication
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence

import httpx

from backends.base import (
    ProgressSummary,
    Project,
    WorkItem,
    WorkItemCreate,
    WorkItemPriority,
    WorkItemStatus,
    WorkItemUpdate,
    WorkTracker,
)


# Linear status mapping
LINEAR_STATUS_MAP = {
    "Todo": WorkItemStatus.TODO,
    "In Progress": WorkItemStatus.IN_PROGRESS,
    "Done": WorkItemStatus.DONE,
    "Blocked": WorkItemStatus.BLOCKED,
    "Backlog": WorkItemStatus.TODO,
    "Canceled": WorkItemStatus.DONE,
}

# Reverse mapping
STATUS_TO_LINEAR = {
    WorkItemStatus.TODO: "Todo",
    WorkItemStatus.IN_PROGRESS: "In Progress",
    WorkItemStatus.DONE: "Done",
    WorkItemStatus.BLOCKED: "Blocked",
}


class LinearBackend(WorkTracker):
    """Linear.app-based work tracker backend.

    This backend uses the Linear GraphQL API to manage issues.
    Each work item corresponds to a Linear issue.

    Attributes:
        api_key: Linear API key.
        team_id: Linear team ID (cached after first query).
        project_id: Linear project ID (cached after initialization).
    """

    API_URL = "https://api.linear.app/graphql"

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize the Linear backend.

        Args:
            api_key: Linear API key. If not provided, uses LINEAR_API_KEY env var.
        """
        self._api_key = api_key or os.environ.get("LINEAR_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Linear API key is required. "
                "Provide via argument or LINEAR_API_KEY environment variable."
            )

        self._client = httpx.AsyncClient(
            headers={
                "Authorization": self._api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._team_id: Optional[str] = None
        self._project_id: Optional[str] = None
        self._project_uuid: Optional[str] = None  # Local UUID for Project object
        self._status_ids: dict[str, str] = {}  # status name -> status id

    async def _execute_query(
        self,
        query: str,
        variables: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query against the Linear API.

        Args:
            query: GraphQL query string.
            variables: Optional query variables.

        Returns:
            Query response data.

        Raises:
            RuntimeError: If the query fails.
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = await self._client.post(self.API_URL, json=payload)
        response.raise_for_status()

        result = response.json()
        if "errors" in result:
            raise RuntimeError(f"Linear API error: {result['errors']}")

        return result.get("data", {})

    async def _ensure_team_id(self) -> str:
        """Get or fetch the team ID."""
        if self._team_id:
            return self._team_id

        query = """
        query {
            viewer {
                id
                organization {
                    teams(first: 1) {
                        nodes {
                            id
                            name
                        }
                    }
                }
            }
        }
        """
        data = await self._execute_query(query)
        teams = data.get("viewer", {}).get("organization", {}).get("teams", {}).get("nodes", [])

        if not teams:
            raise RuntimeError("No teams found in Linear organization")

        self._team_id = teams[0]["id"]
        return self._team_id

    async def _get_status_ids(self) -> dict[str, str]:
        """Get workflow state IDs for the team."""
        if self._status_ids:
            return self._status_ids

        team_id = await self._ensure_team_id()

        query = """
        query($teamId: String!) {
            workflowStates(filter: { team: { id: { eq: $teamId } } }) {
                nodes {
                    id
                    name
                    type
                }
            }
        }
        """
        data = await self._execute_query(query, {"teamId": team_id})
        states = data.get("workflowStates", {}).get("nodes", [])

        for state in states:
            self._status_ids[state["name"]] = state["id"]

        return self._status_ids

    async def _get_status_id(self, status: WorkItemStatus) -> Optional[str]:
        """Get Linear workflow state ID for a status."""
        status_ids = await self._get_status_ids()
        linear_status = STATUS_TO_LINEAR.get(status, "Todo")
        return status_ids.get(linear_status)

    def _parse_issue(self, issue: dict[str, Any]) -> WorkItem:
        """Parse a Linear issue into a WorkItem."""
        # Map Linear status to WorkItemStatus
        linear_status = issue.get("state", {}).get("name", "Todo")
        status = LINEAR_STATUS_MAP.get(linear_status, WorkItemStatus.TODO)

        # Parse priority (Linear: 0=none, 1=urgent, 2=high, 3=normal, 4=low)
        priority = issue.get("priority", 0)
        if priority == 0:
            priority = WorkItemPriority.MEDIUM

        # Parse dates
        created_at = None
        if issue.get("createdAt"):
            try:
                created_at = datetime.fromisoformat(issue["createdAt"].replace("Z", "+00:00"))
            except ValueError:
                pass

        updated_at = None
        if issue.get("updatedAt"):
            try:
                updated_at = datetime.fromisoformat(issue["updatedAt"].replace("Z", "+00:00"))
            except ValueError:
                pass

        completed_at = None
        if issue.get("completedAt"):
            try:
                completed_at = datetime.fromisoformat(issue["completedAt"].replace("Z", "+00:00"))
            except ValueError:
                pass

        # Extract labels
        labels = [
            label.get("name", "")
            for label in issue.get("labels", {}).get("nodes", [])
        ]

        return WorkItem(
            id=issue["id"],
            project_id=self._project_uuid or "",
            title=issue.get("title", ""),
            description=issue.get("description"),
            status=status,
            priority=priority,
            phase=None,  # Linear doesn't have a direct phase concept
            parent_id=issue.get("parent", {}).get("id") if issue.get("parent") else None,
            dependencies=[],
            labels=labels,
            metadata={
                "identifier": issue.get("identifier"),
                "url": issue.get("url"),
            },
            external_id=issue["id"],
            created_at=created_at,
            updated_at=updated_at,
            completed_at=completed_at,
        )

    async def initialize(self, project_dir: Path) -> Project:
        """Initialize the backend for a project."""
        team_id = await self._ensure_team_id()
        project_name = project_dir.name

        # Check if project already exists
        query = """
        query($name: String!) {
            projects(filter: { name: { eq: $name } }, first: 1) {
                nodes {
                    id
                    name
                    description
                    createdAt
                    updatedAt
                }
            }
        }
        """
        data = await self._execute_query(query, {"name": project_name})
        projects = data.get("projects", {}).get("nodes", [])

        if projects:
            # Use existing project
            linear_project = projects[0]
            self._project_id = linear_project["id"]
        else:
            # Create new project
            mutation = """
            mutation($name: String!, $teamIds: [String!]!) {
                projectCreate(input: { name: $name, teamIds: $teamIds }) {
                    success
                    project {
                        id
                        name
                        description
                        createdAt
                        updatedAt
                    }
                }
            }
            """
            data = await self._execute_query(mutation, {
                "name": project_name,
                "teamIds": [team_id],
            })
            linear_project = data.get("projectCreate", {}).get("project", {})
            self._project_id = linear_project["id"]

        # Generate a local UUID for this project
        self._project_uuid = str(uuid.uuid4())

        return Project(
            id=self._project_uuid,
            name=linear_project.get("name", project_name),
            description=linear_project.get("description"),
            directory=str(project_dir),
            metadata={
                "linear_project_id": self._project_id,
                "linear_team_id": team_id,
            },
            created_at=datetime.fromisoformat(linear_project["createdAt"].replace("Z", "+00:00"))
            if linear_project.get("createdAt")
            else None,
            updated_at=datetime.fromisoformat(linear_project["updatedAt"].replace("Z", "+00:00"))
            if linear_project.get("updatedAt")
            else None,
        )

    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID."""
        if project_id != self._project_uuid:
            return None

        if not self._project_id:
            return None

        query = """
        query($id: String!) {
            project(id: $id) {
                id
                name
                description
                createdAt
                updatedAt
            }
        }
        """
        data = await self._execute_query(query, {"id": self._project_id})
        linear_project = data.get("project")

        if not linear_project:
            return None

        return Project(
            id=self._project_uuid,
            name=linear_project.get("name", ""),
            description=linear_project.get("description"),
            metadata={
                "linear_project_id": self._project_id,
            },
        )

    async def create_work_item(
        self,
        project_id: str,
        item: WorkItemCreate,
    ) -> WorkItem:
        """Create a new work item (Linear issue)."""
        team_id = await self._ensure_team_id()

        mutation = """
        mutation($teamId: String!, $title: String!, $description: String, $priority: Int, $projectId: String) {
            issueCreate(input: {
                teamId: $teamId
                title: $title
                description: $description
                priority: $priority
                projectId: $projectId
            }) {
                success
                issue {
                    id
                    identifier
                    title
                    description
                    priority
                    url
                    state {
                        id
                        name
                    }
                    labels {
                        nodes {
                            id
                            name
                        }
                    }
                    createdAt
                    updatedAt
                }
            }
        }
        """
        data = await self._execute_query(mutation, {
            "teamId": team_id,
            "title": item.title,
            "description": item.description,
            "priority": item.priority,
            "projectId": self._project_id,
        })

        issue = data.get("issueCreate", {}).get("issue", {})
        return self._parse_issue(issue)

    async def create_work_items_batch(
        self,
        project_id: str,
        items: list[WorkItemCreate],
    ) -> list[WorkItem]:
        """Create multiple work items in a batch."""
        # Linear doesn't have a batch create API, so we create sequentially
        # Could be optimized with concurrent requests
        results: list[WorkItem] = []
        for item in items:
            work_item = await self.create_work_item(project_id, item)
            results.append(work_item)
        return results

    async def get_work_item(self, item_id: str) -> Optional[WorkItem]:
        """Get a work item by ID."""
        query = """
        query($id: String!) {
            issue(id: $id) {
                id
                identifier
                title
                description
                priority
                url
                state {
                    id
                    name
                }
                parent {
                    id
                }
                labels {
                    nodes {
                        id
                        name
                    }
                }
                createdAt
                updatedAt
                completedAt
            }
        }
        """
        data = await self._execute_query(query, {"id": item_id})
        issue = data.get("issue")

        if not issue:
            return None

        return self._parse_issue(issue)

    async def update_work_item(
        self,
        item_id: str,
        updates: WorkItemUpdate,
    ) -> Optional[WorkItem]:
        """Update a work item."""
        input_data: dict[str, Any] = {}

        if updates.title is not None:
            input_data["title"] = updates.title

        if updates.description is not None:
            input_data["description"] = updates.description

        if updates.priority is not None:
            input_data["priority"] = updates.priority

        if updates.status is not None:
            status_id = await self._get_status_id(updates.status)
            if status_id:
                input_data["stateId"] = status_id

        if not input_data:
            return await self.get_work_item(item_id)

        mutation = """
        mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    description
                    priority
                    url
                    state {
                        id
                        name
                    }
                    parent {
                        id
                    }
                    labels {
                        nodes {
                            id
                            name
                        }
                    }
                    createdAt
                    updatedAt
                    completedAt
                }
            }
        }
        """
        data = await self._execute_query(mutation, {
            "id": item_id,
            "input": input_data,
        })

        issue = data.get("issueUpdate", {}).get("issue")
        if not issue:
            return None

        return self._parse_issue(issue)

    async def get_next_work_item(
        self,
        project_id: str,
        phase: Optional[str] = None,
    ) -> Optional[WorkItem]:
        """Get the next work item to work on."""
        if not self._project_id:
            return None

        # Query for highest priority Todo issue
        query = """
        query($projectId: String!) {
            issues(
                filter: {
                    project: { id: { eq: $projectId } }
                    state: { type: { eq: "unstarted" } }
                }
                orderBy: priority
                first: 1
            ) {
                nodes {
                    id
                    identifier
                    title
                    description
                    priority
                    url
                    state {
                        id
                        name
                    }
                    parent {
                        id
                    }
                    labels {
                        nodes {
                            id
                            name
                        }
                    }
                    createdAt
                    updatedAt
                }
            }
        }
        """
        data = await self._execute_query(query, {"projectId": self._project_id})
        issues = data.get("issues", {}).get("nodes", [])

        if not issues:
            return None

        return self._parse_issue(issues[0])

    async def list_work_items(
        self,
        project_id: str,
        status: Optional[WorkItemStatus] = None,
        phase: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[WorkItem]:
        """List work items for a project."""
        if not self._project_id:
            return []

        # Build filter
        filter_parts = [f'project: {{ id: {{ eq: "{self._project_id}" }} }}']

        if status:
            linear_status = STATUS_TO_LINEAR.get(status, "Todo")
            filter_parts.append(f'state: {{ name: {{ eq: "{linear_status}" }} }}')

        filter_str = "{ " + ", ".join(filter_parts) + " }"

        query = f"""
        query {{
            issues(
                filter: {filter_str}
                orderBy: priority
                first: {limit}
            ) {{
                nodes {{
                    id
                    identifier
                    title
                    description
                    priority
                    url
                    state {{
                        id
                        name
                    }}
                    parent {{
                        id
                    }}
                    labels {{
                        nodes {{
                            id
                            name
                        }}
                    }}
                    createdAt
                    updatedAt
                    completedAt
                }}
            }}
        }}
        """
        data = await self._execute_query(query)
        issues = data.get("issues", {}).get("nodes", [])

        return [self._parse_issue(issue) for issue in issues]

    async def get_progress_summary(
        self,
        project_id: str,
    ) -> ProgressSummary:
        """Get progress summary for a project."""
        if not self._project_id:
            return ProgressSummary()

        query = """
        query($projectId: String!) {
            issues(filter: { project: { id: { eq: $projectId } } }) {
                nodes {
                    state {
                        name
                        type
                    }
                }
            }
        }
        """
        data = await self._execute_query(query, {"projectId": self._project_id})
        issues = data.get("issues", {}).get("nodes", [])

        counts = {
            "todo": 0,
            "in_progress": 0,
            "done": 0,
            "blocked": 0,
        }

        for issue in issues:
            state_type = issue.get("state", {}).get("type", "")
            state_name = issue.get("state", {}).get("name", "")

            if state_type == "completed":
                counts["done"] += 1
            elif state_type == "started":
                counts["in_progress"] += 1
            elif state_name == "Blocked":
                counts["blocked"] += 1
            else:
                counts["todo"] += 1

        return ProgressSummary(**counts)

    async def add_comment(
        self,
        item_id: str,
        content: str,
    ) -> None:
        """Add a comment to a work item."""
        mutation = """
        mutation($issueId: String!, $body: String!) {
            commentCreate(input: { issueId: $issueId, body: $body }) {
                success
            }
        }
        """
        await self._execute_query(mutation, {
            "issueId": item_id,
            "body": content,
        })

    async def claim_work_item(
        self,
        item_id: str,
    ) -> Optional[WorkItem]:
        """Claim a work item by setting it to IN_PROGRESS."""
        return await self.update_work_item(
            item_id,
            WorkItemUpdate(status=WorkItemStatus.IN_PROGRESS),
        )

    async def complete_work_item(
        self,
        item_id: str,
        summary: Optional[str] = None,
    ) -> Optional[WorkItem]:
        """Mark a work item as DONE."""
        if summary:
            await self.add_comment(item_id, f"Completed: {summary}")

        return await self.update_work_item(
            item_id,
            WorkItemUpdate(status=WorkItemStatus.DONE),
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
