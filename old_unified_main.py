from fastapi import FastAPI, HTTPException, Depends
from datetime import timedelta
from typing import List
from datetime import datetime
import traceback
from fastapi.middleware.cors import CORSMiddleware

# Import from user service
from user_services.models import (
    UserCreate, UserResponse, UserUpdate, LoginRequest, Token,
    BaseResponse, UserBaseResponse, UsersListResponse, TokenResponse
)
from user_services.auth import (
    authenticate_user, create_access_token, get_current_active_user, 
    require_admin, ACCESS_TOKEN_EXPIRE_MINUTES
)

from user_services import database
# Import from booking service
from booking_services.booking_models import (
    EventCreate, EventResponse, TimeSlotResponse, BookingCreate, 
    BookingResponse, BookingUpdate, 
    EventBaseResponse, EventsListResponse, TimeSlotsListResponse, EventUpdate,
    BookingBaseResponse, BookingsListResponse, BookingStatus
)
from booking_services import booking_database

# Import from prediction services
from prediction_service.ai_models import (
    PredictionRequest, PredictionResponse, TrainingResponse, 
    DataGenerationRequest, TimeSlotWithPrediction)

from prediction_service.ai_prediction_models import BookingDemandPredictor, train_all_models
from prediction_service.ai_data_generator import generate_synthetic_booking_data, analyze_booking_patterns, get_booking_history_stats

# Create unified FastAPI app
app = FastAPI(
    title="Unified Smart Booking API",
    description="Combined user management and booking system",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origins=["*"],
    expose_headers=["*"]
)

# Helper function for user responses
def create_user_response(user: dict) -> UserResponse:
    return UserResponse(
        id=user["id"], username=user["username"], email=user["email"],
        first_name=user["first_name"], last_name=user["last_name"],
        phone=user["phone"], address=user["address"], city=user["city"],
        country=user["country"], postal_code=user["postal_code"],
        role=user["role"], created_at=user.get("created_at")
    )

# ========== USER MANAGEMENT ENDPOINTS ==========

@app.post("/register", response_model=UserBaseResponse)
async def register(user: UserCreate):
    """Register a new user"""
    try:
        data = (user.username, user.email, user.password, user.first_name, 
                user.last_name, user.phone, user.address, user.city, 
                user.country, user.postal_code)
        success = database.reg(data)
        
        if success:
            new_user = database.get_user_by_username(user.username)
            if new_user:
                return BaseResponse(
                    success=True,
                    message="User registered successfully",
                    data=create_user_response(new_user)
                )
            raise HTTPException(status_code=500, detail="User created but cannot retrieve details")
        raise HTTPException(status_code=400, detail="Username or email already exists")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    """User login - returns JWT token"""
    user = authenticate_user(credentials.username, credentials.password)

    print(f"🔍 User object: {user}")
    print(f"🔍 User ID: {user.get('id') if user else 'No user'}")
    if not user:
        raise HTTPException(
            status_code=401, 
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    
  
    access_token = create_access_token(
        data={
            "sub": user["username"], 
            "role": user["role"],
            "id": user["id"]  
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return BaseResponse(
        success=True,
        message="Login successful",
        data=Token(
            access_token=access_token, 
            token_type="bearer",
            user=create_user_response(user)
        )
    )

@app.post("/users/me", response_model=UserBaseResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """Get current user information"""
    user = database.get_user_by_username(current_user["username"])
    if user:
        return BaseResponse(success=True, message="User retrieved successfully",
                          data=create_user_response(user))
    raise HTTPException(status_code=404, detail="User not found")

@app.put("/users/me", response_model=UserBaseResponse)
async def update_current_user(user_update: UserUpdate, 
                              current_user: dict = Depends(get_current_active_user)):
    """Update current user information"""
    try:
        user = database.get_user_by_username(current_user["username"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        data = (
            user_update.username or user["username"],
            user_update.email or user["email"],
            user_update.password or "",
            user_update.first_name or user["first_name"],
            user_update.last_name or user["last_name"],
            user_update.phone or user["phone"],
            user_update.address or user["address"],
            user_update.city or user["city"],
            user_update.country or user["country"],
            user_update.postal_code or user["postal_code"],
            user["id"]
        )
        
        if database.update(data):
            updated_user = database.single_user(user["id"])
            if updated_user:
                return BaseResponse(success=True, message="User updated successfully",
                                  data=create_user_response(updated_user))
            raise HTTPException(status_code=500, detail="Failed to retrieve updated user")
        raise HTTPException(status_code=400, detail="Failed to update user")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

@app.post("/users", response_model=UsersListResponse)
async def get_all_users(current_user: dict = Depends(require_admin)):
    """Get all users (Admin only)"""
    try:
        users = database.show_all()
        return BaseResponse(
            success=True, message="Users retrieved successfully",
            data=[create_user_response(user) for user in users]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch users: {str(e)}")

@app.post("/users/{user_id}", response_model=UserBaseResponse)
async def get_user(user_id: int, current_user: dict = Depends(require_admin)):
    """Get specific user by ID (Admin only)"""
    user = database.single_user(user_id)
    if user:
        return BaseResponse(success=True, message="User retrieved successfully",
                          data=create_user_response(user))
    raise HTTPException(status_code=404, detail="User not found")

@app.put("/users/{user_id}", response_model=UserBaseResponse)
async def update_user(user_id: int, user_update: UserUpdate,
                     current_user: dict = Depends(require_admin)):
    """Update user information (Admin only)"""
    try:
        current_data = database.single_user(user_id)
        if not current_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        data = (
            user_update.username or current_data["username"],
            user_update.email or current_data["email"],
            user_update.password or "",
            user_update.first_name or current_data["first_name"],
            user_update.last_name or current_data["last_name"],
            user_update.phone or current_data["phone"],
            user_update.address or current_data["address"],
            user_update.city or current_data["city"],
            user_update.country or current_data["country"],
            user_update.postal_code or current_data["postal_code"],
            user_id
        )
        
        if database.update(data):
            updated_user = database.single_user(user_id)
            if updated_user:
                return BaseResponse(success=True, message="User updated successfully",
                                  data=create_user_response(updated_user))
            raise HTTPException(status_code=500, detail="Failed to retrieve updated user")
        raise HTTPException(status_code=400, detail="Failed to update user")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

@app.delete("/users/{user_id}", response_model=BaseResponse)
async def delete_user(user_id: int, current_user: dict = Depends(require_admin)):
    """Delete a user (Admin only)"""
    if database.delete(user_id):
        return BaseResponse(success=True, message="User deleted successfully", data=None)
    raise HTTPException(status_code=404, detail="User not found or cannot be deleted")

# ========== BOOKING ENDPOINTS ==========

@app.post("/events", response_model=EventBaseResponse)
async def create_event(
    event: EventCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new event"""
    try:
        event_id = booking_database.create_event(event)
        if event_id:
            new_event = booking_database.get_event_by_id(event_id)
            if new_event:
                return EventBaseResponse(
                    success=True,
                    message="Event created successfully",
                    data=EventResponse(**new_event)
                )
        return EventBaseResponse(
            success=False,
            message="Failed to create event",
            data=None
        )
    except Exception as e:
        return EventBaseResponse(
            success=False,
            message=f"Event creation failed: {str(e)}",
            data=None
        )

@app.post("/all_events", response_model=EventsListResponse)
async def get_all_events():
    """Get all events"""
    try:
        events = booking_database.get_all_events()
        event_responses = [EventResponse(**event) for event in events]
        return EventsListResponse(
            success=True,
            message="Events fetched successfully",
            data=event_responses
        )
    except Exception as e:
        return EventsListResponse(
            success=False,
            message=f"Failed to fetch events: {str(e)}",
            data=None
        )

@app.post("/events/{event_id}", response_model=EventBaseResponse)
async def get_event(event_id: int):
    """Get specific event by ID"""
    try:
        event = booking_database.get_event_by_id(event_id)
        if event:
            return EventBaseResponse(
                success=True,
                message="Event fetched successfully",
                data=EventResponse(**event)
            )
        return EventBaseResponse(
            success=False,
            message="Event not found",
            data=None
        )
    except Exception as e:
        return EventBaseResponse(
            success=False,
            message=f"Failed to fetch event: {str(e)}",
            data=None
        )

@app.get("/events/{event_id}/slots", response_model=TimeSlotsListResponse)
async def get_available_slots(event_id: int, date: str = None):
    """Get available time slots for an event"""
    try:
        slots = booking_database.get_available_time_slots(event_id, date)
        slot_responses = [TimeSlotResponse(**slot) for slot in slots]
        return TimeSlotsListResponse(
            success=True,
            message="Time slots fetched successfully",
            data=slot_responses
        )
    except Exception as e:
        return TimeSlotsListResponse(
            success=False,
            message=f"Failed to fetch slots: {str(e)}",
            data=None
        )

# ========== EVENT MANAGEMENT ENDPOINTS (Admin Only) ==========

@app.put("/events/{event_id}", response_model=EventBaseResponse)
async def update_event(
    event_id: int,
    event_update: EventUpdate,
    current_user: dict = Depends(require_admin)  # Admin only
):
    """Update event information (Admin only)"""
    try:
        # Get current event data
        current_event = booking_database.get_event_by_id(event_id)
        if not current_event:
            return EventBaseResponse(
                success=False,
                message="Event not found",
                data=None
            )
        
        # Use provided values or keep existing ones
        updated_data = {
            "title": event_update.title or current_event["title"],
            "description": event_update.description or current_event["description"],
            "capacity": event_update.capacity or current_event["capacity"],
            "duration_minutes": event_update.duration_minutes or current_event["duration_minutes"],
            "created_by": current_event["created_by"]  # Keep original creator
        }
        
        # Create EventCreate object with updated data
        updated_event = EventCreate(**updated_data)
        
        success = booking_database.update_event(event_id, updated_event)
        if success:
            updated_event_data = booking_database.get_event_by_id(event_id)
            return EventBaseResponse(
                success=True,
                message="Event updated successfully",
                data=EventResponse(**updated_event_data)
            )
        return EventBaseResponse(
            success=False,
            message="Failed to update event",
            data=None
        )
    except Exception as e:
        return EventBaseResponse(
            success=False,
            message=f"Update failed: {str(e)}",
            data=None
        )

@app.delete("/events/{event_id}", response_model=BaseResponse)
async def delete_event(
    event_id: int,
    current_user: dict = Depends(require_admin)  
):
    """Delete an event (Admin only)"""
    try:
        # Check if event exists
        event = booking_database.get_event_by_id(event_id)
        if not event:
            return BaseResponse(
                success=False,
                message="Event not found",
                data=None
            )
        
        success = booking_database.delete_event(event_id)
        if success:
            return BaseResponse(
                success=True,
                message="Event deleted successfully",
                data=None
            )
        return BaseResponse(
            success=False,
            message="Failed to delete event",
            data=None
        )
    except Exception as e:
        return BaseResponse(
            success=False,
            message=f"Deletion failed: {str(e)}",
            data=None
        )

@app.get("/events/{event_id}/slots-with-prediction", response_model=BaseResponse)
async def get_time_slots_with_prediction(
    event_id: int, 
    date: str = None,
    current_user: dict = Depends(get_current_active_user)
):
    """Get available time slots with AI demand prediction"""
    try:
        # Get available slots
        slots = booking_database.get_available_time_slots(event_id, date)
        
        # Load AI model for predictions
        predictor = BookingDemandPredictor(model_type="random_forest")
        predictor.load_model()
        
        # Add predictions to each slot
        slots_with_prediction = []
        for slot in slots:
            prediction = predictor.predict_slot_demand({
                'event_id': slot['event_id'],
                'start_time': slot['start_time'],
                'max_capacity': slot['max_capacity'],
                'duration_minutes': 60
            })
            
            slot_with_pred = {
                **slot,
                'demand_prediction': prediction
            }
            slots_with_prediction.append(slot_with_pred)
        
        return BaseResponse(
            success=True,
            message="Time slots with demand prediction fetched successfully",
            data=slots_with_prediction
        )
    except Exception as e:
        return BaseResponse(
            success=False,
            message=f"Failed to fetch slots with prediction: {str(e)}",
            data=None
        )
    

@app.post("/bookings", response_model=BookingBaseResponse)
async def create_booking(
    booking: BookingCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new booking (user_id comes from JWT token)"""
    try:
        # Extract user_id from JWT token
        user_id = current_user.get("id")
        if not user_id:
            return BookingBaseResponse(
                success=False,
                message="User ID not found in token",
                data=None
            )
        
        # Create booking using the corrected database function
        booking_id = booking_database.create_booking(
            user_id=user_id,
            time_slot_id=booking.time_slot_id,
            status="confirmed"
        )
        
        if booking_id:
            new_booking = booking_database.get_booking_by_id(booking_id)
            if new_booking:
                return BookingBaseResponse(
                    success=True,
                    message="Booking created successfully",
                    data=BookingResponse(**new_booking)
                )
        
        return BookingBaseResponse(
            success=False,
            message="Booking failed - time slot may be unavailable or you already have a booking for this slot",
            data=None
        )
        
    except Exception as e:
        return BookingBaseResponse(
            success=False,
            message=f"Booking failed: {str(e)}",
            data=None
        )

@app.post("/bookings/my-bookings", response_model=BookingsListResponse)
async def get_my_bookings(current_user: dict = Depends(get_current_active_user)):
    """Get current user's bookings"""
    try:
        # Extract user_id from JWT token
        user_id = current_user.get("id")
        if not user_id:
            return BookingsListResponse(
                success=False,
                message="User ID not found in token",
                data=None
            )
            
        bookings = booking_database.get_user_bookings(user_id)
        booking_responses = [BookingResponse(**booking) for booking in bookings]
        return BookingsListResponse(
            success=True,
            message="Bookings fetched successfully",
            data=booking_responses
        )
    except Exception as e:
        return BookingsListResponse(
            success=False,
            message=f"Failed to fetch bookings: {str(e)}",
            data=None
        )

@app.put("/bookings/{booking_id}", response_model=BookingBaseResponse)
async def update_booking(
    booking_id: int,
    booking_update: BookingUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """Update booking status"""
    try:
        success = booking_database.update_booking_status(booking_id, booking_update.status.value)
        if success:
            updated_booking = booking_database.get_booking_by_id(booking_id)
            if updated_booking:
                return BookingBaseResponse(
                    success=True,
                    message="Booking updated successfully",
                    data=BookingResponse(**updated_booking)
                )
        return BookingBaseResponse(
            success=False,
            message="Booking not found or update failed",
            data=None
        )
    except Exception as e:
        return BookingBaseResponse(
            success=False,
            message=f"Update failed: {str(e)}",
            data=None
        )

@app.post("/bookings/{booking_id}", response_model=BookingBaseResponse)
async def get_booking(booking_id: int, current_user: dict = Depends(get_current_active_user)):
    """Get specific booking by ID"""
    try:
        booking = booking_database.get_booking_by_id(booking_id)
        if booking:
            return BookingBaseResponse(
                success=True,
                message="Booking fetched successfully",
                data=BookingResponse(**booking)
            )
        return BookingBaseResponse(
            success=False,
            message="Booking not found",
            data=None
        )
    except Exception as e:
        return BookingBaseResponse(
            success=False,
            message=f"Failed to fetch booking: {str(e)}",
            data=None
        )
    

@app.post("/ai/predict-demand", response_model=PredictionResponse)
async def predict_demand(
    request: PredictionRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Predict booking demand for a time slot with detailed error handling"""
    try:
        print(f"\n=== Predict Demand Request ===")
        print(f"Event ID: {request.event_id}")
        print(f"Start Time: {request.start_time}")
        print(f"Max Capacity: {request.max_capacity}")
        print(f"Duration: {request.duration_minutes}")
        
        # Initialize predictor
        predictor = BookingDemandPredictor(model_type="random_forest")
        
        # Try to load the model
        try:
            predictor.load_model()
            print("✓ Model loaded successfully")
        except FileNotFoundError as e:
            return PredictionResponse(
                success=False,
                message="AI model not found. Please train the model first using /ai/train-models endpoint",
                data={"error": str(e), "action_needed": "Train model first"}
            )
        except Exception as e:
            return PredictionResponse(
                success=False,
                message=f"Failed to load AI model: {str(e)}",
                data={"error": str(e)}
            )
        
        # Validate start_time format
        try:
            test_time = datetime.fromisoformat(request.start_time.replace('Z', '+00:00'))
            print(f"✓ Start time parsed: {test_time}")
        except Exception as e:
            return PredictionResponse(
                success=False,
                message=f"Invalid start_time format: {str(e)}. Expected ISO format like '2024-01-15T10:00:00'",
                data={"error": str(e)}
            )
        
        # Make prediction
        try:
            prediction = predictor.predict_slot_demand({
                'event_id': request.event_id,
                'start_time': request.start_time,
                'max_capacity': request.max_capacity,
                'duration_minutes': request.duration_minutes
            })
            
            print(f"✓ Prediction successful: {prediction}")
            
            return PredictionResponse(
                success=True,
                message="Demand prediction generated successfully",
                data=prediction
            )
            
        except Exception as e:
            print(f"Prediction error: {str(e)}")
            traceback.print_exc()
            return PredictionResponse(
                success=False,
                message=f"Prediction calculation failed: {str(e)}",
                data={"error": str(e), "traceback": traceback.format_exc()}
            )
            
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        traceback.print_exc()
        return PredictionResponse(
            success=False,
            message=f"Unexpected error: {str(e)}",
            data={"error": str(e)}
        )

@app.post("/ai/train-models", response_model=TrainingResponse)
async def train_ai_models(
    request: DataGenerationRequest = None,
    current_user: dict = Depends(require_admin)
):
    """Train AI models with synthetic data (Admin only)"""
    try:
        if request is None:
            request = DataGenerationRequest()
        
        print(f"\n=== Training AI Models ===")
        print(f"Days back: {request.days_back}")
        print(f"Base probability: {request.base_probability}")
        
        # Generate synthetic data first
        try:
            records = generate_synthetic_booking_data(
                days_back=request.days_back, 
                base_probability=request.base_probability
            )
            print(f"✓ Generated {records} synthetic records")
        except Exception as e:
            return TrainingResponse(
                success=False,
                message=f"Failed to generate synthetic data: {str(e)}",
                results={"error": str(e)}
            )
        
        # Check if we have enough data
        if records == 0:
            return TrainingResponse(
                success=False,
                message="No training data generated. Please check database setup",
                results={"records_generated": 0}
            )
        
        # Train models
        try:
            results = train_all_models()
            
            # Check if any models trained successfully
            successful_models = [k for k, v in results.items() if 'error' not in v]
            
            if successful_models:
                return TrainingResponse(
                    success=True,
                    message=f"Models trained successfully with {records} synthetic records. Trained: {', '.join(successful_models)}",
                    results={
                        "records_generated": records,
                        "models_trained": results
                    }
                )
            else:
                return TrainingResponse(
                    success=False,
                    message="Model training failed for all models",
                    results=results
                )
                
        except Exception as e:
            print(f"Training error: {str(e)}")
            traceback.print_exc()
            return TrainingResponse(
                success=False,
                message=f"Training failed: {str(e)}",
                results={"error": str(e), "traceback": traceback.format_exc()}
            )
            
    except Exception as e:
        return TrainingResponse(
            success=False,
            message=f"Unexpected error: {str(e)}",
            results={"error": str(e)}
        )

@app.post("/ai/generate-data", response_model=BaseResponse)
async def generate_ai_data(
    request: DataGenerationRequest = None,
    current_user: dict = Depends(require_admin)
):
    """Generate synthetic data for AI training (Admin only)"""
    try:
        if request is None:
            request = DataGenerationRequest()
        
        print(f"\n=== Generating Synthetic Data ===")
        print(f"Days back: {request.days_back}")
        print(f"Base probability: {request.base_probability}")
        
        records = generate_synthetic_booking_data(
            days_back=request.days_back, 
            base_probability=request.base_probability
        )
        
        if records > 0:
            return BaseResponse(
                success=True,
                message=f"Successfully generated {records} synthetic booking records",
                data={"records_generated": records}
            )
        else:
            return BaseResponse(
                success=False,
                message="No records generated. Check database setup and time slots",
                data={"records_generated": 0}
            )
            
    except Exception as e:
        print(f"Data generation error: {str(e)}")
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Data generation failed: {str(e)}",
            data={"error": str(e)}
        )

@app.get("/ai/analyze-patterns", response_model=BaseResponse)
async def analyze_booking_patterns_endpoint(
    current_user: dict = Depends(get_current_active_user)
):
    """Analyze booking patterns"""
    try:
        # Capture the analysis output
        from io import StringIO
        import sys
        
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        analyze_booking_patterns()
        
        sys.stdout = old_stdout
        analysis_text = captured_output.getvalue()
        
        return BaseResponse(
            success=True,
            message="Pattern analysis completed successfully",
            data={"analysis": analysis_text}
        )
    except Exception as e:
        return BaseResponse(
            success=False,
            message=f"Analysis failed: {str(e)}",
            data={"error": str(e)}
        )
    
@app.get("/ai/model-status", response_model=BaseResponse)
async def get_model_status(current_user: dict = Depends(get_current_active_user)):
    """Check if AI models are trained and ready"""
    try:
        import os
        
        # CORRECTED: Point to prediction_service directory where models are stored
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_dir = os.path.join(current_dir, "prediction_service")
        
        print(f"Looking for models in: {model_dir}")
        
        models_status = {}
        
        for model_type in ["random_forest", "gradient_boosting"]:
            model_path = os.path.join(model_dir, f"{model_type}_model.pkl")
            scaler_path = os.path.join(model_dir, f"{model_type}_scaler.pkl")
            features_path = os.path.join(model_dir, f"{model_type}_features.pkl")
            
            # Debug: Print file existence
            print(f"{model_type} - Model exists: {os.path.exists(model_path)}")
            print(f"{model_type} - Scaler exists: {os.path.exists(scaler_path)}")
            print(f"{model_type} - Features exists: {os.path.exists(features_path)}")
            
            models_status[model_type] = {
                "model_exists": os.path.exists(model_path),
                "scaler_exists": os.path.exists(scaler_path),
                "features_exists": os.path.exists(features_path),
                "ready": all([
                    os.path.exists(model_path),
                    os.path.exists(scaler_path),
                    os.path.exists(features_path)
                ])
            }
        
        any_ready = any(status["ready"] for status in models_status.values())
        
        return BaseResponse(
            success=True,
            message="Model status retrieved",
            data={
                "models": models_status,
                "any_model_ready": any_ready,
                "recommendation": "Train models using /ai/train-models" if not any_ready else "Models ready for predictions",
                "model_directory": model_dir  # Added for debugging
            }
        )
    except Exception as e:
        return BaseResponse(
            success=False,
            message=f"Failed to check model status: {str(e)}",
            data={"error": str(e)}
        )


@app.get("/ai/model-info", response_model=BaseResponse)
async def get_ai_model_info(current_user: dict = Depends(get_current_active_user)):
    """Get information about AI models"""
    models = {
        "available_models": {
            "random_forest": {
                "name": "Random Forest Classifier",
                "description": "Ensemble learning method - good for general purpose prediction",
                "pros": ["Fast predictions", "Handles non-linear relationships", "Resistant to overfitting"],
                "cons": ["Can be memory intensive with many trees"]
            },
            "gradient_boosting": {
                "name": "Gradient Boosting Classifier",
                "description": "Sequential ensemble method - often better performance",
                "pros": ["High accuracy", "Handles complex patterns", "Feature importance"],
                "cons": ["Slower training", "Risk of overfitting if not tuned"]
            }
        },
        "current_default": "random_forest",
        "features_used": [
            "day_of_week", "is_weekend", "month", "hour",
            "is_morning", "is_afternoon", "is_evening", "is_business_hours",
            "is_peak_hour", "is_summer", "is_winter",
            "event_id", "max_capacity", "duration_minutes", "capacity_normalized"
        ]
    }
    return BaseResponse(
        success=True,
        message="AI model information",
        data=models
    )


@app.get("/ai/data-stats", response_model=BaseResponse)
async def get_ai_data_stats(current_user: dict = Depends(get_current_active_user)):
    """Get statistics about training data"""
    try:
        stats = get_booking_history_stats()
        
        # Add helpful messages
        if stats.get('total_records', 0) == 0:
            stats['recommendation'] = "Generate synthetic data using /ai/generate-data endpoint"
        elif stats.get('total_records', 0) < 100:
            stats['recommendation'] = "Consider generating more data for better model performance"
        else:
            stats['recommendation'] = "Sufficient data available for training"
        
        return BaseResponse(
            success=True,
            message="Training data statistics",
            data=stats
        )
    except Exception as e:
        return BaseResponse(
            success=False,
            message=f"Failed to get data stats: {str(e)}",
            data={"error": str(e)}
        )


# ========== HEALTH CHECK ==========

@app.get("/")
async def root():
    return BaseResponse(
        success=True,
        message="SmartBookingAI Unified API is running",
        data={
            "version": "2.0.0",
            "services": ["user-management", "booking-system", "ai-prediction"],
            "status": "healthy"
        }
    )

@app.get("/health")
async def health_check():
    return BaseResponse(
        success=True,
        message="Service is healthy",
        data={"status": "healthy", "service": "unified-booking-service"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)