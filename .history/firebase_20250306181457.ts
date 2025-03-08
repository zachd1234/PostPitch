import { getFirestore } from 'firebase/firestore';
import {getApps, initializeApp} from "firebase/app";
import {getAuth} from "firebase/auth"
import "firebase/firestore";

const firebaseConfig = {
  apiKey: "AIzaSyB9PnFLTOvA-1UgYN7axI0PLcTtmVBpTO0",
  authDomain: "blog-emailer-294e0.firebaseapp.com",
  databaseURL: "https://blog-emailer-294e0-default-rtdb.firebaseio.com",
  projectId: "blog-emailer-294e0",
  storageBucket: "blog-emailer-294e0.appspot.com",
  messagingSenderId: "513027836347",
  appId: "1:513027836347:web:fe73627088f9323cebdc9e",
  measurementId: "G-DWP2YKSEKB"
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
