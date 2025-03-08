import os
import numpy as np

import requests
from openai import AsyncOpenAI
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
from googleapiclient.discovery import build

import secret
from string_parser import custom_trim, filter_not_utf8

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

class CustErr:
    """A custom error class. This is so I can write
    if type(res)==CustErr: return res
    instead of raising an error. This might help with asyncronous code."""

    message: str

    def __init__(self, message=''):
        self.message = message

from typing import Optional, Tuple
async def find_email_sequence(name, url, company)-> Optional[Tuple[str, str]]:
    """Returns the email and a string of what type of email it is"""
    try:
        firebase_res = await find_email_firestore(name, url)
        if firebase_res: 
            return (firebase_res[0], "firestore " + firebase_res[1])
    except Exception as e:
        print(f"Error with Firebase: {e}")
        # Continue without Firebase
        pass
    
    if not name: return None
    email_rv = await find_email_apollo(name, url, company)
    if email_rv: return (email_rv[0], "apollo")
    return None

async def find_email_firestore(name, url)-> Optional[Tuple[str, str]]:
    """Checks if the email is in the firestore database"""
    try:
        if not initialize_firebase():
            print("Skipping Firebase lookup due to initialization failure")
            return None
            
        db = firestore.client()
        firebase_url = '\\'.join(url.split('/'))
        
        # Try to get email by URL
        try:
            doc_ref = db.collection('emails').document(firebase_url)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                if data and 'email' in data:
                    if data.get('author', None) == name or not data.get('author', None):
                        return (data['email'], 'firestore company')
                    else:
                        return (data['email'], 'firestore author')
        except Exception as e:
            print(f"Error querying Firebase by URL: {e}")
        
        # Try to get email by author name if URL lookup failed
        if name:
            try:
                docs = db.collection('emails').where('author', '==', name).limit(1).get()
                for doc in docs:
                    data = doc.to_dict()
                    if 'email' in data:
                        return (data['email'], 'firestore author')
            except Exception as e:
                print(f"Error querying Firebase by author: {e}")
                
        return None
    except Exception as e:
        print(f"Error in find_email_firestore: {e}")
        return None

async def find_email_apollo(name:str, url: str, company_name: str)-> list[str]:
    api_loc = "https://api.apollo.io/api/v1/people/match"

    data = {
        "api_key": os.environ['APOLLO_API_KEY'],
        "reveal_personal_emails": True,
        "first_name": name.split(' ')[0],
        "last_name": name.split(' ')[-1],
        "domain": url,
        "organization_name": company_name
    }
    headers = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", api_loc, headers=headers, json=data)
    json_res = response.json()
    person = json_res['person']
    possible_emails = []
    if person:
        email = person['email']
        if email and '@' in email:
            possible_emails.append(email)
        personal_emails = person['personal_emails']
        for personal_email in personal_emails:
            if personal_email and '@' in personal_email:
                possible_emails.append(personal_email)
    return possible_emails

def find_word_anchor(a_soup, word):
    a_texts = list(map(lambda x: x.text, a_soup))
    possible_contact_texts = []
    for i in range(len(a_texts)):
        a_text = a_texts[i]
        if word in a_text.lower():
            possible_contact_texts.append((a_text,i))
    contact_texts = []
    if len(possible_contact_texts) >1:
        for text in possible_contact_texts:
            if len(custom_trim(text[0]))<20:
                contact_texts.append(text)
    else: contact_texts = possible_contact_texts
    return contact_texts[-1] if contact_texts else None

# Finds the most similar element of the string array and returns the strings' indexes
async def most_similar(strings, arr):
    embeddings = []
    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )
    for i in range(len(arr)):
        if arr[i]:
            # Embedding each element
            embedding = await client.embeddings.create(input = [filter_not_utf8(arr[i])], model='text-embedding-ada-002')
            embeddings.append((np.array(embedding.data[0].embedding), i)) # type: ignore
    rv = []
    for string in strings:
        embedding = await client.embeddings.create(input = [string], model='text-embedding-ada-002')
        str_vect = np.array(embedding.data[0].embedding) # type: ignore
        min_dist = 2
        min_index = -1.5

        for i in range(len(embeddings)):
            emb = embeddings[i]
            dist = np.linalg.norm(str_vect - emb[0])
            if dist < min_dist:
                min_dist = dist
                min_index = emb[1]
        rv.append(min_index)
    return rv

def initialize_firebase():
    try:
        # Check if Firebase app is already initialized
        if not firebase_admin._apps:
            try:
                # First try: Use serviceAccount.json
                cred = credentials.Certificate('serviceAccount.json')
                firebase_admin.initialize_app(cred, {
                    'projectId': os.environ.get("FIREBASE_PROJECT_ID", "blog-emailer-294e0"),
                    'databaseURL': os.environ.get("FIREBASE_DATABASE_URL", "https://blog-emailer-294e0-default-rtdb.firebaseio.com"),
                    'storageBucket': os.environ.get("FIREBASE_STORAGE_BUCKET", "blog-emailer-294e0.appspot.com")
                })
                print("Firebase initialized with serviceAccount.json")
            except Exception as e:
                print(f"Error initializing Firebase with serviceAccount.json: {e}")
                # Second try: Use environment variables directly
                try:
                    firebase_config = {
                        'apiKey': os.environ.get("FIREBASE_API_KEY"),
                        'authDomain': os.environ.get("FIREBASE_AUTH_DOMAIN"),
                        'databaseURL': os.environ.get("FIREBASE_DATABASE_URL"),
                        'projectId': os.environ.get("FIREBASE_PROJECT_ID"),
                        'storageBucket': os.environ.get("FIREBASE_STORAGE_BUCKET"),
                        'messagingSenderId': os.environ.get("FIREBASE_MESSAGING_SENDER_ID"),
                        'appId': os.environ.get("FIREBASE_APP_ID"),
                        'measurementId': os.environ.get("FIREBASE_MEASUREMENT_ID")
                    }
                    firebase_admin.initialize_app(options=firebase_config)
                    print("Firebase initialized with environment variables")
                except Exception as e2:
                    print(f"Error initializing Firebase with environment variables: {e2}")
                    # Third try: Initialize with default app
                    try:
                        firebase_admin.initialize_app()
                        print("Firebase initialized with default configuration")
                    except Exception as e3:
                        print(f"All Firebase initialization methods failed: {e3}")
                        return False
        else:
            print("Firebase already initialized")
        return True
    except Exception as e:
        print(f"Unexpected error initializing Firebase: {e}")
        return False

async def find_company_email(url, a_soup, words=['contact', 'about']):
    global headers
    print(f"DEBUG: find_company_email called with URL: {url}")
    print(f"DEBUG: a_soup type: {type(a_soup)}")
    
    contact_anchor = None
    for word in words:
        print(f"DEBUG: Searching for word: {word}")
        if not contact_anchor: 
            contact_anchor = find_word_anchor(a_soup, word)
            if contact_anchor:
                print(f"DEBUG: Found anchor for word: {word}")
    
    if not contact_anchor: 
        print("DEBUG: No contact anchor found")
        return None
    
    print(f"DEBUG: Contact anchor found: {contact_anchor}")
    href = a_soup[contact_anchor[1]]['href']
    print(f"DEBUG: Contact href: {href}")
    
    if url not in href and 'www' not in href and 'http' not in href:
        if href[0] == '/':
            href = href[1:]
        href  = custom_trim(url.split('?')[0], '/', '') + '/' + href
        print(f"DEBUG: Modified href: {href}")
    
    try:
        print(f"DEBUG: Requesting contact page: {href}")
        contact_r = requests.get(href, headers=headers)
        print(f"DEBUG: Contact page status code: {contact_r.status_code}")
        
        if contact_r.status_code != 200:
            print("DEBUG: Failed to fetch contact page")
            return None
        
        r_soup = BeautifulSoup(contact_r.content, 'html5lib')
        email = await get_email_from_rsoup(r_soup)
        print(f"DEBUG: Email found: {email}")
        return email
    except Exception as e:
        print(f"DEBUG: Error in find_company_email: {e}")
        return None

async def get_email_from_rsoup(r_soup):
    def get_href(x):
        if  'href' in x.attrs: 
            return x['href']
        return None
    r_soup_hrefs = list(map(get_href, r_soup.find_all('a')))
    email_hrefs = []
    for href in r_soup_hrefs: 
        if href and ('@' in href and '/' not in href and '%' not in href):
            email_hrefs.append(href)
    if not email_hrefs: return None
    email = email_hrefs[(await most_similar(['contact@company.com'], email_hrefs))[0]]
    if 'mailto:' in email:
        email = email.split('mailto:')[-1]
    return (email if '@' in email else None)

async def inurl_email(url):
    try:
        global headers
        query = 'inurl:' + url + ' "email"'
        service = build("customsearch", "v1", developerKey=os.environ['GOOGLE_API_KEY'])
        google_res = service.cse().list(q=query, cx='e3d6fd3b2065c471b', num=2).execute()['items']
        email_urls = list(map(lambda x: x['link'], google_res))
        email = None
        for email_url in email_urls: # Does not itterate through all of res will return something here
            if not email:
                r = requests.get(email_url,headers=headers)
                if r.status_code==200:
                    soup = BeautifulSoup(r.content, 'html5lib')
                    if soup:
                        email = await get_email_from_rsoup(soup)
        return email if email else None
    except Exception as e:
        return CustErr(str(e))
