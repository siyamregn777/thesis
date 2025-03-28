import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.exceptions import FirebaseError

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")  # Download from Firebase Console
firebase_admin.initialize_app(cred)
db = firestore.client()

# Collection references
drivers_ref = db.collection('drivers')
plates_ref = db.collection('plates')
admins_ref = db.collection('admins')
users_ref = db.collection('users')

def init_firebase():
    """Initialize Firebase collections with default data"""
    try:
        # Add default admin if not exists
        admins_ref.document('admin').set({
            'username': 'admin',
            'password': '12341234'
        }, merge=True)
        print("Firebase initialized successfully")
    except FirebaseError as e:
        print(f"Firebase initialization error: {e}")

def get_driver(driver_id):
    doc = drivers_ref.document(driver_id).get()
    return doc.to_dict() if doc.exists else None

def add_driver(driver_id):
    drivers_ref.document(driver_id).set({'id_number': driver_id})

def check_plate(plate_number):
    doc = plates_ref.document(plate_number).get()
    return doc.exists

def register_plate(plate_number, driver_id):
    plates_ref.document(plate_number).set({
        'plate': plate_number,
        'id_number': driver_id
    })

def authenticate_user(username, password, is_admin=False):
    collection = admins_ref if is_admin else users_ref
    doc = collection.document(username).get()
    if doc.exists and doc.to_dict().get('password') == password:
        return True
    return False

def add_user(user_id, password):
    users_ref.document(user_id).set({
        'id_number': user_id,
        'password': password
    })
    add_driver(user_id)