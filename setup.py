"""Setup script for the Whatsoup package."""
from pathlib import Path
from setuptools import setup, find_packages

def parse_requirements(filename):
    """Read a requirements file and return a list of requirements."""
    with open(filename, 'r', encoding='utf-8') as file:
        return file.read().splitlines()

def read_readme():
    """Read the README file and return its contents."""
    with open('README.md', 'r', encoding='utf-8') as file:
        return file.read()

setup(
    name='whatsoup',
    version='1.0.0',
    author='Gabriel Rudloff',
    author_email='gabriel.rudloff@gmail.com',
    description="""A web scraper that exports your entire WhatsApp chat history. Forked from the
                original project by Eddy Harrington.""",
    long_description=read_readme(),
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
