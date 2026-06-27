"""
AGRIOS — Farm Data Export Endpoints
GET /farms/{farm_id}/export/pdf    → branded PDF report
GET /farms/{farm_id}/export/excel  → multi-sheet Excel workbook
GET /farms/{farm_id}/export/csv    → flat CSV of daily logs
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, FarmAccess
from app.services.export_service import export_csv, export_excel, export_pdf

router = APIRouter(prefix="/farms", tags=["exports"])

# ── helpers ───────────────────────────────────────────────────────────────────


def _safe_filename(text: str) -> str:
    """Strip characters that break Content-Disposition filenames."""
    return "".join(c if c.isalnum() or c in "-_ " else "_" for c in text).strip()


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M")


# ── endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/{farm_id}/export/pdf",
    summary="Download farm data as PDF",
    response_description="Branded PDF report of all farm data",
    dependencies=[Depends(require_permission(Permission.FINANCE_VIEW))],
)
async def download_farm_pdf(
    farm_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
    _farm: FarmAccess,
):
    """
    Generate and download a branded AGRIOS PDF report for this farm.

    Includes: farm overview, all flocks, last 100 daily logs,
    vaccination records, expenses, revenue, and a P&L summary.

    **Required permission:** `finance:view`
    """
    try:
        pdf_bytes = await export_pdf(db, farm_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {exc}",
        )

    filename = f"AGRIOS_Report_{_timestamp()}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{farm_id}/export/excel",
    summary="Download farm data as Excel workbook",
    response_description="Multi-sheet Excel workbook (.xlsx)",
    dependencies=[Depends(require_permission(Permission.FINANCE_VIEW))],
)
async def download_farm_excel(
    farm_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
    _farm: FarmAccess,
):
    """
    Generate and download an Excel workbook with one sheet per data type:
    Farm Overview, Flocks, Daily Logs, Vaccinations, Expenses, Revenue,
    and P&L Snapshots.

    **Required permission:** `finance:view`
    """
    try:
        xlsx_bytes = await export_excel(db, farm_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Excel generation failed: {exc}",
        )

    filename = f"AGRIOS_Data_{_timestamp()}.xlsx"
    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{farm_id}/export/csv",
    summary="Download farm daily logs as CSV",
    response_description="Flat CSV file of all daily logs",
    dependencies=[Depends(require_permission(Permission.FINANCE_VIEW))],
)
async def download_farm_csv(
    farm_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
    _farm: FarmAccess,
):
    """
    Generate and download a flat CSV of all daily log entries for this farm.
    Includes a UTF-8 BOM so Excel opens it correctly without import wizard.

    **Required permission:** `finance:view`
    """
    try:
        csv_bytes = await export_csv(db, farm_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CSV generation failed: {exc}",
        )

    filename = f"AGRIOS_Logs_{_timestamp()}.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
