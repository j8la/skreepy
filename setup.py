"""
Skreepy
--
Copyright (C) 2017 - Julien Blanc

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
from setuptools import setup

setup(
    name='skreepy',
    version='1.1.0',
    description='REST API Scheduler',
    long_description='REST API Scheduler',
    platforms=['any'],
    author='Julien Blanc',
    author_email='jbla@tuta.io',
    url='https://github.com/j8la/skreepy',
    download_url='https://github.com/j8la/skreepy',
    license='GNU General Public License v3 or later (GPLv3+)',
    packages=['skreepy'],
    entry_points={
        'console_scripts' : [
            'skreepy = skreepy.skree:main',
        ]
    },
    install_requires=[
        'requests',
    ]
)
