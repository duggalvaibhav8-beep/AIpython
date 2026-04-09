import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from fastapi import FastAPI, HTTPException, Depends
from typing import List
from booking_models import (
    EventCreate, EventResponse, TimeSlotResponse, BookingCreate, 
    BookingResponse, BookingUpdate, AvailabilityRequest,
    BaseResponse, EventBaseResponse, EventsListResponse, 
    TimeSlotsListResponse, BookingBaseResponse, BookingsListResponse,
    BookingStatus
)

import booking_database
from user_services.auth import get_current_active_user  
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Booking Service",
    description="Microservice for event booking and management",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origins=["*"],
    expose_headers=["*"],
)

# Event Management Endpoints
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

# Time Slot Endpoints
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

# Booking Endpoints
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

# Health check endpoint
@app.get("/health")
async def health_check():
    return BaseResponse(
        success=True,
        message="Service is healthy",
        data={"status": "healthy", "service": "booking-service"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)