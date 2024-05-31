from kafka_setup.kafka_config import get_producer
import json
from dotenv import load_dotenv
load_dotenv()


# Produce a message
def message_producer(topic, data):
    producer = get_producer()
    try:
        # Encode the dictionary as JSON bytes 
        message_bytes = json.dumps(data).encode('utf-8')

        # Send the JSON message to the topic
        producer.send(topic, message_bytes)
        producer.flush()
        print(f'Producer published to topic: [{topic}]')
    except Exception as e:
        print(f"Error producing message: {e}")
    finally:
        producer.close()
