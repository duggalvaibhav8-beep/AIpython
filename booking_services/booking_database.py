import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Optional
import os

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir,"booking.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_booking_database():
    """Initialize booking database with required tables"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                capacity INTEGER NOT NULL,
                duration_minutes INTEGER DEFAULT 60,
                start_time DATETIME NOT NULL,  
                end_time DATETIME NOT NULL,    
                created_by INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES login(id)
            )
        """)
        
        # Time slots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS time_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                max_capacity INTEGER NOT NULL,
                available_slots INTEGER NOT NULL,
                is_available BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id),
                CHECK (end_time > start_time)
            )
        """)
        
        # Bookings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                time_slot_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                quantity INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES login(id),
                FOREIGN KEY (time_slot_id) REFERENCES time_slots(id)
            )
        """)
        
        # Booking history for AI training
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS booking_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time_slot_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                booking_date DATE NOT NULL,
                booking_time TIME NOT NULL,
                day_of_week INTEGER NOT NULL,
                is_weekend BOOLEAN NOT NULL,
                month INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert sample events if none exist
        events_exist = cursor.execute("SELECT id FROM events LIMIT 1").fetchone()
        if not events_exist:
            base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            event_start = base_date
            event_end = base_date + timedelta(days=30)  
            
            sample_events = [
                ("AI Workshop", "Introduction to Artificial Intelligence", 30, 120, event_start.isoformat(), event_end.isoformat(), 1),
                ("Yoga Class", "Morning yoga session", 20, 60, event_start.isoformat(), event_end.isoformat(), 1),
                ("Business Meeting", "Team strategy meeting", 15, 90, event_start.isoformat(), event_end.isoformat(), 1),
                ("Code Review", "Pair programming session", 10, 60, event_start.isoformat(), event_end.isoformat(), 1)
            ]
            
            for event in sample_events:
                cursor.execute(
                    """INSERT INTO events (title, description, capacity, duration_minutes, start_time, end_time, created_by) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",  # Updated INSERT
                    event
                )
            
            # Create sample time slots for the next 7 days
            event_ids = [1, 2, 3, 4]  # Assuming these are the IDs of the inserted events
            base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            for event_id in event_ids:
                for day in range(7):
                    current_date = base_date + timedelta(days=day)
                    
                    # Create multiple time slots per day
                    for hour in [9, 11, 14, 16]:  # 9AM, 11AM, 2PM, 4PM
                        start_time = current_date.replace(hour=hour, minute=0)
                        end_time = start_time + timedelta(minutes=60)
                        
                        # Get event capacity for this time slot
                        event_capacity = cursor.execute(
                            "SELECT capacity FROM events WHERE id = ?", (event_id,)
                        ).fetchone()["capacity"]
                        
                        cursor.execute(
                            """INSERT INTO time_slots 
                            (event_id, start_time, end_time, max_capacity, available_slots) 
                            VALUES (?, ?, ?, ?, ?)""",
                            (event_id, start_time.isoformat(), end_time.isoformat(), 
                             event_capacity, event_capacity)
                        )
            
            conn.commit()
            print("Sample events and time slots created successfully")
        
        conn.commit()
        print("Booking database initialized successfully")

# Event Operations
def create_event(event_data):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO events (title, description, capacity, duration_minutes, start_time, end_time, created_by) 
                VALUES (?, ?, ?, ?, ?, ?, ?)""",  # Updated
                (event_data.title, event_data.description, event_data.capacity, 
                 event_data.duration_minutes, event_data.start_time.isoformat(), 
                 event_data.end_time.isoformat(), event_data.created_by)
            )
            event_id = cursor.lastrowid
            conn.commit()
            return event_id
    except Exception as e:
        print(f"Error creating event: {e}")
        return None

def get_all_events():
    """Get all events with capacity info"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get events with aggregated capacity info
            cursor.execute("""
                SELECT 
                    e.*,
                    COALESCE(SUM(ts.max_capacity), 0) as total_capacity,
                    COALESCE(SUM(ts.available_slots), 0) as available_capacity
                FROM events e
                LEFT JOIN time_slots ts ON e.id = ts.event_id AND ts.is_available = TRUE
                GROUP BY e.id
                ORDER BY e.start_time
            """)
            
            events = []
            for row in cursor.fetchall():
                event = dict(row)
                event['booked_capacity'] = event['total_capacity'] - event['available_capacity']
                events.append(event)
            
            return events
            
    except Exception as e:
        print(f"Error fetching events: {e}")
        return []
    

def update_event(event_id, event_data):
    """
    Update an existing event.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Check if event exists
            cursor.execute("SELECT id FROM events WHERE id = ?", (event_id,))
            if not cursor.fetchone():
                print(f"Event {event_id} not found.")
                return False

            # 2. Execute Update
            
            query = """
                UPDATE events SET
                    title = ?,
                    description = ?,
                    capacity = ?,
                    duration_minutes = ?,
                    start_time = ?,
                    end_time = ?
                WHERE id = ?
            """
            
            cursor.execute(query, (
                event_data.title,
                event_data.description,
                event_data.capacity,
                event_data.duration_minutes,
                event_data.start_time,
                event_data.end_time,
                event_id
            ))
            
            conn.commit()
            print(f"✓ Event {event_id} updated successfully.")
            return True
            
    except Exception as e:
        print(f"Error updating event: {e}")
        return False
    

def delete_event(event_id: int):
    """Delete an event and its related time slots and bookings"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # First, delete related bookings and time slots
            cursor.execute("""
                DELETE FROM bookings 
                WHERE time_slot_id IN (SELECT id FROM time_slots WHERE event_id = ?)
            """, (event_id,))
            
            cursor.execute("DELETE FROM time_slots WHERE event_id = ?", (event_id,))
            cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
            
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting event: {e}")
        return False

def get_event_by_id(event_id):
    """Get event by ID with capacity info"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get event
            cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            event = cursor.fetchone()
            
            if not event:
                return None
            
            event_dict = dict(event)
            
            # Calculate total available capacity across all time slots
            capacity_info = cursor.execute("""
                SELECT 
                    COALESCE(SUM(max_capacity), 0) as total_capacity,
                    COALESCE(SUM(available_slots), 0) as available_capacity
                FROM time_slots 
                WHERE event_id = ? AND is_available = TRUE
            """, (event_id,)).fetchone()
            
            event_dict['available_capacity'] = capacity_info['available_capacity']  
            event_dict['booked_capacity'] = capacity_info['total_capacity'] - capacity_info['available_capacity']
            
            return event_dict
            
    except Exception as e:
        print(f"Error fetching event: {e}")
        return None
    
def get_event_statistics(event_id: int):
    """Get detailed statistics for an event"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Event info
            event = cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            if not event:
                return None
            
            # Time slot statistics
            slot_stats = cursor.execute("""
                SELECT 
                    COUNT(*) as total_slots,
                    COUNT(CASE WHEN is_available = TRUE THEN 1 END) as available_slots,
                    SUM(max_capacity) as total_capacity,
                    SUM(available_slots) as available_capacity,
                    MIN(start_time) as earliest_slot,
                    MAX(end_time) as latest_slot
                FROM time_slots 
                WHERE event_id = ?
            """, (event_id,)).fetchone()
            
            # Booking statistics
            booking_stats = cursor.execute("""
                SELECT 
                    COUNT(DISTINCT b.id) as total_bookings,
                    COUNT(DISTINCT b.user_id) as unique_users,
                    SUM(b.quantity) as total_spots_booked,
                    COUNT(CASE WHEN b.status = 'confirmed' THEN 1 END) as confirmed_bookings,
                    COUNT(CASE WHEN b.status = 'cancelled' THEN 1 END) as cancelled_bookings
                FROM bookings b
                JOIN time_slots ts ON b.time_slot_id = ts.id
                WHERE ts.event_id = ?
            """, (event_id,)).fetchone()
            
            return {
                'event': dict(event),
                'slots': dict(slot_stats),
                'bookings': dict(booking_stats),
                'capacity_percentage': round(
                    ((slot_stats['total_capacity'] - slot_stats['available_capacity']) / slot_stats['total_capacity'] * 100)
                    if slot_stats['total_capacity'] > 0 else 0,
                    2
                )
            }
            
    except Exception as e:
        print(f"Error fetching event statistics: {e}")
        return None

# Time Slot Operations
def get_available_time_slots(event_id: int, date: str = None):
    """Get available time slots for an event"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if date:
                # Get slots for specific date
                query = """
                    SELECT ts.*, e.title as event_title 
                    FROM time_slots ts 
                    JOIN events e ON ts.event_id = e.id 
                    WHERE ts.event_id = ? AND DATE(ts.start_time) = ? AND ts.is_available = TRUE AND ts.available_slots > 0
                    ORDER BY ts.start_time
                """
                cursor.execute(query, (event_id, date))
            else:
                # Get all future available slots
                query = """
                    SELECT ts.*, e.title as event_title 
                    FROM time_slots ts 
                    JOIN events e ON ts.event_id = e.id 
                    WHERE ts.event_id = ? AND ts.start_time > datetime('now') 
                    AND ts.is_available = TRUE AND ts.available_slots > 0
                    ORDER BY ts.start_time
                """
                cursor.execute(query, (event_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching time slots: {e}")
        return []


def create_time_slot(event_id: int, start_time: datetime, end_time: datetime, max_capacity: Optional[int] = None):
    """Create a single time slot for an event with overlap checking"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get event to validate and get default capacity
            event = cursor.execute("SELECT capacity, start_time, end_time FROM events WHERE id = ?", (event_id,)).fetchone()
            if not event:
                print("Event not found")
                return None
            
            event_start = datetime.fromisoformat(event['start_time'])
            event_end = datetime.fromisoformat(event['end_time'])
            
            # Validate slot is within event date range
            if not (event_start <= start_time < end_time <= event_end):
                print("Time slot outside event date range")
                return None
            
            # Check for overlapping time slots (OPTIONAL - comment out if you want overlaps)
            overlapping = cursor.execute("""
                SELECT COUNT(*) as count FROM time_slots 
                WHERE event_id = ? 
                AND (
                    (start_time <= ? AND end_time > ?) OR
                    (start_time < ? AND end_time >= ?) OR
                    (start_time >= ? AND end_time <= ?)
                )
            """, (event_id, start_time.isoformat(), start_time.isoformat(),
                  end_time.isoformat(), end_time.isoformat(),
                  start_time.isoformat(), end_time.isoformat())).fetchone()
            
            if overlapping['count'] > 0:
                print(f"Warning: Found {overlapping['count']} overlapping time slots")
                # You can return None to prevent overlaps, or continue to allow them
                # return None  # Uncomment to prevent overlaps

            capacity = max_capacity or event['capacity']
            
            cursor.execute("""
                INSERT INTO time_slots 
                (event_id, start_time, end_time, max_capacity, available_slots, is_available)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (event_id, start_time.isoformat(), end_time.isoformat(), capacity, capacity, True))
            
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        print(f"Error creating time slot: {e}")
        return None
    
def get_user_event_bookings(user_id: int, event_id: int):
    """Get all bookings for a user for a specific event"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    b.*,
                    ts.start_time,
                    ts.end_time,
                    ts.available_slots,
                    e.title as event_title
                FROM bookings b
                JOIN time_slots ts ON b.time_slot_id = ts.id
                JOIN events e ON ts.event_id = e.id
                WHERE b.user_id = ? AND ts.event_id = ? AND b.status != 'cancelled'
                ORDER BY ts.start_time
            """, (user_id, event_id))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching user event bookings: {e}")
        return []



# Booking Operations
def create_booking(user_id: int, event_id: int, time_slot_id: Optional[int] = None, quantity: int = 1, status: str = "pending"):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # If time_slot_id not provided, auto-assign earliest available with enough capacity and no existing booking
            if time_slot_id is None:
                cursor.execute("""
                    SELECT id FROM time_slots 
                    WHERE event_id = ? AND start_time > datetime('now') AND available_slots >= ? 
                    AND is_available = TRUE
                    AND NOT EXISTS (
                        SELECT 1 FROM bookings 
                        WHERE time_slot_id = time_slots.id AND user_id = ? AND status != 'cancelled'
                    )
                    ORDER BY start_time LIMIT 1
                """, (event_id, quantity, user_id))
                row = cursor.fetchone()
                if not row:
                    return None
                time_slot_id = row['id']
            
            # Validate the (provided or auto) time_slot
            slot = cursor.execute(
                "SELECT event_id, available_slots, is_available FROM time_slots WHERE id = ?",
                (time_slot_id,)
            ).fetchone()
            if not slot or slot['event_id'] != event_id or not slot['is_available'] or slot['available_slots'] < quantity:
                return None
            
            # Check existing non-cancelled booking for this user and slot
            cursor.execute(
                """SELECT id FROM bookings 
                WHERE user_id = ? AND time_slot_id = ? AND status != 'cancelled'""",
                (user_id, time_slot_id)
            )
            if cursor.fetchone():
                return None
            
            # Create booking (add quantity)
            cursor.execute(
                """INSERT INTO bookings (user_id, time_slot_id, status, quantity) 
                VALUES (?, ?, ?, ?)""",  # Updated
                (user_id, time_slot_id, status, quantity)
            )
            booking_id = cursor.lastrowid
            
            # Update available slots
            cursor.execute(
                "UPDATE time_slots SET available_slots = available_slots - ? WHERE id = ?",
                (quantity, time_slot_id)  # Use quantity
            )
            
            # Add to booking history (keep as is, but could add quantity if needed)
            # ... (existing code for booking_history)
            
            conn.commit()
            return booking_id
    except Exception as e:
        print(f"Error creating booking: {e}")
        return None

def get_user_bookings(user_id: int):
    """Get all bookings for a user"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.*, e.title as event_title, ts.start_time, ts.end_time 
                FROM bookings b
                JOIN time_slots ts ON b.time_slot_id = ts.id
                JOIN events e ON ts.event_id = e.id
                WHERE b.user_id = ?
                ORDER BY ts.start_time DESC
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching user bookings: {e}")
        return []

def update_booking_status(booking_id: int, status: str):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get current booking info (add quantity)
            cursor.execute(
                "SELECT time_slot_id, status, quantity FROM bookings WHERE id = ?", 
                (booking_id,)
            )
            booking = cursor.fetchone()
            
            if not booking:
                return False
            
            old_status = booking["status"]
            time_slot_id = booking["time_slot_id"]
            quantity = booking["quantity"]  # New
            
            # Update booking status
            cursor.execute(
                "UPDATE bookings SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, booking_id)
            )
            
            # Rule: Both 'confirmed' and 'pending' hold a seat. 'cancelled' releases it.
            
            # 1. If cancelling a booking (Pending/Confirmed -> Cancelled) -> Release Slot
            if old_status in ["confirmed", "pending"] and status == "cancelled":
                cursor.execute(
                    "UPDATE time_slots SET available_slots = available_slots + ? WHERE id = ?",
                    (quantity, time_slot_id)
                )
            
            # 2. If reactivating a booking (Cancelled -> Pending/Confirmed) -> Re-Reserve Slot
            elif old_status == "cancelled" and status in ["confirmed", "pending"]:
                cursor.execute(
                    "UPDATE time_slots SET available_slots = available_slots - ? WHERE id = ?",
                    (quantity, time_slot_id)
                )
                
            # 3. If approving (Pending -> Confirmed), DO NOTHING to capacity.
            #    (The seat was already reserved when the Pending booking was created).
            
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error updating booking: {e}")
        return False

def get_booking_by_id(booking_id: int):
    """Get booking by ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.*, e.title as event_title, ts.start_time, ts.end_time 
                FROM bookings b
                JOIN time_slots ts ON b.time_slot_id = ts.id
                JOIN events e ON ts.event_id = e.id
                WHERE b.id = ?
            """, (booking_id,))
            booking = cursor.fetchone()
            return dict(booking) if booking else None
    except Exception as e:
        print(f"Error fetching booking: {e}")
        return None
    
def get_all_bookings_admin():
    """Get ALL bookings in the system (for Admin)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Join with events and time_slots to get readable details
            cursor.execute("""
                SELECT b.*, e.title as event_title, ts.start_time, ts.end_time 
                FROM bookings b
                JOIN time_slots ts ON b.time_slot_id = ts.id
                JOIN events e ON ts.event_id = e.id
                ORDER BY b.created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching all bookings: {e}")
        return []

def get_bookings_by_event_admin(event_id: int):
    """Get all bookings for a specific event (for Admin)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.*, e.title as event_title, ts.start_time, ts.end_time 
                FROM bookings b
                JOIN time_slots ts ON b.time_slot_id = ts.id
                JOIN events e ON ts.event_id = e.id
                WHERE e.id = ?
                ORDER BY ts.start_time, b.created_at
            """, (event_id,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching event bookings: {e}")
        return []    
    
# === TIME SLOT CRUD OPERATIONS ===

# def create_time_slot(event_id: int, start_time: datetime, end_time: datetime, max_capacity: Optional[int] = None):
#     """Create a single time slot for an event"""
#     try:
#         with get_db_connection() as conn:
#             cursor = conn.cursor()
            
#             # Get event to validate and get default capacity
#             event = cursor.execute("SELECT capacity, start_time, end_time FROM events WHERE id = ?", (event_id,)).fetchone()
#             if not event:
#                 return None
            
#             event_start = datetime.fromisoformat(event['start_time'])
#             event_end = datetime.fromisoformat(event['end_time'])
            
#             if not (event_start <= start_time < end_time <= event_end):
#                 print("Time slot outside event date range")
#                 return None

#             capacity = max_capacity or event['capacity']
            
#             cursor.execute("""
#                 INSERT INTO time_slots 
#                 (event_id, start_time, end_time, max_capacity, available_slots, is_available)
#                 VALUES (?, ?, ?, ?, ?, ?)
#             """, (event_id, start_time.isoformat(), end_time.isoformat(), capacity, capacity, True))
            
#             conn.commit()
#             return cursor.lastrowid
#     except Exception as e:
#         print(f"Error creating time slot: {e}")
#         return None


def get_time_slots_by_event(event_id: int, date: str = None):
    """Get all time slots for an event, optionally filtered by date"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if date:
                cursor.execute("""
                    SELECT ts.*, e.title as event_title, e.capacity as event_capacity
                    FROM time_slots ts
                    JOIN events e ON ts.event_id = e.id
                    WHERE ts.event_id = ? AND DATE(ts.start_time) = ?
                    ORDER BY ts.start_time
                """, (event_id, date))
            else:
                cursor.execute("""
                    SELECT ts.*, e.title as event_title, e.capacity as event_capacity
                    FROM time_slots ts
                    JOIN events e ON ts.event_id = e.id
                    WHERE ts.event_id = ?
                    ORDER BY ts.start_time
                """, (event_id,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error: {e}")
        return []


def update_time_slot(slot_id: int, start_time: datetime = None, end_time: datetime = None, max_capacity: int = None, is_available: bool = None):
    """Update a time slot"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            fields = []
            values = []
            
            if start_time is not None:
                fields.append("start_time = ?")
                values.append(start_time.isoformat())
            if end_time is not None:
                fields.append("end_time = ?")
                values.append(end_time.isoformat())
            if max_capacity is not None:
                # Adjust available_slots if increasing capacity
                cursor.execute("SELECT available_slots, max_capacity FROM time_slots WHERE id = ?", (slot_id,))
                current = cursor.fetchone()
                if current:
                    diff = max_capacity - current['max_capacity']
                    fields.append("max_capacity = ?")
                    fields.append("available_slots = available_slots + ?")
                    values.extend([max_capacity, diff])
            
            if is_available is not None:
                fields.append("is_available = ?")
                values.append(is_available)
            
            if not fields:
                return False
                
            values.append(slot_id)
            query = f"UPDATE time_slots SET {', '.join(fields)} WHERE id = ?"
            
            cursor.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error updating time slot: {e}")
        return False


def delete_time_slot(slot_id: int):
    """Delete a time slot (only if no active bookings)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Prevent deletion if has confirmed bookings
            booked = cursor.execute("""
                SELECT COUNT(*) as count FROM bookings 
                WHERE time_slot_id = ? AND status = 'confirmed'
            """, (slot_id,)).fetchone()['count']
            
            if booked > 0:
                return False, "Cannot delete time slot with active bookings"
                
            cursor.execute("DELETE FROM time_slots WHERE id = ?", (slot_id,))
            conn.commit()
            return True, "Deleted successfully"
    except Exception as e:
        return False, str(e)
    

def create_time_slots_bulk(
    event_id: int, 
    dates: list,  # List of datetime objects (just dates)
    times: list,  # List of tuples: [(start_hour, start_min), ...]
    duration_minutes: int = 60,
    max_capacity: Optional[int] = None
):
    """
    Create multiple time slots at once
    Example: create_time_slots_bulk(
        event_id=1,
        dates=[datetime(2024, 12, 10), datetime(2024, 12, 11)],
        times=[(9, 0), (14, 0), (16, 0)],  # 9AM, 2PM, 4PM
        duration_minutes=60
    )
    """
    try:
        created_slots = []
        
        for date in dates:
            for hour, minute in times:
                start_time = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                end_time = start_time + timedelta(minutes=duration_minutes)
                
                slot_id = create_time_slot(event_id, start_time, end_time, max_capacity)
                if slot_id:
                    created_slots.append(slot_id)
        
        print(f"Created {len(created_slots)} time slots")
        return created_slots
        
    except Exception as e:
        print(f"Error in bulk creation: {e}")
        return []


# Initialize database when module is imported
init_booking_database()