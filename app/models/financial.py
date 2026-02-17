from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Text
from sqlalchemy.sql import func
from app.database import Base
import enum


class InputType(str, enum.Enum):
    FINANCIAL_COMMITMENT = "FINANCIAL_COMMITMENT"
    BALANCE_UPDATE = "BALANCE_UPDATE"
    QUESTION = "QUESTION"


class FinancialRecord(Base):
    __tablename__ = "financial_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    input_type = Column(Enum(InputType), nullable=False)
    
    # For commitments
    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=True)
    commitment_date = Column(DateTime, nullable=True)
    
    # For balance updates
    balance = Column(Float, nullable=True)
    
    # For questions
    question_text = Column(Text, nullable=True)
    
    # Metadata
    raw_input = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Vector ID for commitments (stored in Pinecone)
    vector_id = Column(String, nullable=True, index=True)


class UserBalance(Base):
    __tablename__ = "user_balances"

    user_id = Column(String, primary_key=True, index=True)
    current_balance = Column(Float, default=0.0)
    last_updated = Column(DateTime(timezone=True), server_default=func.now())