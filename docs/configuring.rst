.. Goblet - Web based git repository browser
   Copyright (C) 2012-2014 Dennis Kaarsemaker
   See the LICENSE file for licensing details
Configuring goblet
==================
Goblet can be run without any configuration for a quick test, using the
built-in webserver. This is not suitable for any production environment, but is
very helpful to see if all parts work. Change directory to a directory that
contains one or more git repositories and start goblet::

  cd /home/dennis/code
  GOBLET_DEBUG=1 python -mgoblet

This places werkzeug (the underlying wsgi library) in debug mode. Never do this
in production, as it allows people to execute arbitrary code on your server.

Goblet configuration
--------------------
Goblet itself takes only a few configuration variables to alter its behaviour.
Most important are the root directory for all repositories and the logging
settings. The configuration is actually python code, so you can do interesting
tricks with it. The goblet tarball ships an example configuration with all
parameters and documentation for all of them, please refer to it when creating
your own configuration.

uwsgi configuration
-------------------
The prefered way to serve flask applications like goblet, is to use uwsgi and a
webserver that speaks the wsgi protocol. A document example config is shipped
with goblet. You will need to modify it to your reality (filesystem paths) and
then you can run it. Do *not* run uwsgi as root, but create a special user
account to run uwsgi or use the same user as for your webserer (www-data on
Debian/Ubuntu) and configure uwsgi to switch to that user.

Once configured, it can be started with::

  sudo uwsgi --ini /path/to/uwsgi.ini

And killed again with::

  sudo uwsgi --stop /run/uwsgi.pid

Webserver configuration
-----------------------
I use nginx to serve goblet, and the example config shipped with goblet is the
same as the one I use, except for some filesystem paths and the hostname. The
configuration integrates goblet, git's http-backend for serving the actual
repositories, and lets you serve files in your repository root as well. If you
make goblet work using another httpd, please share your configuration.

fcgiwrap
--------
To make nginx execute the git smart http backend, you will also need to install
and run fcgiwrap. Make sure you edit its initscript and add a line that says::

    export HOME=/nonexistent

If you do not do this, git will try to read :file:`/root/.gitconfig`, which it
cannot do.

Repository configuration
------------------------

Per-repository configuration is not needed either, but like gitweb, goblet can
read some information from the git configuration.

* A description for the repository is read from the :file:`.git/description`
  file.
* The owner of the repository is determined from filesystem permissions, but
  can be overridden by setting the goblet.owner variable in a repository.
* You can tell your visitors where to clone your repositories from. The default
  is to determine it from the :data:`CLONE_URLS_BASE` variable in goblet.conf,
  but can be overridden per repository by setting goblet.clone_url_ssh (and
  _git, and _http)
