"""
Shared utilities for Core-Guard agents.

DRY: Extracts the common _log() helper that was duplicated across all 5 agent files.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database.models import AgentLog


def create_agent_log(
    db: Session,
    agent_name: str,
    message: str,
    log_type: str = "info",
) -> dict[str, str]:
    """
    Persist a Glass Box log entry to the DB and return a dict
    suitable for Socket.io emission.

    This is the single source of truth for agent logging.
    All agents should use this instead of defining their own _log().
    """
    entry = AgentLog(agent=agent_name, message=message, log_type=log_type)
    db.add(entry)
    db.flush()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent_name,
        "message": message,
        "type": log_type,
    }
