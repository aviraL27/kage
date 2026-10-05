"""GitHub notifications read-only integration tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

from kage.config import settings
from kage.tools.registry import registry

logger = logging.getLogger(__name__)


class ListGitHubNotificationsArgs(BaseModel):
    all: bool = Field(
        False,
        description="If true, shows all notifications including already read ones. Defaults to false (unread only).",
    )
    max_results: int = Field(
        10,
        ge=1,
        le=50,
        description="Maximum number of notifications to retrieve (1-50).",
    )


@registry.register(
    name="list_github_notifications",
    description="Fetch unread GitHub notifications and mentions for repositories you participate in. Read-only.",
    args_schema=ListGitHubNotificationsArgs,
)
def list_github_notifications(all: bool = False, max_results: int = 10) -> Dict[str, Any]:
    token = settings.github_token
    if not token:
        return {"error": "GITHUB_TOKEN is not configured in environment or settings."}

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Kage-Agent",
    }
    params = {
        "all": str(all).lower(),
        "per_page": min(max_results, 50),
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get("https://api.github.com/notifications", headers=headers, params=params)
            if resp.status_code != 200:
                return {"error": f"GitHub API error ({resp.status_code}): {resp.text}"}

            raw_notifications = resp.json()
            notifications = []

            for item in raw_notifications[:max_results]:
                repo = item.get("repository", {}).get("full_name", "(unknown repo)")
                subject = item.get("subject", {})
                title = subject.get("title", "(no title)")[:200]
                item_type = subject.get("type", "Notification")
                reason = item.get("reason", "")
                updated_at = item.get("updated_at", "")

                notifications.append({
                    "id": item.get("id"),
                    "repository": repo,
                    "title": f"[UNTRUSTED GITHUB CONTENT]: {title}",
                    "type": item_type,
                    "reason": reason,
                    "updated_at": updated_at,
                })

            return {
                "count": len(notifications),
                "notifications": notifications,
            }

    except Exception as e:
        logger.error(f"Error fetching GitHub notifications: {e}", exc_info=True)
        return {"error": f"GitHub request failed: {str(e)}"}
