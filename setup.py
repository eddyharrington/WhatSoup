from setuptools import setup, find_packages

setup(
    name='WhatSoup',
    version='1.0.0',
    author='Eddy Harrington',
    author_email='eddy@example.com',
    description='A web scraper that exports your entire WhatsApp chat history.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/eddyharrington/WhatSoup',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'autopep8==1.5.4',
        'beautifulsoup4==4.9.3',
        'certifi==2020.12.5',
        'chardet==4.0.0',
        'lxml==4.6.2',
        'prettytable==2.0.0',
        'pycodestyle==2.6.0',
        'python-dateutil==2.8.1',
        'python-dotenv==0.15.0',
        'pytz==2020.5',
        'selenium==3.141.0',
        'six==1.15.0',
        'soupsieve==2.1',
        'toml==0.10.2',
        'urllib3==1.26.2',
        'wcwidth==0.2.5'
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)