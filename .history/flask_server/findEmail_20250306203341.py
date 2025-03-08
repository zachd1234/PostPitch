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
    print(f"DEBUG find_email_sequence: Starting with name={name}, url={url}, company={company}")
    firebase_res = await find_email_firestore(name, url)
    print(f"DEBUG find_email_sequence: Firebase result: {firebase_res}")
    if firebase_res: 
        print(f"DEBUG find_email_sequence: Returning Firebase result: {firebase_res[0]}, type: firestore {firebase_res[1]}")
        return (firebase_res[0], "firestore " + firebase_res[1])
    if not name: 
        print(f"DEBUG find_email_sequence: No name provided, returning None")
        return None
    print(f"DEBUG find_email_sequence: Trying Apollo with name={name}")
    email_rv = await find_email_apollo(name, url, company)
    print(f"DEBUG find_email_sequence: Apollo result: {email_rv}")
    if email_rv: 
        print(f"DEBUG find_email_sequence: Returning Apollo result: {email_rv[0]}")
        return (email_rv[0], "apollo")
    print(f"DEBUG find_email_sequence: No email found, returning None")
    return None

async def find_email_firestore(name, url)-> Optional[Tuple[str, str]]:
    """Returns a tuple with the email and a description of the type of email"""
    print(f"DEBUG find_email_firestore: Searching for email with name={name}, url={url}")
    initialize_firebase()
    db = firestore.client()
    firebase_url = '\\'.join(url.split('/'))
    print(f"DEBUG find_email_firestore: Firebase URL format: {firebase_url}")
    ref = db.collection('sites').document(firebase_url)
    print(f"DEBUG find_email_firestore: Querying document at sites/{firebase_url}")
    doc = ref.get()
    print(f"DEBUG find_email_firestore: Document exists: {doc.exists}")
    if not doc.exists: return None
    data = doc.to_dict()
    print(f"DEBUG find_email_firestore: Document data: {data}")
    if 'email' in data:
        possible_email = data['email']
        print(f"DEBUG find_email_firestore: Found email in document: {possible_email}")
        if '/' not in possible_email and '%' not in possible_email:
            print(f"DEBUG find_email_firestore: Returning company email: {data['email']}")
            return (data['email'], 'company')
        else:
            print(f"DEBUG find_email_firestore: Email contains invalid characters, updating document")
            ref.update({
                "actualAddress": False
            })
    if not name: 
        print(f"DEBUG find_email_firestore: No name provided, returning None")
        return None
    authors = ref.collection('authors')
    print(f"DEBUG find_email_firestore: Checking authors collection for {name}")
    authors_ref = authors.document(name).get()
    print(f"DEBUG find_email_firestore: Author document exists: {authors_ref.exists}")
    if not authors_ref.exists:
        print(f"DEBUG find_email_firestore: No author document found, returning None")
        return None
    author_data = authors_ref.to_dict()
    print(f"DEBUG find_email_firestore: Author data: {author_data}")
    print(f"DEBUG find_email_firestore: Returning personal email: {author_data.get('email')}")
    return (author_data['email'], 'personal')

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
    print(f"DEBUG: get_email_from_rsoup called with soup type: {type(r_soup)}")
    
    def get_href(x):
        if 'href' in x.attrs: 
            return x['href']
        return None
    
    r_soup_hrefs = list(map(get_href, r_soup.find_all('a')))
    print(f"DEBUG: Found {len(r_soup_hrefs)} href links")
    
    email_hrefs = []
    for href in r_soup_hrefs: 
        if href and ('@' in href and '/' not in href and '%' not in href):
            email_hrefs.append(href)
            print(f"DEBUG: Found potential email href: {href}")
    
    if not email_hrefs: 
        print("DEBUG: No email hrefs found")
        return None
    
    print(f"DEBUG: Found {len(email_hrefs)} email hrefs")
    try:
        most_similar_result = await most_similar(['contact@company.com'], email_hrefs)
        print(f"DEBUG: Most similar result: {most_similar_result}")
        email = email_hrefs[most_similar_result[0]]
        
        if 'mailto:' in email:
            email = email.split('mailto:')[-1]
            print(f"DEBUG: Extracted email from mailto: {email}")
        
        print(f"DEBUG: Final email: {email}")
        return (email if '@' in email else None)
    except Exception as e:
        print(f"DEBUG: Error in get_email_from_rsoup: {e}")
        return None

async def inurl_email(url):
    try:
        print(f"DEBUG: inurl_email called with URL: {url}")
        global headers
        query = 'inurl:' + url + ' "email"'
        print(f"DEBUG: Google search query: {query}")
        
        try:
            service = build("customsearch", "v1", developerKey=os.environ['GOOGLE_API_KEY'])
            print("DEBUG: Google API service built successfully")
            
            search_results = service.cse().list(q=query, cx='e3d6fd3b2065c471b', num=2).execute()
            print(f"DEBUG: Google search results: {search_results.keys()}")
            
            if 'items' not in search_results:
                print("DEBUG: No search results found")
                return None
                
            google_res = search_results['items']
            print(f"DEBUG: Found {len(google_res)} search results")
            
            email_urls = list(map(lambda x: x['link'], google_res))
            print(f"DEBUG: Email URLs: {email_urls}")
            
            email = None
            for email_url in email_urls:
                print(f"DEBUG: Checking URL: {email_url}")
                if not email:
                    try:
                        r = requests.get(email_url, headers=headers)
                        print(f"DEBUG: URL status code: {r.status_code}")
                        
                        if r.status_code == 200:
                            soup = BeautifulSoup(r.content, 'html5lib')
                            if soup:
                                print("DEBUG: Successfully parsed page")
                                email = await get_email_from_rsoup(soup)
                                if email:
                                    print(f"DEBUG: Found email: {email}")
                                    break
                    except Exception as e:
                        print(f"DEBUG: Error fetching URL {email_url}: {e}")
            
            print(f"DEBUG: Final email result: {email}")
            return email if email else None
        except Exception as e:
            print(f"DEBUG: Error with Google API: {e}")
            return None
    except Exception as e:
        print(f"DEBUG: Error in inurl_email: {e}")
        return CustErr(str(e))
