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
from prettytable import PrettyTable


def main():
    # Setup selenium to use Chrome browser w/ profile options
    driver = setup_selenium()

    # Load WhatsApp
    if load_whatsapp(driver) == 0:
        print("Success! WhatsApp finished loading and is ready.")
    else:
        print("You've quit WhatSoup.")
        return

    # Get chats
    chats = get_chats(driver)

    # Print chat summary
    print_chats(chats)

    # Ask user what chat to export, or if they wish to quit
    selected_export = select_chat_export(chats)
    if not selected_export:
        return
    else:
        print(f"Success! '{selected_export}' will be scraped and exported.")

    # Find the selected chat in WhatsApp
    found_selected_chat = find_selected_chat(driver, selected_export)
    if found_selected_chat:
        # Load entire chat history
        chat_is_loaded = load_selected_chat(driver)
    else:
        # TODO: Handle unsearchable chat (e.g. abort, manual intervention / input from user (note this has dependency on how we verify discovered chats in find_selected_chat))
        pass

    # Scrape the chat history
    if chat_is_loaded:
        print("Scraping messages...this may take a while.")
        pass
    else:
        # TODO: Handle unloadable chat (e.g. internet loss, browser crash, etc.)
        pass


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

            is_valid_response = False
            while not is_valid_response:
                # Ask user if they want to try loading WhatsApp again
                err_response = input("Proceed (y/n)? ")

                # Check the user's response
                if err_response.strip().lower() == 'y' or err_response.strip().lower() == 'yes':

                    while True:
                        # Ask user if they want to increment the wait time by 10 seconds
                        wait_response = input(
                            f"Increase wait time for WhatsApp to load from {wait_time} seconds to {wait_time + 10} seconds (y/n)? ")

                        # Increase wait time by 10 seconds
                        if wait_response.strip().lower() == 'y' or wait_response.strip().lower() == 'yes':
                            wait_time += 10
                            is_valid_response = True
                            break
                        elif wait_response.strip().lower() == 'n' or wait_response.strip().lower() == 'no':
                            is_valid_response = True
                            break
                        else:
                            is_valid_response = False

                    continue
                # Abort loading WhatsApp
                elif err_response.strip().lower() == 'n' or err_response.strip().lower() == 'no':
                    is_valid_response = True
                    driver.quit()
                    return 1
                # Re-prompt the question
                else:
                    is_valid_response = False
                    continue
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


def get_chats(driver):
    '''Traverses the WhatsApp chat-pane via keyboard input and collects chat information such as person/group name, last chat time and msg'''

    # Find the chat search input because the element below it is always the most recent chat
    chat_search = driver.find_element_by_xpath(
        '//*[@id="side"]/div[1]/div/label/div/div[2]')
    chat_search.click()

    # Count how many chat records there are below the search input by using keyboard navigation because HTML is dynamically changed depending on viewport and location in DOM
    selected_chat = driver.switch_to.active_element
    prev_chat_id = None
    is_last_chat = False
    chats = []

    # Descend through the chats
    while True:
        # Navigate to next chat
        selected_chat.send_keys(Keys.DOWN)

        # Set active element to new chat (without this we can't access the elements '.text' value used below for name/time/msg)
        selected_chat = driver.switch_to.active_element

        # Check if we are on the last chat by comparing current to previous chat
        if selected_chat.id == prev_chat_id:
            is_last_chat = True
        else:
            prev_chat_id = selected_chat.id

        # Gather chat info (chat name, chat time, and last chat message)
        if is_last_chat:
            break
        else:
            # TODO refactor this area later, there have been a few intermittent issues with odd text splits due to inconsistent HTML
            # based on individual/group chats, emojis, attachments, etc. Should use BS4 as it grants more flexibility for slicing HTML.

            chat_info = selected_chat.text.splitlines()

            # One-on-one chats: chat name, last chat time, last chat msg
            if len(chat_info) == 3:
                name_of_chat = chat_info[0]
                last_chat_time = chat_info[1]
                last_chat_msg = chat_info[2]
            # Group chats: chat name, last chat time, name of last msg sender, last chat msg
            elif len(chat_info) == 5:
                # Note: ignore item3 which is always ':' in group chat
                name_of_chat = chat_info[0]
                last_chat_time = chat_info[1]
                last_chat_msg = f"{chat_info[2]}: {chat_info[4]}"
            # Edge cases
            else:
                # One-on-one chat where last message is an emoji. Splits the elements text w/ items 0) name of sender, 2) last chat time
                if len(chat_info) == 2:
                    try:
                        name_of_chat = chat_info[0]
                        last_chat_time = chat_info[1]

                        # TODO below only grabs the first emoji item. If there are many emojis we need to find
                        # all child elements and build a single string of the text/emojis.

                        # Make sure to scrape from the chat preview span (class '_7W_3c') and not username span (class '_1c_mC')
                        last_chat_msg = selected_chat.find_element_by_class_name(
                            '_7W_3c').find_element_by_class_name('emoji').get_attribute('alt')
                    except NoSuchElementException:
                        print(
                            f"Something went wrong while reading a chat card. Skipping '{chat_info}'")
                        continue

                # One-on-one chat where last message is a photo attachment OR Group chat where last message is an emoji.
                # TODO: Intermittent issue only happened 2 or 3 times...One-on-one implementation: splits the elements text w/ items 0) name of group, 1), last chat time, 2) 'Photo', 3) '1'

                # Group chat implementation: splits the elements text w/ items 0) name of group, 1) last chat time, 2) sender, 3) ': '
                elif len(chat_info) == 4:
                    try:
                        name_of_chat = chat_info[0]
                        last_chat_time = chat_info[1]
                        # Make sure to scrape from the chat preview span (class '_7W_3c') and not username span (class '_1c_mC')
                        emoji_loc = selected_chat.find_element_by_class_name(
                            '_7W_3c').find_element_by_class_name('emoji').get_attribute('alt')

                        # Build the entire message by combining text w/ emoji
                        last_chat_msg = f"{chat_info[2]}{chat_info[3].strip()} {emoji_loc}"
                    except NoSuchElementException:
                        print(
                            f"Something went wrong while reading a chat card. Skipping '{chat_info}'")
                        continue

                # Handle any other length in case of errors
                else:
                    print(
                        f"Something went wrong while reading a chat card. Skipping '{chat_info}'")
                    continue

            # Store chat info within a dict
            chat = {"name": name_of_chat,
                    "time": last_chat_time, "message": last_chat_msg}
            chats.append(chat)

    # Navigate back to the top of the chat list
    chat_search.click()
    chat_search.send_keys(Keys.DOWN)

    return chats


def print_chats(chats, full=False):
    '''Prints a summary of the scraped chats'''

    # Print a full summary of the scraped chats
    if full:
        # Create a pretty table
        t = PrettyTable()
        t.field_names = ["#", "Chat Name", "Last Msg Time", "Last Msg"]

        # Style the columns
        for key in t.align.keys():
            t.align[key] = "l"
        t._max_width = {"#": 4, "Chat Name": 25,
                        "Last Msg Time": 12, "Last Msg": 70}

        # Add chat records to the table
        for i, chat in enumerate(chats, start=1):
            t.add_row([str(i), chat['name'], chat['time'], chat['message']])

        # Print the table
        print(t.get_string(title='Your WhatsApp Chats'))
        return

    # Print a short summary (up to 5 most recent chats), and give user option to display more info if they want
    else:
        # Create a pretty table
        t = PrettyTable()
        t.field_names = ["#", "Chat Name", "Last Msg Time", "Last Msg"]

        # Style the columns
        for key in t.align.keys():
            t.align[key] = "l"
        t._max_width = {"#": 4, "Chat Name": 25,
                        "Last Msg Time": 12, "Last Msg": 70}

        # Add up to 5 most recent chat records to the table
        row_count = 0
        for i, chat in enumerate(chats, start=1):
            if i < 6:
                t.add_row([str(i), chat['name'], chat['time'], chat['message']])
                row_count += 1
            else:
                break

        # Print the table
        print(
            f"{t.get_string(title=f'Your {row_count} Most Recent WhatsApp Chats')}\n")

        # Ask user if they want a longer summary
        is_valid_response = False
        while not is_valid_response:
            user_response = input(
                "Would you like to see a complete summary of the scraped chats (y/n)? ")
            if user_response.strip().lower() == 'y' or user_response.strip().lower() == 'yes':
                print_chats(chats, full=True)
                is_valid_response = True
            elif user_response.strip().lower() == 'n' or user_response.strip().lower() == 'no':
                is_valid_response = True
            else:
                is_valid_response = False


def select_chat_export(chats):
    '''Prompts the user to select a chat they want to scrape/export'''

    while True:
        # Ask user to select chat for export
        selected_export = None
        print("\nSelect a chat export option.\n  Options:\n  chat number\t\tSelect chat for export\n  -listchats\t\tList your chats\n  -quit\t\t\tQuit the application\n")
        export_response = input(
            "What chat would you like to scrape and export? ")

        # Check users response
        if export_response.strip().lower() == '-listchats':
            print_chats(chats, full=True)
        elif export_response.strip().lower() == '-quit':
            print("You've quit WhatSoup.")
            return None
        else:
            # Make sure user entered a number correlating to the chat
            try:
                int(export_response)
            except ValueError:
                print("Uh oh! You didn't enter a number. Try again.")
            else:
                if int(export_response) in range(1, len(chats)+1):
                    selected_export = chats[int(
                        export_response)-1]['name']
                    return selected_export
                else:
                    print(
                        f"Uh oh! The only valid options are numbers 1 - {len(chats)}. Try again.")


def load_selected_chat(driver):
    '''Loads entire chat history by repeatedly hitting the home button to fetch more data from WhatsApp'''

    print("Loading messages...this may take a while.")

    # Click in chat window to set focus
    convo_window_xpath = driver.find_element_by_xpath(
        '//*[@id="main"]/div[3]/div/div/div[3]')
    convo_window_xpath.click()
    convo_window = driver.switch_to.active_element

    # Get all the div elements from the chat window - we use it to verify all records have loaded
    current_div_count = len(convo_window_xpath.find_elements_by_xpath("./div"))
    previous_div_count = current_div_count

    # Track dates during loading progress so user knows what timeframe of messages are being loaded
    current_load_date = None

    # Load all messages by hitting home and continually checking div count to verify more messages have loaded
    all_msgs_loaded = False
    while not all_msgs_loaded:
        # Hit home
        convo_window.send_keys(Keys.HOME)

        # Track # of times we check for new messages
        attempts = 0

        # Counts divs to see if new messages actually loaded after hitting HOME
        while True:
            attempts += 1

            # Wait for messages to load
            sleep(1)

            # Recount the child divs and verify if more messages loaded
            current_div_count = len(
                convo_window_xpath.find_elements_by_xpath("./div"))
            if current_div_count > previous_div_count:
                # More messages were loaded
                previous_div_count = current_div_count

                # Try grabbing date of currently loaded messages
                try:
                    # Use the latest date rendered in chat window
                    current_load_date = datetime.strptime(
                        driver.find_element_by_class_name('KpuSa').text, '%m/%d/%Y')
                    print(
                        f"Loaded new messages from {current_load_date.strftime('%m/%d/%Y')}", end="\r")
                except ValueError:
                    # Use last known date because some other info was found using the same class (i.e. chat notifications like 'Missed video call')
                    print(
                        f"Loaded new messages from {current_load_date.strftime('%m/%d/%Y')}", end="\r")
                except:
                    # Use non-date message with same char length of 35 to ensure printed line overwrites the previous print statement
                    print(
                        f"Loaded new messages from your chat!", end="\r")

                # Loop back to hitting Home again to load more messages
                break

            # Check if all messages have loaded (note: 'load earlier messages' div gets deleted from DOM once all messages have loaded)
            load_messages_div = driver.find_element_by_xpath(
                '//*[@id="main"]/div[3]/div/div/div[2]/div').get_attribute('title')
            if load_messages_div == '':
                all_msgs_loaded = True
                print("Success! Your entire chat history has been loaded.")
                break
            else:
                # Make sure we grant user option to exit if ~30sec of hitting home doesn't result in all messages being loaded
                if attempts >= 30:
                    print("This is taking longer than usual...")
                    while True:
                        response = input(
                            "Try loading more messages (y/n)? ")
                        if response.strip().lower() == 'n' or response.strip().lower() == 'no':
                            print(
                                'Error! Aborting conversation loading due to timeout.')
                            return False
                        elif response.strip().lower() == 'y' or response.strip().lower() == 'yes':
                            # Reset counter
                            print("Loading more messages...")
                            attempts = 0
                            break
                        else:
                            continue

    return True


def find_selected_chat(driver, selected_export):
    '''Searches and loads the initial chat. Returns True/False if the chat is found and can be loaded.

    Assumptions:
    1) The chat is searchable and exists because we scraped it earlier in get_chats
    2) The searched chat will always be the first element under the search input box

    TODO Notes:
    - If any of the assumptions are false, then this algorithm will produce errors.
    - Failing scenarios: 1) chat name changes since get_chats scrape, 2) chat name was scraped incorrectly which produces invalid search results (e.g. unsupported characters/encoding)
    '''
    print(f"Searching for '{selected_export}' chat in WhatsApp...")

    # Find the chat via search (TODO: currently we assume it finds the chat because we scraped the chat name already and the first result is always the selected chat. May need to add verification.)
    chat_search = driver.find_element_by_xpath(
        '//*[@id="side"]/div[1]/div/label/div/div[2]')
    chat_search.click()
    chat_search.send_keys(selected_export)
    # TODO: replace sleeps with X attempts and promting to retry?
    sleep(2)

    # Navigate to the chat, first element below search input
    chat_search.send_keys(Keys.DOWN)
    sleep(2)

    # Fetch the element
    search_result = driver.switch_to.active_element

    # No results were found if the active element is still the search box
    if search_result.id == chat_search.id:
        print(f"Error! '{selected_export}' produced no search results.")
        return False
    else:
        # Compare the selected chat to actual chat name header
        chat_name_header = driver.find_element_by_class_name('YEe1t').text
        if chat_name_header == selected_export:
            print(f"Success! '{selected_export}' was found.")
            return True
        else:
            print(
                f"Error! '{selected_export}' search results loaded the wrong chat: '{chat_name_header}'")
            return False


if __name__ == "__main__":
    main()
