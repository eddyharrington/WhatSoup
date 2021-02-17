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
        scraped = scrape_chat(driver)

        # Write to a text file
        if export_txt(selected_export, scraped):
            print("Would you like to scrape another chat?")
            # TODO: refactor to enable looping of scrape activities
        else:
            print("Try again?")
            # TODO: Handle failed txt file export

        # TODO: add support for CSV file export

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
            # Get the name of the chat
            name_of_chat = selected_chat.find_element_by_class_name(
                "_3Tw1q").text
            # Get the container of the contact card's title
            contact_title_container = selected_chat.find_element_by_class_name(
                "_3Tw1q")
            # Then get all the spans it contains
            contact_title_container_spans = contact_title_container.find_elements_by_tag_name(
                'span')
            # Then loop through all those until we find one w/ a title property
            for span_title in contact_title_container_spans:
                if span_title.get_property('title'):
                    name_of_chat = span_title.get_property('title')
                    break

            # Get the time
            last_chat_time = selected_chat.find_element_by_class_name(
                "_2gsiG").text

            # Get the last message
            last_chat_msg_element = selected_chat.find_element_by_class_name(
                "fqPQb")
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

                # Try grabbing date of currently loaded messages (always the latest KpuSa element rendereded after more messages are loaded)
                # TODO: somewhat expensive use of code for what could be an easier way to show progress during scraping. Keep this long term?
                try:
                    # Use a date rendered in chat window such as 1/1/2021
                    current_load_date = datetime.strptime(
                        driver.find_element_by_class_name('KpuSa').text, '%m/%d/%Y')
                    print(
                        f"Loaded new messages from {current_load_date.strftime('%m/%d/%Y')}", end="\r")
                except ValueError:
                    # Use a non-date string value such as Yesterday/Today/Monday/etc, skip over chat event items like missed calls, name updates, etc.

                    # Verify the expected date element is not a chat event by checking for single vs multiple words
                    possible_date = driver.find_element_by_class_name(
                        'KpuSa').text.split(' ')
                    if len(possible_date) == 1:
                        # Skip empty strings
                        if possible_date[0]:
                            print(
                                f"Loaded new messages from {possible_date[0].title()}", end="\r")
                    else:
                        # For group events / sentences, use non-date message with same char length of 35 to ensure printed line overwrites the previous print statement
                        print(
                            f"Loaded new messages from your chat!", end="\r")
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
    '''

    print(f"Searching for '{selected_export}' chat in WhatsApp...")

    # Find the chat via search
    chat_search = driver.find_element_by_xpath(
        '//*[@id="side"]/div[1]/div/label/div/div[2]')
    chat_search.click()

    # Type the chat name into the search box using a JavaScript hack because Selenium/Chromedriver doesn't support all unicode chars - https://bugs.chromium.org/p/chromedriver/issues/detail?id=2269
    emoji_hack_script = f'''
    let chat_search = document.querySelector('._1awRl');
    chat_search.innerHTML = '{selected_export}';
    '''
    driver.execute_script(emoji_hack_script, selected_export)

    # Manually fire the JS listeners/events with keyboard input
    chat_search.send_keys(Keys.SPACE)

    # Remove the unnecessary space from above step
    chat_search.send_keys(Keys.BACKSPACE)

    # Go to the end of the search input box so that the next key (down) can select the chat card (if any)
    chat_search.send_keys(Keys.END)

    # Wait for search results to load (5 sec max)
    try:
        # Look for the unique class that holds 'Search results.'
        WebDriverWait(driver, 5).until(expected_conditions.presence_of_element_located(
            (By.XPATH, "//*[@class='_3soxC _2aY82']")))

        # Force small sleep to deal with issue where focus gets interrupted after wait
        sleep(2)
    except TimeoutException:
        print(
            f"Error! '{selected_export}' produced no search results in WhatsApp.")
        return False
    else:
        # Navigate to the chat, first element below search input
        chat_search.send_keys(Keys.DOWN)

        # Fetch the element
        search_result = driver.switch_to.active_element

        try:
            # Look for the chat name header and a title attribute that matches the selected chat
            WebDriverWait(driver, 5).until(expected_conditions.presence_of_element_located(
                (By.XPATH, f"//*[@id='main']/header/div[2]/div[1]/div/span[contains(@title,'{selected_export}')]")))
        except TimeoutException:
            print(
                f"Error! '{selected_export}' chat could not be loaded in WhatsApp.")
            return False
        else:
            # Get the chat name
            chat_name_header = driver.find_element_by_class_name(
                'YEe1t').find_element_by_tag_name('span').get_attribute('title')

            # Compare searched chat name to the selected chat name
            if chat_name_header == selected_export:
                print(f"Success! '{selected_export}' was found.")
                return True
            else:
                print(
                    f"Error! '{selected_export}' search results loaded the wrong chat: '{chat_name_header}'")
                return False


def scrape_chat(driver):
    '''Turns the chat into soup and scrapes it for key export information: message sender, message date/time, message contents'''

    # Make soup
    soup = BeautifulSoup(driver.page_source, 'lxml')

    # Get all content from chat messages pane (div w/ class 'tSmQ1'), search for and only keep HTML elements which contain messages
    chat_messages = [
        msg for msg in soup.find("div", "tSmQ1").contents if 'message' in " ".join(msg.get('class'))]
    chat_messages_count = len(chat_messages)
    print(f"{chat_messages_count} messages will be scraped and exported.")

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
            f"Exporting message {messages_count} of {chat_messages_count}", end="\r")

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

        # Check if message was recalled / deleted by the user ('_1qQEf' is a unique class for these, typically a div that contains the 'prohibited' emoji/SVG)
        if message.find('div', '_1qQEf'):
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
        messages.append(message_scraped.copy())

        # Loop to the next chat message
        continue

    # Scrape summary
    if len(messages) == chat_messages_count:
        print(f"Success! {len(messages)} messages have been scraped.")
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
    copyable_scrape['datetime'] = datetime.strptime(
        f"{copyable_attrs[0].split(', ')[1]} {copyable_attrs[0].split(', ')[0]}", "%m/%d/%Y %I:%M %p")

    # Check for quoted/replied to and ignore that text
    for c in copyable_text.contents:
        # Check if the replied message contains media (element's data-testid will contain 'media') and skip it
        if c.find(attrs={'data-testid': True}):
            if 'media' in c.find(attrs={'data-testid': True}).get('data-testid'):
                continue
        # Check if the replied message is text (element's class will contain '_3fs13')
        if c.get('class'):
            if not '_3fs13' in c.get('class'):
                copyable_scrape['message'] = c.text
                break

        # No quoted/replied on the current tag
        continue

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
                if element.name == None:
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


def find_chat_datetime_when_copyable_does_not_exist(message, last_msg_date):
    '''Returns a message's date/time when there's no 'copyable-text' attribute within the message e.g. deleted messages, media w/ no text, etc.'''

    # Get date/time (note: every message renders time in a span w/ class '_2JNr-')
    if message.find('span', '_2JNr-'):
        # Get the hour/minute time from the media message
        message_time = message.find('span', '_2JNr-').text

        # Get the sibling div holding the latest chat date, otherwise if that doesn't exist then grab the last msg date
        try:
            # Check if the chat row is a date (a div element w/ 'focusable' class and no 'data-id' attribute)
            sibling_date = message.find_previous_sibling(
                "div", attrs={'data-id': False}).text

            # Try converting to a date/time object
            media_message_datetime = datetime.strptime(
                f"{sibling_date} {message_time}", "%m/%d/%Y %I:%M %p")

            # Build date/time object
            message_datetime = datetime.strptime(
                f"{media_message_datetime.strftime('%#m/%#d/%Y')} {media_message_datetime.strftime('%I:%M %p')}", "%m/%d/%Y %I:%M %p")

            return message_datetime

        # Otherwise last message's date/time (note this could assign the wrong date if for example the last message was 1+ days ago)
        except:
            message_datetime = datetime.strptime(
                f"{last_msg_date.strftime('%#m/%#d/%Y')} {message_time}", "%m/%d/%Y %I:%M %p")

            return message_datetime

    else:
        return None


def is_media_in_message(message):
    '''Returns True if media is discovered within the message by checking the soup for known media flags. If not, it returns False.'''

    # First check for data-testid attributes containing 'media' (this covers gifs, videos, downloadable content)
    possible_media_spans = message.find_all(attrs={'data-testid': True})
    for span in possible_media_spans:
        # Media types are stored in 'data-testid' attribute
        media_attr = span.get('data-testid')

        if 'media' in media_attr:
            return True
        else:
            continue

    # Then check one of the blanket media classes which covers the above and other things like pdfs, txt files, contact cards, etc.
    if message.get('class'):
        # GIFs, image attachments, txt files, pdf files, contact cards, links w/ previewed image
        if '_2FNAC' in message.get('class'):
            return True

        # Voice messages which are nested in child divs so we need to scan all contents
        for c in message.contents:
            if c.get('class'):
                if '_2Irzd' in c.get('class'):
                    return True

    return False


def find_media_sender_when_copyable_does_not_exist(message):
    '''Returns a sender's name when there's no 'copyable-text' attribute within the message'''

    # Check to see if senders name is stored in a span's aria-label attribute (note: this seems to be where it's stored if the persons name is just text / no emoji)
    spans = message.find_all('span')
    sender = None
    has_emoji = False
    for span in spans:
        if span.get('aria-label'):
            # Last char in aria-label is always colon after the senders name
            if span.get('aria-label') != 'Voice message':
                return span.get('aria-label')[:-1]
        elif span.find('img'):
            # Emoji is in name...TODO: below is copy/pasted from selectable. Refactor these two somehow?
            has_emoji = True
            break
        else:
            continue

    # Manually construct the senders name if it has an emoji by building a string from span.text and img/emoji tags
    if has_emoji:
        # Get all elements from container span that uses a unique class for names that contain emojis
        emoji_name_elements = message.find('span', '_19038 _3cwQ7 _1VzZY')

        # Loop over every child element of the span to construct the sender
        name = ''
        for element in emoji_name_elements.contents:
            # Check what kind of element it is
            if element.name == None:
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

    # There is no sender name in the message - pattern for this seems to be 1) sender name has no emoji, 2) msg has media, 3) msg does not have text, 4) msg is a follow-up / consecutive message (doesn't have tail-in icon in message span/svg)
    else:
        # TODO: Study this pattern more and fix later if possible. Solution for now is to return None and then we take the last message's sender from our data structure.
        return None


def export_txt(selected_export, scraped):
    '''Returns True if the scraped data for a selected export is written to local folder/file without any exceptions thrown'''

    print(f"Exporting your chat to local file...")
    # Check if 'exports' directory exists, if not create it
    if not os.path.isdir('exports'):
        os.mkdir('exports')
        print(
            f"'exports' directory created at location: {os.path.dirname(os.path.abspath(__file__))}")

    # Try exporting to a text file
    try:
        # Format file name as 'WhatsApp chat with [name] - [YYYY-MM-DD HH.MM.SS.AM/PM]'
        now = datetime.now().strftime('%Y-%m-%d %H.%M.%S.%p')
        with open(f"exports/WhatsApp chat with {selected_export} - {now}.txt", "wb") as text_file:
            for date_write, messages_write in scraped.items():
                for message_write in messages_write:
                    line = f"{date_write}, {message_write['time']} - {message_write['sender']}: {message_write['message']}\n"
                    encoded = line.encode()
                    text_file.write(encoded)
        print(
            f"Success! 'WhatsApp chat with {selected_export} - {now}.txt' exported.")
        return True

    except Exception as error:
        print(f"Error during export! Error info: {error}")
        return False


if __name__ == "__main__":
    main()
