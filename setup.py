# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name = 'pykwb',
    version = '0.1.2',
    packages = ['pykwb'],
    install_requires = ['pyserial>=3.0.1'],
    description = 'KWB library, for inclusion into HomeAssistant',
    author = 'Markus Peter',
    author_email = 'mpeter@emdev.de',
    url = 'https://github.com/bimbar/pykwb.git',
    license ="MIT",
    include_package_data=True
)
