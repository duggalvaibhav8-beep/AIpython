import sqlite3
from contextlib import contextmanager
from datetime import datetime
import os

@contextmanager
def get_notification_db_connection():
    """Context manager for notification database connections"""
    conn = None
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, "notifications.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        print(f"Notification database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_notification_database():
    """Initialize notification database"""
    with get_notification_db_connection() as conn:
        cursor = conn.cursor()
        
        # Notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_email TEXT NOT NULL,
                recipient_name TEXT,
                notification_type TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                channel TEXT DEFAULT 'email',
                sent_at DATETIME,
                opened_at DATETIME,
                error_message TEXT,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Email templates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT UNIQUE NOT NULL,
                subject_template TEXT NOT NULL,
                body_template TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert default templates if not exist
        templates = [
            (
                "booking_confirmation",
                "Booking Confirmed: {event_title}",
                """
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #4CAF50;">✓ Booking Confirmed!</h2>
                    <p>Dear {user_name},</p>
                    <p>Your booking has been successfully confirmed.</p>
                    
                    <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">Booking Details:</h3>
                        <p><strong>Event:</strong> {event_title}</p>
                        <p><strong>Date & Time:</strong> {start_time}</p>
                        <p><strong>Duration:</strong> {duration} minutes</p>
                        <p><strong>Booking ID:</strong> {booking_id}</p>
                    </div>
                    
                    <p>Please arrive 10 minutes before the scheduled time.</p>
                    <p>If you need to cancel or modify your booking, please log in to your account.</p>
                    
                    <p style="margin-top: 30px;">Best regards,<br>SmartBookingAI Team</p>
                </body>
                </html>
                """
            ),
            (
                "booking_cancellation",
                "Booking Cancelled: {event_title}",
                """
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #f44336;">Booking Cancelled</h2>
                    <p>Dear {user_name},</p>
                    <p>Your booking has been cancelled as requested.</p>
                    
                    <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">Cancelled Booking:</h3>
                        <p><strong>Event:</strong> {event_title}</p>
                        <p><strong>Was scheduled for:</strong> {start_time}</p>
                        <p><strong>Booking ID:</strong> {booking_id}</p>
                    </div>
                    
                    <p>You can make a new booking anytime by visiting our platform.</p>
                    
                    <p style="margin-top: 30px;">Best regards,<br>SmartBookingAI Team</p>
                </body>
                </html>
                """
            ),
            (
                "ai_recommendation",
                "Recommended Time Slots Based on Your Preferences",
                """
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #2196F3;">🤖 AI-Powered Recommendations</h2>
                    <p>Dear {user_name},</p>
                    <p>Based on your booking history and preferences, we've identified optimal time slots for you:</p>
                    
                    <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">Recommended Slots:</h3>
                        {recommendations}
                    </div>
                    
                    <p>These slots have been predicted to match your preferences with <strong>{confidence}% confidence</strong>.</p>
                    <p>Book now to secure your preferred time!</p>
                    
                    <p style="margin-top: 30px;">Best regards,<br>SmartBookingAI Team</p>
                </body>
                </html>
                """
            ),
            (
                "booking_reminder",
                "Reminder: Upcoming Event - {event_title}",
                """
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #FF9800;">⏰ Upcoming Event Reminder</h2>
                    <p>Dear {user_name},</p>
                    <p>This is a friendly reminder about your upcoming booking.</p>
                    
                    <div style="background-color: #fff3e0; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">Event Details:</h3>
                        <p><strong>Event:</strong> {event_title}</p>
                        <p><strong>Time:</strong> {start_time}</p>
                        <p><strong>Location:</strong> {location}</p>
                    </div>
                    
                    <p>We look forward to seeing you!</p>
                    
                    <p style="margin-top: 30px;">Best regards,<br>SmartBookingAI Team</p>
                </body>
                </html>
                """
            )
        ]
        
        for template in templates:
            cursor.execute("""
                INSERT OR IGNORE INTO email_templates (template_name, subject_template, body_template)
                VALUES (?, ?, ?)
            """, template)
        
        conn.commit()
        print("Notification database initialized successfully")

def save_notification(notification_data: dict):
    """Save notification to database"""
    try:
        with get_notification_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notifications 
                (recipient_email, recipient_name, notification_type, subject, body, status, channel, sent_at, error_message, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                notification_data.get("recipient_email"),
                notification_data.get("recipient_name"),
                notification_data.get("notification_type"),
                notification_data.get("subject"),
                notification_data.get("body"),
                notification_data.get("status", "pending"),
                notification_data.get("channel", "email"),
                notification_data.get("sent_at"),
                notification_data.get("error_message"),
                notification_data.get("metadata")
            ))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        print(f"Error saving notification: {e}")
        return None

def get_notification_history(user_email: str, limit: int = 50):
    """Get notification history for a user"""
    try:
        with get_notification_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM notifications 
                WHERE recipient_email = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_email, limit))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching notification history: {e}")
        return []

def get_email_template(template_name: str):
    """Get email template by name"""
    try:
        with get_notification_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM email_templates WHERE template_name = ?
            """, (template_name,))
            template = cursor.fetchone()
            return dict(template) if template else None
    except Exception as e:
        print(f"Error fetching template: {e}")
        return None

def update_notification_status(notification_id: int, status: str, error_message: str = None):
    """Update notification status"""
    try:
        with get_notification_db_connection() as conn:
            cursor = conn.cursor()
            if status == "sent":
                cursor.execute("""
                    UPDATE notifications 
                    SET status = ?, sent_at = ?, error_message = ?
                    WHERE id = ?
                """, (status, datetime.now().isoformat(), error_message, notification_id))
            else:
                cursor.execute("""
                    UPDATE notifications 
                    SET status = ?, error_message = ?
                    WHERE id = ?
                """, (status, error_message, notification_id))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error updating notification status: {e}")
        return False

# Initialize database
init_notification_database()
