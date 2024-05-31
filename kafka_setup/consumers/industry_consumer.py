from kafka_setup.kafka_config import get_consumer
from helpers.add_industry import add_industry
import json
import os
from dotenv import load_dotenv

# from helpers.scraper import scrape_urls
# python -m kafka_setup.consumers.industry_consumer
# (use this command if run this file as standalone because it needs to run as part of the package)


consumer, tp = get_consumer(os.getenv("INDUSTRY_CONSUMER"))


# Consume messages
def consume_and_handle_data():
    try:
        offset = consumer.position(tp)
        print("Industry Consumer Started, Offset: ", offset)

        for message in consumer:
            message_data = json.loads(message.value.decode('utf-8'))
            company_name = message_data.get("company_name")
            industry = add_industry(company_name)
            print(f'Added the {industry} industry')
    except Exception as e:
        print(f"Error generating industry: {e}")
    except KeyboardInterrupt:
        consumer.close()
        print("Industry Consumer Closed")
    finally:
        consumer.close()


if __name__ == "__main__":
    consume_and_handle_data()
