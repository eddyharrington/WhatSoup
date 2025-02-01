from datetime import datetime
from typing import Optional, List, Dict, Any
import os
import pandas as pd
import logging


def parse_datetime(text: str, time_only: Optional[bool] = False) -> datetime:
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
    text = text.upper().replace("A.M.", "AM").replace("P.M.", "PM").replace(",", "")
    formats = ['%I:%M %p %m/%d/%Y', '%I:%M %p %Y-%m-%d'] if not time_only else ['%I:%M %p']
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"{text} does not match a valid datetime format.")

def export_csv(query: str, chat: pd.DataFrame) -> None:
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
    chat.to_csv(file_path, index=False)
    logging.info(f"Success! Your chat has been exported to {file_path}.")
