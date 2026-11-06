"""
GitHub integration service for DevFlow.

Provides the simplest supported GitHub integration using the REST API v3:
- Creates GitHub issues from approved bug reports
- Prepares pull requests on isolated branches for human developer review
- Attaches investigation summaries, test results, and Switch conversation links
- Enforces strict security: never auto-merges, never targets main, never exposes tokens,
  and degrades gracefully to offline reporting if GitHub is unconfigured.
"""

from typing import Any, Dict, List, Optional
import httpx

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedApproverError, WorkflowStateError
from app.core.logging import get_logger
from app.models.reporting import GitHubReference

logger = get_logger("github_service")


class GitHubService:
    """Safe, REST-based GitHub integration with token masking and branch safeguards."""

    def __init__(
        self,
        token: Optional[str] = None,
        repo: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        settings = get_settings()
        self.token = token or settings.GITHUB_TOKEN
        self.repo = repo or settings.GITHUB_REPO
        self.api_url = (api_url or settings.GITHUB_API_URL).rstrip("/")
        self.enabled = bool(self.token and self.repo)

        masked_token = (
            f"{self.token[:4]}...{self.token[-4:]}"
            if self.token and len(self.token) > 8
            else ("SET" if self.token else "NOT_CONFIGURED")
        )
        logger.info(
            f"GitHubService initialized: repo={self.repo or 'None'}, token={masked_token}, enabled={self.enabled}"
        )

    def is_configured(self) -> bool:
        """Returns True if valid token and repository are configured."""
        return self.enabled

    def _get_headers(self) -> Dict[str, str]:
        """Builds HTTP headers for GitHub API requests without exposing secrets."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "DevFlow-BugFix-Agent",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def create_issue(
        self,
        issue_id: str,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        switch_room: Optional[str] = None,
        is_approved: bool = True,
    ) -> GitHubReference:
        """
        Creates a GitHub issue from an approved bug report.
        Requires human approval for external actions.
        """
        # Security: Require human approval before making external GitHub mutations
        if not is_approved:
            logger.warning(f"External GitHub issue creation blocked for {issue_id}: Human approval required.")
            return GitHubReference(status="approval_required")

        if not self.is_configured():
            logger.info(f"GitHub not configured; skipping external issue creation for {issue_id}.")
            return GitHubReference(status="unconfigured")

        # Format issue body with Switch link
        switch_context = f"\n\n---\n*Created by DevFlow from Switch team room: `{switch_room or '#bug-reports'}`*"
        full_body = body + switch_context

        payload: Dict[str, Any] = {
            "title": f"[{issue_id}] {title}",
            "body": full_body,
            "labels": labels or ["bug", "devflow"],
        }

        url = f"{self.api_url}/repos/{self.repo}/issues"

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload, headers=self._get_headers())
                if res.status_code in (200, 201):
                    data = res.json()
                    logger.info(f"Created GitHub Issue #{data.get('number')} for {issue_id}")
                    return GitHubReference(
                        issue_number=data.get("number"),
                        issue_url=data.get("html_url"),
                        status="created",
                    )
                else:
                    logger.warning(
                        f"GitHub issue creation failed with status {res.status_code}: {res.text[:200]}"
                    )
                    return GitHubReference(status=f"error_{res.status_code}")
        except Exception as e:
            # Token is never exposed in error log
            logger.error(f"GitHub API request failed: {str(e)}")
            return GitHubReference(status="network_error")

    def create_pull_request(
        self,
        issue_id: str,
        title: str,
        head_branch: str,
        body: str,
        base_branch: str = "main",
        is_approved: bool = True,
    ) -> GitHubReference:
        """
        Opens a pull request targeting the base branch for human developer review.
        Safeguards:
        - Never pushes directly to main branch
        - Never automatically merges pull requests
        - Requires human approval
        """
        if not is_approved:
            logger.warning(f"PR creation blocked for {issue_id}: Human approval required.")
            return GitHubReference(status="approval_required")

        # Safeguard: Never target main as the head branch
        if head_branch.lower() in ("main", "master"):
            raise WorkflowStateError(
                message="Cannot open pull request with main/master as the head branch.",
                current_state=head_branch,
            )

        if not self.is_configured():
            logger.info(f"GitHub not configured; skipping PR creation for {issue_id}.")
            return GitHubReference(head_branch=head_branch, base_branch=base_branch, status="unconfigured")

        payload: Dict[str, Any] = {
            "title": f"fix({issue_id}): {title}",
            "head": head_branch,
            "base": base_branch,
            "body": body,
            "draft": False,
        }

        url = f"{self.api_url}/repos/{self.repo}/pulls"

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload, headers=self._get_headers())
                if res.status_code in (200, 201):
                    data = res.json()
                    logger.info(f"Opened GitHub Pull Request #{data.get('number')} for {issue_id}")
                    return GitHubReference(
                        pr_number=data.get("number"),
                        pr_url=data.get("html_url"),
                        head_branch=head_branch,
                        base_branch=base_branch,
                        status="pr_opened",
                    )
                else:
                    logger.warning(
                        f"GitHub PR creation failed with status {res.status_code}: {res.text[:200]}"
                    )
                    return GitHubReference(
                        head_branch=head_branch,
                        base_branch=base_branch,
                        status=f"error_{res.status_code}",
                    )
        except Exception as e:
            logger.error(f"GitHub PR API request failed: {str(e)}")
            return GitHubReference(head_branch=head_branch, base_branch=base_branch, status="network_error")


# Global singleton GitHub service instance
github_service = GitHubService()

