import pprint

from flask import jsonify, request, current_app
from werkzeug.utils import secure_filename
from helpers.helper import parse_json
from db import db
from helpers.helper import get_unique_urls, parse_json
from dotenv import load_dotenv
from bson.objectid import ObjectId
from kafka_setup.kafka_producer import message_producer
import os
import jwt
from pinecone import Pinecone
from datetime import datetime, timezone

load_dotenv()

Account = db[os.getenv("ACCOUNT_COLLECTION_NAME")]
Contact = db[os.getenv("CONTACT_COLLECTION_NAME")]
Chat = db[os.getenv("CHAT_COLLECTION_NAME")]
Message = db[os.getenv("MESSAGES_COLLECTION_NAME")]
User = db[os.getenv("USER_COLLECTION_NAME")]


def get_contact():
    try:
        chat_id = request.args.get('chat_id')
        contact_details = Contact.find_one({"chat_id": ObjectId(chat_id)})
        if contact_details:
            data = parse_json(contact_details)
            return jsonify({"data": data}), 200
        else:
            return jsonify({"type": "error", "message": "No contact details found for the specified client ID"}), 404
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500
        


def add_contact():
    try:
        # Retrieve data from request
        linkedIn_url = request.form.get('linkedIn')
        linkedIn_fname = request.form.get('first_name')
        linkedIn_lname = request.form.get('last_name')
        company_id = request.form.get('company_id')

        file = request.files['file']

        if file is None:
            return jsonify({"type": "error", "message": "'file' is required"}), 400

        if not all([company_id, linkedIn_lname, linkedIn_fname, linkedIn_url]):
            return jsonify({"type": "error", "message": 'Missing required fields'}), 400

        if file is not None:
            # Validate file extension
            allowed_extensions = '.html'
            if not file.filename.lower().endswith(allowed_extensions):
                return jsonify({"type": "error",
                                'message': 'Invalid file type. Allowed formats: ' + ', '.join(allowed_extensions)}), 400

            # filename
            filename = secure_filename(file.filename)

            # file path
            file_path = os.path.join(current_app.root_path, 'uploads', "in-html", filename)
            uploads_folder = os.path.dirname(file_path)  # Get the directory path
            if not os.path.exists(uploads_folder):
                os.makedirs(uploads_folder)  # Create the directory if it doesn't exist
            file.save(file_path)  # Save file with new filename

        # checking if company already exists or not
        existing_company = Account.find_one({'_id': ObjectId(company_id)})
        if not existing_company:
            return jsonify({"type": "error", "message":  "Client does not exists"}), 400

        existing_contact = Contact.find_one({
            'linkedIn': linkedIn_url
        })

        if existing_contact:
            return jsonify({"type": "error", "message": "Contact already associated with a client!!"}), 500

        contact_response = Contact.insert_one({
            'linkedIn': linkedIn_url,
            'first_name': linkedIn_fname,
            'last_name': linkedIn_lname,
            'account': ObjectId(company_id),
            "status": "pending",
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc)
        })

        if contact_response.acknowledged:
            Account.find_one_and_update(
                {"_id": ObjectId(company_id)},
                {"$push": {"contacts": contact_response.inserted_id}, "$set": {"updatedAt": datetime.now(timezone.utc)}}
            )

            # Send data to linkedin scrapper
            data = {
                "account": existing_company.get("name"),
                "contact": f"{linkedIn_fname} {linkedIn_lname}",
                "contact_id": str(contact_response.inserted_id),
                "url": linkedIn_url
            }

            if file is not None:
                data["file_path"] = file_path

            message_producer(os.getenv("LINKEDIN_CONSUMER"), data)
            return jsonify({"message": "Contact added!!"}), 200
        else:
            return jsonify({"type": "error", "message": "Failed to add contact!!"}), 500
    except Exception as e:
        print(e)
        return jsonify({"type": "error","message": "An unexpected error occurred: {}".format(str(e))}), 500


def delete_single_url():
    try:
        url = request.args.get('url', '')
        # Initialize pinecone
        pc = Pinecone(
            api_key=os.getenv("PINECONE_API_KEY"),  # find at app.pinecone.io
        )
        index_name = 'sales-bot'
        idx = pc.Index(index_name)

        deleted = idx.delete(
            filter={
                "url": url,
            }
        )
        print(deleted)
        return jsonify('deleted'), 200
    except Exception as e:
        return jsonify({"type": "error","message": "An unexpected error occurred: {}".format(str(e))}), 500


def add_pages():
    try:
        _id = request.json.get("_id")
        pages = request.json.get("pages")

        if not all([_id, pages]):
            return jsonify({"type": "error","message": "'_id' and 'pages' are required"}), 400

        pages = pages.split(",")
        pages = get_unique_urls(pages)
        print("Pages:", pages)

        response = Account.find_one({"_id": ObjectId(_id)})

        if response is None:
            return jsonify({"type": "error","message": "Account Not Found"}), 400

        pages = [page for page in pages if page not in response.get("pages")]

        Account.find_one_and_update(
            {"_id": ObjectId(_id)},
            {"$push": {"pages": {'$each': pages}}, "$set": {"updatedAt": datetime.now(timezone.utc)}}
        )

        # print(pages)
        if len(pages) != 0:
            data = {
                "urls": pages,
                'clientId': str(response.get("_id"))
            }
            message_producer(os.getenv("URL_CONSUMER"), data)

        return jsonify({"message": "Pages are being inserted"}), 200
    except Exception as e:
        return jsonify({"type": "error","message": f"Something went wrong: {e}"}), 500


def delete_page(account_id):
    try:
        page_url = request.json.get("page_url")

        if not page_url:
            return jsonify({"type": "error", "message": "'page_url' is required"}), 400

        response = Account.find_one({"_id": ObjectId(account_id)})

        if response is None:
            return jsonify({"type": "error", "message": "Account Not Found"}), 404

        if page_url not in response.get("pages", []):
            return jsonify({"type": "error", "message": "Page Not Found in Account"}), 404

        Account.update_one(
            {"_id": ObjectId(account_id)},
            {
                "$pull": {
                    "pages": page_url,
                    "scraped_pages": page_url  
                },
                "$set": {"updatedAt": datetime.now(timezone.utc)}
            }
        )

        return jsonify({"message": f"Page '{page_url}' has been deleted from the account"}), 200

    except Exception as e:
        return jsonify({"type": "error", "message": f"Something went wrong: {e}"}), 500


def scrape_apollo_pages():
    try:
        list_url = request.json.get("list_url")

        if not list_url:
            return jsonify({"type": "error", "message": f"List URL Missing"}), 404

        message_producer(os.getenv("URL_CONSUMER"), {"url": list_url})

        return jsonify({"type": "success", "message": "Scraping has begun"}), 200
    except Exception as e:
        return jsonify({"type": "error", "message": f"Something went wrong: {e}"}), 500


def delete_contact():
    try:
        _id = request.json.get("_id")
        if not _id:
            return jsonify({"type": "error", "message": "ID is missing"}), 400

        contact_data = Contact.aggregate([
            {
                "$match": {"_id": ObjectId(_id)}
            },
            {
                "$lookup": {
                  "from": "account_cl",
                  "localField": "account",
                  "foreignField": "_id",
                  "as": "account"
                }
            },
            {
                "$unwind": {"path": "$account"}
            }
        ])
        contact_data = parse_json(contact_data)
        contact_data = contact_data[0] if len(contact_data) > 0 else None

        if contact_data is None:
            return jsonify({"type": "error", "message": "Contact not found"}), 400

        token = request.headers.get("Authorization").split(" ")[1]
        user_id = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"]).get("_id")
        sales_owner = User.find_one({"_id": ObjectId(user_id)})
        sales_owner = sales_owner.get("name")

        if contact_data.get("sales_owner_name") != sales_owner:
            return jsonify({"type": "error", "message": "Unauthorized. Contact is not yours!"}), 403

        if contact_data.get("chat_id") is not None:
            chat_id = ObjectId(contact_data.get("chat_id").get("$oid"))
            Message.delete_many({"chat_id": chat_id})
            Chat.delete_one({"_id": chat_id})

        account_id = ObjectId(contact_data.get("account").get("_id").get("$oid"))
        no_of_contacts = len(contact_data.get("account").get("contacts") or [])

        account_deleted = False
        
        if no_of_contacts == 1:
            Account.delete_one({"_id": account_id})
            account_deleted = True
        else:
            contacts = contact_data.get("account").get("contacts")
            updated_contacts = [ObjectId(contact.get("$oid")) for contact in contacts if str(contact.get("$oid")) != str(_id)]
            Account.find_one_and_update({"_id": account_id}, {"$set": {"contacts": updated_contacts}})

        Contact.delete_one({"_id": ObjectId(_id)})
        return jsonify({"type": "success", "message": "Contact deleted", "account_deleted": account_deleted}), 200
    except Exception as e:
        return jsonify({"type": "error", "message": f"Something went wrong: {e}"}), 500