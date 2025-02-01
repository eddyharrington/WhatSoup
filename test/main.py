"""
This script is used to test the package. It will connect to the Whatsapp Web and get the messages from the first chat
"""
import logging
from whatsoup.whatsoup import WhatsappClient
from whatsoup.utils import export_csv

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    client = WhatsappClient(
        headless=False
    )
    chat_names = client.get_chat_names()
    print("Chat names:", chat_names)
    chat_name = chat_names[0]
    chat = client.get_chat(query=chat_name, messages_number_target=100)
    print("Chat messages:", chat.head())
    filepath = export_csv(chat, chat_name)

