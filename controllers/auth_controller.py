from flask import jsonify, request, redirect, url_for
from db import db
from dotenv import load_dotenv
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
import os
from helpers.helper import parse_json, extract_latest_message, extract_email, extract_subject, extract_date
from bson.objectid import ObjectId
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from upstash_qstash import Client
import base64
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

load_dotenv()

backend_url = os.getenv("FRONTEND_URL")
frontend_url = os.getenv("BACKEND_URL")

# set value 1 for local development
# os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

User = db[os.getenv("USER_COLLECTION_NAME")]
GmailAuth = db[os.getenv("GMAIL_AUTH_COLLECTION_NAME")]
Contact = db[os.getenv("CONTACT_COLLECTION_NAME")]
Chat = db[os.getenv("CHAT_COLLECTION_NAME")]
Message = db[os.getenv("MESSAGES_COLLECTION_NAME")]

CLIENT_CONFIG = {
    'web': {
        'client_id': os.getenv("CLIENT_ID"),
        'project_id': os.getenv("PROJECT_ID"),
        'auth_uri': os.getenv("AUTH_URI"),
        'token_uri': os.getenv("TOKEN_URI"),
        'auth_provider_x509_cert_url': os.getenv("AUTH_PROVIDER_X509_CERT_URL"),
        'client_secret': os.getenv("CLIENT_SECRET"),
        'redirect_uris': os.getenv("REDIRECT_URIS"),
        'javascript_origins': os.getenv("JAVASCRIPT_ORIGINS")
    }
}

SCOPES = os.getenv("SCOPES")
client = Client(os.getenv("QSTASH_TOKEN"))
schedules = client.schedules()

def create_and_add_message(gmail_message_id, content, chat_id, message_date, message_type="human", thread_id=None, subject=None, client_email=None, gmail=None):

    existing_message = Message.find_one({"gmail_message_id": gmail_message_id})
    if existing_message:
        return
    
    if thread_id and subject and client_email:
        chat_details = Chat.find_one({"_id": ObjectId(chat_id)})
        
        if chat_details:
            thread_exists = any(thread.get("thread_id") == thread_id for thread in chat_details.get("threads", []))
            
            if not thread_exists:
                Chat.find_one_and_update(
                    {"_id": ObjectId(chat_id)},
                    {"$push": {"threads": {"thread_id": thread_id, "subject": subject, "client_email": client_email}},
                    "$set": {"updatedAt": datetime.now(timezone.utc)}}
                )
                
                threads = gmail.users().threads().get(userId='me', id=thread_id).execute()
                
                for message in threads["messages"]:
                    labels = message["labelIds"]
                    message_type = "ai" if "SENT" in labels else "human"
                    message_body = extract_latest_message(message)
                    message_date = extract_date(message)
                    create_and_add_message(message.get("id"), message_body, chat_id, message_date, message_type)    
            else:
                create_and_add_message(gmail_message_id, content, chat_id, message_date, message_type)
    else:
        message_response = Message.insert_one({
            'type': message_type,
            'content': content,
            'chat_id': chat_id,
            'createdAt': message_date,
            'updatedAt': message_date,
            'message_from': 'email',
            'gmail_message_id': gmail_message_id
        }).inserted_id
        
        Chat.find_one_and_update(
            {"_id": ObjectId(chat_id)},
            {"$push": {"messages": message_response},
                "$set": {"updatedAt": message_date}}
        )


def user_login():
    try:
        email = request.json.get('email')
        password = request.json.get('password')

        if not all([email, password]):
            return jsonify({"type": "error", 'message': 'Missing required fields'}), 400

        stored_user = User.find_one({"email": email})
        if not stored_user:
            return jsonify({"type": "error",'message': 'User does not exist!!'}), 400

        is_auth = bcrypt.checkpw(password.encode('utf-8'), stored_user.get('password').encode('utf-8'))
        if not is_auth:
            return jsonify({'error': 'Invalid credentials!!'}), 400
        
        expiry_time = datetime.now(timezone.utc) + timedelta(days=1)

        jwt_token = jwt.encode({
            "_id": str(stored_user.get('_id')),
            "exp": expiry_time
        }, os.getenv("JWT_SECRET"), algorithm="HS256")
        
        name = stored_user.get('name')
        role = stored_user.get('role')
        is_gmail_connected = stored_user.get('is_gmail_connected')

        response_data = {"name": name, "token": jwt_token, "role": role, "email": email, "id": str(stored_user.get('_id')), "is_gmail_connected": is_gmail_connected}
        return jsonify(response_data), 200
    except Exception as e:
        return jsonify({"type": "error", "message": "Failed to create user: {}".format(str(e))}), 500


def user_create():
    try:
        name = request.json.get("name")
        email = request.json.get("email")
        password = request.json.get("password")
        role = request.json.get("role")
        role = role if role is not None else "MEMBER"

        if role != "ADMIN" and role != "MEMBER":
            return jsonify({"type": "error", "message": "Invalid Role Value"}), 400

        if name is None or email is None or password is None:
            return jsonify({"type": "error", "message": "Name, Email and Password are required"}), 404

        # Check if the email already exists
        existing_user = User.find_one({"email": email})
        if existing_user:
            return jsonify({"type": "error", "message": "Email already exists"}), 404  # 409 for conflict

        # Verify that user is an admin
        token = request.headers.get("Authorization").split(" ")[1]

        if token is None:
            return jsonify({"type": "error", "message": "Authorization Token missing or invalid"}), 404

        user_id = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"]).get("_id")

        db_user = User.find_one({"_id": ObjectId(user_id)})
        if db_user is None or db_user.get("role") != "ADMIN":
            return jsonify({"type": "error", "message": "Admin access is required"}), 403

        # Hash Password
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

        # Create document
        created_user = User.update_one({"email": email}, {"$set": {
            "name": name,
            "email": email,
            "password": password_hash,
            "role": role,
            "createdAt": datetime.now(timezone.utc),
            "is_gmail_connected": False
            }
        }, upsert=True)

        return jsonify({"message": "User upserted"}), 200
    except Exception as e:
        return jsonify({"type": "error","message": f"Something went wrong: {e}"}), 500
  

def user_update():
    try:
        user_id = request.json.get("userId")
        updates = {}

        # Check if user exists
        user = User.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"type": "error", "message": "User not found"}), 404

        # Update name if provided
        name = request.json.get("name")
        if name:
            updates["name"] = name

        # Update password if provided
        password = request.json.get("password")
        if password:
            password_bytes = password.encode('utf-8')
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
            updates["password"] = password_hash

        # Update role if provided
        role = request.json.get("role")
        if role:
            if role not in ["ADMIN", "MEMBER"]:
                return jsonify({"type": "error", "message": "Invalid Role Value"}), 400
            updates["role"] = role

        # Perform the update
        User.update_one({"_id": ObjectId(user_id)}, {"$set": updates})

        return jsonify({"message": "User updated successfully"}), 200
    except Exception as e:
        return jsonify({"type": "error","message": f"Failed to update user: {str(e)}"}), 500


def user_delete():
    try:
        user_id = request.json.get("_id")

        token = request.headers.get("Authorization").split(" ")[1]
        if token is None:
            return jsonify({"type": "error", "message": "Authorization Token missing or invalid"}), 404

        db_id = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"]).get("_id")

        if user_id == db_id:
            return jsonify({"type": "error", "message": "Cannot delete self"}), 400

        user = User.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"type": "error","message": "User not found"}), 404

        if user.get('is_gmail_connected') is True:
            gmail_data = GmailAuth.find_one({"email": user.get('email')})
            if gmail_data:
                refresh_token = gmail_data.get("refresh_token")
                credentials = Credentials(refresh_token=refresh_token, token_uri=os.getenv("TOKEN_URI"), client_id=os.getenv("CLIENT_ID"), client_secret=os.getenv("CLIENT_SECRET"), token=None)
                
                gmail = build('gmail', 'v1', credentials=credentials)
                response = gmail.users().stop(userId='me').execute()
            
                if not response:
                    if "schedule_id" in gmail_data:
                        schedules.delete(gmail_data.get("schedule_id"))
                    GmailAuth.delete_one({"email": user.get('email')})
            
        User.delete_one({"_id": ObjectId(user_id)})

        return jsonify({"message": "User deleted successfully"}), 200
    except Exception as e:
        return jsonify({"type": "error","message": "An unexpected error occurred: {}".format(str(e))}), 500
    

def get_users():
    try:
        limit = int(request.args.get("limit")) if request.args.get("limit") is not None else 5
        skip = int(request.args.get("skip")) if request.args.get("skip") is not None else 0
        count = User.count_documents({})
        
        response = User.aggregate([
            {
                "$skip": skip
            },
            {
                "$limit": limit
            },
            {
                "$unset": "password"
            }
        ])
        data = parse_json(response)
          
        if not data:
            return jsonify({"type": "error", "message": "No users found"}), 404

        return jsonify({"data": data, "pagination": {"total_count": count, "offset": skip, "limit": limit}}), 200
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500
    

def get_user(email):
    try:
        user = User.find_one({"email": email})
        if user:
            user["_id"] = str(user["_id"])
            del user["password"]
            expiry_time = datetime.now(timezone.utc) + timedelta(days=1)

            jwt_token = jwt.encode({
                "_id": str(user.get('_id')),
                "exp": expiry_time
            }, os.getenv("JWT_SECRET"), algorithm="HS256")
            
            user["token"] = jwt_token
            
            return jsonify({"data": user}), 200
        else:
            return jsonify({"type": "error", "message": "User not found for the provided email"}), 404
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500
    
    
def gmail_auth():
    try:
        email = request.args.get('email')
                
        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
        # flow.redirect_uri = url_for('auth.auth_oauth2callback', _external=True)
        flow.redirect_uri = url_for('auth.auth_oauth2callback', _external=True, _scheme="https")

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            prompt='consent'
        )
        
        auth_state_entry = {
            "$set": {
                "state": state,
                "created_at": datetime.now(timezone.utc)
            }
        }
        
        GmailAuth.update_one({"email": email}, auth_state_entry, upsert=True)
        
        return redirect(authorization_url)
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500
    
    
def oauth2callback():
    try:
        state = request.args.get('state')
        
        if state is None:
            return jsonify({"type": "error", "message": "State parameter is missing."}), 400
        
        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, state=state)
        # flow.redirect_uri = url_for('auth.auth_oauth2callback', _external=True)
        flow.redirect_uri = url_for('auth.auth_oauth2callback', _external=True, _scheme="https")

        authorization_response = request.url
        authorization_response = authorization_response.replace('http://', 'https://')

        flow.fetch_token(authorization_response=authorization_response)
        
        credentials = flow.credentials
        refresh_token = credentials.refresh_token
        gmail_data =  GmailAuth.find_one_and_update(
            {"state": state},
            {"$set": {"refresh_token": refresh_token}},
            upsert=True
        )
        
        schedule_id = gmail_data.get("schedule_id")
        destination_email = gmail_data.get("email")
        watch_res, _ = gmail_watch(destination_email)
        watch_res_json = watch_res.get_json()
        gmail_data = GmailAuth.find_one_and_update(
                        {"state": state},
                        {"$set": {"history_id": watch_res_json['data']['historyId']}},
                        upsert=True
                    )

        if schedule_id is None or schedules.get(schedule_id).get("destination").split("/")[-1] != destination_email:
            res = schedules.create({
                "destination": f"{backend_url}/api/gmail/watch/{gmail_data.get('email')}",
                "cron": "0 0 * * *",
            })
            
            GmailAuth.update_one(
                {"state": state},
                {"$set": {"schedule_id": res.get("scheduleId")}},
                upsert=True
            )
            
        User.find_one_and_update({"email": gmail_data.get("email")}, {"$set": {"is_gmail_connected": True}})

        return redirect(frontend_url)
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500


def gmail_watch(email):
    try:
        gmail_data = GmailAuth.find_one({"email": email})
        if gmail_data:
            refresh_token = gmail_data.get("refresh_token")
            if refresh_token:
                credentials = Credentials(refresh_token=refresh_token, token_uri=os.getenv("TOKEN_URI"), client_id=os.getenv("CLIENT_ID"), client_secret=os.getenv("CLIENT_SECRET"), token=None)
                                
                gmail = build('gmail', 'v1', credentials=credentials)

                watch_request = {
                    'labelIds': ['UNREAD'],
                    'topicName': os.getenv('TOPIC_NAME'),
                    'labelFilterBehavior': 'INCLUDE'
                }
                response =  gmail.users().watch(userId='me', body=watch_request).execute()
                
                if 'historyId' in response:
                    return jsonify({"type": "success", 
                                "message": "Watch request successfully set up.", 
                                "data": response}), 200
                else:
                    return jsonify({"type": "error", "message": "Failed to set up watch request."}), 500
            else:
                return jsonify({"type": "error", "message": "No refresh token found for the provided email."}), 404
        else:
            return jsonify({"type": "error", "message": "Email not found in the database."}), 404
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500
    
    
def gmail_notification():
    try:
        data = request.json.get("message").get("data")
        message = base64.b64decode(data).decode("utf-8")
        
        if message:
            message_data = json.loads(message)
            
            email = message_data.get("emailAddress")
            history_id = message_data.get("historyId")
            
            print(email, history_id)
            
            gmail_data = GmailAuth.find_one({"email": email})
            if gmail_data:
                refresh_token = gmail_data.get("refresh_token")
                if refresh_token:
                    credentials = Credentials(refresh_token=refresh_token, token_uri=os.getenv("TOKEN_URI"), client_id=os.getenv("CLIENT_ID"), client_secret=os.getenv("CLIENT_SECRET"), token=None)
                                    
                    gmail = build('gmail', 'v1', credentials=credentials)
                    prev_history_id = gmail_data.get("history_id")
                    
                    if prev_history_id:
                        history_list = gmail.users().history().list(userId='me', historyTypes='messageAdded', startHistoryId=prev_history_id).execute() 
                        history_id = history_list.get("historyId")
                        
                        if "history" in history_list:
                            for history_entry in history_list["history"]:
                                if "messagesAdded" in history_entry:
                                    for message_added in history_entry["messagesAdded"]:
                                        labels = message_added["message"]["labelIds"]
                                        if "UNREAD" in labels:
                                            message_id = message_added["message"]["id"]
                                            thread_id = message_added["message"]["threadId"]
                                            
                                            print(thread_id, message_id)
                                            
                                            message = gmail.users().messages().get(userId='me', id=message_id).execute()

                                            sender_email = extract_email(message, 'From')
                                            subject = extract_subject(message)
                                                    
                                            client_details = None
                                            
                                            if "SENT" in labels:
                                                receiver_email = extract_email(message, 'To')
                                                client_details = Contact.find_one({"emails": receiver_email})
                                            else:
                                                client_details = Contact.find_one({"emails": sender_email})
                                            
                                            if client_details:
                                                chat_id = client_details.get('chat_id')
                                                latest_message = extract_latest_message(message)
                                                print("message: " + latest_message)
                                                
                                                if chat_id:
                                                    message_type = "ai" if "SENT" in labels else "human"
                                                    message_date = extract_date(message)
                                                    create_and_add_message(message.get("id"), latest_message, ObjectId(chat_id), message_date, message_type, thread_id, subject, sender_email, gmail)
                                                elif "SENT" not in labels:
                                                    chat_response = Chat.insert_one({
                                                        "client": client_details.get('name'),
                                                        "company": client_details.get('company_name'),
                                                        "sales_owner": client_details.get('sales_owner_name'),
                                                        "messages": [],
                                                        "threads": [{ "thread_id": thread_id, "subject": subject, "client_email": sender_email }],
                                                        "createdAt": datetime.now(timezone.utc),
                                                        "updatedAt": datetime.now(timezone.utc)
                                                    })
                                                    
                                                    threads = gmail.users().threads().get(userId='me', id=thread_id).execute()
                                                    
                                                    for message in threads["messages"]:
                                                        labels = message["labelIds"]
                                                        message_type = "ai" if "SENT" in labels else "human"
                                                        message_body = extract_latest_message(message)
                                                        message_date = extract_date(message)
                                                        create_and_add_message(message.get("id"), message_body, chat_response.inserted_id, message_date, message_type)
                                                    
                                                    Contact.find_one_and_update(
                                                        {"_id": ObjectId(client_details.get("_id"))},
                                                        {"$set": {"chat_id": chat_response.inserted_id}}
                                                    )
                    else:
                        history_list = gmail.users().history().list(userId='me', historyTypes='messageAdded', startHistoryId=history_id).execute()
                        history_id = history_list.get("historyId")
                        
                    gmail_data =  GmailAuth.find_one_and_update(
                        {"email": email},
                        {"$set": {"history_id": history_id}},
                        upsert=True
                    )
            
        return jsonify({"message":"ok"}),200
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500
    
    
def disconnect_gmail():
    try:
        email = request.args.get('email')
        
        gmail_data = GmailAuth.find_one({"email": email})
        if gmail_data:
            refresh_token = gmail_data.get("refresh_token")
            if refresh_token:
                credentials = Credentials(refresh_token=refresh_token, token_uri=os.getenv("TOKEN_URI"), client_id=os.getenv("CLIENT_ID"), client_secret=os.getenv("CLIENT_SECRET"), token=None)
                
                gmail = build('gmail', 'v1', credentials=credentials)
                response = gmail.users().stop(userId='me').execute()
                
                if not response:
                    if "schedule_id" in gmail_data:
                        schedules.delete(gmail_data.get("schedule_id"))
                    GmailAuth.delete_one({"email": email})
                    User.find_one_and_update({"email": email}, {"$set": {"is_gmail_connected": False}})
                    return jsonify({"type": "success", "message": "Gmail disconnected successfully."}), 200
                else:
                    return jsonify({"type": "error", "message": "Failed to disconnect Gmail."}), 500
            else:
                return jsonify({"type": "error", "message": "No refresh token found for the provided email."}), 404
        else:
            return jsonify({"type": "error", "message": "Email not found in the database."}), 404
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500


def send_gmail(sender_email):
    try:
        recipient_email = request.json.get('recipient_email')
        message_body = request.json.get('message_body')
        subject = request.json.get('subject')
        message_id = request.json.get('message_id')
        thread_id = request.json.get('thread_id')
        chat_id = request.json.get('chat_id')

        if not all([recipient_email, message_body, thread_id]):
            return {"type": "error", "message": "Missing required parameters. Please provide recipient_email, message_body, and thread_id."}, 400

        gmail_data = GmailAuth.find_one({"email": sender_email})
        if gmail_data:
            client_details = Contact.find_one({"emails": recipient_email})
            if client_details:
                refresh_token = gmail_data.get("refresh_token")
                if refresh_token:
                    credentials = Credentials(
                        refresh_token=refresh_token,
                        token_uri=os.getenv("TOKEN_URI"),
                        client_id=os.getenv("CLIENT_ID"),
                        client_secret=os.getenv("CLIENT_SECRET"),
                        token=None
                    )

                    service = build('gmail', 'v1', credentials=credentials)
                    
                    thread = service.users().threads().get(userId='me', id=thread_id).execute()
                    messages = thread['messages'][0]['payload']['headers']

                    for (k) in messages:
                        if k['name'] == 'Message-ID':
                            email_message_id = k['value']

                    current_date = datetime.now()
                    formatted_date = current_date.strftime("%S")
                    
                    html_text = message_body.replace("\n", f'<br><span style="display: none; opacity: 0">{formatted_date}</span>')
                    html_text = f'<span style="display: none; opacity: 0">{formatted_date}</span>{html_text}<span style="display: none; opacity: 0">{formatted_date}</span>'
                    
                    message = MIMEMultipart()
                    message['to'] = recipient_email
                    message['subject'] = subject
                    message['References '] = email_message_id
                    message['In-Reply-To '] = email_message_id
                    message.attach(MIMEText(html_text, "html"))
                    
                    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

                    create_message = {'raw': encoded_message, 'threadId': thread_id}
                    send_message_res = service.users().messages().send(userId="me", body=create_message).execute()
                    
                    Message.find_one_and_update(
                        {'_id': ObjectId(message_id)},
                        {'$set': {'gmail_message_id': send_message_res.get("id"), 'message_from': 'email', 'content': message_body, 'updatedAt': datetime.now(timezone.utc)}},
                        upsert=True
                    )
                    
                    Chat.find_one_and_update(
                        {"_id": ObjectId(chat_id)},
                        {"$set": {"updatedAt": datetime.now(timezone.utc)}}
                    )
                    return {"type": "success", "message": "Email sent successfully."}, 200
                else:
                    return {"type": "error", "message": "No refresh token found for the provided sender email."}, 404
            else:
                return {"type": "error", "message": "Recipient email not found in the database."}, 404
        else:
            return {"type": "error", "message": "Please make sure that your Gmail is connected!"}, 404

    except Exception as e:
        return {"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}, 500


