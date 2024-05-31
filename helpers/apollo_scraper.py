import pprint
import time
from selenium import webdriver
import selenium.common.exceptions
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import os
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from db import db
from dotenv import load_dotenv
from bson.objectid import ObjectId
from datetime import datetime, timezone
load_dotenv()

time_delay_tiny = 3
time_delay_short = 5
time_delay_long = 15
contacts_per_page = 25

Contact = db[os.getenv("CONTACT_COLLECTION_NAME")]
Account = db[os.getenv("ACCOUNT_COLLECTION_NAME")]


def wait_for_element(driver, by, identifier, multiple=False):
    i = 0
    found = False

    while i != 10 and not found:
        try:
            driver.find_element(by, identifier)
            found = True
        except selenium.common.exceptions.NoSuchElementException:
            time.sleep(1)
            i += 1
            pass

    if multiple:
        return driver.find_elements(by, identifier)

    return driver.find_element(by, identifier)


def login_apollo(driver):
    try:
        driver.get("https://app.apollo.io/#/login")

        form = wait_for_element(driver, By.TAG_NAME, "form")
        inputs = form.find_elements(By.TAG_NAME, 'input')

        email = inputs[0]
        password = inputs[1]

        email.send_keys(os.getenv("APOLLO_MAIL"))
        password.send_keys(os.getenv("APOLLO_PASS"))

        email.submit()
    except selenium.common.exceptions.NoSuchElementException:
        print("Element Not Found in Login")
    except Exception as e:
        print("Login: ", e)


def get_page_info(driver):
    try:
        time.sleep(time_delay_long)
        pagination = wait_for_element(driver, By.CLASS_NAME, "zp_VVYZh")

        print(pagination)
        print(pagination.text)

        if not pagination or not pagination.text:
            raise selenium.common.exceptions.NoSuchElementException

        total = int(pagination.text.split("of")[1].replace(",", ""))
        current = pagination.text.split("of")[0]
        start = int(current.split("-")[0].replace(",", ""))
        end = int(current.split("-")[1].replace(",", ""))

        time.sleep(time_delay_short)
        return start, end, total

    except selenium.common.exceptions.NoSuchElementException:
        print("No entries in list")
        return 0, 0, 0
    except Exception as e:
        print("Page info error: ", e)


def get_information(driver):
    try:
        info = {'name': driver.find_element(By.CLASS_NAME, "zp_Ln9Ws").text.split('\n')[0]}
        # Contact Information
        linkedin_url = driver.find_elements(By.CSS_SELECTOR, ".zp_Ln9Ws>a")
        info['linkedin_url'] = linkedin_url[0].get_attribute("href").replace("http://", "https://") if len(linkedin_url) > 0 else None
        emails = driver.find_elements(By.CSS_SELECTOR, ".zp_jcL6a>a")
        info['emails'] = [mail.text for mail in emails]
        contact_owner = driver.find_elements(By.CLASS_NAME, "zp_I78N2")
        info['contact_owner'] = contact_owner[0].text if len(contact_owner) > 0 else None

        # Account Information
        acc_name = driver.find_elements(By.CLASS_NAME, "zp_Gl1mw")
        info['acc_name'] = acc_name[0].text if len(acc_name) > 0 else None

        website = driver.find_elements(By.CSS_SELECTOR, ".zp_I1ps2>a")
        info['acc_website'] = website[0].get_attribute("href").replace("http://", "https://") if len(website) > 0 else None

        time.sleep(time_delay_tiny)

        toggle_button = driver.find_elements(By.CSS_SELECTOR, ".zp_OIB99")
        if len(toggle_button) > 0:
            toggle_button[0].click()

        description = driver.find_elements(By.CSS_SELECTOR, ".zp_r2pH_")
        info['acc_description'] = description[0].text if len(description) > 0 else None

        tags = driver.find_elements(By.CLASS_NAME, "zp_OBkwl")
        info['acc_tags'] = [tag.text for tag in tags]

        industry = driver.find_elements(By.CLASS_NAME, "zp_QVesc")
        info['acc_industry'] = industry[0].text if len(industry) > 0 else None

        account_owner = driver.find_elements(By.CLASS_NAME, "zp_X0YyR")
        if len(account_owner) == 0:
            account_owner = None
        elif len(account_owner) > 1:
            account_owner = account_owner[1].text
        else:
            account_owner = account_owner[0].text
        info['account_owner'] = account_owner

        return info

    except Exception as e:
        print("Info error: ", e)


def scrape_rows(driver):
    try:
        rows = wait_for_element(driver, By.CLASS_NAME, "zp_cWbgJ", True)

        names = []
        for row in rows:
            try:
                links = row.find_elements(By.TAG_NAME, "a")
                if links:
                    pprint.pprint([link.text for link in links])
                    account = links[2].text if len(links) > 3 else None
                    if account == '':
                        account = None

                    obj = {
                        "contact": links[0].text.split("\n")[0],
                        "account": account
                    }
                    names.append(obj)
            except selenium.common.exceptions.StaleElementReferenceException:
                print("Stale")

        indexes = return_absent(names=names)
        print(indexes)

        for idx, row in enumerate(rows):
            if idx not in indexes:
                continue

            div = row.find_elements(By.CLASS_NAME, "zp_aBhrx")
            driver.execute_script("arguments[0].click();", div[0])
            info = get_information(driver)

            contact = Contact.update_one(
                {
                    "name": info.get("name"),
                    "company_name": info.get('acc_name')
                }, {
                    "$set": {
                        "name": info.get('name'),
                        "company_name": info.get('acc_name'),
                        "linkedin_profile": info.get('linkedin_url'),
                        "emails": info.get('emails'),
                        "sales_owner_name": info.get("contact_owner")
                    }
                },
                upsert=True
            )

            if not contact.upserted_id:
                return

            company = Account.find_one({"name": info.get('acc_name')})

            if company is None:
                new = Account.insert_one({
                    'name': info.get('acc_name'),
                    'website': info.get('acc_website'),
                    'industry': info.get('acc_industry'),
                    'description': info.get('acc_description'),
                    'tags': info.get('acc_tags'),
                    'contacts': [],
                    'createdAt': datetime.now(timezone.utc),
                    'updatedAt': datetime.now(timezone.utc),
                    "sales_owner_name": info.get("account_owner")
                })

                company_id = str(new.inserted_id)
            else:
                company_id = str(company.get("_id"))

            Account.find_one_and_update(
                {"_id": ObjectId(company_id)},
                {"$push": {"contacts": ObjectId(contact.upserted_id)}, "$set": {"updatedAt": datetime.now(timezone.utc)}}
            )

            Contact.update_one({"_id": ObjectId(contact.upserted_id)}, {
                "$set": {"account": ObjectId(company_id),
                         "createdAt": datetime.now(timezone.utc),
                         "updatedAt": datetime.now(timezone.utc)}
            })

    except selenium.common.exceptions.NoSuchElementException:
        print("No rows or tag found")
    except Exception as e:
        print("Rows Error: ", e)


def return_absent(names):
    indexes = []
    for idx, name in enumerate(names):
        contact = name.get('contact')
        account = name.get('account') if name.get('account') != '' else None
        is_present = Contact.count_documents({"name": contact,
                                              "company_name": account}, limit=1) != 0

        if not is_present:
            indexes.append(idx)

    return indexes


def scrape_apollo(url: str):
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        # Login to Apollo
        login_apollo(driver)
        print("Logged in to Apollo")

        time.sleep(time_delay_short)
        driver.get(url)
        print("URL: ", driver.current_url)

        time.sleep(time_delay_short)
        # Iterate through all contacts while also changing pages
        start, end, total = get_page_info(driver)
        while end < total:
            scrape_rows(driver)
            page_no = end // contacts_per_page
            new_url = driver.current_url.split('&page')[0]
            new_url = new_url + f"&page={page_no + 1}"
            driver.get(new_url)
            print("URL: ", driver.current_url)
            start, end, total = get_page_info(driver)

        scrape_rows(driver)
    except selenium.common.exceptions.NoSuchElementException:
        print("Element Not Found")
    except Exception as e:
        print("Main: ", e)


if __name__ == "__main__":
    scrape_apollo("https://app.apollo.io/#/people?finderViewId=5b8050d050a3893c382e9360&contactLabelIds[]=65aa217a92450101c6f33104&prospectedByCurrentTeam[]=yes", "Bhagya")
