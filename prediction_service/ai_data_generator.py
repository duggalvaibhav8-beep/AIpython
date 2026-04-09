"""
Synthetic Booking Data Generator for AI Training - FINAL VERSION
Generates realistic historical booking patterns for ML training
"""

import sqlite3
import random
import csv
from datetime import datetime, timedelta
from contextlib import contextmanager
import os

@contextmanager
def get_booking_db_connection():
    """Context manager for booking database connections"""
    conn = None
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        db_path = os.path.join(parent_dir, "booking_services", "booking.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

@contextmanager
def get_user_db_connection():
    """Context manager for user database connections"""
    conn = None
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        db_path = os.path.join(parent_dir, "user_services", "authentication.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        print(f"User database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def check_tables_exist():
    """Verify required database tables exist"""
    try:
        with get_booking_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t['name'] for t in cursor.fetchall()]
            
            required = ['events', 'time_slots', 'bookings', 'booking_history']
            missing = [t for t in required if t not in tables]
            
            if missing:
                print(f"❌ Missing booking tables: {missing}")
                return False
        
        with get_user_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t['name'] for t in cursor.fetchall()]
            
            if 'login' not in tables:
                print("❌ Missing 'login' table in user database")
                return False
        
        return True
        
    except Exception as e:
        print(f"Error checking tables: {e}")
        return False


def initialize_sample_data():
    """Create sample events and time slots if database is empty"""
    
    with get_booking_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check if events exist
        cursor.execute("SELECT COUNT(*) as count FROM events")
        events_count = cursor.fetchone()["count"]
        
        if events_count == 0:
            print("Creating sample events and time slots...")
            
            # Create sample events
            sample_events = [
                ("AI Workshop", "Introduction to Artificial Intelligence", 30, 120, 1),
                ("Yoga Class", "Morning yoga session", 20, 60, 1),
                ("Business Meeting", "Team strategy meeting", 15, 90, 1),
                ("Coding Bootcamp", "Learn Python programming", 25, 120, 1),
                ("Consultation", "One-on-one consultation", 5, 30, 1)
            ]
            
            for event in sample_events:
                cursor.execute(
                    """INSERT INTO events (title, description, capacity, duration_minutes, created_by) 
                    VALUES (?, ?, ?, ?, ?)""",
                    event
                )
            
            conn.commit()
            
            # Create historical time slots (past 90 days)
            cursor.execute("SELECT id, capacity, duration_minutes FROM events")
            events = cursor.fetchall()
            
            # base_date = datetime.now() - timedelta(days=90)
            now = datetime.now()
            
            for event in events:
                event_id = event['id']
                capacity = event['capacity']
                
                # Create slots for past 90 days
                for day_offset in range(90):
                    past_date = now - timedelta(days=day_offset)
                    
                    # Create multiple time slots per day
                    for hour in [8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20]:
                        slot_start = past_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                        slot_end = slot_start + timedelta(minutes=60)
                        
                        cursor.execute(
                            """INSERT INTO time_slots 
                            (event_id, start_time, end_time, max_capacity, available_slots) 
                            VALUES (?, ?, ?, ?, ?)""",
                            (event_id, slot_start.isoformat(), slot_end.isoformat(), capacity, capacity, True)
                        )

                # ALSO create FUTURE time slots (for booking)
                for day_offset in range(1, 31):  
                    future_date = now + timedelta(days=day_offset)
                    
                    # Create multiple time slots per day
                    for hour in [8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20]:
                        slot_start = future_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                        slot_end = slot_start + timedelta(minutes=60)
                        
                        cursor.execute(
                            """INSERT INTO time_slots 
                            (event_id, start_time, end_time, max_capacity, available_slots, is_available) 
                            VALUES (?, ?, ?, ?, ?, ?)""",
                            (event_id, slot_start.isoformat(), slot_end.isoformat(), capacity, capacity, True)
                        )        
            
            conn.commit()
            print(f"✓ Created sample events with both past (for AI) and future (for booking) time slots")
    
    # Ensure users exist
    with get_user_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM login")
        user_count = cursor.fetchone()["count"]
        
        if user_count == 0:
            print("Creating sample users...")
            for i in range(1, 21):  # Create 20 sample users
                try:
                    cursor.execute(
                        "INSERT OR IGNORE INTO login (username, email, password) VALUES (?, ?, ?)",
                        (f"user{i}", f"user{i}@example.com", "hashed_password")
                    )
                except:
                    pass
            conn.commit()
            print(f"✓ Created sample users")


def generate_synthetic_booking_data(days_back=180, base_probability=0.35):
    """
    Generate realistic synthetic booking history for AI training
    
    Args:
        days_back: Number of days of historical data to generate
        base_probability: Base probability of a booking (adjusted by patterns)
    
    Returns:
        Number of records created
    """
    
    # Verify database setup
    if not check_tables_exist():
        print("❌ Required tables missing. Initialize databases first.")
        return 0
    
    # Get time slots
    with get_booking_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, event_id, start_time FROM time_slots")
        time_slots = cursor.fetchall()
        
        if not time_slots:
            print("No time slots found. Running initialization...")
            initialize_sample_data()
            cursor.execute("SELECT id, event_id, start_time FROM time_slots")
            time_slots = cursor.fetchall()
            
            if not time_slots:
                print("❌ Failed to create time slots")
                return 0
    
    # Get user IDs
    with get_user_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM login")
        users = cursor.fetchall()
        user_ids = [u["id"] for u in users]
        
        if not user_ids:
            print("❌ No users found in database")
            return 0
    
    print(f"\nGenerating synthetic booking data...")
    print(f"  Days back: {days_back}")
    print(f"  Base probability: {base_probability}")
    print(f"  Time slots: {len(time_slots)}")
    print(f"  Users: {len(user_ids)}")
    
    records_added = 0
    now = datetime.now()
    
    with get_booking_db_connection() as conn:
        cursor = conn.cursor()
        
        for slot in time_slots:
            slot_id = slot["id"]
            slot_start = datetime.fromisoformat(slot["start_time"])
            
            # Only generate data for past time slots
            if slot_start > now:
                continue
            
            # Calculate booking probability based on realistic patterns
            hour = slot_start.hour
            day_of_week = slot_start.weekday()
            month = slot_start.month
            is_weekend = day_of_week >= 5
            
            probability = base_probability
            
            # === TIME OF DAY PATTERNS ===
            # Peak business hours (10-11 AM, 2-3 PM)
            if hour in [10, 11, 14, 15]:
                probability *= 1.8
            
            # Good business hours (9 AM - 5 PM)
            elif 9 <= hour <= 17:
                probability *= 1.4
            
            # Early morning (8 AM)
            elif hour == 8:
                probability *= 1.1
            
            # Evening hours (6-8 PM)
            elif hour in [18, 19, 20]:
                probability *= 0.7
            
            # Late night (after 8 PM)
            elif hour > 20:
                probability *= 0.2  # Very low demand
            
            # Very early (before 8 AM)
            elif hour < 8:
                probability *= 0.3
            
            # === DAY OF WEEK PATTERNS ===
            # Weekdays have higher demand
            if not is_weekend:
                probability *= 1.3
            else:
                # Weekends have lower demand
                probability *= 0.7
            
            # === SEASONAL PATTERNS ===
            # Summer (June-August) - slightly lower due to vacations
            if month in [6, 7, 8]:
                probability *= 0.9
            
            # Holiday season (December)
            if month == 12:
                probability *= 0.8
            
            # Back to work/school (September, January)
            if month in [1, 9]:
                probability *= 1.2
            
            # Cap probability at 95%
            probability = min(probability, 0.95)
            
            # Decide if this slot gets booked
            if random.random() < probability:
                user_id = random.choice(user_ids)
                
                # 90% confirmed, 10% cancelled
                status = "confirmed" if random.random() < 0.9 else "cancelled"
                
                # Booking was made 1-14 days before the slot
                created_at = (slot_start - timedelta(days=random.randint(1, 14))).isoformat()
                
                try:
                    cursor.execute(
                        """INSERT INTO booking_history 
                        (time_slot_id, user_id, booking_date, booking_time, 
                         day_of_week, is_weekend, month, status, created_at) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            slot_id,
                            user_id,
                            slot_start.date().isoformat(),
                            slot_start.time().isoformat(),
                            day_of_week,
                            is_weekend,
                            month,
                            status,
                            created_at
                        )
                    )
                    records_added += 1
                    
                except sqlite3.IntegrityError:
                    if "FOREIGN KEY constraint failed" in str(e):
                        print(f"Foreign key error for slot {slot_id} or user {user_id}, skipping...")
                        continue
                    else:
                        print(f"Integrity error: {e}")
                        continue
                    
                except Exception as e:
                    print(f"Error inserting record for slot {slot_id}: {e}")
                    continue
                except Exception as e:
                    print(f"Error inserting record: {e}")
        
        conn.commit()
    
    print(f"\n✓ Successfully generated {records_added} synthetic booking records")
    
    # Show statistics
    with get_booking_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM booking_history")
        total = cursor.fetchone()["total"]
        print(f"✓ Total booking history records: {total}")
    
    return records_added


def analyze_booking_patterns():
    """Analyze and display booking patterns from generated data"""
    
    with get_booking_db_connection() as conn:
        cursor = conn.cursor()
        
        print("\n" + "="*60)
        print("BOOKING PATTERN ANALYSIS")
        print("="*60)
        
        # Total bookings
        cursor.execute("SELECT COUNT(*) as count FROM booking_history")
        total = cursor.fetchone()["count"]
        
        if total == 0:
            print("No booking history data available.")
            return
        
        print(f"\nTotal Historical Bookings: {total}")
        
        # Bookings by status
        print("\nBookings by Status:")
        cursor.execute("""
            SELECT status, COUNT(*) as count, 
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM booking_history), 2) as percentage
            FROM booking_history 
            GROUP BY status
        """)
        for row in cursor.fetchall():
            print(f"  {row['status']:.<20} {row['count']:>6} ({row['percentage']}%)")
        
        # Top booking hours
        print("\nTop 10 Booking Hours:")
        cursor.execute("""
            SELECT strftime('%H', booking_time) as hour, 
                   COUNT(*) as count,
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM booking_history), 2) as percentage
            FROM booking_history 
            GROUP BY hour 
            ORDER BY count DESC 
            LIMIT 10
        """)
        for row in cursor.fetchall():
            hour_12 = int(row['hour']) % 12 or 12
            am_pm = "AM" if int(row['hour']) < 12 else "PM"
            print(f"  {hour_12:2d}:00 {am_pm} {row['count']:>6} bookings ({row['percentage']}%)")
        
        # Weekday vs Weekend
        print("\nWeekday vs Weekend:")
        cursor.execute("""
            SELECT 
                CASE WHEN is_weekend = 0 THEN 'Weekday' ELSE 'Weekend' END as day_type,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM booking_history), 2) as percentage
            FROM booking_history 
            GROUP BY is_weekend
        """)
        for row in cursor.fetchall():
            print(f"  {row['day_type']:.<20} {row['count']:>6} ({row['percentage']}%)")
        
        print("\n" + "="*60 + "\n")


def export_to_csv(filename="synthetic_bookings.csv"):
    """Export booking history data to CSV file for analysis"""
    
    print(f"\nExporting data to {filename}...")
    
    with get_booking_db_connection() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT 
                bh.id,
                e.title as event_title,
                bh.booking_date,
                bh.booking_time,
                bh.day_of_week,
                bh.is_weekend,
                bh.month,
                bh.status,
                bh.created_at
            FROM booking_history bh
            JOIN time_slots ts ON bh.time_slot_id = ts.id
            JOIN events e ON ts.event_id = e.id
            ORDER BY bh.booking_date DESC, bh.booking_time DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("No data to export.")
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                headers = ['ID', 'Event', 'Date', 'Time', 'DayOfWeek', 
                          'IsWeekend', 'Month', 'Status', 'CreatedAt']
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                
                for row in rows:
                    writer.writerow(row)
            
            print(f"✓ Successfully exported {len(rows)} rows to {filename}")
            
        except Exception as e:
            print(f"❌ Export failed: {e}")


def get_booking_history_stats():
    """Get quick statistics about booking history (for API)"""
    
    try:
        with get_booking_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as total FROM booking_history")
            total = cursor.fetchone()["total"]
            
            if total == 0:
                return {
                    "total_records": 0,
                    "has_data": False,
                    "message": "No booking history data"
                }
            
            cursor.execute("SELECT COUNT(*) as confirmed FROM booking_history WHERE status = 'confirmed'")
            confirmed = cursor.fetchone()["confirmed"]
            
            cursor.execute("SELECT COUNT(*) as cancelled FROM booking_history WHERE status = 'cancelled'")
            cancelled = cursor.fetchone()["cancelled"]
            
            return {
                "total_records": total,
                "confirmed_bookings": confirmed,
                "cancelled_bookings": cancelled,
                "confirmation_rate": round(confirmed / total, 4) if total > 0 else 0,
                "has_data": True
            }
            
    except Exception as e:
        return {
            "total_records": 0,
            "error": str(e),
            "has_data": False
        }


if __name__ == "__main__":
    """Direct execution for testing"""
    
    print("="*60)
    print("SmartBookingAI - Synthetic Data Generator")
    print("="*60)
    
    try:
        # Initialize sample data if needed
        initialize_sample_data()
        
        # Generate synthetic booking data
        records = generate_synthetic_booking_data(days_back=90, base_probability=0.35)
        
        if records > 0:
            # Analyze patterns
            analyze_booking_patterns()
            
            # Export to CSV
            export_to_csv("synthetic_bookings.csv")
            
            print("\n✓ Data generation complete!")
            print("  You can now train the AI models using this data")
            print("  Run: python ai_prediction_models.py")
        else:
            print("\n❌ No data was generated")
            print("  Please check database initialization")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()