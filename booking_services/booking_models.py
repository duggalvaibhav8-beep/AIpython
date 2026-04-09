# from pydantic import BaseModel
# from typing import Optional, TypeVar, Generic
# from datetime import datetime
# from enum import Enum

# T = TypeVar('T')

# class BaseResponse(BaseModel, Generic[T]):
#     success: bool
#     message: str
#     data: Optional[T] = None

# class BookingStatus(str, Enum):
#     CONFIRMED = "confirmed"
#     CANCELLED = "cancelled"
#     PENDING = "pending"
#     COMPLETED = "completed"

# class EventCreate(BaseModel):
#     title: str
#     description: Optional[str] = None
#     capacity: int
#     duration_minutes: int = 60
#     created_by: int

# class EventResponse(BaseModel):
#     id: int
#     title: str
#     description: Optional[str]
#     capacity: int
#     duration_minutes: int
#     created_by: int
#     created_at: datetime

# class EventUpdate(BaseModel):
#     title: Optional[str] = None
#     description: Optional[str] = None
#     capacity: Optional[int] = None
#     duration_minutes: Optional[int] = None

# class TimeSlotCreate(BaseModel):
#     event_id: int
#     start_time: datetime
#     end_time: datetime
#     max_capacity: Optional[int] = None

# class TimeSlotResponse(BaseModel):
#     id: int
#     event_id: int
#     start_time: datetime
#     end_time: datetime
#     max_capacity: int
#     available_slots: int
#     is_available: bool

# class BookingCreate(BaseModel):
#     time_slot_id: int

# class BookingResponse(BaseModel):
#     id: int
#     user_id: int
#     time_slot_id: int
#     status: BookingStatus
#     created_at: datetime
#     event_title: Optional[str] = None
#     start_time: Optional[datetime] = None
#     end_time: Optional[datetime] = None

# class AvailabilityRequest(BaseModel):
#     event_id: int
#     date: str  # YYYY-MM-DD format

# class BookingUpdate(BaseModel):
#     status: BookingStatus

# # Type aliases for common responses
# EventBaseResponse = BaseResponse[EventResponse]
# EventsListResponse = BaseResponse[list[EventResponse]]
# TimeSlotBaseResponse = BaseResponse[TimeSlotResponse]
# TimeSlotsListResponse = BaseResponse[list[TimeSlotResponse]]
# BookingBaseResponse = BaseResponse[BookingResponse]
# BookingsListResponse = BaseResponse[list[BookingResponse]]


from pydantic import BaseModel, Field, validator
from typing import Optional, TypeVar, Generic, List
from datetime import datetime
from enum import Enum

T = TypeVar('T')

class BaseResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None

class BookingStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    PENDING = "pending"
    COMPLETED = "completed"



class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    capacity: int
    duration_minutes: int = 60
    start_time: datetime  # New: Required overall event start time (e.g., 2023-12-01T09:00:00)
    end_time: datetime    # New: Required overall event end time (e.g., 2023-12-31T17:00:00)
    created_by: int


class EventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    capacity: int
    duration_minutes: int
    start_time: datetime
    end_time: datetime
    created_by: int
    created_at: datetime
    
    # Add these fields
    available_capacity: Optional[int] = None
    booked_capacity: Optional[int] = None
    total_capacity: Optional[int] = None

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    capacity: Optional[int] = None
    duration_minutes: Optional[int] = None
    start_time: Optional[datetime] = None  # New: Allow updating
    end_time: Optional[datetime] = None    # New: Allow updating

class TimeSlotCreate(BaseModel):
    event_id: int
    start_time: datetime
    end_time: datetime
    max_capacity: Optional[int] = None

class TimeSlotResponse(BaseModel):
    id: int
    event_id: int
    start_time: datetime
    end_time: datetime
    max_capacity: int
    available_slots: int
    is_available: bool
    
    # Add these optional fields
    event_title: Optional[str] = None
    percentage_full: Optional[float] = None
    status: Optional[str] = None  # "available", "filling_fast", "full"



class TimeSlotAvailability(BaseModel):
    """Detailed availability information for a time slot"""
    slot_id: int
    start_time: datetime
    end_time: datetime
    time_display: str  # e.g., "09:00 AM - 10:00 AM"
    max_capacity: int
    available_capacity: int
    booked_capacity: int
    percentage_full: float
    status: str  # "available", "filling_fast", "almost_full", "fully_booked"
    can_book: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "slot_id": 5,
                "start_time": "2024-12-10T09:00:00",
                "end_time": "2024-12-10T10:00:00",
                "time_display": "09:00 AM - 10:00 AM",
                "max_capacity": 30,
                "available_capacity": 25,
                "booked_capacity": 5,
                "percentage_full": 16.7,
                "status": "available",
                "can_book": True
            }
        }


class DailyTimeSlots(BaseModel):
    """Time slots grouped by a specific date"""
    date: str  # YYYY-MM-DD
    day_name: str  # Monday, Tuesday, etc.
    slots: List[TimeSlotAvailability]
    total_slots: int
    available_slots: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-12-10",
                "day_name": "Monday",
                "slots": [],
                "total_slots": 4,
                "available_slots": 3
            }
        }


class EventWithCapacity(BaseModel):
    """Event information including capacity statistics"""
    id: int
    title: str
    description: Optional[str]
    capacity: int  # Per time slot capacity
    duration_minutes: int
    start_time: datetime
    end_time: datetime
    created_by: int
    created_at: datetime
    
    # Capacity statistics
    total_capacity: int  # Sum of all time slot capacities
    available_capacity: int
    booked_capacity: int
    percentage_booked: float
    capacity_status: str  # "available", "filling_up", "almost_full", "sold_out"
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "title": "AI Workshop",
                "capacity": 30,
                "total_capacity": 120,  # 4 slots × 30
                "available_capacity": 95,
                "booked_capacity": 25,
                "percentage_booked": 20.8,
                "capacity_status": "available"
            }
        }


class BookingCreate(BaseModel):
    event_id: int = Field(description="ID of the event to book")
    time_slot_id: Optional[int] = Field(default=None, description="Specific time slot ID (optional; auto-assign if not provided)")
    quantity: int = Field(default=1, ge=1, description="Number of slots/seats to book (default: 1)")

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": 1,
                "time_slot_id": 5,  # Optional
                "quantity": 2
            }
        }

class BookingResponse(BaseModel):
    id: int
    user_id: int
    time_slot_id: int
    status: BookingStatus
    quantity: int  # Updated: Include quantity
    created_at: datetime
    event_title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class AvailabilityRequest(BaseModel):
    event_id: int
    date: str  # YYYY-MM-DD format

class BookingUpdate(BaseModel):
    status: BookingStatus

class BookingValidationRequest(BaseModel):
    """Request to validate booking before creation"""
    event_id: int
    time_slot_id: Optional[int] = None
    quantity: int = Field(default=1, ge=1, le=50)
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v < 1:
            raise ValueError('Quantity must be at least 1')
        if v > 50:
            raise ValueError('Quantity cannot exceed 50 per booking')
        return v
    

class BookingValidationResponse(BaseModel):
    """Response from booking validation"""
    can_book: bool
    requested_quantity: int
    available_capacity: int
    reason: Optional[str] = None
    suggested_slots: Optional[List[TimeSlotAvailability]] = None
    time_slot_info: Optional[dict] = None


class CalendarDay(BaseModel):
    """Availability for a single day"""
    date: str  # YYYY-MM-DD
    day_number: int
    has_slots: bool
    total_slots: int
    available_slots: int
    status: str  # "available", "limited", "full", "no_slots"


class MonthlyCalendar(BaseModel):
    """Calendar view for a month"""
    year: int
    month: int
    month_name: str
    event_id: int
    event_title: str
    days: List[CalendarDay]

class BulkTimeSlotCreate(BaseModel):
    """Create multiple time slots at once"""
    # Removed: event_id (now provided via path in endpoint)
    dates: List[str]  # List of dates in YYYY-MM-DD format
    times: List[str]  # List of times in HH:MM format (24-hour)
    duration_minutes: int = 60
    max_capacity: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "dates": ["2024-12-10", "2024-12-11", "2024-12-12"],
                "times": ["09:00", "14:00", "16:00"],
                "duration_minutes": 60,
                "max_capacity": 30
            }
        }
    
    @validator('times')
    def validate_times(cls, v):
        for t in v:
            try:
                hour, minute = map(int, t.split(':'))
                if not (0 <= hour < 24 and 0 <= minute < 60):
                    raise ValueError(f"Invalid time format: {t}")
            except:
                raise ValueError(f"Time must be in HH:MM format: {t}")
        return v
    

class EventStatistics(BaseModel):
    """Detailed statistics for an event"""
    event_id: int
    event_title: str
    
    # Slot statistics
    total_time_slots: int
    available_time_slots: int
    
    # Capacity statistics
    total_capacity: int
    available_capacity: int
    booked_capacity: int
    percentage_booked: float
    
    # Booking statistics
    total_bookings: int
    confirmed_bookings: int
    cancelled_bookings: int
    unique_users: int
    
    # Time range
    earliest_slot: Optional[datetime]
    latest_slot: Optional[datetime]


class UserBookingSummary(BaseModel):
    """Summary of user's bookings"""
    user_id: int
    total_bookings: int
    confirmed_bookings: int
    cancelled_bookings: int
    upcoming_bookings: int
    past_bookings: int
    total_spots_booked: int
    bookings: List[BookingResponse]


class TimeRange(BaseModel):
    """Represents a time range for a slot"""
    start_time: str = Field(description="Start time in HH:MM format (24-hour)")
    end_time: str = Field(description="End time in HH:MM format (24-hour)")
    
    @validator('start_time', 'end_time')
    def validate_time_format(cls, v):
        try:
            hour, minute = map(int, v.split(':'))
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError(f"Invalid time: {v}")
        except:
            raise ValueError(f"Time must be in HH:MM format: {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_time": "09:00",
                "end_time": "11:00"
            }
        }


class DateTimeSlots(BaseModel):
    """Time slots for a specific date"""
    date: str = Field(description="Date in YYYY-MM-DD format")
    time_ranges: List[TimeRange] = Field(description="List of time ranges for this date")
    
    @validator('date')
    def validate_date(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Date must be in YYYY-MM-DD format: {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-12-11",
                "time_ranges": [
                    {"start_time": "09:00", "end_time": "12:00"},
                    {"start_time": "14:00", "end_time": "16:00"},
                    {"start_time": "18:00", "end_time": "20:00"}
                ]
            }
        }


class FlexibleBulkTimeSlotCreate(BaseModel):
    date_slots: List[DateTimeSlots] = Field(description="Date-specific time slot configurations")
    # max_capacity: Optional[int] = Field(default=None, description="Max capacity per slot (uses event capacity if not provided)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "date_slots": [
                    {
                        "date": "2024-12-11",
                        "time_ranges": [
                            {"start_time": "09:00", "end_time": "12:00"},
                            {"start_time": "14:00", "end_time": "16:00"},
                            {"start_time": "18:00", "end_time": "20:00"}
                        ]
                    },
                    {
                        "date": "2024-12-12",
                        "time_ranges": [
                            {"start_time": "13:00", "end_time": "14:00"},
                            {"start_time": "15:00", "end_time": "16:00"}
                        ]
                    }
                ]
            }
        }


class SimpleBulkTimeSlotCreate(BaseModel):
    """Simpler format: Same times for all dates (backward compatible)"""
    event_id: int
    dates: List[str]
    times: List[str]  # Simple time strings like ["09:00", "14:00"]
    duration_minutes: int = 60
    max_capacity: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": 1,
                "dates": ["2024-12-10", "2024-12-11"],
                "times": ["09:00", "14:00", "16:00"],
                "duration_minutes": 60
            }
        }

# Type aliases for common responses
EventBaseResponse = BaseResponse[EventResponse]
EventsListResponse = BaseResponse[list[EventResponse]]
TimeSlotBaseResponse = BaseResponse[TimeSlotResponse]
TimeSlotsListResponse = BaseResponse[list[TimeSlotResponse]]
BookingBaseResponse = BaseResponse[BookingResponse]
BookingsListResponse = BaseResponse[list[BookingResponse]]

EventWithCapacityResponse = BaseResponse[EventWithCapacity]
EventStatisticsResponse = BaseResponse[EventStatistics]
CalendarResponse = BaseResponse[MonthlyCalendar]
DailyTimeSlotsResponse = BaseResponse[List[DailyTimeSlots]]
ValidationResponse = BaseResponse[BookingValidationResponse]
UserSummaryResponse = BaseResponse[UserBookingSummary]