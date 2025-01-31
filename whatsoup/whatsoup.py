import os
import logging
from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementNotInteractableException
from dotenv import load_dotenv
from timeit import default_timer as timer
import pandas as pd
from typing import Optional, List, Dict, Any

def setup_selenium() -> webdriver.Chrome:
    """
    Sets up and returns a Selenium WebDriver instance for Chrome.

    This function loads environment variables from a .env file to get the path to the Chrome WebDriver
    and the Chrome user profile. It then configures the WebDriver with these settings and sets a script
    timeout of 90 seconds.

    Returns:
        webdriver.Chrome: A configured instance of Chrome WebDriver.

    Raises:
        ValueError: If the DRIVER_PATH or CHROME_PROFILE environment variables are not set.
    """

    load_dotenv()
    DRIVER_PATH = os.getenv('DRIVER_PATH')
    CHROME_PROFILE = os.getenv('CHROME_PROFILE')
    if not DRIVER_PATH or not CHROME_PROFILE:
        raise ValueError("Please provide the path to the Chrome WebDriver and Chrome Profile in a .env file.")

    options = webdriver.ChromeOptions()
    service = Service(executable_path=DRIVER_PATH)
    options.add_argument(f"user-data-dir={CHROME_PROFILE}")
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_script_timeout(90)

    return driver


def whatsapp_is_loaded(driver: webdriver.Chrome) -> bool:
    """
    Checks if WhatsApp Web is loaded and the user is logged in.

    This function navigates to the WhatsApp Web URL and waits for the user to be logged in.
    If the user is not logged in within the specified wait time, it logs an error message and returns False.
    If the user is logged in successfully, it logs a success message and returns True.

    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance for Chrome.

    Returns:
        bool: True if WhatsApp Web is loaded and the user is logged in, False otherwise.
    """

    logging.info("Loading WhatsApp...")
    driver.get('https://web.whatsapp.com/')

    wait_time = 20
    while not user_is_logged_in(driver, wait_time):
        logging.error(f"WhatsApp did not load within {wait_time} seconds. Make sure you are logged in and let's try again.")
        return False

    logging.info("Success! WhatsApp finished loading and is ready.")
    return True


def user_is_logged_in(driver: webdriver.Chrome, wait_time: int) -> bool:
    """
    Check if the user is logged into WhatsApp Web.

    This function waits for a specific element to appear on the page to determine if the user is logged in.
    It waits for the element with ID 'pane-side' to be present within the given wait time.

    Args:
        driver (webdriver.Chrome): The WebDriver instance controlling the browser.
        wait_time (int): The maximum amount of time (in seconds) to wait for the element to appear.

    Returns:
        bool: True if the element is found within the wait time, indicating the user is logged in; False otherwise.
    """
    try:
        WebDriverWait(driver, wait_time).until(
            presence_of_element_located((By.ID, 'pane-side')))
        return True
    except TimeoutException:
        return False


def find_selected_chat(driver: webdriver.Chrome, query: str) -> None:
    """
    Searches for a specific chat in WhatsApp Web and selects it.

    Args:
        driver (webdriver.Chrome): The WebDriver instance controlling the browser.
        query (str): The name or keyword to search for in the chat list.
    """
    logging.info(f"Searching the chat for user '{query}'...")
    retries = 3
    for attempt in range(retries):
        try:
            side = driver.find_element(By.ID, 'side')
            chat_search = side.find_element(By.CLASS_NAME, "lexical-rich-text-input")
            chat_search.click()
            ActionChains(driver).send_keys_to_element(chat_search, query).perform()
            sleep(1)
            break
        except (StaleElementReferenceException, ElementNotInteractableException) as e:
            if attempt < retries - 1:
                logging.warning(f"StaleElementReferenceException encountered while searching and clicking. Retrying... ({attempt + 1}/{retries})")
                sleep(2)
            else:
                logging.error("Could not find the chat search element after multiple attempts.")
                raise e

    try:
        WebDriverWait(driver, 5).until(
            presence_of_element_located((By.XPATH, "//*[@aria-label='Search results.']"))
        )
    except TimeoutException as e:
        logging.error(f"'{query}' produced no search results in WhatsApp.")
        raise e

    retries = 3
    for attempt in range(retries):
        try:
            search_results = driver.find_element(By.XPATH, "//*[@aria-label='Search results.']")
            chat = search_results.find_element(By.XPATH, ".//div[@role='listitem'][2]")
            chat.click()
        except (NoSuchElementException, StaleElementReferenceException) as e:
            if attempt < retries - 1:
                logging.warning(f"StaleElementReferenceException encountered while clicking the chat. Retrying... ({attempt + 1}/{retries})")
                sleep(2)
            else:
                logging.error(f"'{query}' chat could not be loaded in WhatsApp after 3 attempts.")
                raise e



def load_selected_chat(driver: webdriver.Chrome, messages_number_target: Optional[int] = None) -> None:
    """
    Loads the selected chat in the WhatsApp Web interface by scrolling to the top and clicking the "load more messages" button if available.

    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance controlling the browser.
        messages_number_target (Optional[int]): The target number of messages to load. If None, all messages will be loaded.

    Raises:
        StaleElementReferenceException: If a stale element reference exception is encountered more than three times in a row.
    """
    start = timer()
    logging.info("Loading messages...")

    total_row_elems = 0
    row_elem_n = len(driver.find_elements(By.XPATH, '//*[@role="row"]'))
    counter = 0
    while top_elem := driver.find_element(By.XPATH, '//*[@id="main"]/div[3]/div/div[2]/div[2]'):
        if messages_number_target and total_row_elems >= messages_number_target:
            logging.info("Message number target reached.")
            break
        logging.info("Loading more messages...")
        if row_elem_n == total_row_elems:
            try:
                top_button = top_elem.find_element(By.XPATH, './/button')
            except (NoSuchElementException, StaleElementReferenceException):
                top_button = False
            if top_button:
                logging.info("Clicking the top button...")
                try:
                    top_button.click()
                    sleep(5)
                    row_elem_n = len(driver.find_elements(By.XPATH, '//*[@role="row"]'))
                except StaleElementReferenceException:
                    counter += 1
                    if counter > 3:
                        raise StaleElementReferenceException("StaleElementReferenceException encountered too many times.")
                continue
            else:
                logging.info("Reached the top")
                break

        try:
            ActionChains(driver).scroll_to_element(top_elem).perform()
            total_row_elems = row_elem_n
            sleep(2)
            row_elem_n = len(driver.find_elements(By.XPATH, '//*[@role="row"]'))
            counter = 0
        except StaleElementReferenceException:
            counter += 1
            if counter > 3:
                raise StaleElementReferenceException("StaleElementReferenceException encountered too many times.")
            else:
                continue

    logging.info(f"Success! Your entire chat history has been loaded in {round(timer() - start)} seconds.")


def scrape_chat(driver: webdriver.Chrome) -> List[Dict[str, Any]]:
    """
    Scrapes chat messages from a WhatsApp Web page using a Selenium WebDriver.

    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance controlling the browser.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing details of a scraped message.
            Each dictionary contains the following keys:
                - sender (str or None): The sender of the message.
                - datetime (str or None): The datetime of the message.
                - message (str or None): The text content of the message.
                - has_emoji_text (bool): Whether the message contains emoji text.
                - data-id (str): The unique identifier of the message.
    """
    logging.info("Scraping messages...")
    soup = BeautifulSoup(driver.page_source, 'lxml')
    chat_messages = soup.find_all("div", attrs={"data-id": True})

    messages = []
    for message in chat_messages:
        message_scraped = {
            "sender": None,
            "datetime": None,
            "message": None,
            "has_emoji_text": False,
            "data-id": message.get('data-id')
        }

        copyable_text = message.find('div', 'copyable-text')
        if copyable_text and copyable_text.get("data-pre-plain-text"):
            copyable_scrape = scrape_copyable(copyable_text)
            message_scraped.update(copyable_scrape)

            selectable_text = copyable_text.find('span', 'selectable-text') or copyable_text.find('div', 'selectable-text')
            if selectable_text:
                message_scraped['has_emoji_text'] = bool(selectable_text.find('img'))
                message_scraped['message'] = scrape_selectable(selectable_text, message_scraped['has_emoji_text'])

            messages.append(message_scraped)

    logging.info(f"Success! All {len(messages)} messages have been scraped.")
    return messages


def scrape_copyable(copyable_text: BeautifulSoup) -> Dict[str, Any]:
    """
    Extracts and parses information from a BeautifulSoup object containing copyable text.

    Args:
        copyable_text (BeautifulSoup): A BeautifulSoup object representing the copyable text element.

    Returns:
        Dict[str, Any]: A dictionary containing the sender, datetime, and message extracted from the copyable text.
            - 'sender' (str): The name of the sender.
            - 'datetime' (datetime): The datetime when the message was sent.
            - 'message' (str): The message text.
    """
    copyable_attrs = copyable_text.get('data-pre-plain-text').strip()[1:-1].split('] ')
    return {
        'sender': copyable_attrs[1],
        'datetime': parse_datetime(f"{copyable_attrs[0].split(', ')[1]} {copyable_attrs[0].split(', ')[0]}"),
        'message': copyable_text.find('span', 'copyable-text') or ''
    }


def scrape_selectable(selectable_text: BeautifulSoup, has_emoji: bool = False) -> str:
    """
    Extracts text from a BeautifulSoup object, optionally including emoji descriptions.

    Args:
        selectable_text (BeautifulSoup): The BeautifulSoup object containing the text to be extracted.
        has_emoji (bool, optional): A flag indicating whether the text contains emojis represented by <img> tags. 
                                    If True, the alt attribute of <img> tags will be included in the extracted text. 
                                    Defaults to False.

    Returns:
        str: The extracted text, including emoji descriptions if has_emoji is True.
    """
    if has_emoji:
        message = ''
        for span in selectable_text.find_all('span'):
            for element in span.contents:
                if element.name is None:
                    message += str(element)
                elif element.name == 'img':
                    message += element.get('alt')
        return message
    return selectable_text.text


def parse_datetime(text: str, time_only: bool = False) -> datetime:
    """
    Parses a datetime string into a datetime object.

    Args:
        text (str): The datetime string to parse.
        time_only (bool, optional): If True, only parses the time part of the string. Defaults to False.

    Returns:
        datetime: The parsed datetime object.

    Raises:
        ValueError: If the text does not match any of the valid datetime formats.
    """
    text = text.upper().replace("A.M.", "AM").replace("P.M.", "PM")
    formats = ['%m/%d/%Y %I:%M %p', '%Y-%m-%d %I:%M %p'] if not time_only else ['%I:%M %p']
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"{text} does not match a valid datetime format.")


def export_csv(query: str, chat: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Exports chat data to a CSV file.

    This function takes a query string and a list of chat messages, and exports
    the chat data to a CSV file. The CSV file is saved in the 'exports' directory,
    with the filename based on the query string.

    Args:
        query (str): The query string used to name the CSV file.
        chat (List[Dict[str, Any]]): A list of dictionaries containing chat messages.
    """
    if not os.path.isdir('exports'):
        os.mkdir('exports')
    file_path = f"exports/{query.lower().replace(' ','_')}.csv"
    df = pd.DataFrame(chat)
    df.to_csv(file_path, index=False)
    logging.info(f"Success! Your chat has been exported to {file_path}.")
    return df


def get_chat(query: str, messages_number_target: Optional[int] = None, return_dataframe: Optional[bool] = False) -> Optional[pd.DataFrame]:
    """
    Retrieves chat messages from WhatsApp based on the chat that best matches a query.
    
    Args:
        query (str): The name or keyword to search for in the chat list.
        messages_number_target (Optional[int], optional): The target number of messages to load. Defaults to None.
        return_dataframe (Optional[bool], optional): If True, returns the chat messages as a pandas DataFrame. Defaults to False.
    
    Returns:
        Optional[pd.DataFrame]: A DataFrame containing the chat messages if return_dataframe is True, otherwise None.
    
    Raises:
        TimeoutError: If WhatsApp does not load within the specified time.
        Exception: If any other error occurs during the chat scraping process.
    """

    driver = setup_selenium()
    try:
        if not whatsapp_is_loaded(driver):
            raise TimeoutError("WhatsApp did not load within the specified time.")
        
        find_selected_chat(driver, query)

        load_selected_chat(driver, messages_number_target)

        chat = scrape_chat(driver)
        df = export_csv(query, chat)

        if return_dataframe:
            return df

    except Exception as e:
        logging.error("An error occurred while trying to scrape the chat!")
        raise e
    finally:
        logging.info("You've quit WhatSoup.")
        driver.quit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    query = "Caro (Barcelona)"
    messages_number_target = 100
    get_chat(query=query, messages_number_target=messages_number_target)
