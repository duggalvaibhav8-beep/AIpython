from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum

class NotificationType(str, Enum):
    BOOKING_CONFIRMATION = "booking_confirmation"
    BOOKING_CANCELLATION = "booking_cancellation"
    BOOKING_REMINDER = "booking_reminder"
    AI_RECOMMENDATION = "ai_recommendation"
    EVENT_UPDATE = "event_update"
    SLOT_AVAILABILITY = "slot_availability"

class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"

class EmailNotificationRequest(BaseModel):
    recipient_email: EmailStr
    recipient_name: str
    notification_type: NotificationType
    subject: Optional[str] = None
    data: dict  # Contains booking details, event info, etc.

class SMSNotificationRequest(BaseModel):
    phone_number: str
    recipient_name: str
    notification_type: NotificationType
    message: str

class BulkNotificationRequest(BaseModel):
    recipients: List[EmailStr]
    notification_type: NotificationType
    subject: str
    data: dict

class NotificationResponse(BaseModel):
    id: Optional[int] = None
    recipient_email: Optional[str] = None
    notification_type: str
    status: str  # sent, failed, pending
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None

class NotificationHistoryResponse(BaseModel):
    id: int
    recipient_email: str
    notification_type: str
    subject: str
    status: str
    sent_at: datetime
    opened_at: Optional[datetime] = None

class BaseResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
