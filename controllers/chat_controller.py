from flask import jsonify, request
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ChatMessageHistory
from dotenv import load_dotenv
from datetime import datetime, timezone
from db import db
import os
from helpers.helper import parse_json
from bson.objectid import ObjectId
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone as PineconeLC
from helpers.helper import extract_data_from_context
from pymongo import ReturnDocument
from langchain.chains.combine_documents import create_stuff_documents_chain

load_dotenv()

Chat = db[os.getenv("CHAT_COLLECTION_NAME")]
Message = db[os.getenv("MESSAGES_COLLECTION_NAME")]
Message_feedback = db[os.getenv("MESSAGE_FEEDBACK_CL")]


def send_message(chat_id):
    try:
        client_message = request.json.get('client_message')
        use_ai = request.json.get('use_ai')
        message_type = request.json.get('message_type')
        generate_with_ai = request.json.get('generate_with_ai')

        if use_ai is None:
            use_ai = False
        elif use_ai is False:
            if message_type is None:
                return jsonify({"type": "error", 'message': "'message_type' is required when 'use_ai' is false"}), 400

        if message_type is not None:
            if message_type != "human" and message_type != "ai":
                return jsonify({"type": "error", 'message': "Illegal value for 'message_type' [human|ai]"}), 400

        if not all([client_message, chat_id]):
            return jsonify({"type": "error", 'message': 'Please provide all the details'}), 400

        # check if the conversation exists or not
        existing_chat_res = Chat.find({"_id": ObjectId(chat_id)})
        existing_chat_res = parse_json(existing_chat_res)
        if not existing_chat_res:
            return jsonify({"type": "error", 'message': 'No chat found'}), 400

        company_name = existing_chat_res[0]['company']
        
        if generate_with_ai is not True:
            # store the client_message in the database as client message
            message_response = Message.insert_one({
                'type': message_type if message_type is not None else "human",
                'content': client_message,
                'chat_id': ObjectId(chat_id),
                "createdAt": datetime.now(timezone.utc),
                "updatedAt": datetime.now(timezone.utc),
                'message_from': 'human'
            })

            Chat.find_one_and_update(
                {"_id": ObjectId(chat_id)},
                {
                    "$push": {"messages": message_response.inserted_id},
                    "$set": {"updatedAt": datetime.now(timezone.utc)}
                }
            )

        if use_ai:
            demo_ephemeral_chat_history = ChatMessageHistory()

            # retrieved previous conversation
            res = Chat.aggregate([
                {
                    "$match":{
                        "_id":ObjectId(chat_id)
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

            prev_messages = parse_json(res)
            if not prev_messages:
                return jsonify({"type":"error", "message":"No chat with this profile"}),404
            
            for message in prev_messages[0]['messages']:
                if message.get('type') == 'human':
                    demo_ephemeral_chat_history.add_user_message(message.get('content'))
                else:
                    demo_ephemeral_chat_history.add_ai_message(message.get('content'))

            # taking context from the pinecone
            embeddings = OpenAIEmbeddings()
            vectorstore = PineconeLC.from_existing_index("sales-bot", embeddings)
            retriever = vectorstore.as_retriever(search_type='similarity',
                                                 search_kwargs={
                                                     'k': 10
                                                 }, )

            search_results = retriever.invoke(f"Find the details about the {company_name}. As well as find services of AlphaBI and past works.")

            chat = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.8)

            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        """Consider your self as Business development executive at AlphaBI, a digital transformation partner company.
                    You have sent an ice breaker message to a potential client and they have responded with a question, now you have to answer the questions that the clients asks related to the ice breaker message or AlphaBI's work abilities or past works.

                    MUST:
                    - Do not mention that you're provided any kind of data or don't say thanks about it
                    - Message should be crafted from the context: \n{context}
                    """,

                    ),
                    MessagesPlaceholder(variable_name="messages"),
                ]
            )
            
            chain = create_stuff_documents_chain(chat, prompt)
            response = chain.invoke({"messages": demo_ephemeral_chat_history.messages, "context": search_results})

            # store the response in database as the ai response
            ai_message_response = Message.insert_one({
                'type': 'ai',
                'content': response,
                'chat_id': ObjectId(chat_id),
                "createdAt": datetime.now(timezone.utc),
                "updatedAt": datetime.now(timezone.utc),
                'message_from': 'ai'
            })

            Chat.find_one_and_update({"_id": ObjectId(chat_id)}, {
                "$push": {"messages": ai_message_response.inserted_id}, "$set": {"updatedAt": datetime.now(timezone.utc)}})
            
            return jsonify({"data": {
                '_id': str(ai_message_response.inserted_id),
                'type': 'ai',
                'content': response,
                'chat_id': chat_id,
                "createdAt": datetime.now(timezone.utc),
                "updatedAt": datetime.now(timezone.utc),
                'message_from': 'ai'
            }}), 200
        else:
            return jsonify({"data": {
                "_id": str(message_response.inserted_id),
                'type': message_type if message_type is not None else "human",
                'content': client_message,
                'chat_id': chat_id,
                "createdAt": datetime.now(timezone.utc),
                "updatedAt": datetime.now(timezone.utc),
                'message_from': 'human'
            }}), 200
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500


def edit_message(message_id):
    try:
        client_message = request.json.get("client_message")
        message = Message.find_one_and_update({"_id": ObjectId(message_id)}, {"$set": {"content": client_message,
                                                                                       "updatedAt": datetime.now(timezone.utc)}})

        Chat.find_one_and_update({"_id": message.get("chat_id")}, {"$set": {"updatedAt": datetime.now(timezone.utc)}})
        return jsonify({"message": "Edited Successfully", "data": client_message}), 200
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500


def get_chats():
    try:
        sales_owner = request.args.get("sales_owner")
        chats = Chat.find({"sales_owner": sales_owner}, {"client": 1, "company": 1, "updatedAt": 1})
        chats = parse_json(chats)
        return jsonify({"data": chats}), 200

    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500


def get_chat(chat_id):  
    try:
        limit = int(request.args.get("limit")) if request.args.get("limit") is not None else 10
        skip = int(request.args.get("skip")) * limit if request.args.get("skip") is not None else 0
        count = Message.count_documents({"chat_id": ObjectId(chat_id)})

        response = Chat.aggregate([
            {
                "$match":
                    {
                        "_id": ObjectId(chat_id),
                    },
            },
            {
                "$lookup": {
                    "from": "messages_cl",
                    "localField": "messages",
                    "foreignField": "_id",
                    "as": "messages",
                    "pipeline": [
                        {
                            "$sort": {"createdAt": -1},
                        },
                        {
                            "$skip": skip,
                        },
                        {
                            "$limit": limit,
                        },
                        {
                            "$unset": ["chat_id"],
                        },
                        {
                            "$lookup": {
                                "from": "message_feedback_cl",
                                "localField": "feedback",
                                "foreignField": "_id",
                                "as": "feedback",
                                "pipeline": [
                                    {
                                        "$project": {
                                            "value": 1,
                                            "_id": 0,
                                        },
                                    },
                                ],
                            },
                        },
                        {
                            "$unwind": {
                                "path": "$feedback",
                                "preserveNullAndEmptyArrays": True,
                            },
                        },
                        {
                            "$set": {
                                "feedback": "$feedback.value",
                            },
                        },
                    ],
                },
            },
        ])
        data = parse_json(response)

        if not data:
            data = {}

        return jsonify({"data": data[0], "pagination": {"total_count": count, "offset": skip, "limit": limit}}), 200
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500


def start_chat():
    try:
        ice_breaker = request.json.get('ice_breaker')
        client_name = request.json.get('client_name')
        company_name = request.json.get('company_name')
        sales_owner = request.json.get("sales_owner")

        res_existing_msg = Chat.find({"client": client_name, "company": company_name, "sales_owner": sales_owner})
        chat_exists = parse_json(res_existing_msg)
        if chat_exists:
            return jsonify({"message": "Chat already exists!!", "id": str(chat_exists[0]['_id']['$oid'])}), 200

        if not all([ice_breaker, client_name]):
            return jsonify({"type": "error", 'message': 'No ice breaker found'}), 400

        chat_response = Chat.insert_one({
            "client": client_name,
            "company": company_name,
            "sales_owner": sales_owner,
            "messages": [],
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc)
        })

        message_response = Message.insert_one({
            'type': 'ai',
            'content': ice_breaker,
            'chat_id': chat_response.inserted_id,
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc),
            'message_from': 'ai'
        })

        Chat.find_one_and_update({"_id": ObjectId(chat_response.inserted_id)},
                                 {"$push": {"messages": message_response.inserted_id}})

        return jsonify({"message": "Chat Created!!", "id": str(chat_response.inserted_id)}), 200
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500


def rate_message(message_id):
    try:
        rating = int(request.json.get("value"))
        message = request.json.get("message")
        user_id = request.json.get("user_id")

        if message is None or user_id is None:
            return jsonify({"type": "error", "message": "Field 'message', 'user_id' is required"}), 400

        if rating is None or rating not in [-1, 0, 1]:
            return jsonify({"type": "error", "message": f"Inappropriate feedback value: {rating}"}), 400

        msg_exists = Message.find_one({"_id": ObjectId(message_id)})
        message_exists = parse_json(msg_exists)
        if not message_exists:
            return jsonify({"type": "error", "message": "Message not found"}), 400

        try:
            fb = Message_feedback.find_one_and_update({
                "message_id": ObjectId(message_id),
            }, {
                "$set": {
                    "message": message,
                    "message_id": ObjectId(message_id),
                    "user": ObjectId(user_id),
                    "value": rating
                }
            }, upsert=True, return_document=ReturnDocument.AFTER)
        except Exception as e:
            return jsonify({"type": "error", "message": "Failed to add feedback!"}), 400

        Message.find_one_and_update({"_id": ObjectId(message_id)}, {"$set": {"feedback": fb["_id"]}})

        return jsonify({"message": "Feedback added!!"}), 200
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500
