# WhatSoup 🍲

The objective of this project is to scrape WhatsApp chat messages from the WhatsApp Web interface.

This is a fork of [WhatSoup](https://github.com/eddyharrington/WhatSoup.git) by Eddy Harrington. The main goal in this fork is to add support for the newest version of WhatsApp Web as well as the newer versions of Selenium and BeautifulSoup.

One of the main issues with such a tool is that WhatsApp Web is constantly changing, and the original tool was last updated in 2021. This fork aims first to simplify the logic at the spense of some features, and to add support for the current version of WhatsApp Web as of January 2025.

I am most likely not going to maintain this project, but I hope that it can be useful to someone. Also feel free to make a pull request if you want to add a feature or fix a bug, this is an open source project after all.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Setup](#setup)
3. [Usage](#usage)

## Prerequisites

1. Currently this has been tested on linux, and therefore instructions are for this environment. If you are using Windows or Mac, you will need to adapt the instructions accordingly.
1. You will need to have a whatsapp account and a phone with whatsapp installed. (duh)
1. You will need to have python version 3.9 or greater installed on your computer.

## Setup

1. Make sure your WhatsApp chat settings are set to English language. This needs to be done on your phone (instructions [here](https://faq.whatsapp.com/general/account-and-profile/how-to-change-whatsapps-language/)). You can change it back afterwards, but for now the script relies on certain HTML elements/attributes that contain English characters/words.

1. Create a virtual environment and activate it (optional but recommended):

   ```
   python3 -m venv env
   source env/bin/activate
   ```

1. Install the package and its requirements

   ```
   pip install git+github.com/grudloff/WhatSoup.git
   ```

1. Install Chrome browser if you haven't already
   ```
   sudo apt-get install google-chrome-stable
   ```

1. Download [ChromeDriver](https://googlechromelabs.github.io/chrome-for-testing/#stable) and extract it to a local folder (such as the `env` folder)
   ```
   # Linux
   wget https://storage.googleapis.com/chrome-for-testing-public/132.0.6834.159/linux64/chromedriver-linux64.zip
   unzip chromedriver-linux64.zip -d env
   ```
1. Get your Chrome browser `Profile Path` by opening Chrome and entering `chrome://version` into the URL bar. In linux by default this corresponds to `~/.config/google-chrome/Default`.

1. Create an `.env` file with an entry for `DRIVER_PATH` and `CHROME_PROFILE`. Following the previous steps these should correspond to the following:
   ```
   # .env
   DRIVER_PATH = 'env/chromedriver'
   CHROME_PROFILE = '/home/<your-username>/.config/google-chrome/Default'
   ```

# Usage

   ```python
   from whatsoup.whatsoup import whatsappClient
   from whatsoup.utils import export_csv
   import pandas as pd
   import logging

   # Set up logging for debugging purposes
   logging.basicConfig(level=logging.INFO)

   # Initialize the client
   client = whatsappClient(
      # The first time you run this, you will need to scan the QR code with your phone
      # and therefore should not be run in headless mode
      headless=False
   )
   query: str = 'chat_name'
   chat: pd.DataFrame = client.get_chat(query=query,
                          messages_number_target=100,
                          )
   export_csv(chat, query)
   ```
