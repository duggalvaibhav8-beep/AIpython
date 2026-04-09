"""
AI Models for SmartBookingAI
Pydantic models for AI prediction services
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any

class PredictionRequest(BaseModel):
    event_id: int
    start_time: str 
    max_capacity: int
    duration_minutes: int = 60

class PredictionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class TrainingResponse(BaseModel):
    success: bool
    message: str
    results: Optional[Dict[str, Any]] = None

class DataGenerationRequest(BaseModel):
    days_back: int = 180
    base_probability: float = 0.35

class TimeSlotWithPrediction(BaseModel):
    id: int
    event_id: int
    start_time: str
    end_time: str
    max_capacity: int
    available_slots: int
    is_available: bool
    event_title: Optional[str] = None
    demand_prediction: Dict[str, Any]  