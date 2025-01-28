Getting started with developing inkex
=====================================

.. highlight:: bash

.. warning::

    This document is tailored for contributors to the inkex package and core extensions.
    
    Extension authors should look here: :ref:`authors-tutorial`

Repository setup
----------------

It is possible to synchronize a fork with the extensions repository - whenever a branch in the 
mirrored repository is updated, your fork will be updated too (usually with a delay of up to one
hour). See `Settings -> Repository -> Mirroring Repositories` and add a "Pull" mirror.

.. warning:: 

    If you use this method, **do not** add commits to branches that should be synced 
    (such as `master`).
    Depending on the exact settings of the mirroring option, you will either lose your changes,
    lose the synchronisation or run into a messed up branch history.

Always check out submodules as well::

    git submodule update && git submodule init

Python setup
------------

On every operating system, you need a working Python environment. Currently, inkex is tested 
against Python 3.8-3.11.

inkex manages its dependencies using `poetry <https://python-poetry.org/docs/>`_. It can be installed using::

    pip install poetry

Install the dependencies and the pre-commit hook::

    poetry install
    pre-commit install

Testing changes in Inkscape
---------------------------

Most of the time, calling the python file of the extension directly and through unit tests is
sufficient. In some cases, the interaction between Inkscape and the extension should be tested, 
though.

Assuming you have managed to make Inkscape look in the correct folder for the extensions (see hints
for different operating systems below), the python 
file of an extension is reloaded every time the extension is run. For changes to the inx file or 
the command line parameters of the extension (as defined in the 
:func:`~inkex.base.InkscapeExtension.add_arguments` method) you need to restart Inkscape.

Developing extensions on Windows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


.. highlight:: batch

To test extensions with a given Inkscape version, download the 7z archive of that version, 
unarchive it and delete the ``inkscape\share\extensions`` folder. Next, create a symlink in that 
folder from an administrative command prompt::

    cd [directory of the unzipped Inkscape folder]
    mklink /D share\extensions C:\path\to\your\fork

If you start ``bin\inkscape`` now, the extensions are loaded from your fork.

Developing extensions on Linux
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. highlight:: bash

A very similar path to Windows can be used when working off an appimage build.

Extract the appimage into a new folder called ``squashfs-root``::

    /path/to/appimage --appimage-extract
    squashfs-root/AppRun --system-data-directory

This prints the location of the extensions folder. Create a symlink to your repo there and run::

    squashfs-root/AppRun

Trying / Changing a merge request locally
-----------------------------------------

Add this to ``git config -e`` (only once)::

    [remote "upstream"]
        url = git@gitlab.com:inkscape/extensions.git
        fetch = +refs/merge-requests/*/head:refs/remotes/origin/merge-requests/*
    [alias]
        mr = !sh -c 'git fetch $1 merge-requests/$2/head:mr-$1-$2 && git checkout mr-$1-$2' -

Check out the merge request !123::

    git mr upstream 123

Push changes to the source branch ``source-branch-name`` of fork in the namespace (typically the 
author's username) ``xyz``::

    git push git@gitlab.com:xyz/extensions.git mr-origin-123:source-branch-name 


Adding/Updating dependencies
----------------------------

.. highlight:: bash

The *direct* dependencies of inkex are declared in the ``pyproject.toml`` file.

There is also a lockfile named ``poetry.lock`` which has *all* the dependencies 
(direct, dependencies of direct, dependencies of dependencies of direct and so on till the leaf dependencies) 
pinned to specific versions (versions which were compatible the last time lockfile was updated).

To update all the dependencies in the lockfile to latest compatible versions, enter::

    poetry lock

To add/update a particular dependency, add it to ``pyproject.toml`` manually. The dependency should be declared in the 
``[tool.poetry.dependencies]`` TOML table, while a dependency required only during development of inkex should be declared in 
``[tool.poetry.dev-dependencies]``.

Then update the lockfile using::

    poetry lock

Alternatively, you can add a dependency and update the lockfile in a single command::

    poetry add "lxml@^4.5.0" --lock

Both the ``pyproject.toml`` and ``poetry.lock`` are to be committed to the repository.

.. note::

    You don't need to install the dependencies to add/update them. So, the commands above don't install anything. 
    However, if you are using poetry to manage the environment, and want to also install the dependencies, 
    remove the ``--lock`` options from the commands and use ``poetry update`` instead of ``poetry lock``.

.. note::

    Dependencies should be updated according to the `policy <https://wiki.inkscape.org/wiki/Tracking_Dependencies#Distros>`_ defined in Inkscape wiki .

Creating a tag / publishing a version
-------------------------------------

1. Update the ``pyproject.toml`` file to the correct version number and push it to the target branch.
2. Create the tag (either on GitLab or offline + pushing)
3. Run ``poetry build``. This will create the wheel and the archive in the ``dist/`` folder.
4. Setup the ``~/.pypirc`` file according to `the instructions <https://packaging.python.org/en/latest/specifications/pypirc/>`_
5. Upload it: ``twine upload -r pypi dist/*``
6. Delete the contents of the dist folder: ``rm -r dist``