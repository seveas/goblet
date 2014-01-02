.. Goblet - Web based git repository browser
   Copyright (C) 2012-2014 Dennis Kaarsemaker
   See the LICENSE file for licensing details
Installing goblet
=================
Goblet is easiest to install on Ubuntu 12.10, as I provide packages for it
myself. Most dependencies are also easy to install, but goblet uses
libgit2/pygit2, and a patched git to provide its features. These projects are
all still quite unstable. The packages I provide work, but if you want to
compile them yourself, please follow the instructions below.

To use the packages I provide, add my personal package archives to your ubuntu
system with the following commands::

  sudo add-apt-repository ppa:dennis/devtools
  sudo add-apt-repository ppa:dennis/python
  sudo apt-get update

Now you can install goblet and all its dependencies with a single apt command::

  sudo apt-get install goblet

Non-python dependencies
-----------------------
The only non-python dependencies are xz, git and groff. Goblet does require a
patched git though. If you do not use the packages I provide, please build
your own git with Jeff King's blame-tree patches applied. You can find
these, rebased against the latest git version, as the last four patches on `my
git clone`_

Python dependencies
-------------------
Goblet requires Python 2.6 or newer, python 3 is not yet supported. It has
only a few python dependencies: the flask/werkzeug/jinja2/pygments
combination as web framework, markdown and docutils for rendering markdown and
rst, and whelk for executing git commands. These can all be installed with
pip, or from my repositories or the Ubuntu repositories.

pygit2
------
As the libgit2 and pygit2 projects do not yet provide stable releases, they
need to be built from a git checkout if you do not use the packages I provide.
As no API compatibility is guaranteed, it is best to use the exact same
versions as me. The following sequence of commands will download, build and
install libgit2 and pygit2 into :file:`/usr/local`::

  sudo apt-get install cmake python-all-devel

  git clone git://github.com/libgit2/libgit2.git
  pushd libgit2
  git checkout bb19532
  mkdir build && cd build
  cmake --build ..
  sudo cmake --build . --target install
  popd

  git clone git://github.com/libgit2/pygit2.git
  pushd pygit2
  git checkout 29ce23c
  python setup.py build
  sudo python setup.py install
  popd

  sudo ldconfig

Goblet itself
-------------
When all dependencies have been installed, goblet can be installed with pip, or
you can live on the bleeding edge and clone the git repository from github::

  git clone git://github.com/seveas/goblet.git
  cd goblet
  git submodule init
  git submodule update

With git now installed, please proceed to :doc:`configuring` and learn how to
configure goblet.

.. _`my git clone`: https://github.com/seveas/git/commits/dk/private
