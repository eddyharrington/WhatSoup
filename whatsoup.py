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
    # Setup selenium to use Chrome browser w/ profile options
    driver = setup_selenium()

    # Load WhatsApp
    if load_whatsapp(driver) == 0:
        print("Success! WhatsApp finished loading and is ready.")
    else:
        print("You've quit WhatSoup.")
        return


def setup_selenium():
    '''Setup Selenium to use Chrome webdriver'''

    # Load driver and chrome profile from local directories
    DRIVER_PATH = os.getenv('DRIVER_PATH')
    CHROME_PROFILE = os.getenv('CHROME_PROFILE')
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-data-dir={CHROME_PROFILE}")
    driver = webdriver.Chrome(
        executable_path=DRIVER_PATH, chrome_options=options)

    return driver


def load_whatsapp(driver):
    '''Attempts to load WhatsApp in the browser'''

    # Open WhatsApp
    driver.get('https://web.whatsapp.com/')
    driver.maximize_window()

    # Check if user is already logged in
    logged_in, wait_time = False, 20
    while not logged_in:

        # Try logging in
        logged_in = user_is_logged_in(driver, wait_time)

        # Allow user to try again and extend the wait time for WhatsApp to load
        if not logged_in:
            # Display error to user
            print(
                f"Error: WhatsApp did not load within {wait_time} seconds. Make sure you are logged in and let's try again.")

            # Ask user if they want to try loading WhatsApp again
            err_response = input("Proceed (y/n)?")

            # Check the user's response
            if err_response.lower() == 'y' or err_response.lower() == 'yes':
                # Ask user if they want to increment the wait time by 10 seconds
                wait_response = input(
                    f"Increase wait time for WhatsApp to load from {wait_time} seconds to {wait_time + 10} seconds? (y/n)")

                # Increase wait time by 10 seconds
                if wait_response.lower() == 'y' or wait_response.lower() == 'yes':
                    wait_time += 10

                continue

            # Abort loading WhatsApp
            else:
                driver.quit()
                return 1
    # Success
    return 0


def user_is_logged_in(driver, wait_time):
    '''Checks if the user is logged in to WhatsApp by looking for the pressence of the chat-pane'''

    try:
        chat_pane = WebDriverWait(driver, wait_time).until(
            expected_conditions.presence_of_element_located((By.ID, 'pane-side')))
        return True
    except TimeoutException:
        return False


if __name__ == "__main__":
    main()
