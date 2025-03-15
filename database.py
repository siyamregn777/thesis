import mysql.connector
from mysql.connector import Error

def get_db_connection():
    """
    Establish and return a connection to the database.
    Handles connection errors gracefully.
    """
    try:
        conn = mysql.connector.connect(
            host='localhost',  
            user='root',  # Replace with your MySQL username
            password='root',  # Replace with your MySQL password
            database='yolov8'  # Updated database name
        )
        return conn
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        return None

def init_db():
    """
    Initialize the database and create necessary tables.
    Handles errors during table creation.
    """
    conn = get_db_connection()
    if conn is None:
        print("Failed to initialize database: No connection.")
        return

    try:
        c = conn.cursor()
        
        # Create Drivers table
        c.execute('''
            CREATE TABLE IF NOT EXISTS drivers (
                id_number VARCHAR(255) PRIMARY KEY
            )
        ''')
        
        # Create License Plates table
        c.execute('''
            CREATE TABLE IF NOT EXISTS plates (
                plate VARCHAR(255) PRIMARY KEY,
                id_number VARCHAR(255),
                FOREIGN KEY (id_number) REFERENCES drivers (id_number) ON DELETE CASCADE
            )
        ''')
        
        # Create Admins table
        c.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                username VARCHAR(255) PRIMARY KEY,
                password VARCHAR(255) NOT NULL
            )
        ''')
        
        # Create Users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id_number VARCHAR(255) PRIMARY KEY,
                password VARCHAR(255) NOT NULL,
                FOREIGN KEY (id_number) REFERENCES drivers (id_number) ON DELETE CASCADE
            )
        ''')
        
        # Insert default admin account
        c.execute('''
            INSERT IGNORE INTO admins (username, password)
            VALUES ('admin', '12341234')
        ''')
        
        conn.commit()
        print("Database initialized successfully.")
    except Error as e:
        print(f"Error initializing database: {e}")
    finally:
        if conn:
            conn.close()

def execute_query(query, params=None, fetch_one=False):
    """
    Execute a SQL query and return the results.
    Handles errors during query execution.
    """
    conn = get_db_connection()
    if conn is None:
        print("Failed to execute query: No connection.")
        return None

    try:
        c = conn.cursor()
        c.execute(query, params or ())
        if fetch_one:
            result = c.fetchone()
        else:
            result = c.fetchall()
        conn.commit()
        return result
    except Error as e:
        print(f"Error executing query: {e}")
        return None
    finally:
        if conn:
            conn.close()

def insert_data(query, params=None):
    """
    Insert data into the database.
    Handles errors during data insertion.
    """
    conn = get_db_connection()
    if conn is None:
        print("Failed to insert data: No connection.")
        return False

    try:
        c = conn.cursor()
        c.execute(query, params or ())
        conn.commit()
        return True
    except Error as e:
        print(f"Error inserting data: {e}")
        return False
    finally:
        if conn:
            conn.close()