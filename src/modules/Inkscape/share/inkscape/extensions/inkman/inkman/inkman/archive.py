#
# Copyright (c) Gary Wilson Jr. <gary@thegarywilson.com> and contributors.
#
# MIT License, see https://github.com/gdub/python-archive/blob/master/LICENSE.txt
#
"""
Compatability for zip and tar files, taken from upstream and stripped down
to provide list and read interface, removed PY2 support.
"""

import os
import tarfile
import zipfile


class ArchiveException(Exception):
    """Base exception class for all archive errors."""


class UnrecognizedArchiveFormat(ArchiveException):
    """Error raised when passed file is not a recognized archive format."""


class Archive(object):
    """
    The external API class that encapsulates an archive implementation.
    """

    def __init__(self, filename, ext=""):
        """
        Arguments:
        * 'file' can be a string path to a file or a file-like object.
        * Optional 'ext' argument can be given to override the file-type
          guess that is normally performed using the file extension of the
          given 'file'.  Should start with a dot, e.g. '.tar.gz'.
        """
        cls = self._archive_cls(filename, ext=ext)
        self._archive = cls(filename)

    def __enter__(self):
        return self._archive

    def __exit__(self, exc, value, traceback):
        pass

    @staticmethod
    def _archive_cls(filename, ext=""):
        """
        Return the proper Archive implementation class, based on the file type.
        """
        cls = None
        if not isinstance(filename, str):
            try:
                filename = filename.name
            except AttributeError:
                raise UnrecognizedArchiveFormat(
                    "File object not a recognized archive format."
                )
        lookup_filename = filename + ext
        base, tail_ext = os.path.splitext(lookup_filename.lower())
        cls = extension_map.get(tail_ext)
        if not cls:
            base, ext = os.path.splitext(base)
            cls = extension_map.get(ext)
        if not cls:
            raise UnrecognizedArchiveFormat(
                "Path not a recognized archive format: %s" % filename
            )
        return cls


class BaseArchive(object):
    def __del__(self):
        if hasattr(self, "_archive"):
            self._archive.close()

    def list(self):
        raise NotImplementedError()

    def filenames(self):
        raise NotImplementedError()


class TarArchive(BaseArchive):
    def __init__(self, filename):
        # tarfile's open uses different parameters for file path vs. file obj.
        if isinstance(filename, str):
            self._archive = tarfile.open(name=filename)
        else:
            self._archive = tarfile.open(fileobj=filename)

    def filenames(self):
        return self._archive.getnames()

    def read(self, name):
        return self._archive.extractfile(name).read()


class ZipArchive(BaseArchive):
    def __init__(self, file):
        # ZipFile's 'file' parameter can be path (string) or file-like obj.
        self._archive = zipfile.ZipFile(file)

    def filenames(self):
        return self._archive.namelist()

    def read(self, name):
        return self._archive.read(name)


extension_map = {
    ".egg": ZipArchive,
    ".zip": ZipArchive,
    ".tar": TarArchive,
    ".tar.bz2": TarArchive,
    ".tar.gz": TarArchive,
    ".tgz": TarArchive,
    ".tz2": TarArchive,
}
