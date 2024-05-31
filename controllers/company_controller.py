from flask import jsonify, request

from db import db
from helpers.helper import parse_json
from helpers.helper import get_unique_urls
from dotenv import load_dotenv
from bson.objectid import ObjectId
import os
from datetime import datetime, timezone

load_dotenv()

Account = db[os.getenv("ACCOUNT_COLLECTION_NAME")]
Contact = db[os.getenv("CONTACT_COLLECTION_NAME")]


def get_company_data():
    try:
        limit = int(request.args.get("limit")) if request.args.get("limit") is not None else 4
        skip = int(request.args.get("skip")) * limit if request.args.get("skip") is not None else 0
        account = request.args.get("account")
        sales_owner = request.args.get("sales_owner")
        count = Account.count_documents({
            "name": {"$regex": account, "$options": "i"},
            "sales_owner_name": sales_owner
        })

        steps = [
            {
                "$match": 
                    {
                        "name": { "$regex": account, "$options": "i"},
                        "sales_owner_name": sales_owner
                    }
            },
            {
                "$skip": skip
            },
            {
                "$limit": limit
            },
            {
                "$sort": {
                    "updatedAt": -1
                }
            },
            {
                "$lookup":
                    {
                        "from": "contact_cl",
                        "localField": "contacts",
                        "foreignField": "_id",
                        "as": "contacts",
                    },
            },
            {
                "$unset": ["description", "tags"]
            },
            {
                "$project": {
                    "name": 1,
                    "contacts.name": 1,
                    "updatedAt": 1,
                    "createdAt": 1,
                    "industry": 1,
                    "website": 1
                }
            }
        ]

        response = Account.aggregate(steps)
        data = parse_json(response)

        if not data:
            return jsonify({"data": [], "pagination": {"total_count": count, "offset": skip, "limit": limit}}), 200

        return jsonify({"data": data, "pagination": {"total_count": count, "offset": skip, "limit": limit}}), 200
    except Exception as e:
        return jsonify({"type": "error","message": "An unexpected error occurred: {}".format(str(e))}), 500


def create_company():
    try:
        # Retrieve data from request
        company_name = request.json.get('company_name')
        company_website = request.json.get('company_website')
        sales_owner = request.json.get("sales_owner")

        if not all([company_name, company_website]):
            return jsonify({"type": "error","message": 'Missing required fields'}), 400

        company_website = get_unique_urls([company_website])[0]

        # checking if company already exists or not
        existing_company = Account.find_one({
            '$or': [
                {'website': company_website},
                {'name': company_name}
            ]
        })
        if existing_company:
            return jsonify({"type": "error","message":  "Client already exists"}), 400

        response = Account.insert_one({
            'name': company_name,
            'website': company_website,
            'sales_owner': sales_owner if sales_owner is not None else "AlphaBI",
            'pages': [],
            'scraped_pages': [],
            'contacts': [],
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc)
        })

        if response.acknowledged:
            return jsonify({"message": "Client created"}), 200
        else:
            return jsonify({"type": "error","message": "Can't create client"}), 500
    except Exception as e:
        return jsonify({"type": "error","message":  "An unexpected error occurred: {}".format(str(e))}), 500


def update_company(client_id):
    try:
        company_name = request.json.get('company_name')
        company_website = request.json.get('company_website')
        company_industry = request.json.get('industry')
        
        if company_name is None or company_website is None:
            return jsonify({"type": "error","message": "Please provide all the field"}),400
        # Checking if client already exists or not
        company_filter = {"_id": ObjectId(client_id)}
        existing_company = Account.find_one(company_filter)

        if not existing_company:
            return jsonify({"type": "error","message": "Client does not exists"}), 400

        update = {
            "$set": {
                "updatedAt": datetime.now(timezone.utc)
            }
        }

        if company_name is not None and len(company_name) != 0:
            temp = update.get("$set")
            temp["name"] = company_name
            update["$set"] = temp

        if company_website is not None and len(company_website) != 0:
            temp = update.get("$set")
            temp["website"] = company_website
            update["$set"] = temp

            temp = update.get("$set")
            temp["tags.0"] = company_industry
            update["$set"] = temp

        Account.update_one(company_filter, update)
        return jsonify({"message": "Updated successfully!"}), 200
    except Exception as e:
        return jsonify({"type": "error","message": "An unexpected error occurred: {}".format(str(e))}), 500


def delete_company():
    try:
        client_id = request.json.get('_id')
        contact_response = Contact.delete_many({'account': ObjectId(client_id)})
        if contact_response.acknowledged:
            response = Account.delete_one({"_id": ObjectId(client_id)})
            if response.deleted_count == 1:
                return jsonify({"message": "Deleted successfully!"}), 200
            else:
                return jsonify({"type": "error","message": "Client not found!"}), 400
        else:
            return jsonify({"type": "error","message":  "Failed to delete associated contacts!!"}), 404
    except Exception as e:
        return jsonify({"type": "error","message": "An unexpected error occurred: {}".format(str(e))}), 500


def get_single_company(client_id):
    try:
        response = Account.aggregate([
            {
                "$match":
                    {
                        "_id": ObjectId(client_id)
                    }
            },
            {
                "$lookup":
                    {
                        "from": "contact_cl",
                        "localField": "contacts",
                        "foreignField": "_id",
                        "as": "contacts",
                    },
            }])
        data = parse_json(response)

        if not data:
            return jsonify({"type": "error","message":  "Client not found"}), 404

        return jsonify(data[0]), 200
    except Exception as e:
        return jsonify({"type": "error","message": "An unexpected error occurred: {}".format(str(e))}), 500
