import time
from typing import Sequence

import selenium.common.exceptions
from langchain_community.document_loaders import AsyncChromiumLoader
from langchain_community.document_transformers import BeautifulSoupTransformer
from langchain_core.documents import Document

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import os
import platform
from selenium.webdriver.common.by import By
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

from db import db
from helpers.helper import decrypt_message, encrypt_message

load_dotenv()
LinkedIn = db[os.getenv("LINKED_IN_LOGIN")]
Contact = db[os.getenv("CONTACT_COLLECTION_NAME")]


def scrape_urls(urls: list[str]) -> Sequence[Document]:
    loader = AsyncChromiumLoader(urls)
    html = loader.load()

    bs_transformer = BeautifulSoupTransformer()
    docs_transformed = bs_transformer.transform_documents(html, tags_to_extract=["h1", "h2", "h3", "main", "p", "span"])

    return docs_transformed


def linkedin_login():
    try:
        print("Login Start")
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        # LinkedIn Login
        driver.get("https://linkedin.com/login")
        email = driver.find_element(By.ID, "username")
        password = driver.find_element(By.ID, "password")
        email.send_keys(os.getenv("LINKED_IN_EMAIL"))
        password.send_keys(os.getenv("LINKED_IN_PASSWORD"))
        email.submit()

        # Save last logged in timestamp and
        # Save session cookies in DB
        cookies = driver.get_cookies()
        enc_cookies = encrypt_message(json.dumps(cookies), os.getenv("COOKIES_KEY"))
        LinkedIn.find_one_and_update({"name": "creds"}, {
            "$set": {
                "last_logged_in": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "cookies": enc_cookies
            }
        }, upsert=True)
        driver.quit()
        print("Login End")
    except Exception as e:
        print(e)


def scrape_linkedin(url: str, local=False) -> str:
    """This function scrapes a given LinkedIn URL

    T̶h̶i̶s̶ f̶u̶n̶c̶t̶i̶o̶n̶ w̶i̶l̶l̶ w̶o̶r̶k̶ p̶r̶o̶p̶e̶r̶l̶y̶ w̶i̶t̶h̶ l̶o̶c̶a̶l̶ H̶T̶M̶L̶ f̶i̶l̶e̶s̶ a̶s̶
    L̶i̶n̶k̶e̶d̶I̶n̶ d̶o̶e̶s̶ n̶o̶t̶ s̶u̶p̶p̶o̶r̶t̶ s̶c̶r̶a̶p̶i̶n̶g̶. G̶o̶ t̶o̶ t̶h̶e̶ w̶a̶n̶t̶e̶d̶ L̶i̶n̶k̶e̶d̶I̶n̶
    U̶R̶L̶ a̶n̶d̶ d̶o̶w̶n̶l̶o̶a̶d̶ t̶h̶e̶ h̶t̶m̶l̶ m̶a̶n̶u̶a̶l̶l̶y̶ a̶n̶d̶ s̶a̶v̶e̶ t̶h̶e̶ f̶i̶l̶e̶ o̶n̶ y̶o̶u̶r̶
    c̶o̶m̶p̶u̶t̶e̶r̶.

    When you provide the file path for a local file, provide the complete path preceded by 'file://' and set local=True

    :param url: Live URL or Local HTML path
    :param local: True if local path is given
    :return: The file path of the Markdown file created
    """
    try:
        print("Scraping Start")
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        print("Driver Start")
        if not local:
            # This will perform a LinkedIn login if a login has not been performed in the last 24 hours
            creds = LinkedIn.find_one({"name": "creds"})
            if creds is None or creds.get("cookies") is None or creds.get("cookies") == "[]":
                linkedin_login()

            timestamp = LinkedIn.find_one({"name": "creds"}).get("last_logged_in")
            date_time = datetime.strptime(timestamp, "%d/%m/%Y %H:%M:%S")
            now = date_time.now()

            # one_day = 24 * 60 * 60
            two_hours = 2 * 60 * 60
            if (now - date_time).total_seconds() > two_hours:
                linkedin_login()

            # Load the session cookies
            decrypted_cookies = decrypt_message(LinkedIn.find_one({"name": "creds"}).get("cookies"), os.getenv("COOKIES_KEY"))
            cookies = json.loads(decrypted_cookies)
            print(cookies)
            driver.get(url)
            for cookie in cookies:
                driver.add_cookie(cookie)
            print("Cookies Set")
            driver.refresh()
            driver.get(url)

        if not os.path.exists(os.path.join(os.getcwd(), "uploads", "account_md")):
            os.mkdir(os.path.join(os.getcwd(), "uploads", "account_md"))

        # Check for Windows system in case of local file
        is_windows = True if platform.system() == "Windows" else False
        if is_windows and local:
            file_name = '{}.md'.format(url.rstrip("/").split("\\")[-1].split("?")[0].split(".")[0])
        else:
            file_name = f'{url.rstrip("/").split("/")[-1].split("?")[0].split(".")[0]}.md'

        print("Path:", os.path.join(os.getcwd(), "uploads", "account_md", file_name))
        driver.get(url)
        with open(os.path.join(os.getcwd(), "uploads", "account_md", file_name), "w", encoding='utf-8') as file:
            # Extract Basic Information
            info = driver.find_element(By.CLASS_NAME, "ph5")
            name = info.find_element(By.XPATH, "//div[2]/div/div/span/a").text
            print(name)
            description = driver.find_element(By.XPATH,
                                              "//*[@id='profile-content']/div/div[2]/div/div/main/section[1]/div["
                                              "2]/div[2]/div[1]/div[2]").text
            print(description)
            location = driver.find_element(By.XPATH,
                                           "//*[@id='profile-content']/div/div[2]/div/div/main/section[1]/div[2]/div["
                                           "2]/div[2]/span[1]").text

            print(location)
            try:
                about = driver.find_element(By.XPATH,
                                            "//div[@id='about']/following-sibling::div/following-sibling::div").text
            except selenium.common.exceptions.NoSuchElementException:
                about = ""

            file.write(f"# {name}  \n{about}  \n\n---\n### Information\n")
            file.write(f"Name: {name}  \nDescription: {description}  \nLocation: {location}  \n\n")

            # Extract Experience Information
            experiences = driver.find_elements(By.XPATH,
                                               "//div[@id='experience']/following-sibling::div/following-sibling::div"
                                               "/ul/li")
            file.write("### Experiences\n")
            for it in experiences:
                try:
                    texts = it.text.split("\n")
                    exp_title = texts[0]
                    exp_company = texts[2].split("·")[0].strip() if texts[2].split("·")[0].strip() else "Missing"
                    exp_type = texts[2].split("·")[1].strip() if len(texts[2].split("·")) > 1 else "Missing"
                    dates = texts[4].split("·")[0].strip() if texts[4].split("·")[0].strip() else "Missing"
                    duration = texts[4].split("·")[1].strip() if len(texts[4].split("·")) > 1 else "Missing"
                    location = texts[6] if len(texts) > 6 else "Missing"
                    description = " ".join(texts[8:]) if len(texts) > 8 else "Missing"

                    file.write(f"""- Title: {exp_title}  \nCompany: {exp_company}  \nType: {exp_type}  \n \
    Dates: {dates}  \nDuration: {duration}  \nLocation: {location}  \nDescription: {description}\n\n\n""")
                except Exception:
                    pass

        with open(os.path.join(os.getcwd(), "uploads", "account_md", file_name), "r", encoding='utf-8') as file:
            print(file.read())

        driver.quit()
        return os.path.join(os.getcwd(), "uploads", "account_md", file_name)
    except selenium.common.exceptions.NoSuchElementException:
        print("Element Not Found")
        if not local:
            Contact.find_one_and_update({"linkedIn": url}, {"$set": {"status": "failed", "updatedAt": datetime.now(timezone.utc)}})
    except KeyboardInterrupt:
        pass
    except Exception as e:
        raise Exception(f"LinkedIn scraping error: {e}")
