#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

from setuptools import find_packages, setup

setup(
    name='cozmonaut',
    version='0.1.0',
    description='Python code for the Cozmonaut project',
    python_requires='>=3.6.0',
    url='https://github.com/cozmonauts/app',
    packages=find_packages(exclude=['python', 'src']),
    install_requires=[
        'cozmo',
        'dlib',
        'mysql-connector',
        'numpy',
        'opencv-python',
        'pillow',
    ],
    include_package_data=True,
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
)
