from flask import jsonify, request
from dotenv import load_dotenv
from db import db
import os
from bson.objectid import ObjectId
from datetime import datetime, timezone
from pymongo import ReturnDocument
from langchain.memory import ChatMessageHistory
from helpers.helper import parse_json
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone as PineconeLC
from helpers.helper import extract_data_from_context
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains.combine_documents import create_stuff_documents_chain

load_dotenv()


Chat = db[os.getenv("CHAT_COLLECTION_NAME")]
Message = db[os.getenv("MESSAGES_COLLECTION_NAME")]
Contact = db[os.getenv("CONTACT_COLLECTION_NAME")]
Account = db[os.getenv("ACCOUNT_COLLECTION_NAME")]
LinkedinURL = db[os.getenv("LINKEDIN_URL_COLLECTION_NAME")]

def lin_add_message():
    try:
        # get details from the request body
        sender = request.json.get('sender')
        message = request.json.get('message')
        time = request.json.get('time')
        linkedin_url = request.json.get('linkedin_url')
        sales_owner = request.json.get('sales_owner')

        # handle missing fields
        if not all([sender,message, time, linkedin_url, sales_owner]):
            return jsonify({"type": "error", 'message': 'Please provide all the fields'}), 400
        
        # check for existing the contact
        existing_contact = Contact.find_one({"linkedin_profile": linkedin_url})

        # if contact not found
        if not existing_contact:
            return jsonify({"type":"error", "message":"Contact does not exist!!"}),404

        sales_owner_name = existing_contact.get('sales_owner_name') or None
        if sales_owner_name != sales_owner:
            return jsonify({"type":"error", "message":f"Contact is not assigned to you. It is assigned to {sales_owner_name}"}),403
        
        # ---done with contact---
            
        # get id of contact
        id_of_contact = existing_contact.get('_id') 

        # get chat id from the contact
        chat_id_from_contact = existing_contact.get('chat_id') 

        if not chat_id_from_contact:
            # get details to create chat
            client_name = existing_contact.get('name')
            account_id = existing_contact.get('account') 
            company_name = existing_contact.get('company_name')
            if not company_name:
                account_detail = Account.find_one({"_id":account_id})
                if account_detail:
                    company_name = account_detail.get('name')

            # create the chat
            created_chat = Chat.insert_one({
                "client":client_name,
                "company":company_name or 'none',
                "sales_owner":sales_owner,
                "messages":[],
                "linkedin_profile":linkedin_url,
                "createdAt":datetime.now(timezone.utc),
                "updatedAt": datetime.now(timezone.utc)
            })

            if not created_chat:
                return jsonify({"message":"Failed to create Chat!!", "type":"error"}),400
            else:
                chat_id_from_contact = created_chat.inserted_id
                Contact.find_one_and_update({"_id": id_of_contact},{"$set":{"chat_id":created_chat.inserted_id}})
        

        # find chat(document) from the chat collection based on chat id received from the contact
        existing_chat_res = Chat.find_one({"_id": chat_id_from_contact})
        
        # ---done with chat---

        # get chat id 
        chat_id = existing_chat_res.get('_id') or created_chat.inserted_id

        # to determine whether it's human or ai message we'll keep track of few names, if the current name is among them then the message will be of type ai otherwise of type human
        if sender == sales_owner:
            message_type = "ai"
        else:
            message_type = "human"

        # converted time string into suitable format date string for mongoDB
        time = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")

        message_exists = Message.find_one({"chat_id":chat_id,"content":message, "createdAt":time})
        if message_exists:
            return jsonify({"type":"success","message":"Message already saved!!"}),303
        
        message_response = Message.insert_one({
            'type': message_type,
            'content': message,
            'chat_id': ObjectId(chat_id),
            "createdAt":time ,
            "updatedAt": datetime.now(timezone.utc),
            "message_from":"linkedin"
        })

        Chat.find_one_and_update({"_id": chat_id}, {"$push": {"messages": message_response.inserted_id},
                                                                "$set": {"updatedAt": datetime.now(timezone.utc)}})
        
        return jsonify({"type":"success","message":"Message saved successfully !!"}),200
        
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500


def lin_gen_message():
    try:
        linkedin_url = request.json.get('linkedin_url')
        sales_owner = request.json.get('sales_owner')

        if not all([linkedin_url, sales_owner]):
            return jsonify({"type":"error", "message":"Please provide linkedin url and sales owner"}),400
        
        demo_ephemeral_chat_history = ChatMessageHistory()

        existing_chat_contact = Contact.find_one({"linkedin_profile":linkedin_url})

        # if contact not found
        if not existing_chat_contact:
            return jsonify({"type":"error", "message":"Contact does not exist!!"}),404

        sales_owner_name = existing_chat_contact.get('sales_owner_name')
        if sales_owner_name != sales_owner:
            return jsonify({"type":"error", "message":f"Contact is not assigned to you. It is assigned to {sales_owner_name}"}),403
        
        chat_id_from_contact = existing_chat_contact.get('chat_id')

        if not chat_id_from_contact:
            return jsonify({"type":"error", "message":"Please save the messages first"}),400 
        
        company_name = existing_chat_contact.get('company_name')

        # retrieve previous conversation
        prev_messages = Chat.aggregate([
            {
                "$match":{
                    "_id":chat_id_from_contact
                }
            },
            {
                "$lookup":{
                    "from": "messages_cl",
                    "localField": "messages",
                    "foreignField": "_id",
                    "as": "messages",
                    "pipeline": [
                        {
                            "$sort":{
                                "createdAt":1
                            }
                        }
                    ]
                }
            }
        ])

        prev_messages = parse_json(prev_messages)
        if not prev_messages:
            return jsonify({"type":"error", "message":"No chat with this profile"}),404
        

        for message in prev_messages[0]['messages']:
            if message.get('type') == 'human':
                demo_ephemeral_chat_history.add_user_message(message.get('content'))
            else:
                demo_ephemeral_chat_history.add_ai_message(message.get('content'))
        print(demo_ephemeral_chat_history)
        embeddings = OpenAIEmbeddings()
        vectorstore = PineconeLC.from_existing_index("sales-bot", embeddings)
        retriever = vectorstore.as_retriever(search_type='similarity',
                                                search_kwargs={
                                                    'k': 10,
                                              }, )
        
        search_results = retriever.invoke(f"Find the details about the {company_name}. As well as find information about the past work that AlphaBI has done or been part of.")
        
        chat = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.8)

        prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        """
                        Consider your self as Business development executive at AlphaBI, a digital transformation partner company.
                        There's an ongoing conversation with a potential client in linkedin messages.
                        Answer the latest question of the client with context provided: \n{context} 
                        If you are not asked any question then just generate an conversation starter message using the above provided context.
                    """,

                    ),
                    MessagesPlaceholder(variable_name="messages"),
                ]
            )
        
        chain = create_stuff_documents_chain(chat, prompt)

        response = chain.invoke({"messages": demo_ephemeral_chat_history.messages, "context": search_results })

        return jsonify({
            "type":"success",
            "message":response
        }),200

    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500
    

def lin_get_url():
    threadURL = request.json.get('threadURL')

    if not threadURL:
        return jsonify({"type":"error", "message":"Please provide threadID"}),400
    
    existing_lin_url = LinkedinURL.find_one({"threadID":threadURL})

    if not existing_lin_url:
        return jsonify({"type":"error", "message":"Thread id does not exist"}), 404
    
    return jsonify({"url":existing_lin_url.get('linkedin_profile')}),200
    

def lin_save_url():
    currentThread = request.json.get('currentThread')
    linkedin_profile = request.json.get('clickedUrl')
    
    if not all([currentThread, linkedin_profile]):
        return jsonify({"type":"error", "message":"Please provide all details"}),400
    
    existing = LinkedinURL.find_one({"threadID":currentThread})
    if existing:
        return jsonify({"message":"already saved the url"}),200
    
    response = LinkedinURL.insert_one({
        "threadID":currentThread,
        "linkedin_profile":linkedin_profile,
        "createdAt":datetime.now(timezone.utc),
    })

    if not response:
        return jsonify({"type":"error","message":"Failed to save the url"}), 400
    
    return jsonify({"message":"Saved the url!! "}),200
    
    