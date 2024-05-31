import subprocess
import platform


def start_consumers():
    is_windows = True if platform.system() == "Windows" else False

    if is_windows:
        subprocess.Popen(["python3", "-m", "kafka_setup.consumers.scrape_consumer"], shell=True, stdout=True, stderr=True)
        subprocess.Popen(["python3", "-m", "kafka_setup.consumers.embed_consumer"], shell=True, stdout=True, stderr=True)
        subprocess.Popen(["python3", "-m", "kafka_setup.consumers.linkedin_consumer"], shell=True, stdout=True, stderr=True)
        subprocess.Popen(["python3", "-m", "kafka_setup.consumers.industry_consumer"], shell=True, stdout=True, stderr=True)
        subprocess.Popen(["python3", "-m", "kafka_setup.consumers.blog_consumer"], shell=True, stdout=True, stderr=True)
    else:
        subprocess.Popen(["python3 -m kafka_setup.consumers.scrape_consumer"], shell=True, stdout=True, stderr=True)
        subprocess.Popen(["python3 -m kafka_setup.consumers.embed_consumer"], shell=True, stdout=True, stderr=True)
        subprocess.Popen(["python3 -m kafka_setup.consumers.linkedin_consumer"], shell=True, stdout=True, stderr=True)
        subprocess.Popen(["python3 -m kafka_setup.consumers.industry_consumer"], shell=True, stdout=True, stderr=True)
        subprocess.Popen(["python3 -m kafka_setup.consumers.blog_consumer"], shell=True, stdout=True, stderr=True)