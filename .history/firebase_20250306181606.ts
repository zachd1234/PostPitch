import { getFirestore } from 'firebase/firestore';
import {getApps, initializeApp} from "firebase/app";
import {getAuth} from "firebase/auth"
import "firebase/firestore";

// Load Firebase configuration from environment variables
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  databaseURL: process.env.NEXT_PUBLIC_FIREBASE_DATABASE_URL,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID
};

if(getApps.length){
  //TODO: Handle this case 
  throw Error("There is already an instance of our database running. Please contact the PostPitch developers if this issue persists.")
}

const app = initializeApp(firebaseConfig);

const auth = getAuth(app)
const db = getFirestore()

const firebaseObj = {
  "db": db,
  "auth": auth
}

export default firebaseObj
