from kafka import KafkaConsumer, KafkaProducer, TopicPartition
from dotenv import load_dotenv
import os
load_dotenv()


config = {
    'bootstrap_servers': os.getenv("BOOTSTRAP_SERVERS"),
    'sasl_mechanism': os.getenv("SASL_MECHANISM"),
    'security_protocol': os.getenv("SECURITY_PROTOCOL"),
    'sasl_plain_username': os.getenv("SASL_PLAIN_USERNAME"),
    'sasl_plain_password': os.getenv("SASL_PLAIN_PASSWORD"),
    'group.id': os.getenv("CONSUMER_GROUP_ID"),
    'auto.offset.reset': os.getenv("CONSUMER_AUTO_OFFSET_RESET")
}


def get_consumer(topic: str, group: str = "") -> (KafkaConsumer, TopicPartition):
    consumer = KafkaConsumer(
        bootstrap_servers=config['bootstrap_servers'],
        sasl_mechanism=config['sasl_mechanism'],
        security_protocol=config['security_protocol'],
        sasl_plain_username=config['sasl_plain_username'],
        sasl_plain_password=config['sasl_plain_password'],
        group_id=group if group.strip() != "" else config['group.id'],
        auto_offset_reset=config['auto.offset.reset'],
        enable_auto_commit=True
    )

    tp = TopicPartition(topic=topic, partition=0)
    consumer.assign([tp])
    return consumer, tp


def get_producer() -> KafkaProducer:
    return KafkaProducer(bootstrap_servers=config['bootstrap_servers'],
                         sasl_mechanism=config['sasl_mechanism'],
                         security_protocol=config['security_protocol'],
                         sasl_plain_username=config['sasl_plain_username'],
                         sasl_plain_password=config['sasl_plain_password'],
                         api_version=(2, 0, 2))
