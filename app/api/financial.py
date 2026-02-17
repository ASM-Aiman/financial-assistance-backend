from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.financial import FinancialInput, ProcessedResult, FinancialRecordResponse
from app.services.financial_service import financial_service

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])


@router.post("/process", response_model=ProcessedResult)
async def process_financial_input(
    input_data: FinancialInput,
    db: Session = Depends(get_db)
):
    """
    Process any financial input:
    - Commitments (future expenses)
    - Balance updates
    - Questions
    """
    try:
        result = await financial_service.process_input(
            db=db,
            user_id=input_data.user_id,
            text=input_data.text
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}"
        )


@router.get("/summary/{user_id}")
async def get_user_summary(user_id: str, db: Session = Depends(get_db)):
    """Get financial summary for a user."""
    try:
        summary = financial_service.get_user_summary(db, user_id)
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summary: {str(e)}"
        )


@router.get("/history/{user_id}", response_model=List[FinancialRecordResponse])
async def get_user_history(user_id: str, limit: int = 50, db: Session = Depends(get_db)):
    """Get user's financial history."""
    from app.models.financial import FinancialRecord
    
    records = db.query(FinancialRecord).filter(
        FinancialRecord.user_id == user_id
    ).order_by(FinancialRecord.created_at.desc()).limit(limit).all()
    
    return records