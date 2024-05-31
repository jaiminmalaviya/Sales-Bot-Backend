from kafka_setup.kafka_config import get_consumer
from helpers.vectorstore import embed_text
import json
import os
from dotenv import load_dotenv

# from helpers.scraper import scrape_urls
# python -m kafka_setup.consumers.embed_consumer
# (use this command if run this file as standalone because it needs to run as part of the package)


consumer, tp = get_consumer(os.getenv("EMBED_CONSUMER"))


# Consume messages
def consume_and_handle_data():
    try:
        offset = consumer.position(tp)
        print("Embed Consumer Started, Offset: ", offset)
        for message in consumer:
            message_data = json.loads(message.value.decode('utf-8'))
            print("Embed start")

            content = message_data.get("content")
            file_type = message_data.get("file_type")
            client = message_data.get("client")
            file_path = message_data.get("file_path")
            if message_data.get("metadata") is not None:
                metadata = message_data["metadata"]
            else:
                metadata = {}
            embed_text(content, file_type, client, metadata, file_path)
            if file_type == "txt":
                print(f"URL embedded: [{ metadata.get('url')}]")
            else:
                print(f'embedded the {file_type} file')
    except KeyboardInterrupt:
        consumer.close()
        print("Embed Consumer Closed")
    except Exception as e:
        print(f"Error embed consuming message: {e}")
    finally:
        consumer.close()


if __name__ == "__main__":
    consume_and_handle_data()