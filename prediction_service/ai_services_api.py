"""
AI Prediction Service API
FastAPI microservice for booking demand predictions
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import sqlite3
from contextlib import contextmanager
import os
import sys

# Import prediction models
from ai_prediction_models import BookingDemandPredictor

app = FastAPI(
    title="SmartBookingAI - Prediction Service",
    description="AI-powered booking demand prediction microservice",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global predictor instance
predictor = None
MODEL_TYPE = "random_forest"  # Default model

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, "booking.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

# Pydantic models
class TimeSlotInfo(BaseModel):
    event_id: int
    start_time: str
    max_capacity: int
    duration_minutes: Optional[int] = 60

class PredictionResponse(BaseModel):
    time_slot_id: Optional[int] = None
    probability: float
    demand_level: str
    is_recommended: bool
    timestamp: str

class BulkPredictionRequest(BaseModel):
    time_slots: List[Dict]

class TrainingRequest(BaseModel):
    model_type: Optional[str] = "random_forest"

class ModelInfo(BaseModel):
    model_type: str
    is_loaded: bool
    last_trained: Optional[str] = None

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize predictor on startup"""
    global predictor
    
    print("Starting AI Prediction Service...")
    
    try:
        predictor = BookingDemandPredictor(model_type=MODEL_TYPE)
        predictor.load_model()
        print(f"✓ Model loaded successfully: {MODEL_TYPE}")
    except FileNotFoundError:
        print("⚠ No trained model found. Please train the model first.")
        print("  You can train by calling POST /api/train")
    except Exception as e:
        print(f"✗ Error loading model: {e}")

@app.get("/")
def read_root():
    """Health check endpoint"""
    return {
        "service": "SmartBookingAI - Prediction Service",
        "status": "running",
        "model_loaded": predictor is not None and predictor.model is not None,
        "model_type": MODEL_TYPE
    }

@app.get("/api/health")
def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "model_info": {
            "type": MODEL_TYPE,
            "loaded": predictor is not None and predictor.model is not None
        }
    }

@app.post("/api/predict", response_model=PredictionResponse)
def predict_demand(time_slot: TimeSlotInfo):
    """
    Predict booking demand for a specific time slot
    
    Args:
        time_slot: Time slot information including event_id, start_time, capacity
    
    Returns:
        Prediction with probability and demand level
    """
    
    if predictor is None or predictor.model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Please train the model first using POST /api/train"
        )
    
    try:
        # Convert to dict for prediction
        slot_dict = time_slot.dict()
        
        # Get prediction
        result = predictor.predict_slot_demand(slot_dict)
        
        return PredictionResponse(
            probability=result['probability'],
            demand_level=result['demand_level'],
            is_recommended=result['is_recommended'],
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@app.post("/api/predict/time-slot/{time_slot_id}", response_model=PredictionResponse)
def predict_for_time_slot_id(time_slot_id: int):
    """
    Predict demand for a time slot by its ID (fetches info from database)
    
    Args:
        time_slot_id: ID of the time slot in the database
    
    Returns:
        Prediction with probability and demand level
    """
    
    if predictor is None or predictor.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        # Fetch time slot info from database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ts.*, e.duration_minutes 
                FROM time_slots ts
                JOIN events e ON ts.event_id = e.id
                WHERE ts.id = ?
            """, (time_slot_id,))
            
            slot = cursor.fetchone()
            
            if not slot:
                raise HTTPException(status_code=404, detail="Time slot not found")
            
            # Prepare slot info
            slot_info = {
                'event_id': slot['event_id'],
                'start_time': slot['start_time'],
                'max_capacity': slot['max_capacity'],
                'duration_minutes': slot['duration_minutes']
            }
            
            # Get prediction
            result = predictor.predict_slot_demand(slot_info)
            
            return PredictionResponse(
                time_slot_id=time_slot_id,
                probability=result['probability'],
                demand_level=result['demand_level'],
                is_recommended=result['is_recommended'],
                timestamp=datetime.now().isoformat()
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@app.post("/api/predict/bulk")
def predict_bulk(request: BulkPredictionRequest):
    """
    Predict demand for multiple time slots
    
    Args:
        request: List of time slot information
    
    Returns:
        List of predictions
    """
    
    if predictor is None or predictor.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        predictions = []
        
        for slot in request.time_slots:
            result = predictor.predict_slot_demand(slot)
            predictions.append({
                'time_slot': slot,
                'probability': result['probability'],
                'demand_level': result['demand_level'],
                'is_recommended': result['is_recommended']
            })
        
        return {
            'predictions': predictions,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk prediction error: {str(e)}")

@app.get("/api/recommend/event/{event_id}")
def recommend_slots(event_id: int, limit: int = 5):
    """
    Get recommended time slots for an event based on predicted demand
    
    Args:
        event_id: ID of the event
        limit: Maximum number of recommendations
    
    Returns:
        List of recommended time slots sorted by demand
    """
    
    if predictor is None or predictor.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get available future time slots
            cursor.execute("""
                SELECT ts.*, e.duration_minutes 
                FROM time_slots ts
                JOIN events e ON ts.event_id = e.id
                WHERE ts.event_id = ? 
                AND ts.start_time > datetime('now')
                AND ts.is_available = 1
                AND ts.available_slots > 0
                ORDER BY ts.start_time
            """, (event_id,))
            
            slots = cursor.fetchall()
            
            if not slots:
                return {
                    'event_id': event_id,
                    'recommendations': [],
                    'message': 'No available time slots found'
                }
            
            # Predict demand for each slot
            recommendations = []
            for slot in slots:
                slot_info = {
                    'event_id': slot['event_id'],
                    'start_time': slot['start_time'],
                    'max_capacity': slot['max_capacity'],
                    'duration_minutes': slot['duration_minutes']
                }
                
                prediction = predictor.predict_slot_demand(slot_info)
                
                recommendations.append({
                    'time_slot_id': slot['id'],
                    'start_time': slot['start_time'],
                    'end_time': slot['end_time'],
                    'available_slots': slot['available_slots'],
                    'probability': prediction['probability'],
                    'demand_level': prediction['demand_level'],
                    'is_recommended': prediction['is_recommended']
                })
            
            # Sort by probability (descending) and limit results
            recommendations.sort(key=lambda x: x['probability'], reverse=True)
            recommendations = recommendations[:limit]
            
            return {
                'event_id': event_id,
                'recommendations': recommendations,
                'timestamp': datetime.now().isoformat()
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation error: {str(e)}")

@app.post("/api/train")
def train_model(request: TrainingRequest, background_tasks: BackgroundTasks):
    """
    Train the AI model on historical booking data
    
    Args:
        request: Training configuration (model type)
    
    Returns:
        Training status
    """
    
    global predictor, MODEL_TYPE
    
    try:
        MODEL_TYPE = request.model_type
        predictor = BookingDemandPredictor(model_type=MODEL_TYPE)
        
        # Train model
        metrics = predictor.train()
        
        # Save model
        predictor.save_model()
        
        return {
            'status': 'success',
            'message': f'Model trained successfully: {MODEL_TYPE}',
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training error: {str(e)}")

@app.get("/api/model/info", response_model=ModelInfo)
def get_model_info():
    """Get information about the current model"""
    
    return ModelInfo(
        model_type=MODEL_TYPE,
        is_loaded=predictor is not None and predictor.model is not None,
        last_trained=None  # Could store this in database
    )

@app.get("/api/stats/predictions")
def get_prediction_stats():
    """Get statistics about prediction patterns"""
    
    if predictor is None or predictor.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get some stats from booking history
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_bookings,
                    SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_bookings,
                    AVG(CASE WHEN is_weekend = 1 THEN 1.0 ELSE 0.0 END) as weekend_ratio
                FROM booking_history
            """)
            
            stats = cursor.fetchone()
            
            return {
                'total_historical_bookings': stats['total_bookings'],
                'confirmed_bookings': stats['confirmed_bookings'],
                'weekend_booking_ratio': round(stats['weekend_ratio'], 3),
                'model_type': MODEL_TYPE
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)