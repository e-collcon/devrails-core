// web-app/src/lib/firebase.ts
// DevRails PoC | PRD-001 v1.0 | TASK-010
//
// Firebase client SDK initialization.
// Reads config from NEXT_PUBLIC_FIREBASE_* environment variables.
//
// EPIC-002 / TASK-012: Firebase Auth (Google Sign-In) wired below.
// Phase 3 (EPIC-010, TASK-083): Implement Firestore read helper
//
// IMPORTANT: This file initializes the Firebase CLIENT SDK only.
// The Firebase ADMIN SDK lives in spike-engine only and is never imported here.
// The web-app never receives, stores, or handles GCP credentials.

import { initializeApp, getApps } from "firebase/app";
import { GoogleAuthProvider, getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
export const googleProvider = new GoogleAuthProvider();
