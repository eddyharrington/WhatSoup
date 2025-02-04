"""
This script is used to test the package. It will connect to the Whatsapp Web and get the messages
from the first chat
"""
import logging
import pandas as pd
from whatsoup.whatsoup import WhatsappClient
from whatsoup.utils import export_csv

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    client = WhatsappClient(
        headless=False
    )
    user_name: str = client.get_user_name()
    print("User name:", user_name)
    chat_names: list[str] = client.get_chat_names()
    print("Chat names:", chat_names)
    chat_name: str = chat_names[0]
    chat: pd.DataFrame = client.get_chat(query=chat_name, messages_number_target=100)
    print("Chat messages:", chat.head())
    filepath: str = export_csv(chat, chat_name)
