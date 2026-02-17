from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


class InputType(str, Enum):
    FINANCIAL_COMMITMENT = "FINANCIAL_COMMITMENT"
    BALANCE_UPDATE = "BALANCE_UPDATE"
    QUESTION = "QUESTION"


class FinancialInput(BaseModel):
    user_id: str
    text: str = Field(..., min_length=1, max_length=1000)


class ClassifiedInput(BaseModel):
    input_type: InputType
    confidence: float
    extracted_data: dict


class CommitmentData(BaseModel):
    description: str
    amount: float = Field(..., gt=0)
    date: Optional[datetime] = None


class BalanceData(BaseModel):
    balance: float = Field(..., ge=0)


class QuestionData(BaseModel):
    question: str
    target_amount: Optional[float] = None


class ProcessedResult(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
    advice: Optional[str] = None


class FinancialRecordResponse(BaseModel):
    id: int
    input_type: InputType
    description: Optional[str]
    amount: Optional[float]
    balance: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True