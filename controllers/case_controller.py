from flask import jsonify,request,current_app
from db import db
from helpers.helper import parse_json
from dotenv import load_dotenv
from bson.objectid import ObjectId
import os
from werkzeug.utils import secure_filename
from helpers.helper import create_random_string
from helpers.vectorstore import FileType
from flask.helpers import get_root_path
from datetime import datetime, timezone
from kafka_setup.kafka_producer import message_producer

load_dotenv()

Case = db[os.getenv("CASE_COLLECTION_NAME")]

def case_data():
    try:
        response = Case.find({})
        data = parse_json(response)

        if not data: 
            data = []
        
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500


def create_case():
    try:
        # Access form data and file
        title = request.form.get('title')  
        keywords_string = request.form.get('keywords')
        drive_url = request.form.get("drive_url")

        if not all([title, keywords_string]):
            return jsonify({"type": "error", 'message': 'Missing required fields'}), 400
        
        if 'file' not in request.files:
            return jsonify({"type": "error", 'message': 'No file uploaded'}), 400

        file = request.files['file']  # Access uploaded file

        keywords = keywords_string.split(',')

        # Check for existing case
        existing_client = Case.find_one({'title': title})  # Use title for unique
        if existing_client:
            return jsonify({"type": "error", "message": "Case already exists"}), 400

        # Validate file extension
        allowed_extensions = ('.md', '.pdf', '.txt')
        if not file.filename.lower().endswith(allowed_extensions):
            return jsonify({"type": "error", 'message': 'Invalid file type. Allowed formats: ' + ', '.join(allowed_extensions)}), 400

        # filename
        filename = secure_filename(file.filename)
        base, ext = os.path.splitext(filename)  # Split filename into base and extension
        random_string = create_random_string()
        new_filename = f"{base}_{random_string}{ext}"  # Construct new filename with random string

        # file path
        file_path = os.path.join(current_app.root_path, 'uploads', new_filename)
        uploads_folder = os.path.dirname(file_path)  # Get the directory path
        if not os.path.exists(uploads_folder):
            os.makedirs(uploads_folder)  # Create the directory if it doesn't exist
        file.save(file_path)  # Save file with new filename

        # Insert case data, including file path
        response = Case.insert_one({
            'title': title,
            'file_path': f'uploads/{new_filename}',   #append the root path when we retrieve the document from the database
            'keywords': keywords,
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc)
        })

        if response.acknowledged:
            metadata = {
                'keywords': keywords,
                "drive_url": drive_url,
            }
            data = {
                "content":"",
                "client": 'AlphaBI',
                "metadata": metadata,
                "file_path":file_path,
                "file_type":FileType.MD.value
            }
            message_producer(os.getenv("EMBED_CONSUMER"), data)
            return jsonify({"message": "Case created"}), 200
        else:
            return jsonify({"type": "error", "message": "Can't create case"}), 500

    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500

def delete_case():
    try:
        case_id = request.json.get("_id")
        
        case_to_delete = Case.find_one({"_id": ObjectId(case_id)})
        if case_to_delete:
            file_path= case_to_delete.get('file_path')
            file_path = os.path.join(current_app.root_path, file_path)  # Construct full file path
            if os.path.exists(file_path):  # Check if file exists
                os.remove(file_path)  # Delete the file
            else:
                print(f"File not found: {file_path}")
                
        response = Case.delete_one({"_id": ObjectId(case_id)})  
        
        if response.deleted_count == 1:
            return jsonify({"message": "Case deleted"}), 200
        else:
            return jsonify({"type": "error", "message": "Case not found"}), 404
    except Exception as e:
        return jsonify({"type": "error", "message": "An unexpected error occurred: {}".format(str(e))}), 500
