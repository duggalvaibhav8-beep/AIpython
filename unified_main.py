from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from datetime import datetime, timedelta
from typing import List, Dict, Any
import traceback
import json
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
    BookingBaseResponse, BookingsListResponse, BookingStatus, BulkTimeSlotCreate, 
    FlexibleBulkTimeSlotCreate, SimpleBulkTimeSlotCreate
)
from booking_services import booking_database
from booking_services.booking_database import get_db_connection, get_all_events

# Import from prediction services
from prediction_service.ai_models import (
    PredictionRequest, PredictionResponse, TrainingResponse, 
    DataGenerationRequest, TimeSlotWithPrediction)

from prediction_service.ai_prediction_models import BookingDemandPredictor, train_all_models
from prediction_service.ai_data_generator import generate_synthetic_booking_data, analyze_booking_patterns, get_booking_history_stats, export_to_csv

# Import notification modules
from notification_services.notification_models import (
    EmailNotificationRequest,
    SMSNotificationRequest,
    BulkNotificationRequest,
    NotificationResponse,
    NotificationHistoryResponse,
    BaseResponse as NotificationBaseResponse,
    NotificationType
)
from notification_services import notification_database
from notification_services.email_services import EmailService

# Create unified FastAPI app
app = FastAPI(
    title="Unified Smart Booking API",
    description="Combined user management, booking system and notification service",
    version="2.0.0"
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

# Initialize email service
email_service = EmailService()

# Helper function for user responses
def create_user_response(user: dict) -> UserResponse:
    return UserResponse(
        id=user["id"], username=user["username"], email=user["email"],
        first_name=user["first_name"], last_name=user["last_name"],
        phone=user["phone"], address=user["address"], city=user["city"],
        country=user["country"], postal_code=user["postal_code"],
        role=user["role"], created_at=user.get("created_at")
    )

def render_template(template_body: str, data: dict) -> str:
    """Render email template with data"""
    try:
        return template_body.format(**data)
    except KeyError as e:
        print(f"Missing template variable: {e}")
        return template_body


def send_email_notification(
    recipient_email: str,
    recipient_name: str,
    notification_type: str,
    data: dict
) -> tuple[bool, str, int]:
    """
    Send email notification
    Returns: (success, message, notification_id)
    """
    try:
        # Get template
        template = notification_database.get_email_template(notification_type)
        if not template:
            return False, f"Template not found: {notification_type}", None
        
        # Prepare template data
        template_data = {
            "user_name": recipient_name,
            **data
        }
        
        # Render subject and body
        subject = render_template(template["subject_template"], template_data)
        body = render_template(template["body_template"], template_data)
        
        # Save notification to database
        notification_id = notification_database.save_notification({
            "recipient_email": recipient_email,
            "recipient_name": recipient_name,
            "notification_type": notification_type,
            "subject": subject,
            "body": body,
            "status": "pending",
            "channel": "email",
            "metadata": json.dumps(data)
        })
        
        # Send email
        success, error = email_service.send_email(
            recipient_email=recipient_email,
            subject=subject,
            html_body=body
        )
        
        # Update status
        if success:
            notification_database.update_notification_status(
                notification_id, 
                "sent",
                None
            )
            return True, "Email sent successfully", notification_id
        else:
            notification_database.update_notification_status(
                notification_id, 
                "failed",
                error
            )
            return False, f"Failed to send email: {error}", notification_id
            
    except Exception as e:
        error_msg = f"Error sending notification: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return False, error_msg, None

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
                return UserBaseResponse(
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
    
    return TokenResponse(
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
        return UserBaseResponse(success=True, message="User retrieved successfully",
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
                return UserBaseResponse(success=True, message="User updated successfully",
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
        return UsersListResponse(
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
        return UserBaseResponse(success=True, message="User retrieved successfully",
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
                return UserBaseResponse(success=True, message="User updated successfully",
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

@app.post("/events/{event_id}/slots", response_model=TimeSlotsListResponse)
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
    

@app.get("/admin/bookings/all", response_model=BookingsListResponse)
async def get_all_bookings_admin_endpoint(
    current_user: dict = Depends(require_admin)
):
    """
    Get EVERY booking in the system.
    (Admin Only)
    """
    try:
        bookings = booking_database.get_all_bookings_admin()
        booking_responses = [BookingResponse(**booking) for booking in bookings]
        
        return BookingsListResponse(
            success=True,
            message=f"Retrieved {len(bookings)} total bookings",
            data=booking_responses
        )
    except Exception as e:
        return BookingsListResponse(
            success=False,
            message=f"Failed to fetch bookings: {str(e)}",
            data=None
        )

@app.get("/admin/bookings/event/{event_id}", response_model=BookingsListResponse)
async def get_event_bookings_admin_endpoint(
    event_id: int,
    current_user: dict = Depends(require_admin)
):
    """
    Get all bookings for a specific Event ID.
    (Admin Only)
    """
    try:
        # First check if event exists
        event = booking_database.get_event_by_id(event_id)
        if not event:
            return BookingsListResponse(
                success=False,
                message=f"Event {event_id} not found",
                data=None
            )

        bookings = booking_database.get_bookings_by_event_admin(event_id)
        booking_responses = [BookingResponse(**booking) for booking in bookings]
        
        return BookingsListResponse(
            success=True,
            message=f"Retrieved {len(bookings)} bookings for event '{event['title']}'",
            data=booking_responses
        )
    except Exception as e:
        return BookingsListResponse(
            success=False,
            message=f"Failed to fetch event bookings: {str(e)}",
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
        
        # --- FIX: Handle Date Logic Carefully ---
        # 1. Determine new Start Time
        if event_update.start_time:
            new_start = event_update.start_time # It's already a datetime from Pydantic
        else:
            # Parse existing string from DB to datetime
            new_start = datetime.fromisoformat(current_event["start_time"].replace("Z", ""))
        
        # 2. Determine new End Time
        if event_update.end_time:
            new_end = event_update.end_time
        else:
            new_end = datetime.fromisoformat(current_event["end_time"].replace("Z", ""))
        
        # 3. Construct updated data with STRINGS for dates
        updated_data = {
            "title": event_update.title or current_event["title"],
            "description": event_update.description or current_event["description"],
            "capacity": event_update.capacity or current_event["capacity"],
            "duration_minutes": event_update.duration_minutes or current_event["duration_minutes"],
            "start_time": new_start.isoformat(), # <--- Convert to String
            "end_time": new_end.isoformat(),     # <--- Convert to String
            "created_by": current_event["created_by"]
        }
        
        # Create EventCreate object 
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
            message="Failed to update event (Database error)",
            data=None
        )
    except Exception as e:
        # Print error to console for debugging
        print(f"Update Error: {str(e)}") 
        traceback.print_exc()
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
        
        if not slots:
            return BaseResponse(
                success=True,
                message="No available time slots found",
                data=[]
            )
        
        # Load AI model for predictions
        try:
            predictor = BookingDemandPredictor(model_type="random_forest")
            predictor.load_model()
        except FileNotFoundError:
            return BaseResponse(
                success=False,
                message="AI model not trained. Please train the model first using /ai/train-models",
                data=None
            )
        except Exception as e:
            traceback.print_exc()
            return BaseResponse(
                success=False,
                message=f"Failed to load AI model: {str(e)}",
                data=None
            )
        
        # Get event details for duration
        event = booking_database.get_event_by_id(event_id)
        if not event:
            return BaseResponse(
                success=False,
                message="Event not found",
                data=None
            )
        
        # Add predictions to each slot
        slots_with_prediction = []
        for slot in slots:
            try:
                prediction = predictor.predict_slot_demand({
                    'event_id': slot['event_id'],
                    'start_time': slot['start_time'],
                    'max_capacity': slot['max_capacity'],
                    'duration_minutes': event.get('duration_minutes', 60)
                })
                
                slot_with_pred = {
                    **slot,
                    'demand_prediction': prediction
                }
                slots_with_prediction.append(slot_with_pred)
            except Exception as e:
                print(f"Error predicting for slot {slot['id']}: {e}")
                traceback.print_exc()
                # Include slot without prediction rather than failing completely
                slots_with_prediction.append({
                    **slot,
                    'demand_prediction': {
                        'error': str(e),
                        'demand_level': 'Unknown',
                        'probability': 0.0
                    }
                })
        
        return BaseResponse(
            success=True,
            message=f"Found {len(slots_with_prediction)} time slots with demand predictions",
            data=slots_with_prediction
        )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Failed to fetch slots with prediction: {str(e)}",
            data=None
        )

@app.get("/events/{event_id}/slots-by-date", response_model=BaseResponse)
async def get_slots_grouped_by_date(
    event_id: int,
    start_date: str = None,  # YYYY-MM-DD format
    end_date: str = None
):
    """
    Get available time slots grouped by date for better user experience
    Example response:
    {
      "2024-12-10": [
        {"slot_id": 1, "time": "09:00 AM", "available": 30, "capacity": 30},
        {"slot_id": 2, "time": "02:00 PM", "available": 25, "capacity": 30}
      ],
      "2024-12-11": [...]
    }
    """
    try:
        from collections import defaultdict
        
        # Get event details
        event = booking_database.get_event_by_id(event_id)
        if not event:
            return BaseResponse(
                success=False,
                message=f"Event {event_id} not found",
                data=None
            )
        
        # Get all available slots
        slots = booking_database.get_available_time_slots(event_id, date=start_date)
        
        if not slots:
            return BaseResponse(
                success=True,
                message="No available time slots found",
                data={
                    "event_id": event_id,
                    "event_title": event['title'],
                    "slots_by_date": {}
                }
            )
        
        # Group slots by date
        slots_by_date = defaultdict(list)
        
        for slot in slots:
            start_time = datetime.fromisoformat(slot['start_time'])
            date_key = start_time.strftime('%Y-%m-%d')
            time_str = start_time.strftime('%I:%M %p')
            
            slots_by_date[date_key].append({
                "slot_id": slot['id'],
                "time": time_str,
                "start_time": slot['start_time'],
                "end_time": slot['end_time'],
                "available_capacity": slot['available_slots'],
                "max_capacity": slot['max_capacity'],
                "percentage_available": round((slot['available_slots'] / slot['max_capacity']) * 100, 1) if slot['max_capacity'] > 0 else 0,
                "status": "available" if slot['available_slots'] > 5 else "filling_fast"
            })
        
        # Sort dates and times
        sorted_slots = {}
        for date in sorted(slots_by_date.keys()):
            sorted_slots[date] = sorted(slots_by_date[date], key=lambda x: x['start_time'])
        
        return BaseResponse(
            success=True,
            message=f"Found {len(slots)} available time slots",
            data={
                "event_id": event_id,
                "event_title": event['title'],
                "event_description": event['description'],
                "duration_minutes": event['duration_minutes'],
                "total_dates": len(sorted_slots),
                "slots_by_date": sorted_slots
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Error fetching time slots: {str(e)}",
            data=None
        )


@app.post("/bookings/check-availability", response_model=BaseResponse)
async def check_booking_availability(
    request: dict,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Check if a booking is possible before actually creating it
    Request: {
        "event_id": 1,
        "time_slot_id": 5,  # optional
        "quantity": 3
    }
    """
    try:
        event_id = request.get("event_id")
        time_slot_id = request.get("time_slot_id")
        quantity = request.get("quantity", 1)
        
        if not event_id:
            return BaseResponse(
                success=False,
                message="event_id is required",
                data=None
            )
        
        # If specific slot requested
        if time_slot_id:
            with booking_database.get_db_connection() as conn:
                cursor = conn.cursor()
                slot = cursor.execute(
                    """SELECT ts.*, e.title as event_title 
                       FROM time_slots ts 
                       JOIN events e ON ts.event_id = e.id
                       WHERE ts.id = ? AND ts.event_id = ?""",
                    (time_slot_id, event_id)
                ).fetchone()
                
                if not slot:
                    return BaseResponse(
                        success=False,
                        message="Time slot not found or doesn't belong to this event",
                        data=None
                    )
                
                can_book = slot['available_slots'] >= quantity and slot['is_available']
                
                return BaseResponse(
                    success=True,
                    message="Availability checked",
                    data={
                        "can_book": can_book,
                        "time_slot_id": time_slot_id,
                        "requested_quantity": quantity,
                        "available_capacity": slot['available_slots'],
                        "start_time": slot['start_time'],
                        "end_time": slot['end_time'],
                        "reason": None if can_book else f"Only {slot['available_slots']} spots available"
                    }
                )
        
        # If no specific slot, find best available options
        else:
            slots = booking_database.get_available_time_slots(event_id)
            suitable_slots = [
                s for s in slots 
                if s['available_slots'] >= quantity and s['is_available']
            ]
            
            if suitable_slots:
                # Sort by soonest time
                suitable_slots.sort(key=lambda x: x['start_time'])
                
                return BaseResponse(
                    success=True,
                    message=f"Found {len(suitable_slots)} suitable time slots",
                    data={
                        "can_book": True,
                        "requested_quantity": quantity,
                        "suitable_slots_count": len(suitable_slots),
                        "recommended_slots": [
                            {
                                "slot_id": s['id'],
                                "start_time": s['start_time'],
                                "end_time": s['end_time'],
                                "available_capacity": s['available_slots']
                            }
                            for s in suitable_slots[:5]  # Show top 5
                        ]
                    }
                )
            else:
                return BaseResponse(
                    success=True,
                    message="No suitable time slots available",
                    data={
                        "can_book": False,
                        "requested_quantity": quantity,
                        "reason": f"No time slots with {quantity} available spots",
                        "suggestion": "Try reducing quantity or checking other dates"
                    }
                )
        
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Error checking availability: {str(e)}",
            data=None
        )
    

@app.post("/bookings/create-with-validation", response_model=BookingBaseResponse)
async def create_booking_with_validation(
    booking: BookingCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Enhanced booking creation with better validation and error messages
    Automatically suggests alternatives if requested slot is full
    """
    try:
        user_id = current_user.get("id")
        if not user_id:
            return BookingBaseResponse(
                success=False,
                message="User ID not found in token",
                data=None
            )
        
        # Pre-validation check
        with booking_database.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # If specific slot requested, validate it
            if booking.time_slot_id:
                slot = cursor.execute(
                    """SELECT ts.*, e.title as event_title 
                       FROM time_slots ts 
                       JOIN events e ON ts.event_id = e.id
                       WHERE ts.id = ? AND ts.event_id = ?""",
                    (booking.time_slot_id, booking.event_id)
                ).fetchone()
                
                if not slot:
                    return BookingBaseResponse(
                        success=False,
                        message="Invalid time slot selected",
                        data=None
                    )
                
                # Check if user already has booking
                existing = cursor.execute(
                    """SELECT id FROM bookings 
                       WHERE user_id = ? AND time_slot_id = ? AND status != 'cancelled'""",
                    (user_id, booking.time_slot_id)
                ).fetchone()
                
                if existing:
                    return BookingBaseResponse(
                        success=False,
                        message="You already have a booking for this time slot",
                        data=None
                    )
                
                # Check capacity
                if slot['available_slots'] < booking.quantity:
                    # Find alternative slots
                    alternatives = cursor.execute(
                        """SELECT id, start_time, end_time, available_slots 
                           FROM time_slots 
                           WHERE event_id = ? AND available_slots >= ? 
                           AND is_available = TRUE AND start_time > datetime('now')
                           ORDER BY start_time LIMIT 3""",
                        (booking.event_id, booking.quantity)
                    ).fetchall()
                    
                    return BookingBaseResponse(
                        success=False,
                        message=f"Only {slot['available_slots']} spots available. You requested {booking.quantity}.",
                        data={
                            "alternative_slots": [
                                {
                                    "slot_id": alt['id'],
                                    "start_time": alt['start_time'],
                                    "end_time": alt['end_time'],
                                    "available": alt['available_slots']
                                }
                                for alt in alternatives
                            ] if alternatives else []
                        }
                    )
        
        # Attempt to create booking
        booking_id = booking_database.create_booking(
            user_id=user_id,
            event_id=booking.event_id,
            time_slot_id=booking.time_slot_id,
            quantity=booking.quantity,
            status="pending"
        )
        
        if booking_id:
            new_booking = booking_database.get_booking_by_id(booking_id)
            if new_booking:
                # Optional: Send confirmation email
                # send_email_notification(...)
                
                return BookingBaseResponse(
                    success=True,
                    message=f"Booking confirmed! {booking.quantity} spot(s) reserved.",
                    data=BookingResponse(**new_booking)
                )
        
        return BookingBaseResponse(
            success=False,
            message="Booking failed. Please try again or contact support.",
            data=None
        )
        
    except Exception as e:
        traceback.print_exc()
        return BookingBaseResponse(
            success=False,
            message=f"Booking failed: {str(e)}",
            data=None
        )



@app.get("/events/{event_id}/availability-calendar", response_model=BaseResponse)
async def get_availability_calendar(
    event_id: int,
    month: int = None,  # 1-12
    year: int = None
):
    """
    Get a calendar view of availability for an event
    Shows which dates have available slots
    """
    try:
        from collections import defaultdict
        
        if month is None or year is None:
            now = datetime.now()
            month = now.month
            year = now.year
        
        event = booking_database.get_event_by_id(event_id)
        if not event:
            return BaseResponse(
                success=False,
                message="Event not found",
                data=EventResponse(**event)
            )
        
        # Get all slots for the event
        slots = booking_database.get_available_time_slots(event_id)
        
        # Group by date
        calendar = defaultdict(lambda: {
            "total_slots": 0,
            "available_slots": 0,
            "total_capacity": 0,
            "available_capacity": 0,
            "status": "no_slots"
        })
        
        for slot in slots:
            start_time = datetime.fromisoformat(slot['start_time'])
            
            # Filter by month/year
            if start_time.month != month or start_time.year != year:
                continue
            
            date_key = start_time.strftime('%Y-%m-%d')
            
            calendar[date_key]["total_slots"] += 1
            if slot['available_slots'] > 0:
                calendar[date_key]["available_slots"] += 1
            calendar[date_key]["total_capacity"] += slot['max_capacity']
            calendar[date_key]["available_capacity"] += slot['available_slots']
        
        # Determine status for each date
        for date_key in calendar:
            data = calendar[date_key]
            if data["available_capacity"] == 0:
                data["status"] = "fully_booked"
            elif data["available_capacity"] < data["total_capacity"] * 0.3:
                data["status"] = "almost_full"
            else:
                data["status"] = "available"
        
        return BaseResponse(
            success=True,
            message=f"Calendar for {year}-{month:02d}",
            data={
                "event_id": event_id,
                "event_title": event['title'],
                "month": month,
                "year": year,
                "calendar": dict(calendar)
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Error generating calendar: {str(e)}",
            data=None
        )
    

@app.post("/bookings", response_model=BookingBaseResponse)
async def create_booking(
    booking: BookingCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new booking (user_id from JWT; auto-assign time_slot if not provided)"""
    try:
        user_id = current_user.get("id")
        if not user_id:
            return BookingBaseResponse(
                success=False,
                message="User ID not found in token",
                data=None
            )
        
        # Updated call: Pass event_id, time_slot_id (optional), quantity
        booking_id = booking_database.create_booking(
            user_id=user_id,
            event_id=booking.event_id,
            time_slot_id=booking.time_slot_id,
            quantity=booking.quantity,
            status="pending"
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
            message="Booking failed - no available time slot with sufficient capacity. Use /events/{event_id}/slots for suggestions.",
            data=None
        )
    except Exception as e:
        traceback.print_exc()
        return BookingBaseResponse(
            success=False,
            message=f"Booking failed: {str(e)}",
            data=None
        )
    
@app.get("/events/{event_id}/capacity", response_model=BaseResponse)
async def get_event_capacity_status(event_id: int):
    """
    Get detailed capacity information for an event
    Shows total, booked, and available capacity
    """
    try:
        event = booking_database.get_event_by_id(event_id)
        
        if not event:
            return BaseResponse(
                success=False,
                message=f"Event ID {event_id} not found",
                data=None
            )
        
        available = event['available_capacity']
        total = event['capacity']
        booked = event['booked_capacity']
        percentage_booked = (booked / total * 100) if total > 0 else 0
        
        # Determine status
        if available == 0:
            status = "FULLY BOOKED"
            status_emoji = "🔴"
        elif available <= 10:
            status = "ALMOST FULL"
            status_emoji = "🟡"
        elif percentage_booked < 50:
            status = "PLENTY OF SEATS"
            status_emoji = "🟢"
        else:
            status = "FILLING UP"
            status_emoji = "🟠"
        
        return BaseResponse(
            success=True,
            message=f"{status_emoji} {status}",
            data={
                'event_id': event_id,
                'event_title': event['title'],
                'total_capacity': total,
                'booked_capacity': booked,
                'available_capacity': available,
                'percentage_booked': round(percentage_booked, 1),
                'status': status,
                'can_book': available > 0
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Failed to get capacity info: {str(e)}",
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
        traceback.print_exc()
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
        traceback.print_exc()
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
        traceback.print_exc()
        return BookingBaseResponse(
            success=False,
            message=f"Failed to fetch booking: {str(e)}",
            data=None
        )
    

# ========== AI PREDICTION ENDPOINTS ==========

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
        traceback.print_exc()
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
            export_to_csv("synthetic_bookings.csv")
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
    

@app.get("/api/recommend/event/{event_id}", response_model=BaseResponse)
async def recommend_slots_endpoint(
    event_id: int, 
    limit: int = 10,
    current_user: dict = Depends(get_current_active_user)
):
    """Get recommended slots with detailed prediction data for each time slot"""
    try:
        # Load AI model
        predictor = BookingDemandPredictor(model_type="random_forest")
        try:
            predictor.load_model()
        except FileNotFoundError:
            return BaseResponse(
                success=False, 
                message="AI model not trained. Please train the model first using /ai/train-models", 
                data=None
            )
        except Exception as e:
            traceback.print_exc()
            return BaseResponse(
                success=False, 
                message=f"Failed to load AI model: {str(e)}", 
                data=None
            )

        # Get all available slots for this event
        available_slots = booking_database.get_available_time_slots(event_id)
        if not available_slots:
            return BaseResponse(
                success=True, 
                message="No available time slots found.", 
                data={
                    "event_id": event_id,
                    "total_slots": 0,
                    "recommendations": [],
                    "grouped_by_demand": {
                        "high_demand": [],
                        "medium_demand": [],
                        "low_demand": []
                    }
                }
            )

        # Get event details
        event = booking_database.get_event_by_id(event_id)
        if not event:
            return BaseResponse(
                success=False, 
                message=f"Event {event_id} not found", 
                data=None
            )

        recommendations = []
        errors = []
        
        for slot in available_slots:
            try:
                # Get AI prediction for this slot
                ai_result = predictor.predict_slot_demand({
                    'event_id': slot['event_id'],
                    'start_time': slot['start_time'],
                    'max_capacity': slot['max_capacity'],
                    'duration_minutes': event.get('duration_minutes', 60)
                })
                
                # Parse start time for better display
                start_time = datetime.fromisoformat(slot['start_time'].replace('Z', '+00:00'))
                
                recommendations.append({
                    "slot_id": slot['id'],
                    "start_time": slot['start_time'],
                    "end_time": slot['end_time'],
                    "display_time": start_time.strftime('%I:%M %p'),
                    "display_date": start_time.strftime('%Y-%m-%d'),
                    "day_of_week": start_time.strftime('%A'),
                    "seats_available": slot['available_slots'],
                    "max_capacity": slot['max_capacity'],
                    "percentage_available": round((slot['available_slots'] / slot['max_capacity']) * 100, 1) if slot['max_capacity'] > 0 else 0,
                    
                    # AI Prediction Details
                    "demand_prediction": {
                        "probability": ai_result['probability'],
                        "demand_level": ai_result['demand_level'],
                        "demand_score": ai_result['demand_score'],
                        "confidence": ai_result['confidence'],
                        "is_recommended": ai_result['is_recommended'],
                        "recommendation": ai_result['recommendation'],
                        "model_type": ai_result['model_type']
                    },
                    
                    # For sorting and filtering
                    "popularity_score": ai_result['demand_score'],
                    "is_high_demand": ai_result['demand_level'] == "High",
                    "is_medium_demand": ai_result['demand_level'] == "Medium",
                    "is_low_demand": ai_result['demand_level'] == "Low"
                })
                
            except Exception as e:
                error_msg = f"Error predicting for slot {slot['id']}: {e}"
                print(error_msg)
                traceback.print_exc()
                errors.append(error_msg)
        
        if not recommendations:
            return BaseResponse(
                success=False, 
                message="Failed to generate predictions for any slots. Check logs for details.", 
                data={
                    "errors": errors,
                    "total_slots_attempted": len(available_slots)
                }
            )

        # Sort by demand score (highest first)
        recommendations.sort(key=lambda x: x["popularity_score"], reverse=True)
        
        # Group by demand level for better organization
        grouped_recommendations = {
            "high_demand": [r for r in recommendations if r["demand_prediction"]["demand_level"] == "High"],
            "medium_demand": [r for r in recommendations if r["demand_prediction"]["demand_level"] == "Medium"],
            "low_demand": [r for r in recommendations if r["demand_prediction"]["demand_level"] == "Low"]
        }
        
        return BaseResponse(
            success=True,
            message=f"Found {len(recommendations)} time slots with predictions",
            data={
                "event_id": event_id,
                "event_title": event['title'],
                "event_description": event.get('description', ''),
                "total_slots": len(available_slots),
                "total_recommendations": len(recommendations),
                "limit": limit,
                "recommendations": recommendations[:limit],
                "all_recommendations": recommendations,  # Include all for frontend filtering
                "grouped_by_demand": grouped_recommendations,
                "summary": {
                    "high_demand_count": len(grouped_recommendations["high_demand"]),
                    "medium_demand_count": len(grouped_recommendations["medium_demand"]),
                    "low_demand_count": len(grouped_recommendations["low_demand"]),
                    "best_time": recommendations[0]["display_time"] if recommendations else None,
                    "best_day": recommendations[0]["day_of_week"] if recommendations else None,
                    "best_slot_id": recommendations[0]["slot_id"] if recommendations else None
                },
                "errors": errors if errors else None
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False, 
            message=f"Error generating recommendations: {str(e)}", 
            data={"error": str(e), "traceback": traceback.format_exc()}
        )
    

@app.get("/events/{event_id}/slots-with-ai-predictions", response_model=BaseResponse)
async def get_time_slots_with_ai_predictions(
    event_id: int,
    sort_by: str = "demand",  # Options: "demand", "time", "availability"
    current_user: dict = Depends(get_current_active_user)
):
    """Get time slots with AI predictions for frontend display"""
    try:
        # Call the recommend endpoint directly (not as HTTP call)
        rec_response = await recommend_slots_endpoint(event_id, limit=100, current_user=current_user)
        
        # Check if the response is successful
        if not rec_response.success:
            return rec_response
        
        # Get the data
        data = rec_response.data
        
        if not data or not isinstance(data, dict):
            return BaseResponse(
                success=False,
                message="No data returned from recommendations",
                data=None
            )
        
        # Get recommendations list
        recommendations = data.get("all_recommendations", data.get("recommendations", []))
        
        if not recommendations:
            return BaseResponse(
                success=True,
                message="No time slots available for this event",
                data=data
            )
        
        # Apply sorting based on parameter
        if sort_by == "time":
            recommendations.sort(key=lambda x: x.get("start_time", ""))
        elif sort_by == "availability":
            recommendations.sort(key=lambda x: x.get("seats_available", 0), reverse=True)
        # Default is already sorted by demand
        
        # Update the data with sorted recommendations
        data["recommendations"] = recommendations[:data.get("limit", 10)]
        data["all_recommendations"] = recommendations
        data["sort_by"] = sort_by
        
        return BaseResponse(
            success=True,
            message=f"Time slots with AI predictions for event: {data.get('event_title', 'Unknown')} (sorted by {sort_by})",
            data=data
        )
        
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Error getting slots with predictions: {str(e)}",
            data={"error": str(e), "traceback": traceback.format_exc()}
        )


@app.get("/ai/diagnostic", response_model=BaseResponse)
async def ai_diagnostic(current_user: dict = Depends(get_current_active_user)):
    """Diagnostic endpoint to check AI model status and test prediction"""
    try:
        import os
        
        # Check model files
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_dir = os.path.join(current_dir, "prediction_service")
        
        model_path = os.path.join(model_dir, "random_forest_model.pkl")
        scaler_path = os.path.join(model_dir, "random_forest_scaler.pkl")
        metadata_path = os.path.join(model_dir, "random_forest_metadata.pkl")
        
        files_exist = {
            "model": os.path.exists(model_path),
            "scaler": os.path.exists(scaler_path),
            "metadata": os.path.exists(metadata_path)
        }
        
        # Try to load model
        model_loaded = False
        model_error = None
        try:
            predictor = BookingDemandPredictor(model_type="random_forest")
            predictor.load_model()
            model_loaded = True
        except Exception as e:
            model_error = str(e)
        
        # Check training data
        stats = get_booking_history_stats()
        
        # Test prediction if model loaded
        test_prediction = None
        prediction_error = None
        if model_loaded:
            try:
                test_prediction = predictor.predict_slot_demand({
                    'event_id': 1,
                    'start_time': datetime.now().isoformat(),
                    'max_capacity': 30,
                    'duration_minutes': 60
                })
            except Exception as e:
                prediction_error = str(e)
        
        return BaseResponse(
            success=True,
            message="AI Diagnostic Complete",
            data={
                "model_files": files_exist,
                "model_directory": model_dir,
                "model_loaded": model_loaded,
                "model_error": model_error,
                "training_data_stats": stats,
                "test_prediction": test_prediction,
                "prediction_error": prediction_error,
                "recommendation": (
                    "✅ AI system is working" if model_loaded and not prediction_error
                    else "⚠️ Train model using /ai/train-models" if not model_loaded
                    else f"❌ Error: {prediction_error or model_error}"
                )
            }
        )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Diagnostic failed: {str(e)}",
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
        traceback.print_exc()
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
        
        for model_type in ["random_forest"]:  # Only random_forest is implemented
            model_path = os.path.join(model_dir, f"{model_type}_model.pkl")
            scaler_path = os.path.join(model_dir, f"{model_type}_scaler.pkl")
            metadata_path = os.path.join(model_dir, f"{model_type}_metadata.pkl")
            
            # Debug: Print file existence
            print(f"{model_type} - Model exists: {os.path.exists(model_path)}")
            print(f"{model_type} - Scaler exists: {os.path.exists(scaler_path)}")
            print(f"{model_type} - Metadata exists: {os.path.exists(metadata_path)}")
            
            models_status[model_type] = {
                "model_exists": os.path.exists(model_path),
                "scaler_exists": os.path.exists(scaler_path),
                "metadata_exists": os.path.exists(metadata_path),
                "ready": all([
                    os.path.exists(model_path),
                    os.path.exists(scaler_path)
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
        traceback.print_exc()
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
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Failed to get data stats: {str(e)}",
            data={"error": str(e)}
        )
    

@app.get("/events/{event_id}/statistics", response_model=BaseResponse)
async def get_event_statistics(event_id: int):
    """Get detailed event statistics"""
    stats = booking_database.get_event_statistics(event_id)
    if stats:
        return BaseResponse(
            success=True,
            message="Event statistics retrieved",
            data=stats
        )
    return BaseResponse(
        success=False,
        message="Event not found",
        data=None
    )


@app.post("/events/{event_id}/bulk-slots", response_model=BaseResponse)
async def create_bulk_time_slots(
    event_id: int,  # Added: Capture from path
    bulk_data: BulkTimeSlotCreate,
    current_user: dict = Depends(require_admin)
):
    from datetime import datetime, timedelta
    
    try:
        created_slots = []
        for date_str in bulk_data.dates:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            for time_str in bulk_data.times:
                hour, minute = map(int, time_str.split(':'))
                start_time = datetime.combine(date_obj, datetime.min.time()).replace(hour=hour, minute=minute)
                end_time = start_time + timedelta(minutes=bulk_data.duration_minutes)
                
                slot_id = booking_database.create_time_slot(
                    event_id,  # Changed: Use path event_id instead of bulk_data.event_id
                    start_time,
                    end_time,
                    bulk_data.max_capacity
                )
                if slot_id:
                    created_slots.append(slot_id)
        
        return BaseResponse(
            success=True,
            message=f"Created {len(created_slots)} time slots",
            data={"created_slots": created_slots}
        )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Failed to create slots: {str(e)}",
            data=None
        )


@app.post("/events/{event_id}/bulk-slots-flexible", response_model=BaseResponse)
async def create_flexible_bulk_time_slots(
    event_id: int,
    bulk_data: FlexibleBulkTimeSlotCreate,
    current_user: dict = Depends(require_admin)
):
    try:
        created_slots = []
        errors = []
        
        # Fetch event once
        event = booking_database.get_event_by_id(event_id)
        if not event:
            return BaseResponse(success=False, message="Event not found", data=None)
        
        event_capacity = event["capacity"]
        event_start = datetime.fromisoformat(event["start_time"].replace("Z", "+00:00"))
        event_end = datetime.fromisoformat(event["end_time"].replace("Z", "+00:00"))

        for date_slot in bulk_data.date_slots:
            try:
                date_obj = datetime.strptime(date_slot.date, "%Y-%m-%d").date()
                
                for time_range in date_slot.time_ranges:
                    try:
                        start_hour, start_min = map(int, time_range.start_time.split(':'))
                        end_hour, end_min = map(int, time_range.end_time.split(':'))
                        
                        start_time = datetime.combine(date_obj, datetime.min.time()).replace(
                            hour=start_hour, minute=start_min
                        )
                        end_time = datetime.combine(date_obj, datetime.min.time()).replace(
                            hour=end_hour, minute=end_min
                        )

                        if end_time <= start_time:
                            errors.append({
                                "date": date_slot.date,
                                "time_range": f"{time_range.start_time}-{time_range.end_time}",
                                "error": "End time must be after start time"
                            })
                            continue

                        # Critical: Check if slot is within event overall date range
                        if not (event_start <= start_time and end_time <= event_end):
                            errors.append({
                                "date": date_slot.date,
                                "time_range": f"{time_range.start_time}-{time_range.end_time}",
                                "error": f"Slot outside event date range ({event_start.date()} to {event_end.date()})"
                            })
                            continue

                        slot_id = booking_database.create_time_slot(
                            event_id,
                            start_time,
                            end_time,
                            event_capacity,
                        )
                        
                        if slot_id:
                            created_slots.append({
                                "slot_id": slot_id,
                                "date": date_slot.date,
                                "start_time": start_time.isoformat(),
                                "end_time": end_time.isoformat()
                            })
                        else:
                            # This case now only happens on overlap or DB error
                            errors.append({
                                "date": date_slot.date,
                                "time_range": f"{time_range.start_time}-{time_range.end_time}",
                                "error": "Overlapping time slot or database error"
                            })
                            
                    except Exception as e:
                        errors.append({
                            "date": date_slot.date,
                            "time_range": f"{time_range.start_time}-{time_range.end_time}",
                            "error": f"Invalid time format: {str(e)}"
                        })
            except Exception as e:
                errors.append({
                    "date": date_slot.date,
                    "error": f"Invalid date: {str(e)}"
                })

        return BaseResponse(
            success=len(created_slots) > 0 or len(errors) == 0,
            message=f"Created {len(created_slots)} time slots"
                    + (f", {len(errors)} failed" if errors else ""),
            data={
                "created_slots": created_slots,
                "total_created": len(created_slots),
                "errors": errors or None
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(success=False, message=f"Server error: {str(e)}", data=None)


@app.post("/events/bulk-slots-simple", response_model=BaseResponse)
async def create_simple_bulk_time_slots(
    bulk_data: SimpleBulkTimeSlotCreate,
    current_user: dict = Depends(require_admin)
):
    """
    Create time slots with simple format (same times for all dates)
    
    Example:
    {
      "event_id": 1,
      "dates": ["2024-12-10", "2024-12-11"],
      "times": ["09:00", "14:00", "16:00"],
      "duration_minutes": 120
    }
    
    This will create:
    - Dec 10: 09:00-11:00, 14:00-16:00, 16:00-18:00
    - Dec 11: 09:00-11:00, 14:00-16:00, 16:00-18:00
    """
    try:
        created_slots = []
        errors = []
        
        for date_str in bulk_data.dates:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            for time_str in bulk_data.times:
                try:
                    hour, minute = map(int, time_str.split(':'))
                    start_time = datetime.combine(
                        date_obj, 
                        datetime.min.time()
                    ).replace(hour=hour, minute=minute)
                    end_time = start_time + timedelta(minutes=bulk_data.duration_minutes)
                    
                    slot_id = booking_database.create_time_slot(
                        bulk_data.event_id,
                        start_time,
                        end_time,
                        bulk_data.max_capacity
                    )
                    
                    if slot_id:
                        created_slots.append({
                            "slot_id": slot_id,
                            "date": date_str,
                            "time": time_str,
                            "start_time": start_time.isoformat(),
                            "end_time": end_time.isoformat()
                        })
                    else:
                        errors.append({
                            "date": date_str,
                            "time": time_str,
                            "error": "Failed to create slot"
                        })
                        
                except Exception as e:
                    errors.append({
                        "date": date_str,
                        "time": time_str,
                        "error": str(e)
                    })
        
        return BaseResponse(
            success=len(created_slots) > 0,
            message=f"Created {len(created_slots)} time slots",
            data={
                "created_slots": created_slots,
                "total_created": len(created_slots),
                "errors": errors if errors else None
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Failed to create slots: {str(e)}",
            data=None
        )


@app.get("/events/{event_id}/booking-flow", response_model=BaseResponse)
async def get_booking_flow_data(event_id: int):
    """Get all data needed for booking flow in one call"""
    try:
        event = booking_database.get_event_by_id(event_id)
        slots_by_date = await get_slots_grouped_by_date(event_id)
        capacity = await get_event_capacity_status(event_id)
        
        return BaseResponse(
            success=True,
            message="Booking flow data",
            data={
                "event": event,
                "slots_by_date": slots_by_date.data if slots_by_date.success else {},
                "capacity": capacity.data if capacity.success else {}
            }
        )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Failed to get booking flow data: {str(e)}",
            data=None
        )

# ========== NOTIFICATION ENDPOINTS ==========

@app.post("/notifications/send-email", response_model=BaseResponse)
async def send_email_endpoint(
    request: EmailNotificationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_active_user)
):
    """Send email notification"""
    try:
        success, message, notification_id = send_email_notification(
            recipient_email=request.recipient_email,
            recipient_name=request.recipient_name,
            notification_type=request.notification_type.value,
            data=request.data
        )
        
        return BaseResponse(
            success=success,
            message=message,
            data={
                "notification_id": notification_id,
                "recipient": request.recipient_email,
                "type": request.notification_type.value
            }
        )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Failed to send notification: {str(e)}",
            data=None
        )


@app.post("/notifications/send-booking-confirmation", response_model=BaseResponse)
async def send_booking_confirmation(
    booking_data: dict,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Send booking confirmation email
    Expected booking_data:
    {
        "recipient_email": "user@example.com",
        "recipient_name": "John Doe",
        "event_title": "AI Workshop",
        "start_time": "2024-12-10 10:00 AM",
        "duration": 60,
        "booking_id": 123
    }
    """
    try:
        success, message, notification_id = send_email_notification(
            recipient_email=booking_data["recipient_email"],
            recipient_name=booking_data["recipient_name"],
            notification_type="booking_confirmation",
            data=booking_data
        )
        
        return BaseResponse(
            success=success,
            message=message,
            data={"notification_id": notification_id}
        )
    except KeyError as e:
        return BaseResponse(
            success=False,
            message=f"Missing required field: {str(e)}",
            data=None
        )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Error: {str(e)}",
            data=None
        )


@app.post("/notifications/send-cancellation", response_model=BaseResponse)
async def send_cancellation_notification(
    booking_data: dict,
    current_user: dict = Depends(get_current_active_user)
):
    """Send booking cancellation email"""
    try:
        success, message, notification_id = send_email_notification(
            recipient_email=booking_data["recipient_email"],
            recipient_name=booking_data["recipient_name"],
            notification_type="booking_cancellation",
            data=booking_data
        )
        
        return BaseResponse(
            success=success,
            message=message,
            data={"notification_id": notification_id}
        )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Error: {str(e)}",
            data=None
        )


@app.post("/notifications/send-ai-recommendation", response_model=BaseResponse)
async def send_ai_recommendation(
    recommendation_data: dict,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Send AI-powered slot recommendations
    Expected data:
    {
        "recipient_email": "user@example.com",
        "recipient_name": "John Doe",
        "recommendations": "<ul><li>Slot 1: Mon 10 AM (High demand)</li></ul>",
        "confidence": 85
    }
    """
    try:
        success, message, notification_id = send_email_notification(
            recipient_email=recommendation_data["recipient_email"],
            recipient_name=recommendation_data["recipient_name"],
            notification_type="ai_recommendation",
            data=recommendation_data
        )
        
        return BaseResponse(
            success=success,
            message=message,
            data={"notification_id": notification_id}
        )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Error: {str(e)}",
            data=None
        )


@app.post("/notifications/send-reminder", response_model=BaseResponse)
async def send_booking_reminder(
    reminder_data: dict,
    current_user: dict = Depends(get_current_active_user)
):
    """Send booking reminder"""
    try:
        success, message, notification_id = send_email_notification(
            recipient_email=reminder_data["recipient_email"],
            recipient_name=reminder_data["recipient_name"],
            notification_type="booking_reminder",
            data=reminder_data
        )
        
        return BaseResponse(
            success=success,
            message=message,
            data={"notification_id": notification_id}
        )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Error: {str(e)}",
            data=None
        )


@app.post("/notifications/bulk", response_model=BaseResponse)
async def send_bulk_notification(
    request: BulkNotificationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_admin)
):
    """Send bulk notifications (Admin only)"""
    try:
        results = []
        success_count = 0
        failed_count = 0
        
        for recipient_email in request.recipients:
            success, message, notification_id = send_email_notification(
                recipient_email=recipient_email,
                recipient_name="Valued User",
                notification_type=request.notification_type.value,
                data=request.data
            )
            
            results.append({
                "email": recipient_email,
                "success": success,
                "notification_id": notification_id
            })
            
            if success:
                success_count += 1
            else:
                failed_count += 1
        
        return BaseResponse(
            success=True,
            message=f"Bulk notification completed: {success_count} sent, {failed_count} failed",
            data={
                "total": len(request.recipients),
                "success": success_count,
                "failed": failed_count,
                "results": results
            }
        )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Bulk notification failed: {str(e)}",
            data=None
        )


@app.get("/notifications/history/{user_email}", response_model=BaseResponse)
async def get_notification_history(
    user_email: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get notification history for a user"""
    try:
        # Check if user can only see their own history (unless admin)
        if current_user.get("role") != "admin":
            if current_user.get("username") != user_email.split("@")[0]:
                return BaseResponse(
                    success=False,
                    message="Unauthorized: Can only view your own history",
                    data=None
                )
        
        history = notification_database.get_notification_history(user_email)
        
        return BaseResponse(
            success=True,
            message=f"Retrieved {len(history)} notifications",
            data={
                "count": len(history),
                "notifications": history
            }
        )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Error fetching history: {str(e)}",
            data=None
        )


@app.get("/notifications/templates", response_model=BaseResponse)
async def get_available_templates(
    current_user: dict = Depends(get_current_active_user)
):
    """Get list of available notification templates"""
    templates = [
        {
            "name": "booking_confirmation",
            "description": "Sent when a booking is confirmed",
            "required_fields": ["event_title", "start_time", "duration", "booking_id"]
        },
        {
            "name": "booking_cancellation",
            "description": "Sent when a booking is cancelled",
            "required_fields": ["event_title", "start_time", "booking_id"]
        },
        {
            "name": "ai_recommendation",
            "description": "AI-powered slot recommendations",
            "required_fields": ["recommendations", "confidence"]
        },
        {
            "name": "booking_reminder",
            "description": "Reminder before event",
            "required_fields": ["event_title", "start_time", "location"]
        }
    ]
    
    return BaseResponse(
        success=True,
        message="Available templates",
        data={"templates": templates}
    )


@app.get("/notifications/stats", response_model=BaseResponse)
async def get_notification_stats(
    current_user: dict = Depends(require_admin)
):
    """Get notification statistics (Admin only)"""
    try:
        with notification_database.get_notification_db_connection() as conn:
            cursor = conn.cursor()
            
            # Total notifications
            total = cursor.execute("SELECT COUNT(*) as count FROM notifications").fetchone()["count"]
            
            # By status
            by_status = cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM notifications 
                GROUP BY status
            """).fetchall()
            
            # By type
            by_type = cursor.execute("""
                SELECT notification_type, COUNT(*) as count 
                FROM notifications 
                GROUP BY notification_type
            """).fetchall()
            
            # Recent (last 24 hours)
            recent = cursor.execute("""
                SELECT COUNT(*) as count 
                FROM notifications 
                WHERE created_at > datetime('now', '-1 day')
            """).fetchone()["count"]
            
            return BaseResponse(
                success=True,
                message="Notification statistics",
                data={
                    "total_notifications": total,
                    "recent_24h": recent,
                    "by_status": [dict(row) for row in by_status],
                    "by_type": [dict(row) for row in by_type]
                }
            )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(
            success=False,
            message=f"Error fetching stats: {str(e)}",
            data=None
        )

# ========== ADMIN ANALYTICS & CHARTS ==========

@app.get("/admin/charts/booking-trends", response_model=BaseResponse)
async def get_booking_trends_chart(
    period: str = "monthly",  # daily, weekly, monthly
    current_user: dict = Depends(require_admin)
):
    """Get booking trends for Chart.js"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if period == "daily":
                query = """
                    SELECT DATE(b.created_at) as date, COUNT(*) as count
                    FROM bookings b 
                    WHERE b.status != 'cancelled'
                    GROUP BY DATE(b.created_at) 
                    ORDER BY date DESC 
                    LIMIT 30
                """
            elif period == "weekly":
                query = """
                    SELECT strftime('%Y-%W', b.created_at) as week, COUNT(*) as count
                    FROM bookings b
                    WHERE b.status != 'cancelled'
                    GROUP BY week 
                    ORDER BY week DESC 
                    LIMIT 12
                """
            else:  # monthly
                query = """
                    SELECT strftime('%Y-%m', b.created_at) as month, COUNT(*) as count
                    FROM bookings b
                    WHERE b.status != 'cancelled'
                    GROUP BY month 
                    ORDER BY month DESC 
                    LIMIT 12
                """
            
            cursor.execute(query)
            data = cursor.fetchall()
            
            # Convert to list of dicts
            data_dicts = [dict(row) for row in data]
            
            return BaseResponse(
                success=True,
                message=f"Booking trends ({period})",
                data={
                    "labels": [row["date"] if period=="daily" else row["week"] if period=="weekly" else row["month"] for row in data_dicts][::-1],
                    "datasets": [{
                        "label": "Bookings",
                        "data": [row["count"] for row in data_dicts][::-1],
                        "borderColor": "rgb(75, 192, 192)",
                        "backgroundColor": "rgba(75, 192, 192, 0.2)",
                        "tension": 0.4
                    }]
                }
            )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(success=False, message=str(e), data=None)

@app.get("/admin/charts/event-popularity", response_model=BaseResponse)
async def get_event_popularity_chart(
    limit: int = 10,
    current_user: dict = Depends(require_admin)
):
    """Get most popular events for bar chart"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    e.title as event_title,
                    COUNT(b.id) as booking_count,
                    SUM(b.quantity) as total_spots,
                    AVG(ts.max_capacity - ts.available_slots) as avg_utilization
                FROM events e
                LEFT JOIN time_slots ts ON e.id = ts.event_id
                LEFT JOIN bookings b ON ts.id = b.time_slot_id AND b.status != 'cancelled'
                GROUP BY e.id
                ORDER BY booking_count DESC
                LIMIT ?
            """
            
            cursor.execute(query, (limit,))
            events = [dict(row) for row in cursor.fetchall()]
            
            return BaseResponse(
                success=True,
                message="Event popularity chart",
                data={
                    "labels": [e["event_title"] for e in events],
                    "datasets": [
                        {
                            "label": "Number of Bookings",
                            "data": [e["booking_count"] or 0 for e in events],
                            "backgroundColor": "rgba(54, 162, 235, 0.5)",
                            "borderColor": "rgba(54, 162, 235, 1)",
                            "borderWidth": 1
                        },
                        {
                            "label": "Total Spots Booked",
                            "data": [e["total_spots"] or 0 for e in events],
                            "backgroundColor": "rgba(255, 99, 132, 0.5)",
                            "borderColor": "rgba(255, 99, 132, 1)",
                            "borderWidth": 1
                        }
                    ]
                }
            )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(success=False, message=str(e), data=None)

@app.get("/admin/charts/booking-status", response_model=BaseResponse)
async def get_booking_status_chart(current_user: dict = Depends(require_admin)):
    """Pie chart of booking statuses"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    status,
                    COUNT(*) as count,
                    SUM(quantity) as total_spots
                FROM bookings 
                GROUP BY status
            """
            
            cursor.execute(query)
            statuses = [dict(row) for row in cursor.fetchall()]
            
            # Color mapping for different statuses
            color_map = {
                "confirmed": "#4CAF50",  # Green
                "pending": "#FFC107",     # Amber
                "cancelled": "#F44336",   # Red
                "completed": "#2196F3"    # Blue
            }
            
            return BaseResponse(
                success=True,
                message="Booking status distribution",
                data={
                    "labels": [s["status"].capitalize() for s in statuses],
                    "datasets": [{
                        "data": [s["count"] for s in statuses],
                        "backgroundColor": [color_map.get(s["status"], "#9E9E9E") for s in statuses],
                        "borderWidth": 2
                    }]
                }
            )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(success=False, message=str(e), data=None)

@app.get("/admin/charts/peak-hours", response_model=BaseResponse)
async def get_peak_booking_hours(current_user: dict = Depends(require_admin)):
    """Line chart showing bookings by hour of day"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    strftime('%H', ts.start_time) as hour,
                    COUNT(DISTINCT b.id) as booking_count,
                    SUM(b.quantity) as total_spots
                FROM bookings b
                JOIN time_slots ts ON b.time_slot_id = ts.id
                WHERE b.status != 'cancelled'
                GROUP BY hour
                ORDER BY hour
            """
            
            cursor.execute(query)
            hours_data = [dict(row) for row in cursor.fetchall()]
            
            # Create labels for all 24 hours
            all_hours = [f"{h:02d}:00" for h in range(24)]
            hour_dict = {h["hour"]: h for h in hours_data}
            
            return BaseResponse(
                success=True,
                message="Peak booking hours",
                data={
                    "labels": all_hours,
                    "datasets": [
                        {
                            "label": "Number of Bookings",
                            "data": [hour_dict.get(str(h).zfill(2), {}).get("booking_count", 0) for h in range(24)],
                            "borderColor": "rgb(255, 159, 64)",
                            "backgroundColor": "rgba(255, 159, 64, 0.2)",
                            "fill": True
                        },
                        {
                            "label": "Total Spots",
                            "data": [hour_dict.get(str(h).zfill(2), {}).get("total_spots", 0) for h in range(24)],
                            "borderColor": "rgb(75, 192, 192)",
                            "backgroundColor": "rgba(75, 192, 192, 0.2)",
                            "fill": True
                        }
                    ]
                }
            )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(success=False, message=str(e), data=None)

@app.get("/admin/charts/ai-performance", response_model=BaseResponse)
async def get_ai_performance_chart(current_user: dict = Depends(require_admin)):
    """Chart showing AI prediction accuracy over time"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get actual vs predicted (simplified version)
            query = """
                SELECT 
                    DATE(b.created_at) as date,
                    COUNT(*) as actual_bookings,
                    -- For real implementation, you'd join with prediction history table
                    -- This is a placeholder
                    ROUND(COUNT(*) * 0.8) as predicted_bookings  -- Sample prediction
                FROM bookings b
                WHERE b.status = 'confirmed'
                GROUP BY DATE(b.created_at)
                ORDER BY date DESC
                LIMIT 14
            """
            
            cursor.execute(query)
            data = [dict(row) for row in cursor.fetchall()]
            
            return BaseResponse(
                success=True,
                message="AI Prediction Performance",
                data={
                    "labels": [d["date"] for d in data][::-1],
                    "datasets": [
                        {
                            "label": "Actual Bookings",
                            "data": [d["actual_bookings"] for d in data][::-1],
                            "borderColor": "rgb(54, 162, 235)",
                            "backgroundColor": "rgba(54, 162, 235, 0.2)",
                        },
                        {
                            "label": "Predicted Bookings",
                            "data": [d["predicted_bookings"] for d in data][::-1],
                            "borderColor": "rgb(255, 99, 132)",
                            "backgroundColor": "rgba(255, 99, 132, 0.2)",
                            "borderDash": [5, 5]
                        }
                    ]
                }
            )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(success=False, message=str(e), data=None)

@app.get("/admin/charts/capacity-utilization", response_model=BaseResponse)
async def get_capacity_utilization_chart(current_user: dict = Depends(require_admin)):
    """Gauge chart for capacity utilization"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    e.title,
                    SUM(ts.max_capacity) as total_capacity,
                    SUM(ts.max_capacity - ts.available_slots) as used_capacity,
                    ROUND((SUM(ts.max_capacity - ts.available_slots) * 100.0 / NULLIF(SUM(ts.max_capacity), 0)), 2) as utilization_percentage
                FROM events e
                JOIN time_slots ts ON e.id = ts.event_id
                GROUP BY e.id
                HAVING total_capacity > 0
                ORDER BY utilization_percentage DESC
                LIMIT 5
            """
            
            cursor.execute(query)
            events = [dict(row) for row in cursor.fetchall()]
            
            return BaseResponse(
                success=True,
                message="Capacity utilization by event",
                data={
                    "labels": [e["title"] for e in events],
                    "datasets": [{
                        "label": "Utilization %",
                        "data": [e["utilization_percentage"] for e in events],
                        "backgroundColor": [
                            "#FF6384" if p > 80 else  # Red for >80%
                            "#FFCE56" if p > 50 else  # Yellow for >50%
                            "#4BC0C0"                 # Green for <=50%
                            for p in [e["utilization_percentage"] for e in events]
                        ]
                    }]
                }
            )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(success=False, message=str(e), data=None)

@app.get("/admin/charts/user-registration", response_model=BaseResponse)
async def get_user_registration_chart(current_user: dict = Depends(require_admin)):
    """User registration timeline"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Since we don't have user registration dates in login table,
            # we'll use booking creation as proxy
            query = """
                SELECT 
                    strftime('%Y-%m', b.created_at) as month,
                    COUNT(DISTINCT b.user_id) as active_users
                FROM bookings b
                WHERE b.status != 'cancelled'
                GROUP BY month
                ORDER BY month DESC
                LIMIT 12
            """
            
            cursor.execute(query)
            data = [dict(row) for row in cursor.fetchall()]
            
            return BaseResponse(
                success=True,
                message="User activity trends",
                data={
                    "labels": [d["month"] for d in data][::-1],
                    "datasets": [{
                        "label": "Active Users",
                        "data": [d["active_users"] for d in data][::-1],
                        "borderColor": "rgb(153, 102, 255)",
                        "backgroundColor": "rgba(153, 102, 255, 0.2)",
                        "fill": True
                    }]
                }
            )
    except Exception as e:
        traceback.print_exc()
        return BaseResponse(success=False, message=str(e), data=None)


        
# ========== HEALTH CHECK ==========

@app.get("/")
async def root():
    return BaseResponse(
        success=True,
        message="SmartBookingAI Unified API is running",
        data={
            "version": "2.0.0",
            "services": ["user-management", "booking-system", "ai-prediction", "notification-service"],
            "status": "healthy"
        }
    )

@app.get("/health")
async def health_check():
    return BaseResponse(
        success=True,
        message="Service is healthy",
        data={
            "status": "healthy", 
            "service": "unified-booking-service",
            "email_configured": bool(email_service.sender_password)
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)