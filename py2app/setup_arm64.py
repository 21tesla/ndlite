
import re
import os
import sys
from setuptools import setup

CONDA_ENV_LIB = os.path.join(sys.prefix, 'lib')

# 1. Dynamically extract the version from updater.py
with open('../src/ndlite/core/updater.py', 'r') as f:
    version_string = re.search(r'^VERSION\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE).group(1)

APP = ['../src/ndlite/main.py']
DATA_FILES = [] 

# 2. Add the plist dictionary to explicitly set the Mac App bundle versions
OPTIONS = {
    'iconfile': '../icons/app_icon.icns',  
    'argv_emulation': True,                 
    'packages': ['requests'],
    'includes': ['ssl'],
    'frameworks': [f'{CONDA_ENV_LIB}/libffi.8.dylib',
                '/opt/homebrew/opt/openssl@3/lib/libssl.3.dylib',
                '/opt/homebrew/opt/openssl@3/lib/libcrypto.3.dylib'],
    'plist': {
        'CFBundleName': 'ndlite',
        'CFBundleShortVersionString': version_string,  
        'CFBundleVersion': version_string,  
    }
}

setup(
    name='ndlite',
    app=APP,
    version=version_string,  
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)


    
