import json
import re
from typing import Dict, Any
import google.generativeai as genai
from app.config import settings
from app.schemas.financial import InputType, ClassifiedInput, CommitmentData, BalanceData, QuestionData

genai.configure(api_key=settings.GEMINI_API_KEY)


class GeminiService:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-pro')
    
    async def classify_and_extract(self, text: str) -> ClassifiedInput:
        """Classify intent and extract structured data from user input."""
        
        prompt = f"""
        Analyze this financial input and classify it into one of three types:
        1. FINANCIAL_COMMITMENT - Future spending plans (e.g., "dinner Saturday 2500")
        2. BALANCE_UPDATE - Current balance reporting (e.g., "balance is 18000")
        3. QUESTION - Financial questions (e.g., "can I afford 5000 gadget?")
        
        Input: "{text}"
        
        Respond ONLY with valid JSON in this exact format:
        {{
            "input_type": "FINANCIAL_COMMITMENT" | "BALANCE_UPDATE" | "QUESTION",
            "confidence": 0.0-1.0,
            "extracted_data": {{
                // For FINANCIAL_COMMITMENT:
                "description": "what the expense is for",
                "amount": numeric_amount,
                "date": "ISO date string or null",
                
                // For BALANCE_UPDATE:
                "balance": numeric_balance,
                
                // For QUESTION:
                "question": "full question text",
                "target_amount": numeric_amount_if_mentioned or null
            }}
        }}
        
        Rules:
        - Amounts should be numeric (remove currency symbols)
        - Dates: parse relative dates (today, tomorrow, this Saturday) to ISO format
        - If uncertain, use the most likely type with lower confidence
        """
        
        try:
            response = await self.model.generate_content_async(prompt)
            result_text = response.text
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(result_text)
            
            return ClassifiedInput(**result)
            
        except Exception as e:
            # Fallback classification based on keywords
            return self._fallback_classification(text)
    
    def _fallback_classification(self, text: str) -> ClassifiedInput:
        """Simple keyword-based fallback classification."""
        text_lower = text.lower()
        
        # Check for balance keywords
        if any(word in text_lower for word in ["balance", "have", "now", "current"]):
            amount = self._extract_amount(text)
            return ClassifiedInput(
                input_type=InputType.BALANCE_UPDATE,
                confidence=0.7,
                extracted_data={"balance": amount if amount else 0}
            )
        
        # Check for question keywords
        if any(word in text_lower for word in ["can i", "should i", "afford", "?", "how much"]):
            amount = self._extract_amount(text)
            return ClassifiedInput(
                input_type=InputType.QUESTION,
                confidence=0.7,
                extracted_data={
                    "question": text,
                    "target_amount": amount
                }
            )
        
        # Default to commitment
        amount = self._extract_amount(text)
        return ClassifiedInput(
            input_type=InputType.FINANCIAL_COMMITMENT,
            confidence=0.6,
            extracted_data={
                "description": text,
                "amount": amount if amount else 0,
                "date": None
            }
        )
    
    def _extract_amount(self, text: str) -> float:
        """Extract numeric amount from text."""
        numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', text.replace(',', ''))
        if numbers:
            return float(numbers[-1])  # Usually the last number is the amount
        return 0.0
    
    async def generate_advice(
        self,
        question: str,
        current_balance: float,
        upcoming_commitments: list,
        target_amount: Optional[float] = None
    ) -> str:
        """Generate personalized financial advice."""
        
        total_commitments = sum(c.get('amount', 0) for c in upcoming_commitments)
        available_funds = current_balance - total_commitments
        
        commitments_text = "\n".join([
            f"- {c.get('description', 'Unknown')}: ${c.get('amount', 0):.2f}"
            for c in upcoming_commitments[:5]  # Top 5 recent
        ]) if upcoming_commitments else "No upcoming commitments"
        
        prompt = f"""
        As a financial advisor, answer this question: "{question}"
        
        User's Financial Context:
        - Current Balance: ${current_balance:.2f}
        - Upcoming Commitments: ${total_commitments:.2f}
        - Available Funds (after commitments): ${available_funds:.2f}
        {f"- Target Purchase Amount: ${target_amount:.2f}" if target_amount else ""}
        
        Upcoming Commitments:
        {commitments_text}
        
        Provide:
        1. Direct answer to the question
        2. Brief reasoning based on their financial situation
        3. Practical recommendation
        4. If suggesting to wait, explain why
        
        Keep response concise (2-3 sentences) but helpful and personalized.
        """
        
        try:
            response = await self.model.generate_content_async(prompt)
            return response.text.strip()
        except Exception as e:
            # Fallback advice
            if target_amount and target_amount > available_funds:
                return f"Based on your balance of ${current_balance:.2f} and upcoming commitments of ${total_commitments:.2f}, you have ${available_funds:.2f} available. The ${target_amount:.2f} purchase exceeds your available funds. Consider waiting until after your commitments are fulfilled."
            else:
                return f"You have ${available_funds:.2f} available after upcoming commitments. This purchase appears affordable, but ensure you maintain an emergency buffer."


gemini_service = GeminiService()