from setuptools import setup, find_packages
from pathlib import Path

# Read the requirements from the requirements.txt file
def parse_requirements(filename):
    with open(filename, 'r') as file:
        return file.read().splitlines()

setup(
    name='whatsoup',
    version='1.0.0',
    author='Gabriel Rudloff',
    author_email='gabriel.rudloff@gmail.com',
    description='A web scraper that exports your entire WhatsApp chat history. Forked from the original project by Eddy Harrington.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/grudloff/WhatSoup',
    packages=find_packages(),
    install_requires=parse_requirements(Path(__file__).parent / 'requirements.txt'),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.9',
)
