from db import db
from helpers.vectorstore import FileType
from kafka_setup.kafka_config import get_consumer
from helpers.scraper import scrape_linkedin
import json
import os
from dotenv import load_dotenv
from kafka_setup.kafka_producer import message_producer
from bson.objectid import ObjectId
from datetime import datetime, timezone

load_dotenv()

# python -m kafka_setup.consumers.linkedin_consumer
# (use this command if run this file as standalone because it needs to run as part of the package)


consumer, tp = get_consumer(os.getenv("LINKEDIN_CONSUMER"))
Account = db[os.getenv("ACCOUNT_COLLECTION_NAME")]
Contact = db[os.getenv("CONTACT_COLLECTION_NAME")]


# Consume messages
def consume_and_handle_data():
    try:
        offset = consumer.position(tp)
        print("LinkedIn Consumer Started, Offset: ", offset)
        for message in consumer:
            message_data = json.loads(message.value.decode('utf-8'))

            account = message_data.get("account")
            contact = message_data.get("contact")
            contact_id = message_data.get("contact_id")
            file_path = message_data.get("file_path")
            url = message_data.get("url")

            if url is None and file_path is None:
                raise Exception("A URL or file path is required for scraping")

            if not all([account, contact_id, contact]):
                raise Exception("Account, Contact or Contact ID not present")

            ip = f"file://{file_path}" if file_path is not None else url
            markdown_path = scrape_linkedin(ip, local=True if file_path is not None else False)

            data = {
                "file_type": FileType.MD.value,
                "file_path": markdown_path,
                "client": account,
                "metadata": {
                    "contact": contact
                }
            }

            print(data)
            if markdown_path is not None:
                message_producer(os.getenv("EMBED_CONSUMER"), data)

            Contact.find_one_and_update({"_id": ObjectId(contact_id), "status": "pending"}, {
                "$set": {
                    "status": "done",
                    "updatedAt": datetime.now(timezone.utc)
                }
            })
    except KeyboardInterrupt:
        consumer.close()
        print("LinkedIn Consumer Closed")
    except Exception as e:
        print(f"Error linkedin consuming message: {e}")

    finally:
        consumer.close()


if __name__ == "__main__":
    consume_and_handle_data()
