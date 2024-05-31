from kafka_setup.kafka_config import get_consumer
from helpers.vectorstore import embed_text
import json
import os
from dotenv import load_dotenv
from db import db
from helpers.custom_error import CustomEmbedError
# from helpers.scraper import scrape_urls
# python -m kafka_setup.consumers.blog_consumer
# (use this command if run this file as standalone because it needs to run as part of the package)

Blogs = db[os.getenv("BLOGS_COLLECTION_NAME")]
consumer, tp = get_consumer(os.getenv("BLOG_CONSUMER"))


# Consume messages
def consume_and_handle_data():
    try:
        offset = consumer.position(tp)
        print("Blog Consumer Started, Offset: ", offset)
        for message in consumer:
            message_data = json.loads(message.value.decode('utf-8'))
            print(message.value.decode('utf-8'))
            print("Embed start")

            content = message_data.get("content")
            file_type = message_data.get("file_type")
            client = message_data.get("client")
            file_path = message_data.get("file_path")
            if message_data.get("metadata") is not None:
                metadata = message_data["metadata"]
            else:
                metadata = {}

            try:
                embed_text(content, file_type, client, metadata, file_path)
                new_date = metadata.get('date')

                existing_doc = Blogs.find_one({})
                if existing_doc:
                    existing_date = existing_doc.get("updatedAt")
                else:
                    existing_date = '1970-01-01T00:00:00.000Z'

                # Compare the dates
                if existing_date is None or new_date > existing_date:
                    # Define the update operation
                    update_operation = {
                        "$set": {
                            "updatedAt": new_date
                        }
                    }
                    Blogs.update_one({}, update_operation, upsert=True)
                print(f'embedded the {file_type} file')
            except CustomEmbedError:
                Blogs.update_one({},{
                        "$push":{
                        "failed": metadata.get('url')
                        }
                    },upsert=True)
                print('Added title to failed')

    except KeyboardInterrupt:
        consumer.close()
        print("Blog Consumer Closed")
    except Exception as e:
        print(f"Error blog consuming message: {e}")
    finally:
        consumer.close()


if __name__ == "__main__":
    consume_and_handle_data()