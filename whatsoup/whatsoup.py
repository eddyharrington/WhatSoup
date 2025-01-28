import os
import csv

from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementNotInteractableException
from prettytable import PrettyTable
from dotenv import load_dotenv
from timeit import default_timer as timer


def main():
    # Setup selenium to use Chrome browser w/ profile options
    driver = setup_selenium()

    # Load WhatsApp
    if not whatsapp_is_loaded(driver):
        print("You've quit WhatSoup.")
        driver.quit()
        return

    # Get chats
    chats = get_chats(driver)

    # Print chat summary
    print_chats(chats)

    # Prompt user to select a chat for export, then locate and load it in WhatsApp
    finished = False
    while not finished:
        chat_is_loaded = False
        while not chat_is_loaded:
            # Select a chat and locate in WhatsApp
            chat_is_loadable = False
            while not chat_is_loadable:
                # Ask user what chat to export
                selected_chat = select_chat(chats)
                if not selected_chat:
                    print("You've quit WhatSoup.")
                    driver.quit()
                    return

                # Find the selected chat in WhatsApp
                found_selected_chat = find_selected_chat(driver, selected_chat)
                if found_selected_chat:
                    # Break and proceed to load/scrape the chat
                    chat_is_loadable = True
                else:
                    # Clear chat search
                    driver.find_element_by_xpath(
                        '//*[@id="side"]/div[1]/div/span/button').click()

            # Load entire chat history
            chat_is_loaded = load_selected_chat(driver)

        # Scrape the chat history
        scraped = scrape_chat(driver)

        # Export the chat
        scrape_is_exported(selected_chat, scraped)

        # Ask user if they wish to finish and exit WhatSoup
        finished = user_is_finished()

    # Quit WhatSoup
    print("You've quit WhatSoup.")
    driver.quit()
    return


def setup_selenium():
    '''Setup Selenium to use Chrome webdriver'''

    # Load driver and chrome profile from local directories
    load_dotenv()
    DRIVER_PATH = os.getenv('DRIVER_PATH')
    CHROME_PROFILE = os.getenv('CHROME_PROFILE')

    # Configure selenium
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-data-dir={CHROME_PROFILE}")
    driver = webdriver.Chrome(
        executable_path=DRIVER_PATH, options=options)
    # Change default script timeout from 30sec to 90sec for execute_script tasks which slow down significantly in very large chats
    driver.set_script_timeout(90)

    return driver


def whatsapp_is_loaded(driver):
    '''Attempts to load WhatsApp in the browser'''

    print("Loading WhatsApp...", end="\r")

    # Open WhatsApp
    driver.get('https://web.whatsapp.com/')

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

                # Try again
                if err_response.strip().lower() in {'y', 'yes'}:
                    is_valid_response = True
                    continue
                # Abort loading WhatsApp
                elif err_response.strip().lower() in {'n', 'no'}:
                    is_valid_response = True
                    return False
                # Re-prompt the question
                else:
                    is_valid_response = False
                    continue

    # Success
    print("Success! WhatsApp finished loading and is ready.")
    return True


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

    print("Loading your chats...", end="\r")

    # Wrap entire function in a retryable try/catch because chat-pane DOM changes frequently due to users typing, sending messages, and occasional WhatsApp notifications
    retry_attempts = 0
    while retry_attempts < 3:
        retry_attempts += 1

        # Try traversing the chat-pane
        try:
            # Find the chat search (xpath == 'Search or start new chat' element)
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
                    # Get the container of the contact card's title (xpath == parent div container to the span w/ title attribute set to chat name)
                    contact_title_container = selected_chat.find_element_by_xpath(
                        "./div/div[2]/div/div[1]")
                    # Then get all the spans it contains
                    contact_title_container_spans = contact_title_container.find_elements_by_tag_name(
                        'span')
                    # Then loop through all those until we find one w/ a title property
                    for span_title in contact_title_container_spans:
                        if span_title.get_property('title'):
                            name_of_chat = span_title.get_property('title')
                            break

                    # Get the time (xpath == div element that holds last chat time e.g. 'Wednesday' or '1/1/2021')
                    last_chat_time = selected_chat.find_element_by_xpath(
                        "./div/div[2]/div/div[2]").text

                    # Get the last message (xpath == div element that holds a span w/ title attribute set to last chat message)
                    last_chat_msg_element = selected_chat.find_element_by_xpath(
                        "./div/div[2]/div[2]/div")
                    last_chat_msg = last_chat_msg_element.find_element_by_tag_name(
                        'span').get_attribute('title')

                    # Strip last message of left-to-right directional encoding ('\u202a' and '\u202c') if it exists
                    if '\u202a' in last_chat_msg or '\u202c' in last_chat_msg:
                        last_chat_msg = last_chat_msg.lstrip(
                            u'\u202a')
                        last_chat_msg = last_chat_msg.rstrip(
                            u'\u202c')

                    # Check if last message is a group chat and if so prefix the senders name to the message
                    last_chat_msg_sender = last_chat_msg_element.find_element_by_tag_name(
                        'span').text
                    if '\n: \n' in last_chat_msg_sender:
                        # Group have multiple spans to separate sender, colon, and msg contents e.g. '<sender>: <msg>', so we take the first item after splitting to capture the senders name
                        last_chat_msg_sender = last_chat_msg_sender.split('\n')[
                            0]

                        # Prefix the message w/ senders name
                        last_chat_msg = f"{last_chat_msg_sender}: {last_chat_msg}"

                    # Store chat info within a dict
                    chat = {"name": name_of_chat,
                            "time": last_chat_time, "message": last_chat_msg}
                    chats.append(chat)

            # Navigate back to the top of the chat list
            chat_search.click()
            chat_search.send_keys(Keys.DOWN)

            print("Success! Your chats have been loaded.")
            break

        # Catch errors related to DOM changes
        except (StaleElementReferenceException, ElementNotInteractableException) as e:
            if retry_attempts == 3:
                # Make sure we grant user option to exit if DOM keeps changing while scanning chat list
                print("This is taking longer than usual...")
                while True:
                    response = input(
                        "Try loading chats again (y/n)? ")
                    if response.strip().lower() in {'n', 'no'}:
                        print(
                            'Error! Aborting chat load by user due to frequent DOM changes.')
                        if type(e).__name__ == 'StaleElementReferenceException':
                            raise StaleElementReferenceException
                        else:
                            raise ElementNotInteractableException
                    elif response.strip().lower() in {'y', 'yes'}:
                        retry_attempts = 0
                        break
                    else:
                        continue
            else:
                pass

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
        t._max_width = {"#": 3, "Chat Name": 25,
                        "Last Msg Time": 10, "Last Msg": 40}

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
        t._max_width = {"#": 3, "Chat Name": 25,
                        "Last Msg Time": 10, "Last Msg": 40}

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
            if user_response.strip().lower() in {'y', 'yes'}:
                print_chats(chats, full=True)
                is_valid_response = True
            elif user_response.strip().lower() in {'n', 'no'}:
                is_valid_response = True
            else:
                is_valid_response = False


def select_chat(chats):
    '''Prompts the user to select a chat they want to scrape/export'''

    print("\nSelect a chat export option.\n  Options:\n  chat number\t\tSelect chat for export\n  -listchats\t\tList your chats\n  -quit\t\t\tQuit the application\n")
    while True:
        # Ask user to select chat for export
        selected_chat = None
        response = input(
            "What chat would you like to scrape and export? ")

        # Check users response
        if response.strip().lower() == '-listchats':
            print_chats(chats, full=True)
        elif response.strip().lower() == '-quit':
            return None
        else:
            # Make sure user entered a number correlating to the chat
            try:
                int(response)
            except ValueError:
                print("Uh oh! You didn't enter a number. Try again.")
            else:
                if int(response) in range(1, len(chats)+1):
                    selected_chat = chats[int(
                        response)-1]['name']
                    return selected_chat
                else:
                    print(
                        f"Uh oh! The only valid options are numbers 1 - {len(chats)}. Try again.")


def load_selected_chat(driver):
    '''Loads entire chat history by repeatedly scrolling up to fetch more data from WhatsApp'''
    start = timer()
    print("Loading messages...", end="\r")

    # Set focus to chat window (xpath == div element w/ aria-label set to 'Message list. Press right arrow key...')
    message_list_element = driver.find_element_by_xpath(
        "//*[@id='main']/div[3]/div/div/div[contains(@aria-label,'Message list')]")
    message_list_element.send_keys(Keys.NULL)

    # Get scroll height of the chat pane div so we can calculate if new messages were loaded
    current_scroll_height = driver.execute_script(
        "return arguments[0].scrollHeight;", message_list_element)
    previous_scroll_height = current_scroll_height

    # Load all messages by scrolling up and continually checking scroll height to verify more messages have loaded
    all_msgs_loaded = False
    retry_attempts, success_attempts = 0, 0
    while not all_msgs_loaded:
        # Scroll to anchor at top of message list (fetches more messages)
        driver.execute_script(
            "arguments[0].scrollIntoView();", message_list_element)

        # Grant some time for messages to load
        sleep(2)

        # Get scroll height of the chat pane div so we can calculate if new messages were loaded
        previous_scroll_height = current_scroll_height
        current_scroll_height = driver.execute_script(
            "return arguments[0].scrollHeight;", message_list_element)

        # Check if scroll height changed
        if current_scroll_height > previous_scroll_height:
            # New messages were loaded, reset retry counter
            retry_attempts = 0

            # Increment success attempts for user awareness
            success_attempts += 1
            print(
                f"Load new messages succeeded {success_attempts} times", end="\r")

            # Loop back and load more messages
            continue

        # Check if all messages were loaded or retry loading more
        elif current_scroll_height == previous_scroll_height:
            # All messages loaded? (xpath == 'load earlier messages' / 'loading messages...' div that is deleted from DOM after all messages have loaded)
            loading_earlier_msgs = driver.find_element_by_xpath(
                '//*[@id="main"]/div[3]/div/div/div[2]/div').get_attribute('title')
            if 'load' not in loading_earlier_msgs:
                all_msgs_loaded = True
                end = timer()
                print(
                    f"Success! Your entire chat history has been loaded in {round(end - start)} seconds.")
                break

            # Retry loading more messages
            else:
                # Make sure we grant user option to exit if ~60sec of attempting to load more messages doesn't result in new messages loading
                if retry_attempts >= 30:
                    print("This is taking longer than usual...")
                    while True:
                        response = input(
                            "Try loading more messages (y/n)? ")
                        if response.strip().lower() in {'n', 'no'}:
                            print(
                                'Error! Aborting chat load by user due to loading timeout.')
                            return False
                        elif response.strip().lower() in {'y', 'yes'}:
                            # Set focus to chat window again
                            message_list_element.send_keys(Keys.NULL)

                            # Reset counter
                            retry_attempts = 0
                            break
                        else:
                            continue

                # Increment retry acounter and load more messages
                else:
                    retry_attempts += 1
                    continue

    return True


def find_selected_chat(driver, selected_chat):
    '''Searches and loads the initial chat. Returns True/False if the chat is found and can be loaded.

    Assumptions:
    1) The chat is searchable and exists because we scraped it earlier in get_chats
    2) The searched chat will always be the first element under the search input box
    '''

    print(f"Searching for '{selected_chat}'...", end="\r")

    # Find the chat via search (xpath == 'Search or start new chat' element)
    chat_search = driver.find_element_by_xpath(
        '//*[@id="side"]/div[1]/div/label/div/div[2]')
    chat_search.click()

    # Type the chat name into the search box using a JavaScript hack because Selenium/Chromedriver doesn't support all unicode chars - https://bugs.chromium.org/p/chromedriver/issues/detail?id=2269
    driver.execute_script(
        f"arguments[0].innerHTML = '{selected_chat}'", chat_search)

    # Manually fire the JS listeners/events with keyboard input that adds/removes a space at end of search string
    chat_search.send_keys(Keys.END)
    chat_search.send_keys(Keys.SPACE)
    chat_search.send_keys(Keys.BACKSPACE)

    # Wait for search results to load (5 sec max)
    try:
        # Look for the unique class that holds 'Search results.'
        WebDriverWait(driver, 5).until(expected_conditions.presence_of_element_located(
            (By.XPATH, "//*[@id='pane-side']/div[1]/div/div[contains(@aria-label,'Search results.')]")))

        # Force small sleep to deal with issue where focus gets interrupted after wait
        sleep(2)
    except TimeoutException:
        print(
            f"Error! '{selected_chat}' produced no search results in WhatsApp.")
        return False
    else:
        # Navigate to the chat, first element below search input
        chat_search.send_keys(Keys.DOWN)

        # Fetch the element
        search_result = driver.switch_to.active_element

        try:
            # Look for the chat name header and a title attribute that matches the selected chat
            WebDriverWait(driver, 5).until(expected_conditions.presence_of_element_located(
                (By.XPATH, f"//*[@id='main']/header/div[2]/div[1]/div/span[contains(@title,'{selected_chat}')]")))
        except TimeoutException:
            print(
                f"Error! '{selected_chat}' chat could not be loaded in WhatsApp.")
            return False
        else:
            # Get the chat name (xpath == span w/ title set to chat name, a descendant of header tag and anchored at top of chat window)
            chat_name_header = driver.find_element_by_xpath(
                '//*[@id="main"]/header/div[2]/div[1]/div/span').get_attribute('title')

            # Compare searched chat name to the selected chat name
            if chat_name_header == selected_chat:
                print(f"Success! '{selected_chat}' was found.")
                return True
            else:
                print(
                    f"Error! '{selected_chat}' search results loaded the wrong chat: '{chat_name_header}'")
                return False


def scrape_chat(driver):
    '''Turns the chat into soup and scrapes it for key export information: message sender, message date/time, message contents'''

    print("Scraping messages...", end="\r")

    # Make soup
    soup = BeautifulSoup(driver.page_source, 'lxml')

    # Get the 'Message list' element that is a container for all messages in the right chat pane
    message_list = driver.find_element_by_xpath(
        '//*[@id="main"]/div[3]/div/div/div[2]').get_attribute('class')

    # Search for and only keep HTML elements which contain actual messages
    chat_messages = [
        msg for msg in soup.find("div", message_list).contents if 'message' in " ".join(msg.get('class'))]
    chat_messages_count = len(chat_messages)

    # Get users profile name
    you = get_users_profile_name(chat_messages)

    # Loop thru all chat messages, scrape chat info into a dict, and add it to a list
    messages = []
    messages_count = 0
    last_msg_date = None
    for message in chat_messages:
        # Count messages for progress message to user and to compare expected vs actual scraped chat messages
        messages_count += 1
        print(
            f"Scraping message {messages_count} of {chat_messages_count}", end="\r")

        # Dictionary for holding chat information (sender, msg date/time, msg contents, message content types, and data-id for debugging)
        message_scraped = {
            "sender": None,
            "datetime": None,
            "message": None,
            "has_copyable_text": False,
            "has_selectable_text": False,
            "has_emoji_text": False,
            "has_media": False,
            "has_recall": False,
            "data-id": message.get('data-id')
        }

        # Approach for scraping: search for everything we need in 'copyable-text' to start with, then 'selectable-text', and so on as we look for certain HTML patterns. As patterns are identified, update the message_scraped dict.
        # Check if message has 'copyable-text' (copyable-text tends to be a container div for messages that have text in it, storing sender/datetime within data-* attributes)
        copyable_text = message.find('div', 'copyable-text')
        if copyable_text:
            message_scraped['has_copyable_text'] = True

            # Scrape the 'copyable-text' element for the message's sender, date/time, and contents
            copyable_scrape = scrape_copyable(copyable_text)

            # Update the message object
            message_scraped['datetime'] = copyable_scrape['datetime']
            last_msg_date = message_scraped['datetime']
            message_scraped['sender'] = copyable_scrape['sender']
            message_scraped['message'] = copyable_scrape['message']

            # Check if message has 'selectable-text' (selectable-text tends to be a copyable-text child container span/div for messages that have text in it, storing the actual chat message text/emojis)
            if copyable_text.find('span', 'selectable-text'):
                # Span element
                selectable_text = copyable_text.find(
                    'span', 'selectable-text')
            else:
                # Div element
                selectable_text = copyable_text.find(
                    'div', 'selectable-text')

            # Check if message has emojis and overwrite the message object w/ updated chat message
            if selectable_text:
                message_scraped['has_selectable_text'] = True

                # Does it contain emojis? Emoji's are renderd as <img> elements which are child to the parent span/div container w/ selectable-text class
                if selectable_text.find('img'):
                    message_scraped['has_emoji_text'] = True

                # Get message from selectable and overwrite existing chat message
                message_scraped['message'] = scrape_selectable(
                    selectable_text, message_scraped['has_emoji_text'])

        # Check if message was recalled
        if is_recall_in_message(message):
            message_scraped['has_recall'] = True

            # Update the message object
            message_scraped['datetime'] = find_chat_datetime_when_copyable_does_not_exist(
                message, last_msg_date)
            last_msg_date = message_scraped['datetime']
            message_scraped['sender'] = you
            message_scraped['message'] = "<You deleted this message>"

        # Check if the message has media
        message_scraped['has_media'] = is_media_in_message(message)
        if message_scraped['has_media']:
            # Check if it also has text
            if message_scraped['has_copyable_text']:
                # Update chat message w/ media omission (note that copyable has already scraped the sender + datetime)
                message_scraped['message'] = f"<Media omitted> {message_scraped['message']}"

            else:
                # Without copyable, we need to scrape the sender in a different way
                if 'message-out' in message.get('class'):
                    # Message was sent by the user
                    message_scraped['sender'] = you
                elif 'message-in' in message.get('class'):
                    # Message was sent from a friend of the user
                    message_scraped['sender'] = find_media_sender_when_copyable_does_not_exist(
                        message)
                    if not message_scraped['sender']:
                        # Only occurs intermittently when the senders name does not exist in the message - so we take the last message's sender
                        message_scraped['sender'] = messages[-1]['sender']
                else:
                    pass

                # Get the date/time and update the message object
                message_scraped['datetime'] = find_chat_datetime_when_copyable_does_not_exist(
                    message, last_msg_date)
                last_msg_date = message_scraped['datetime']
                message_scraped['message'] = '<Media omitted>'

        # Add the message object to list
        if 'grouped-sticker' not in message.get('data-id'):
            messages.append(message_scraped.copy())
        else:
            # Make duplicate entry for grouped sticker to match behavior with WhatsApp export (i.e. a group sticker == 2 lines in the txt export both with <Media omitted> messages)
            messages.append(message_scraped.copy())
            messages.append(message_scraped.copy())

            # Finally, update expectd msg count
            chat_messages_count += 1

        # Loop to the next chat message
        continue

    # Scrape summary
    if len(messages) == chat_messages_count:
        print(f"Success! All {len(messages)} messages have been scraped.")
    else:
        print(
            f"Warning! {len(messages)} messages scraped but {chat_messages_count} expected.")

    # Create a dict with chat date as key and empty list as value which will store all msgs for that date
    messages_dict = {msg_list['datetime'].strftime(
        "%m/%d/%Y"): [] for msg_list in messages}

    # Update the dict by inserting message content as values
    for m in messages:
        messages_dict[m['datetime'].strftime("%m/%d/%Y")].append(
            {'time': m['datetime'].strftime("%I:%M %p"), 'sender': m['sender'], 'message': m['message']})

    return messages_dict


def get_users_profile_name(chat_messages):
    '''Returns the user's profile name so we can determine who 'You' is in the conversation.

    WhatsApp's default 'export' fucntionality renders the users profile name and never 'You'.
    '''

    you = None
    for chat in chat_messages:
        if 'message-out' in chat.get('class'):
            chat_exists = chat.find('div', 'copyable-text')
            if chat_exists:
                you = chat.find(
                    'div', 'copyable-text').get('data-pre-plain-text').strip()[1:-1].split('] ')[1]
                break
    return you


def scrape_copyable(copyable_text):
    '''Returns a dict with values for sender, date/time, and contents of the WhatsApp message'''

    copyable_scrape = {'sender': None, 'datetime': None, 'message': None}

    # Get the elements attributes that hold the sender and date/time values
    copyable_attrs = copyable_text.get(
        'data-pre-plain-text').strip()[1:-1].split('] ')

    # Get the sender, date/time, and msg contents
    copyable_scrape['sender'] = copyable_attrs[1]
    copyable_scrape['datetime'] = parse_datetime(
        f"{copyable_attrs[0].split(', ')[1]} {copyable_attrs[0].split(', ')[0]}")

    # Get the text-only portion of the message contents (always in a span w/ copyable-text class)
    content = copyable_text.find('span', 'copyable-text')
    if content:
        copyable_scrape['message'] = content
    else:
        copyable_scrape['message'] = ''

    return copyable_scrape


def scrape_selectable(selectable_text, has_emoji=False):
    '''Returns message contents of a chat by checking for and handling emojis'''

    # Does it contain emojis?
    if has_emoji:
        # Construct the message manually because emoji content is broken up into many span/img elements that we need to loop through
        # Loop over every child span of selectable-text, as these wrap the text and emojis/imgs
        message = ''
        for span in selectable_text.find_all('span'):

            # Loop over every child element of the span to construct the message
            for element in span.contents:
                # Check what kind of element it is
                if element.name is None:
                    # Text, ignoring empty strings
                    if element == ' ':
                        continue
                    else:
                        message += str(element)
                elif element.name == 'img':
                    # Emoji
                    message += element.get('alt')
                else:
                    # Skip other elements (note: have not found any occurrences of this happening...yet)
                    continue

        return message
    else:
        # Return the text only
        return selectable_text.text


def is_recall_in_message(message):
    '''Returns True if message contains recall pattern (a span will contain 'recalled' in data-*), if not returns False.'''
    # Check if message contains spans
    spans = message.find_all('span')
    if spans:
        # Check all spans for recalled
        for span in spans:
            if span.get('data-testid') == 'recalled':
                return True

    return False


def find_chat_datetime_when_copyable_does_not_exist(message, last_msg_date):
    '''Returns a message's date/time when there's no 'copyable-text' attribute within the message e.g. deleted messages, media w/ no text, etc.'''

    spans = message.find_all('span')
    # Check if spans exist
    if spans:
        for span in spans:
            # Check spans w/ text if they are dates/times
            if span.text:
                try:
                    parse_datetime(span.text, time_only=True)
                except ValueError:
                    # Span text is not a date/time value
                    continue
                else:
                    # Get the hour/minute time from the media message
                    message_time = span.text

                    # Get a sibling div holding the latest chat date, otherwise if that doesn't exist then grab the last msg date
                    try:
                        # Check if row from message list is a date and not a chat, grabs the first available prior date (this fires for all but the first date of chat history messaging)
                        sibling_date = message.find_previous_sibling(
                            "div", attrs={'data-id': False}).text
                        if not sibling_date:
                            # Use the previous messages date if it exists
                            if last_msg_date:
                                sibling_date = last_msg_date.strftime(
                                    '%m/%d/%Y')
                            else:
                                # Otherwise use the next available subsequent date (note this fires only on the first message w/ rare conditions when copyable-text doesn't exist; could assign the wrong date if for example the next available date is 1+ day in advance of the current message)
                                sibling_date = message.find_next_sibling(
                                    "div", attrs={'data-id': False}).text

                        # Try converting to a date/time object
                        media_message_datetime = parse_datetime(
                            f"{sibling_date} {message_time}")

                        # Build date/time object
                        message_datetime = parse_datetime(
                            f"{media_message_datetime.strftime('%m/%d/%Y')} {media_message_datetime.strftime('%I:%M %p')}")

                        return message_datetime

                    # Otherwise last message's date/time (note this could assign the wrong date if for example the last message was 1+ days ago)
                    except ValueError:
                        message_datetime = parse_datetime(
                            f"{last_msg_date.strftime('%m/%d/%Y')} {message_time}")

                        return message_datetime

    else:
        return None


def parse_datetime(text, time_only=False):
    '''Try parsing and returning datetimes in a North American standard, otherwise raise a ValueError'''
    # TODO lazy approach to handling variances of North America date/time values MM/DD/YYYY AM/PM or YYYY-MM-DD A.M./P.M.

    # Normalize the text
    text = text.upper().replace("A.M.", "AM").replace("P.M.", "PM")

    # Try parsing when text is some datetime value e.g. 2/15/2021 2:35 P.M.
    if not time_only:
        for fmt in ('%m/%d/%Y %I:%M %p', '%Y-%m-%d %I:%M %p'):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        raise ValueError(
            f"{text} does not match a valid datetime format of '%m/%d/%Y %I:%M %p' or '%Y-%m-%d %I:%M %p'. Make sure your WhatsApp language settings on your phone are set to English.")

    # Try parsing when text is some time value e.g. 2:35 PM
    else:
        try:
            return datetime.strptime(text, '%I:%M %p')
        except ValueError:
            pass
        raise ValueError(
            f"{text} does not match expected time format of '%I:%M %p'. Make sure your WhatsApp language settings on your phone are set to English.")


def is_media_in_message(message):
    '''Returns True if media is discovered within the message by checking the soup for known media flags. If not, it returns False.'''

    # First check for data-testid attributes containing 'media' or 'download' (this covers gifs, videos, downloadable content)
    possible_media_spans = message.find_all(attrs={'data-testid': True})
    for span in possible_media_spans:
        # Media types are stored in 'data-testid' attribute
        media_attr = span.get('data-testid')

        if 'media' in media_attr or 'download' in media_attr:
            return True
        else:
            continue

    # Check if the media is a shared contact e.g. vCard/VCF, or a sticker
    if message.get('class'):
        # Check for shared contact
        copyable = message.find('div', 'copyable-text')
        if copyable:
            # Get all buttons
            buttons = copyable.find_all('div', {'role': 'button'})
            if buttons:
                # Look for contact card button pattern (2 divs w/ titles of 'Message X' and 'Add to a group')
                for button in buttons:
                    # Only check buttons with Title attribute
                    if button.get('title'):
                        # Check if 'Message' is in the title (full title would be for example 'Message Bob Ross')
                        if 'Message' in button.get('title'):
                            # Next sibling should always be the 'Add to a group' button
                            if button.nextSibling:
                                if button.nextSibling.get('title') == 'Add to a group':
                                    return True

        # Check for group sticker (2 side-by-side stickers)
        if 'grouped-sticker' in message.get('data-id'):
            return True

        # Check for individual sticker
        images = message.find_all('img')
        if images:
            for image in images:
                if 'blob' in image.get('src'):
                    return True

    return False


def find_media_sender_when_copyable_does_not_exist(message):
    '''Returns a sender's name when there's no 'copyable-text' attribute within the message'''

    # Check to see if senders name is stored in a span's aria-label attribute (note: this seems to be where it's stored if the persons name is just text / no emoji)
    spans = message.find_all('span')
    has_emoji = False
    for span in spans:
        if span.get('aria-label'):
            # Last char in aria-label is always colon after the senders name
            if span.get('aria-label') != 'Voice message':
                return span.get('aria-label')[:-1]
        elif span.find('img'):
            # Emoji is in name and needs to be handled differently
            has_emoji = True
            break
        else:
            continue

    # Manually construct the senders name if it has an emoji by building a string from span.text and img/emoji tags
    if has_emoji:
        # Get all elements from known emoji container span (always contained within a div that uses the class 'color-#' and will be the 0th child item)
        emoji_name_elements = message.select("div[class*='color']")[0].next

        # Loop over every child element of the span to construct the senders name
        name = ''
        for element in emoji_name_elements.contents:
            # Check what kind of element it is
            if element.name is None:
                # Text, ignoring empty strings
                if element == ' ':
                    continue
                else:
                    name += str(element)
            elif element.name == 'img':
                # Emoji
                name += element.get('alt')
            else:
                # Skip other elements (note: have not found any occurrences of this happening...yet)
                continue

        return name

    # There is no sender name in the message, an issue that occurrs very infrequently (e.g. 6000+ msg chat occurred 3 times) - pattern for this seems to be 1) sender name has no emoji, 2) msg has media, 3) msg does not have text, 4) msg is a follow-up / consecutive message (doesn't have tail-in icon in message span/svg)
    else:
        # TODO: Study this pattern more and fix later if possible. Solution for now is to return None and then we take the last message's sender from our data structure.
        return None


def scrape_is_exported(selected_chat, scraped):
    '''Returns True/False if an export file type is selected and succesfully exported'''

    print("\nSelect an export format.\n  Options:\n  txt\t\tExport to .txt file type\n  csv\t\tExport to .csv file type\n  html\t\tExport to .html file type\n  -abort\tAbort the export\n")
    is_exported = False
    while not is_exported:
        # Ask user to select export type
        response = input(
            "What format do you want to export to? ")

        # Check users response
        if response.strip().lower() == 'txt':
            if export_txt(selected_chat, scraped):
                is_exported = True
        elif response.strip().lower() == 'csv':
            if export_csv(selected_chat, scraped):
                is_exported = True
        elif response.strip().lower() == 'html':
            if export_html(selected_chat, scraped):
                is_exported = True
        elif response.strip().lower() == '-abort':
            print(f"You've aborted the export for '{selected_chat}'.")
            return False
        else:
            print(
                f"Uh oh! '{response.strip().lower()}' is not a valid option. Try again.")

    return True


def export_txt(selected_chat, scraped):
    '''Returns True if the scraped data for a selected export is written to local .txt file without any exceptions thrown'''

    # Make sure exports directory exists
    export_dir_setup()

    print(f"Exporting to local .txt file...", end="\r")
    # Try exporting to a text file
    try:
        # Format file name as 'WhatsApp chat with [name] - [YYYY-MM-DD HH.MM.SS.AM/PM]'
        now = datetime.now().strftime('%Y-%m-%d %H.%M.%S.%p')

        # Write to file
        with open(f"exports/WhatsApp Chat with {selected_chat} - {now}.txt", "wb") as text_file:
            for date_write, messages_write in scraped.items():
                for message_write in messages_write:
                    line = f"{date_write}, {message_write['time']} - {message_write['sender']}: {message_write['message']}\n"
                    encoded = line.encode()
                    text_file.write(encoded)

        print(
            f"Success! 'WhatsApp Chat with {selected_chat} - {now}.txt' exported.")
        return True

    except Exception as error:
        print(f"Error during txt export! Error info: {error}")
        return False


def export_csv(selected_chat, scraped):
    '''Returns True if the scraped data for a selected export is written to local .csv file without any exceptions thrown'''

    # Make sure exports directory exists
    export_dir_setup()

    # Unpack into nested lists
    data = []
    for date, messages in scraped.items():
        for message in messages:
            # Unpack into a list
            message = [date, message['time'],
                       message['sender'], message['message']]

            # Add to parent list
            data.append(message)

    print(f"Exporting to local .csv file...", end="\r")
    # Try exporting to a csv file
    try:
        # Format file name as 'WhatsApp chat with [name] - [YYYY-MM-DD HH.MM.SS.AM/PM]'
        now = datetime.now().strftime('%Y-%m-%d %H.%M.%S.%p')

        # Write to file
        with open(f"exports/WhatsApp Chat with {selected_chat} - {now}.csv", "w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file, delimiter=",")
            writer.writerow(['Date', 'Time', 'Sender', 'Message'])
            writer.writerows(data)

        print(
            f"Success! 'WhatsApp Chat with {selected_chat} - {now}.csv' exported.")
        return True

    except Exception as error:
        print(f"Error during csv export! Error info: {error}")
        return False


def export_html(selected_chat, scraped):
    '''Returns True if the scraped data for a selected export is written to local .html file without any exceptions thrown'''

    # Make sure exports directory exists
    export_dir_setup()

    # Unpack into nested lists
    data = []
    for date, messages in scraped.items():
        for message in messages:
            # Unpack into a list
            message = [date, message['time'],
                       message['sender'], message['message']]

            # Add to parent list
            data.append(message)

    # Create a pretty table
    t = PrettyTable()
    t.field_names = ['Date', 'Time', 'Sender', 'Message']

    # Add chat records to the table
    for message in data:
        t.add_row(message)

    # Get HTML string from PrettyTable
    html = t.get_html_string()

    print(f"Exporting to local .html file...", end="\r")
    # Try exporting to a html file
    try:
        # Format file name as 'WhatsApp chat with [name] - [YYYY-MM-DD HH.MM.SS.AM/PM]'
        now = datetime.now().strftime('%Y-%m-%d %H.%M.%S.%p')

        # Write to file
        with open(f"exports/WhatsApp Chat with {selected_chat} - {now}.html", "wb") as html_file:
            encoded = html.encode()
            html_file.write(encoded)

        print(
            f"Success! 'WhatsApp Chat with {selected_chat} - {now}.html' exported.")
        return True

    except Exception as error:
        print(f"Error during html export! Error info: {error}")
        return False


def export_dir_setup():
    '''Creates a local 'exports' directory if it does not already exist'''

    if not os.path.isdir('exports'):
        os.mkdir('exports')
        print(
            f"'exports' directory created: {os.path.dirname(os.path.abspath(__file__))}")


def user_is_finished():
    '''Returns True/False is the user wants to finish and exit WhatSoup'''

    is_valid_response = False
    while not is_valid_response:
        response = input("Proceed with exporting another chat (y/n)? ")

        # Do not exit WhatSoup
        if response.strip().lower() in {'y', 'yes'}:
            return False
        # Quit and exit
        elif response.strip().lower() in {'n', 'no'}:
            return True
        # Re-prompt the question
        else:
            continue


if __name__ == "__main__":
    main()
