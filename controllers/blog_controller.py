import os
from db import db
from helpers.helper import parse_json
from strapi.fetch_blogs import fetch_and_set
from flask import jsonify
from helpers.custom_error import CustomEmbedError
Blogs = db[os.getenv("BLOGS_COLLECTION_NAME")]

def fetch_blog():
    try:
        db_date_data = Blogs.find_one({})
        if db_date_data:
            db_date = parse_json(db_date_data)
            last_fetched_date = db_date.get('updatedAt') if db_date.get('updatedAt') is not None else '1970-01-01T00:00:00.000Z'
        else:    
            last_fetched_date = '1970-01-01T00:00:00.000Z'

        kula_response = fetch_and_set(f'https://kula-strapi-dev-app-lotqt.ondigitalocean.app/api/blogs?populate=writtenBy,Body&fields[0]=blogTitle&fields[1]=blogDescription&fields[2]=summary&fields[3]=blogSlug&fields[4]=updatedAt&filters[updatedAt][$gt]={last_fetched_date}')
        alpha_response = fetch_and_set(f'https://lobster-app-qktb6.ondigitalocean.app/api/blogs?populate=writtenBy,Body&fields[0]=Title&fields[1]=Tagline&fields[2]=slug&fields[3]=updatedAt&filters[updatedAt][$gt]={last_fetched_date}')
        print(kula_response)
        print(alpha_response)
        if kula_response and alpha_response:
            return jsonify({"message":"Successfully pushed to the blog consumer"}),200
        elif not kula_response:
            raise CustomEmbedError("Kula fetch failed")
        elif not alpha_response:
            raise CustomEmbedError("Alpha fetch failed")
    except CustomEmbedError as e:
        return jsonify({"type": "error", "message": str(e)}), 500
    except Exception as e:
        return jsonify({"type": "error", "message": "Failed to embed blog: {}".format(str(e))}), 500