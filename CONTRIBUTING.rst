
============
Contributing
============

If you wish to contribute to this project, please fork it `on github`_ and
send a pull request.  

Tests
=====

After making any changes in your fork, please ensure that all of the tests
complete and that your new version is able to be uploaded to pypi.  Please do
this before sending a pull request.

The core tests are run by `tox`_, which is confiured to expect all of the
supported `python` versions to be present.  The easiest way to make sure
they're available is by installing and using `pyenv`_.  

.. _tox: https://tox.readthedocs.io/en/latest/
.. _pyenv: https://github.com/pyenv/pyenv

Once you have `pyenv` set up, make sure you have each of the supported
versions of python specified by the `envlist` in `tox.ini`.  This will likely
look something like::

    pyenv install 2.7.16
    pyenv install 3.4.10
    pyenv install 3.5.7
    pyenv install 3.6.9
    pyenv install 3.7.4
    pyenv install 3.8.0
    pyenv global 3.8.0 3.7.4 3.6.9 3.5.7 3.4.10 2.7.16 system

Install the development dependencies::

    pip install -r requirements_dev.txt

After that, you can run the unit tests::

    tox

To limit tests to a particular python environment::

    tox -e py38

Or to run only the linting tests::

    tox -e flake8
    tox -e pydocstyle
    tox -e pylint

Finally, make sure that your changes build properly and can be uploaded to
PyPi::

    python setup.py sdist bdist_wheel
    twine check dist/*

Documentation
=============

If your changes affect any documented behaviour of **check_mount**, please
make sure you update the documentation as well, before sending a pull request.

Currently, the main documentation exists in the `README.rst` file at the top
of the repository.  This file is used by both PyPi and Sphinx to produce the
documentation that appears on PyPi and ReadTheDocs.  Changes must be
compatible with both dialects of reStructuredText.

The PyPi documentation is tested in the dist files with the above `twine`
command.  To check the Sphinx documentation you must test a build in the docs
directory.

First, install the required dependencies::

    pip install -r requirements_doc.txt

Then, build the documentation::

    cd docs
    make html


