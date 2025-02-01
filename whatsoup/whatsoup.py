import os
import logging
from bs4 import BeautifulSoup
from time import sleep
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
from typing import Optional, Dict, Any
from utils import parse_datetime, export_csv

class whatsappClient():
    """
    A class to scrape WhatsApp chat messages using a Selenium WebDriver.

    This class provides methods to scrape chat messages from a WhatsApp Web page using a Selenium WebDriver.
    It can search for a specific chat, load all messages in the chat, and export the chat data to a CSV file.

    Attributes:
        headless (bool): Whether to run Chrome in headless mode.
        script_timeout (int): The time (in seconds) to wait for scripts to execute before timing out.
        driver (webdriver.Chrome): The Selenium WebDriver instance for Chrome.
    """

    def __init__(self, headless: bool = True, script_timeout: int = 90):
        self.headless = headless
        self.script_timeout = script_timeout
        self.driver: webdriver.Chrome = self.setup_selenium()

    def __setattr__(self, name, value):
        if hasattr(self, 'driver') and name in ['headless', 'script_timeout']:
            self.driver.quit()
            self.driver = self.setup_selenium()
        super().__setattr__(name, value)

    def setup_selenium(self) -> webdriver.Chrome:
        """
        Sets up and returns a Selenium WebDriver instance for Chrome.

        This function loads environment variables from a .env file to get the path to the Chrome WebDriver
        and the Chrome user profile. It then configures the WebDriver with these settings and sets a script
        timeout.

        Args:
            headless (bool): Whether to run Chrome in headless mode.
            script_timeout (int): The time (in seconds) to wait for scripts to execute before timing out.

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
        if self.headless == True:
            options.add_argument("--headless")
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_script_timeout(self.script_timeout)

        return driver

    def whatsapp_is_loaded(self) -> bool:
        """
        Checks if WhatsApp Web is loaded and the user is logged in.

        This function navigates to the WhatsApp Web URL and waits for the user to be logged in.
        If the user is not logged in within the specified wait time, it logs an error message and returns False.
        If the user is logged in successfully, it logs a success message and returns True.

        Returns:
            bool: True if WhatsApp Web is loaded and the user is logged in, False otherwise.
        """

        logging.info("Loading WhatsApp...")
        self.driver.get('https://web.whatsapp.com/')

        wait_time = 20
        while not self.user_is_logged_in(wait_time):
            logging.error(f"WhatsApp did not load within {wait_time} seconds. Make sure you are logged in and let's try again.")
            return False

        logging.info("Success! WhatsApp finished loading and is ready.")
        return True


    def user_is_logged_in(self, wait_time: int) -> bool:
        """
        Check if the user is logged into WhatsApp Web.

        This function waits for a specific element to appear on the page to determine if the user is logged in.
        It waits for the element with ID 'pane-side' to be present within the given wait time.

        Args:
            wait_time (int): The maximum amount of time (in seconds) to wait for the element to appear.

        Returns:
            bool: True if the element is found within the wait time, indicating the user is logged in; False otherwise.
        """
        try:
            WebDriverWait(self.driver, wait_time).until(
                presence_of_element_located((By.ID, 'pane-side')))
            return True
        except TimeoutException:
            return False


    def find_selected_chat(self, query: str) -> None:
        """
        Searches for a specific chat in WhatsApp Web and selects it.

        Args:
            query (str): The name or keyword to search for in the chat list.
        """
        logging.info(f"Searching the chat for user '{query}'...")
        logging.info("Typing the search query...")
        retries = 3
        for attempt in range(retries):
            try:
                left_panel = self.driver.find_element(By.ID, 'side')
                chat_search = left_panel.find_element(By.CLASS_NAME, "lexical-rich-text-input") 
                chat_search.click()
                ActionChains(self.driver).send_keys_to_element(chat_search, query).perform()
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
            WebDriverWait(self.driver, 5).until(
                presence_of_element_located((By.XPATH, "//*[@aria-label='Search results.']"))
            )
            logging.info("Search results found.")
        except TimeoutException as e:
            logging.error(f"'{query}' produced no search results in WhatsApp.")
            raise e

        logging.info("Clicking the chat...")
        retries = 3
        for attempt in range(retries):
            try:
                search_results = self.driver.find_element(By.XPATH, "//*[@aria-label='Search results.']")
                chat = search_results.find_element(By.XPATH, ".//div[@role='listitem'][2]")
                chat.click()
                logging.info(f"Chat selected.")
            except (NoSuchElementException, StaleElementReferenceException) as e:
                if attempt < retries - 1:
                    logging.warning(f"StaleElementReferenceException encountered while clicking the chat. Retrying... ({attempt + 1}/{retries})")
                    sleep(2)
                else:
                    logging.error(f"'{query}' chat could not be loaded in WhatsApp after 3 attempts.")
                    raise e

    def load_selected_chat(self, messages_number_target: Optional[int] = None) -> None:
        """
        Loads the selected chat in the WhatsApp Web interface by scrolling to the top and clicking the "load more messages" button if available.

        Args:
            messages_number_target (Optional[int]): The target number of messages to load. If None, all messages will be loaded.

        Raises:
            StaleElementReferenceException: If a stale element reference exception is encountered more than three times in a row.
        """
        start = timer()
        logging.info("Loading messages...")

        message_count = 0
        current_message_count = len(self.driver.find_elements(By.XPATH, '//*[@role="row"]'))
        counter = 0
        while top_elem := self.driver.find_element(By.XPATH, '//*[@id="main"]/div[3]/div/div[2]/div[2]'):
            if messages_number_target and message_count >= messages_number_target:
                logging.info("Message number target reached.")
                break
            logging.info("Scrolling up...")
            if current_message_count == message_count:
                try:
                    top_button = top_elem.find_element(By.XPATH, './/button')
                except (NoSuchElementException, StaleElementReferenceException):
                    top_button = False
                if top_button:
                    logging.info("Clicking the top button...")
                    try:
                        top_button.click()
                        sleep(5) # wait for the messages to load
                        current_message_count = len(self.driver.find_elements(By.XPATH, '//*[@role="row"]'))
                    except StaleElementReferenceException:
                        counter += 1
                        if counter > 3:
                            raise StaleElementReferenceException("StaleElementReferenceException encountered too many times.")
                    continue
                else:
                    logging.info("Reached the top of the chat!")
                    break

            try:
                ActionChains(self.driver).scroll_to_element(top_elem).perform()
                sleep(2) # wait for the messages to load
                message_count = current_message_count
                current_message_count = len(self.driver.find_elements(By.XPATH, '//*[@role="row"]'))
                counter = 0
            except StaleElementReferenceException:
                counter += 1
                if counter > 3:
                    raise StaleElementReferenceException("StaleElementReferenceException encountered too many times.")
                else:
                    continue

        logging.info(f"Success! Your entire chat history has been loaded in {round(timer() - start)} seconds.")

    def scrape_chat(self) -> pd.DataFrame:
        """
        Scrapes chat messages from a WhatsApp Web page using a Selenium WebDriver.

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
        soup = BeautifulSoup(self.driver.page_source, 'lxml')
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
                copyable_scrape = self.scrape_copyable(copyable_text)
                message_scraped.update(copyable_scrape)

                selectable_text = copyable_text.find('span', 'selectable-text') or copyable_text.find('div', 'selectable-text')
                if selectable_text:
                    message_scraped['has_emoji_text'] = bool(selectable_text.find('img'))
                    message_scraped['message'] = self.scrape_selectable(selectable_text, message_scraped['has_emoji_text'])

                messages.append(message_scraped)

        logging.info(f"Success! All {len(messages)} messages have been scraped.")
        chat = pd.DataFrame(messages)
        return chat

    def scrape_copyable(self, copyable_text: BeautifulSoup) -> Dict[str, Any]:
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
        timestamp, sender = copyable_text.get('data-pre-plain-text').strip()[1:-1].split('] ')
        return {
            'sender': sender,
            'datetime': parse_datetime(timestamp),
            'message': copyable_text.find('span', 'copyable-text') or ''
        }

    def scrape_selectable(self, selectable_text: BeautifulSoup, has_emoji: bool = False) -> str:
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

    def get_chat(self, query: str, messages_number_target: Optional[int] = None) -> pd.DataFrame:
        """
        Retrieves chat messages from WhatsApp based on the chat that best matches a query.
        
        Args:
            query (str): The name or keyword to search for in the chat list.
            messages_number_target (Optional[int], optional): The target number of messages to load. Defaults to None.
        
        Returns:
            pd.DataFrame: A DataFrame containing the chat messages.
        
        Raises:
            TimeoutError: If WhatsApp does not load within the specified time.
            Exception: If any other error occurs during the chat scraping process.
        """

        try:
            if not self.whatsapp_is_loaded():
                raise TimeoutError("WhatsApp did not load within the specified time.")
            
            self.find_selected_chat(query)

            self.load_selected_chat(messages_number_target)

            chat = self.scrape_chat()
            return chat

        except Exception as e:
            logging.error("An error occurred while trying to scrape the chat!")
            raise e

        finally:
            self.driver.close()

    def __del__(self):
        self.driver.quit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    load_dotenv()
    query = os.environ.get('QUERY')
    messages_number_target = 100
    client = whatsappClient()
    chat = client.get_chat(query=query, messages_number_target=messages_number_target)
    filepath = export_csv(chat, query)
