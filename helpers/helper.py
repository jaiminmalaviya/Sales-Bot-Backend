from bson import json_util
import json
import random
import string
import base64
from cryptography.fernet import Fernet
import re
from datetime import datetime, timezone


def parse_json(data):
    return json.loads(json_util.dumps(data))

def create_random_string(length=7):
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(length))

def get_unique_urls(url_list):
    unique_urls = set()
    for url in url_list:
        url = 'https://' + url if '://' not in url else url
        url_with_www = url.replace('://www.', '://') if 'www.' in url else url
        unique_urls.add(url_with_www.rstrip('/').lower())

    return list(unique_urls)

def encrypt_message(message, key):
    f = Fernet(key)
    encrypted_message = f.encrypt(message.encode())
    return encrypted_message

def decrypt_message(encrypted_message, key):
    f = Fernet(key)
    decrypted_message = f.decrypt(encrypted_message).decode()
    return decrypted_message

def extract_data_from_context(context):
    extracted_data = []
    for document in context:
        extracted_data.append(document.page_content)
    return extracted_data

def decode_base64url_message(encoded_message):
    missing_padding = len(encoded_message) % 4
    if missing_padding:
        encoded_message += '=' * (4 - missing_padding)
    
    standard_base64 = encoded_message.replace('-', '+').replace('_', '/')
    decoded_bytes = base64.b64decode(standard_base64)
    decoded_message = decoded_bytes.decode('utf-8')
    return decoded_message

def extract_latest_message(message):
    message_parts = message.get("payload", {}).get("parts")
    encoded_message_body = ""

    if message_parts:
        encoded_message_body = message_parts[0].get("body", {}).get("data", "")
    else:
        encoded_message_body = message.get("payload", {}).get("body", {}).get("data", "")
        
    decoded_message_body = decode_base64url_message(encoded_message_body)
    latest_message = re.split(r"\n.*[\,].*\<\s*.*>", decoded_message_body)[0]
    return latest_message.strip()

def extract_info(message, prop):
    info = None
    prop = prop.lower() 

    for header in message['payload']['headers']:
        if header['name'].lower() == prop:
            info = header['value']
            break
    
    return info

def extract_email(message, prop='From'):
    email = None
    info = extract_info(message, prop)
    
    if info:
        start_index = info.find('<')
        end_index = info.find('>')
        if start_index != -1 and end_index != -1:
            info = info[start_index + 1:end_index]
            match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', info)
            if match:
                email = match.group()
    
    return email

def extract_subject(message):
    subject = extract_info(message, 'Subject')
    return subject

def extract_date(message):
    date_str = extract_info(message, 'Date')  
    parsed_date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
    return parsed_date