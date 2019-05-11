#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import os

from setuptools import find_packages, setup


def load_version():
    """
    Load the cozmonaut module version into the __version__ global variable.
    """

    global __version__

    # Directory containing this script
    dir = os.path.abspath(os.path.dirname(__file__))

    # Get path to version file
    path = os.path.join(dir, 'cozmonaut', '__version__.py')

    # Open version file
    with open(path) as file:
        # Execute version file and save its globals
        g = {}
        exec(file.read(), g)

        # Save version number
        __version__ = g['__version__']


# Load version number
load_version()

setup(
    name='cozmonaut',
    version=__version__,
    author='The Cozmonauts',
    url='https://github.com/cozmonauts/app',
    packages=find_packages(exclude=['venv']),
    python_requires='>=3.6.0',
    install_requires=[
        'cmd2',
        'cozmo',
        'docopt',
        'dlib',
        'mysql-connector-python',
        'numpy',
        'opencv-python',
        'pillow',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ]
)
