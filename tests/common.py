# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""common.py - common utils and such for the gitarootools test suite"""

import os

try:
    # noinspection PyProtectedMember
    from importlib import resources as importlib_resources
except ImportError:
    import importlib_resources  # Python 3.6 compatible


class ResourceCopier:
    """object that copies importlib resources to a destination directory"""

    def __init__(self, srcpkg, destdir):
        """initialize a ResourceCopier

        srcpkg: (importlib.resources.Package) package from which to import resources
        destdir: (path) directory to which to copy resources (created if doesn't exist)
        """
        os.makedirs(destdir, exist_ok=True)
        self.destdir = destdir
        self.srcpkg = srcpkg

    def make_subdir(self, subdir=None, create=True):
        """create subdir of self.destdir and return its path

        if subdir is None, just return self.destdir
        create: if False, don't actual create the subdir after all
        raise ValueError if subdir is an absolute path
        """
        real_destdir = self.destdir
        if subdir is not None:
            if os.path.isabs(subdir):
                raise ValueError(f"subdir can't be an absolute path, was {subdir!r}")
            real_destdir = os.path.join(real_destdir, subdir)
            if create:
                os.makedirs(real_destdir, exist_ok=True)
        return real_destdir

    def copy_resource_to_destdir(self, resource, srcpkg=None, subdir=None):
        """copy resource from srcpkg to self.destdir/subdir

        resource: (importlib.resources.Resource) resource to copy
        srcpkg: (importlib.resources.Package) can specify this here to copy resource
          from a different package than the one specified at init
        destsubdir: if specified, copy resource to this subdirectory of self.destdir
        returns: path to the resource file copied to destdir
        """
        # 1. Choose whether to use argument or instance srcpkg
        if srcpkg is None:
            srcpkg = self.srcpkg

        # 2. Create subdir of destdir
        real_destdir = self.make_subdir(subdir)

        # 3. Copy importlib resource to self.destdir/subdir
        resource_destpath = os.path.join(real_destdir, resource)
        with open(resource_destpath, "wb") as resource_destfile:
            resource_destfile.write(importlib_resources.read_binary(srcpkg, resource))

        return resource_destpath

    def copy_contents_to_destdir(self, srcpkg=None, subdir=None, recursive=False):
        """copy all resources from srcpkg to self.destdir/subdir

        srcpkg: an  importlib.resources.Package. can specify this to import contents
          from a different package than the one specified at init
        subdir: if specified, copy resource to this subdirectory of the tempdir
        recursive: recurse into submodules, copying their resources to a respective
          subdir in self.destdir
        returns: path of destdir/subdir
        """

        # 1. Choose whether to use argument or instance srcpkg
        if srcpkg is None:
            srcpkg = self.srcpkg

        # 2. Create subdir of self.destdir
        real_destdir = self.make_subdir(subdir, create=False)

        # 3. Copy importlib resources to destdir/subdir
        created_real_destdir = False
        for resource in importlib_resources.contents(srcpkg):
            if importlib_resources.is_resource(srcpkg, resource):

                # only create a new subdir if we have something to copy into it
                # (or if srcpkg only has __init__.py, we make a matching empty subdir)
                if not created_real_destdir:
                    os.makedirs(real_destdir, exist_ok=True)
                    created_real_destdir = True

                if resource == "__init__.py":
                    continue  # don't copy to destdir

                resource_destpath = os.path.join(real_destdir, resource)
                with open(resource_destpath, "wb") as resource_destfile:
                    resource_destfile.write(
                        importlib_resources.read_binary(srcpkg, resource)
                    )
            elif recursive:  # is a dir and we're descending into subpackages
                child_srcpkg = f"{srcpkg}.{resource}"
                self.copy_contents_to_destdir(
                    srcpkg=child_srcpkg, subdir=resource, recursive=True
                )

        return real_destdir


def make_resource2destdir(srcpkg, destdir):
    """method copy_resource_to_destdir of a new ResourceCopier instance"""
    rc = ResourceCopier(srcpkg, destdir)
    return rc.copy_resource_to_destdir


def make_contents2destdir(srcpkg, destdir):
    """method copy_contents_to_destdir of a new ResourceCopier instance"""
    rc = ResourceCopier(srcpkg, destdir)
    return rc.copy_contents_to_destdir


def make_both2destdir(srcpkg, destdir):
    """methods (copy_resource_to_destdir, copy_contents_to_destdir)

    returns tuple of those methods of a new ResourceCopier instance
    """
    rc = ResourceCopier(srcpkg, destdir)
    return rc.copy_resource_to_destdir, rc.copy_contents_to_destdir


def read_binary(filepath):
    """return bytes read from filepath"""
    with open(filepath, "rb") as file:
        return file.read()


def read_text(filepath, encoding="utf-8"):
    """return text read from filepath"""
    with open(filepath, "rt", encoding=encoding) as file:
        return file.read()
