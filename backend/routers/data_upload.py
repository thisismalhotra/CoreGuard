"""
CSV Upload endpoints for demand forecast data.
"""

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session

from auth import require_role
from database.connection import get_db
from database.models import DemandForecast, Part, User
from rate_limit import limiter

router = APIRouter(prefix="/api/upload", tags=["upload"])

REQUIRED_COLUMNS = {"part_id", "forecast_qty"}
OPTIONAL_COLUMNS = {"period", "source", "confidence_level", "notes"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB


@router.post("/demand-forecast")
@limiter.limit("10/minute")
async def upload_demand_forecast(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator", "approver", "admin")),
) -> dict:
    """
    Upload a CSV file to create/update demand forecast entries.

    Required columns: part_id, forecast_qty
    Optional columns: period, source, confidence_level, notes

    Upserts by (part_id, period) — updates existing rows, creates new ones.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 2 MB)")

    try:
        text = contents.decode("utf-8-sig")  # Handle BOM from Excel
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV file is empty or has no headers")

    # Normalize column names (strip whitespace, lowercase)
    columns = {col.strip().lower() for col in reader.fieldnames}
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(sorted(missing))}. "
                   f"Required: {', '.join(sorted(REQUIRED_COLUMNS))}",
        )

    # Cache part lookups
    part_cache: dict[str, int] = {}

    created = 0
    updated = 0
    errors: list[dict] = []
    now = datetime.now(timezone.utc)
    default_period = f"{now.year}-Q{(now.month - 1) // 3 + 1}"

    for row_num, row in enumerate(reader, start=2):  # Row 1 is header
        # Normalize keys
        row = {k.strip().lower(): v.strip() if v else "" for k, v in row.items()}

        part_id_str = row.get("part_id", "").strip()
        forecast_qty_str = row.get("forecast_qty", "").strip()

        if not part_id_str:
            errors.append({"row": row_num, "error": "Missing part_id"})
            continue

        if not forecast_qty_str:
            errors.append({"row": row_num, "part_id": part_id_str, "error": "Missing forecast_qty"})
            continue

        try:
            forecast_qty = int(forecast_qty_str)
            if forecast_qty < 0:
                raise ValueError("negative")
        except ValueError:
            errors.append({"row": row_num, "part_id": part_id_str, "error": f"Invalid forecast_qty: '{forecast_qty_str}'"})
            continue

        # Look up part
        if part_id_str not in part_cache:
            part = db.query(Part).filter(Part.part_id == part_id_str).first()
            if part:
                part_cache[part_id_str] = part.id
            else:
                errors.append({"row": row_num, "part_id": part_id_str, "error": f"Part '{part_id_str}' not found in database"})
                continue

        db_part_id = part_cache[part_id_str]
        period = row.get("period", "").strip() or default_period
        source = row.get("source", "").strip() or "MANUAL_OVERRIDE"
        confidence = row.get("confidence_level", "").strip() or "MEDIUM"
        notes = row.get("notes", "").strip()

        # Validate confidence_level
        if confidence.upper() not in ("HIGH", "MEDIUM", "LOW"):
            confidence = "MEDIUM"
        else:
            confidence = confidence.upper()

        # Upsert: check if (part_id, period) exists
        existing = (
            db.query(DemandForecast)
            .filter(DemandForecast.part_id == db_part_id, DemandForecast.period == period)
            .first()
        )

        if existing:
            existing.forecast_qty = forecast_qty
            existing.source = source
            existing.confidence_level = confidence
            existing.notes = notes or existing.notes
            existing.updated_at = now
            updated += 1
        else:
            entry = DemandForecast(
                part_id=db_part_id,
                forecast_qty=forecast_qty,
                period=period,
                source=source,
                confidence_level=confidence,
                notes=notes,
                updated_at=now,
            )
            db.add(entry)
            created += 1

    db.commit()

    return {
        "created": created,
        "updated": updated,
        "total_processed": created + updated,
        "errors": errors,
        "error_count": len(errors),
    }
