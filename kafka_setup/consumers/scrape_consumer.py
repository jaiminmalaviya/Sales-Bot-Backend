from db import db
from helpers.vectorstore import FileType
from kafka_setup.kafka_config import get_consumer
from helpers.scraper import scrape_urls
import json
import os
from dotenv import load_dotenv
from bson.objectid import ObjectId
from helpers.apollo_scraper import scrape_apollo

from kafka_setup.kafka_producer import message_producer

load_dotenv()

# python -m kafka_setup.consumers.scrape_consumer
# (use this command if run this file as standalone because it needs to run as part of the package)


consumer, tp = get_consumer(os.getenv("URL_CONSUMER"))
Account = db[os.getenv("ACCOUNT_COLLECTION_NAME")]


# Consume messages
def consume_and_handle_data():
    try:
        offset = consumer.position(tp)
        print("Scrape Consumer Started, Offset: ", offset)
        for message in consumer:
            print(os.getenv("CONSUMER_GROUP_ID"))
            message_data = json.loads(message.value.decode('utf-8'))

            # Extract Apollo URL from the message
            url = message_data.get("url")

            # Call the scraper function
            scrape_apollo(url)

            print("Apollo List Scraped")

    except KeyboardInterrupt:
        consumer.close()
        print("LinkedIn Consumer Closed")
    except Exception as e:
        print(f"Error scrape consuming message: {e}")

    finally:
        consumer.close()


if __name__ == "__main__":
    consume_and_handle_data()
