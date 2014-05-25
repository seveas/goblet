#!/usr/bin/python

from distutils.core import setup

setup(name = "goblet",
      version = "0.3.5",
      author = "Dennis Kaarsemaker",
      author_email = "dennis@kaarsemaker.net",
      url = "http://seveas.github.com/goblet",
      description = "Git web interface using libgit2 and flask",
      packages = ["goblet"],
      package_data = {'goblet': ['themes/*/*/*.*', 'themes/*/*/*/*']},
      classifiers = [
          'Development Status :: 3 - Alpha',
          'Environment :: Web Environment',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
          'Topic :: Software Development',
          'Topic :: Software Development :: Version Control',
      ]
)
