import requests
import json
import os
from helpers.helper import create_random_string
from kafka_setup.kafka_producer import message_producer
from helpers.vectorstore import FileType
from db import db
from helpers.helper import parse_json

Blogs = db[os.getenv("BLOGS_COLLECTION_NAME")]

def fetch_and_set(url):
    try:
        blogs_data= requests.get(url)
        blogs_json = json.loads(blogs_data.text)
        blogs = blogs_json['data']

        if not os.path.exists(os.path.join(os.getcwd(), "blogs")):
            os.mkdir(os.path.join(os.getcwd(), "blogs"))
        
        for blog in blogs:
            attributes = blog.get("attributes")

            blogTitle = attributes.get("Title") or attributes.get("blogTitle") or "No title available"
            blogDescription = attributes.get("blogDescription") or "No description available"
            blogTagline = attributes.get("Tagline") or "No tagline available"
            summary = attributes.get("Summary") or attributes.get("summary") or "No summary available"
            slug = attributes.get("blogSlug") or attributes.get("slug") or "No slug"
            Body = attributes.get("Body") or "No content in the body"
            updatedAt = attributes.get("updatedAt")
            
            
            writer_detail = []
            writtenBy = attributes.get("writtenBy").get("data")

            # filename
            random_string = create_random_string()
            filename = f"blogs_{random_string}.md" 

            with open(os.path.join(os.getcwd(), "blogs", filename), "w", encoding='utf-8') as file:
                file.write(f"# {blogTitle}\n\n")
                file.write(f"**Description:** {blogDescription}\n\n")
                file.write(f"**Tagline:** {blogTagline}\n\n")
                file.write(f"**Summary:** {summary}\n\n")
                file.write(f"**Slug:** {slug}\n\n") #just for fun

                file.write(f"**Content** \n\n")
                for item in Body:  
                    for i in range(1, 7):
                        heading_key = f'h{i}'
                        if heading_key in item:
                            heading = item[heading_key]
                            break
                    else:
                        heading = None

                    if heading:
                        file.write(f"## {heading}\n\n")
                    if 'paragraph' in item:
                        file.write(f"{item['paragraph']}\n\n")
                    elif 'Paragraph' in item:
                        file.write(f"{item['Paragraph']}\n\n")
                    else:
                        pass
                
                file.write(f"**Writers** \n\n")
                for writer_info in writtenBy:
                    writer_attributes = writer_info.get('attributes')  
                    file.write(f"Name: {writer_attributes.get('name')} \n")
                    file.write(f"Position: {writer_attributes.get('position')}\n")
                    file.write(f"Company: {writer_attributes.get('company')}\n\n")
                    writer_detail.append(
                        writer_attributes.get('name')
                    )

            metadata = {
                    "url": slug,
                    "title": blogTitle,
                    "author":writer_detail,
                    "date":updatedAt
                }
            data = {
                    "content":"",
                    "client": 'Blogs',
                    "metadata": metadata,
                    "file_path":os.path.join(os.getcwd(), "blogs", filename),
                    "file_type":FileType.MD.value
                }
            message_producer("blogs",data)
        
        return True
    except Exception as e:
        print({"type": "error","message": "An unexpected error occurred: {}".format(str(e))})
        return False







