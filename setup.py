#!/usr/bin/env python3

from os.path import dirname, abspath
from setuptools import setup


source_directory = dirname(abspath(__file__))

with open('requirements.txt', 'r') as f:
    requirement_list = f.read().split('\n')

setup(
    name="factoriomcd",
    description="Daemon that acts as a bridge between Factorio server and mission control.",
    author="Maikel Wever",
    author_email="maikelwever@gmail.com",
    packages=['factoriomcd'],
    install_requires=requirement_list,
    version="0.0.1",
    entry_points=dict(
        console_scripts=[
            "fmcd = factoriomcd.main:main",
        ]
    )
)
