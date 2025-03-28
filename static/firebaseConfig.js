// firebaseConfig.js

// Import Firebase functions (modular SDK)
import { initializeApp } from "firebase/app";
import { getFirestore, collection, doc, setDoc, getDoc } from "firebase/firestore";

// Your Firebase configuration object
const firebaseConfig = {  
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId:import.meta.env.VITE_FIREBASE_PROJECTID,
  storageBucket:import.meta.env.VITE_FIREBASE_VITE_FIREBASE_PROJECTID,
  messagingSenderId:import.meta.env.VITE_FIREBASE_MESSAGEING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_AOO_ID
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Firestore
const db = getFirestore(app);

// Reference to the 'drivers' collection
const driversCollection = collection(db, "drivers");

// Example: Add a new driver to the collection
async function addDriver() {
  const driverRef = doc(driversCollection, "DRIVER_ID_123");
  try {
    await setDoc(driverRef, {
      required: "yes",
      // You can add more fields here as needed
    });
    console.log("Driver added successfully!");
  } catch (error) {
    console.error("Error adding driver: ", error);
  }
}

// Example: Get a driver document
async function getDriver(driverId) {
  const driverRef = doc(driversCollection, driverId);
  const driverDoc = await getDoc(driverRef);
  if (driverDoc.exists()) {
    console.log("Driver data: ", driverDoc.data());
  } else {
    console.log("No such driver!");
  }
}

addDriver();
