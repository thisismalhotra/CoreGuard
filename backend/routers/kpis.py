"""
KPI & Settings REST endpoints.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Inventory, PurchaseOrder, AgentLog
from schemas import KPIsResponse, LogDelayResponse, GlassBoxLog

router = APIRouter(prefix="/api", tags=["kpis"])


def get_log_delay(request: Request) -> float:
    """Return the current log delay from app.state (thread-safe)."""
    return getattr(request.app.state, "log_delay_seconds", 2.0)


@router.get("/kpis", response_model=KPIsResponse)
def get_kpis(db: Session = Depends(get_db)) -> dict:
    """Dashboard KPIs for the Network Status tab."""
    total_inventory = db.query(Inventory).all()
    total_on_hand = sum(i.on_hand for i in total_inventory)
    total_safety = sum(i.safety_stock for i in total_inventory)

    orders = db.query(PurchaseOrder).all()
    auto_approved = sum(1 for o in orders if o.status.value == "APPROVED")
    total_orders = len(orders)

    # Count distinct agents that have logged activity
    active_agents = db.query(AgentLog.agent).distinct().count()

    return {
        "inventory_health": round(total_on_hand / total_safety, 2) if total_safety > 0 else 0,
        "total_on_hand": total_on_hand,
        "total_safety_stock": total_safety,
        "active_threads": active_agents,
        "automation_rate": round(auto_approved / total_orders * 100, 1) if total_orders > 0 else 100.0,
        "total_orders": total_orders,
    }


@router.get("/logs", response_model=list[GlassBoxLog])
def get_logs(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    """Return recent agent logs (persisted Glass Box entries)."""
    logs = db.query(AgentLog).order_by(AgentLog.id.desc()).limit(limit).all()
    return [
        {
            "timestamp": log.timestamp.isoformat() if log.timestamp else "",
            "agent": log.agent,
            "message": log.message,
            "type": log.log_type,
        }
        for log in reversed(logs)  # Oldest first for display
    ]


@router.get("/settings/log-delay", response_model=LogDelayResponse)
def get_log_delay_setting(request: Request) -> dict:
    """Return the current log delay setting."""
    return {"delay": getattr(request.app.state, "log_delay_seconds", 2.0)}


@router.post("/settings/log-delay", response_model=LogDelayResponse)
def set_log_delay_setting(request: Request, delay: float = 2.0) -> dict:
    """Update the delay (in seconds) between each log line during simulations."""
    # Clamp to reasonable range and store on app.state (thread-safe for single worker)
    request.app.state.log_delay_seconds = max(0.5, min(delay, 5.0))
    return {"delay": request.app.state.log_delay_seconds}
