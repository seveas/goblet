.. Goblet - Web based git repository browser
   Copyright (C) 2012-2014 Dennis Kaarsemaker
   See the LICENSE file for licensing details
Serving git repositories with goblet
====================================

Goblet is a fast, easy to customize web frontend for `git`_ repositories. It
was created because existing alternatives are either not very easy to
customize (gitweb), require C programming to do so (cgit), or are tied into
other products, such as bugtrackers (redmin, github).

Goblet is currently in alpha status, so not all goals have been met yet.
Contributions are welcome, the most useful contribution is using it and
reporting all issues you have.

If you want to see goblet in action, you can find a running instance on
`kaarsemaker.net`_. If you like what you see, proceed to :doc:`install` and
enjoy!

Should you hit a problem installing or using goblet, please report it on
`github`_. Reports about uncaught python exceptions should include full
backtraces. If the repository triggering the bug/issue is public, please
include a link to the repository and the link to the bug so I can reproduce it.

Features
--------
The following features have been implemented already.

* Basic repository browsing, files and commits
* Integration with git-http-backend for serving repositories
* Syntax highlighting of source code
* Snapshot downloads for all commits and tags
* Blame output like gitweb
* Directory lists like github, including last change per file

Features that are planned, but not implemented include:

* Caching of generated html (snapshots and blame-tree output are cached)
* Extensibility, including better integration of documentation
* Theming

Goblet is a repository *browser*. Any patch or extension that enhances browsing
functionality is welcome, but things like a bugtracker or repository management
is not what goblet will grow. For both of these, good existing alternatives
exist. Patches that improve the cooperation between goblet and e.g. gitolite
would be welcome, but reimplementing gitolite in goblet would be the wrong
thing to do.

Table of contents
-----------------
.. toctree::
   :maxdepth: 2

   install
   configuring

.. _`git`: http://git-scm.com
.. _`github`: https://github.com/seveas/goblet/issues
.. _`kaarsemaker.net`: http://git.kaarsemaker.net
