from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.models.financial import FinancialRecord, UserBalance, InputType
from app.schemas.financial import (
    ClassifiedInput, 
    CommitmentData, 
    BalanceData, 
    QuestionData,
    ProcessedResult
)
from app.services.gemini_service import gemini_service
from app.services.pinecone_service import pinecone_service


class FinancialService:
    async def process_input(
        self,
        db: Session,
        user_id: str,
        text: str
    ) -> ProcessedResult:
        """Main entry point for processing financial input."""
        
        # Step 1: Classify and extract
        classification = await gemini_service.classify_and_extract(text)
        
        # Step 2: Route to appropriate handler
        if classification.input_type == InputType.FINANCIAL_COMMITMENT:
            return await self._handle_commitment(
                db, user_id, text, classification.extracted_data
            )
        
        elif classification.input_type == InputType.BALANCE_UPDATE:
            return await self._handle_balance_update(
                db, user_id, text, classification.extracted_data
            )
        
        elif classification.input_type == InputType.QUESTION:
            return await self._handle_question(
                db, user_id, text, classification.extracted_data
            )
        
        return ProcessedResult(
            success=False,
            message="Unable to classify input",
            data=None
        )
    
    async def _handle_commitment(
        self,
        db: Session,
        user_id: str,
        raw_input: str,
        data: dict
    ) -> ProcessedResult:
        """Handle FINANCIAL_COMMITMENT type."""
        
        commitment_data = CommitmentData(**data)
        
        # Create database record
        record = FinancialRecord(
            user_id=user_id,
            input_type=InputType.FINANCIAL_COMMITMENT,
            description=commitment_data.description,
            amount=commitment_data.amount,
            commitment_date=commitment_data.date,
            raw_input=raw_input
        )
        
        db.add(record)
        db.commit()
        db.refresh(record)
        
        # Store in Pinecone for vector search
        try:
            vector_id = await pinecone_service.store_commitment(
                user_id=user_id,
                commitment_id=str(record.id),
                description=commitment_data.description,
                amount=commitment_data.amount,
                date=commitment_data.date.isoformat() if commitment_data.date else None
            )
            
            # Update record with vector ID
            record.vector_id = vector_id
            db.commit()
            
        except Exception as e:
            # Log error but don't fail the operation
            print(f"Pinecone storage failed: {e}")
        
        return ProcessedResult(
            success=True,
            message=f"Added commitment: {commitment_data.description} (${commitment_data.amount:.2f})",
            data={
                "id": record.id,
                "description": commitment_data.description,
                "amount": commitment_data.amount,
                "date": commitment_data.date.isoformat() if commitment_data.date else None
            }
        )
    
    async def _handle_balance_update(
        self,
        db: Session,
        user_id: str,
        raw_input: str,
        data: dict
    ) -> ProcessedResult:
        """Handle BALANCE_UPDATE type."""
        
        balance_data = BalanceData(**data)
        
        # Create record
        record = FinancialRecord(
            user_id=user_id,
            input_type=InputType.BALANCE_UPDATE,
            balance=balance_data.balance,
            raw_input=raw_input
        )
        db.add(record)
        
        # Update or create user balance
        user_balance = db.query(UserBalance).filter(
            UserBalance.user_id == user_id
        ).first()
        
        if user_balance:
            user_balance.current_balance = balance_data.balance
            user_balance.last_updated = datetime.utcnow()
        else:
            user_balance = UserBalance(
                user_id=user_id,
                current_balance=balance_data.balance
            )
            db.add(user_balance)
        
        db.commit()
        db.refresh(record)
        
        return ProcessedResult(
            success=True,
            message=f"Balance updated to ${balance_data.balance:.2f}",
            data={
                "id": record.id,
                "balance": balance_data.balance
            }
        )
    
    async def _handle_question(
        self,
        db: Session,
        user_id: str,
        raw_input: str,
        data: dict
    ) -> ProcessedResult:
        """Handle QUESTION type."""
        
        question_data = QuestionData(**data)
        
        # Get current balance from SQL (source of truth)
        user_balance = db.query(UserBalance).filter(
            UserBalance.user_id == user_id
        ).first()
        
        current_balance = user_balance.current_balance if user_balance else 0.0
        
        # Get upcoming commitments from SQL (not vector DB for calculations)
        upcoming = db.query(FinancialRecord).filter(
            FinancialRecord.user_id == user_id,
            FinancialRecord.input_type == InputType.FINANCIAL_COMMITMENT,
            FinancialRecord.commitment_date >= datetime.utcnow()
        ).order_by(FinancialRecord.commitment_date).limit(10).all()
        
        upcoming_list = [
            {
                "description": u.description,
                "amount": u.amount,
                "date": u.commitment_date.isoformat() if u.commitment_date else None
            }
            for u in upcoming
        ]
        
        # Get relevant commitments from vector DB for context (not calculations)
        try:
            relevant_commitments = await pinecone_service.query_relevant_commitments(
                user_id=user_id,
                query=question_data.question,
                top_k=3
            )
        except Exception as e:
            relevant_commitments = []
            print(f"Vector search failed: {e}")
        
        # Generate advice using Gemini
        advice = await gemini_service.generate_advice(
            question=question_data.question,
            current_balance=current_balance,
            upcoming_commitments=upcoming_list,
            target_amount=question_data.target_amount
        )
        
        # Create record
        record = FinancialRecord(
            user_id=user_id,
            input_type=InputType.QUESTION,
            question_text=question_data.question,
            raw_input=raw_input
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        
        return ProcessedResult(
            success=True,
            message="Question answered",
            data={
                "id": record.id,
                "question": question_data.question,
                "current_balance": current_balance,
                "upcoming_commitments_count": len(upcoming_list),
                "relevant_commitments_from_vector_db": len(relevant_commitments)
            },
            advice=advice
        )
    
    def get_user_summary(self, db: Session, user_id: str) -> dict:
        """Get financial summary for user."""
        
        # Current balance
        user_balance = db.query(UserBalance).filter(
            UserBalance.user_id == user_id
        ).first()
        
        # Recent commitments
        commitments = db.query(FinancialRecord).filter(
            FinancialRecord.user_id == user_id,
            FinancialRecord.input_type == InputType.FINANCIAL_COMMITMENT
        ).order_by(FinancialRecord.created_at.desc()).limit(10).all()
        
        # Recent history
        history = db.query(FinancialRecord).filter(
            FinancialRecord.user_id == user_id
        ).order_by(FinancialRecord.created_at.desc()).limit(20).all()
        
        return {
            "current_balance": user_balance.current_balance if user_balance else 0.0,
            "total_commitments": sum(c.amount for c in commitments if c.amount),
            "commitments": [
                {
                    "description": c.description,
                    "amount": c.amount,
                    "date": c.commitment_date.isoformat() if c.commitment_date else None
                }
                for c in commitments
            ],
            "recent_history": [
                {
                    "type": h.input_type.value,
                    "raw_input": h.raw_input,
                    "created_at": h.created_at.isoformat()
                }
                for h in history
            ]
        }


financial_service = FinancialService()