import sqlite3
from contextlib import contextmanager
from user_services.auth_utils import get_password_hash
import os

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, "authentication.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        yield conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_database():
    """Initialize database with required tables"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                address TEXT,
                city TEXT,
                country TEXT,
                postal_code TEXT,
                role TEXT DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create admin user if not exists
        admin_exists = cursor.execute(
            "SELECT id FROM login WHERE username = ?", ("admin",)
        ).fetchone()
        
        if not admin_exists:
            hashed_password = get_password_hash("admin123")
            cursor.execute(
                """INSERT INTO login (username, email, password, first_name, last_name, phone, role) 
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("admin", "admin@smartbooking.com", hashed_password, "System", "Administrator", "+1234567890", "admin")
            )
            print("Admin user created: admin / admin123")
        
        conn.commit()
        print("Database initialized successfully")

def reg(data):
    """Register a new user"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Unpack all fields
            (username, email, password, first_name, last_name, 
             phone, address, city, country, postal_code) = data
            
            # Hash password before storing
            hashed_password = get_password_hash(password)
            
            cursor.execute(
                """INSERT INTO login 
                (username, email, password, first_name, last_name, phone, address, city, country, postal_code) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                (username, email, hashed_password, first_name, last_name, 
                 phone, address, city, country, postal_code)
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        print("Username or email already exists")
        return False
    except Exception as e:
        print(f"Registration error: {e}")
        return False

def get_user_by_username(username: str):
    """Get user by username"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM login WHERE username = ?", (username,))
            user = cursor.fetchone()
            return dict(user) if user else None
    except Exception as e:
        print(f"Error fetching user: {e}")
        return None

def show_all():
    """Get all users"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM login WHERE role != 'admin' ")
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching all users: {e}")
        return []

def delete(user_id):
    """Delete a user"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM login WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False

def single_user(user_id):
    """Get single user by ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM login WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            return dict(user) if user else None
    except Exception as e:
        print(f"Error fetching user: {e}")
        return None

def update(data):
    """Update user information"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Unpack all fields
            (username, email, password, first_name, last_name, 
             phone, address, city, country, postal_code, user_id) = data
            
            # If password is being updated, hash it
            if password and password.strip():
                hashed_password = get_password_hash(password)
            else:
                # Get current password
                current_user = single_user(user_id)
                hashed_password = current_user["password"] if current_user else None
            
            if not hashed_password:
                return False
                
            cursor.execute(
                """UPDATE login SET 
                username=?, email=?, password=?, first_name=?, last_name=?, 
                phone=?, address=?, city=?, country=?, postal_code=? 
                WHERE id=?""", 
                (username, email, hashed_password, first_name, last_name, 
                 phone, address, city, country, postal_code, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        print("Username or email already exists")
        return False
    except Exception as e:
        print(f"Update error: {e}")
        return False

# Initialize database when module is imported
init_database()