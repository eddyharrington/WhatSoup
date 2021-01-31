import requests
import os

from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def main():
    driver = setupSelenium()

    # Try loading whatsapp in browser, grant max of 30sec to load
    driver.get('https://web.whatsapp.com/')
    delay = 20
    try:
        chat_pane = WebDriverWait(driver, delay).until(
            expected_conditions.presence_of_element_located((By.ID, 'pane-side')))
        print("Success: WhatsApp finished loading and is ready!")
    except TimeoutException:
        driver.close()
        return print(f"Failure: WhatsApp did not load within 30 seconds! Make sure you're logged in and WhatsApp is loaded, or increase the wait time (currently set at {delay} seconds)")


def setupSelenium():
    '''Setup Selenium to use Chrome webdriver'''

    # Load driver and chrome profile from local directories set in the .env file
    DRIVER_PATH = os.getenv('DRIVER_PATH')
    CHROME_PROFILE = os.getenv('CHROME_PROFILE')
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-data-dir={CHROME_PROFILE}")
    driver = webdriver.Chrome(
        executable_path=DRIVER_PATH, chrome_options=options)

    return driver


if __name__ == "__main__":
    main()
