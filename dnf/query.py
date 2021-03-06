# query.py
# Implements Query.
#
# Copyright (C) 2012-2013  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import functools
import hawkey
import itertools
import types
import dnf.exceptions
import dnf.selector
from dnf.util import is_glob_pattern

from dnf.yum.i18n import _
from .pycomp import basestring

def is_nevra(pattern):
    try:
        hawkey.split_nevra(pattern)
    except hawkey.ValueException:
        return False
    return True

class Query(hawkey.Query):
    # :api
    # :api also includes hawkey.Query.filter

    def available(self):
        # :api
        return self.filter(reponame__neq=hawkey.SYSTEM_REPO_NAME)

    def downgrades(self):
        # :api
        return self.filter(downgrades=True)

    def filter_autoglob(self, **kwargs):
        nargs = {}
        for (key, value) in kwargs.items():
            if dnf.query.is_glob_pattern(value):
                nargs[key + "__glob"] = value
            else:
                nargs[key] = value
        return self.filter(**nargs)

    def installed(self):
        # :api
        return self.filter(reponame=hawkey.SYSTEM_REPO_NAME)

    def latest(self):
        # :api
        return self.filter(latest_per_arch=True)

    def upgrades(self):
        # :api
        return self.filter(upgrades=True)

    def name_dict(self):
        d = {}
        for pkg in self:
            d.setdefault(pkg.name, []).append(pkg)
        return d

    def na_dict(self):
        return per_arch_dict(self.run())

    def pkgtup_dict(self):
        return per_pkgtup_dict(self.run())

    def nevra(self, *args):
        args_len = len(args)
        if args_len == 3:
            return self.filter(name=args[0], evr=args[1], arch=args[2])
        if args_len == 1:
            nevra = hawkey.split_nevra(args[0])
        elif args_len == 5:
            nevra = args
        else:
            raise TypeError("nevra() takes 1, 3 or 5 str params")
        return self.filter(
            name=nevra.name, epoch=nevra.epoch, version=nevra.version,
            release=nevra.release, arch=nevra.arch)

def _construct_result(sack, patterns, ignore_case,
                      include_repo=None, exclude_repo=None,
                      downgrades_only=False,
                      updates_only=False,
                      latest_only=False,
                      get_query=False):
    """ Generic query builder.

        patterns can be:
        :: a string pattern we will use to match against package names
        :: a list of strings representing patterns that are ORed together
        :: None in which case we query over all names.

        If 'get_query' is False the built query is evaluated and matching
        packages returned. Otherwise the query itself is returned (for instance
        to be further specified and then evaluated).
    """
    if isinstance(patterns, basestring):
        patterns = [patterns]
    elif patterns is None:
        patterns = []
    glob = len(list(filter(is_glob_pattern, patterns))) > 0

    flags = []
    q = sack.query()
    if ignore_case:
        flags.append(hawkey.ICASE)
    if len(patterns) == 0:
        pass
    elif glob:
        q.filterm(*flags, name__glob=patterns)
    else:
        q.filterm(*flags, name=patterns)
    if include_repo:
        q.filterm(reponame__eq=include_repo)
    if exclude_repo:
        q.filterm(reponame__neq=exclude_repo)
    q.filterm(downgrades=downgrades_only)
    q.filterm(upgrades=updates_only)
    q.filterm(latest__eq=latest_only)
    if get_query:
        return q
    return q.run()

def by_provides(sack, patterns, ignore_case=False, get_query=False):
    if isinstance(patterns, basestring):
        patterns = [patterns]
    try:
        reldeps = list(map(functools.partial(hawkey.Reldep, sack), patterns))
    except hawkey.ValueException:
        return sack.query().filter(empty=True)
    q = sack.query()
    flags = []
    if ignore_case:
        flags.append(hawkey.ICASE)
    q.filterm(*flags, provides=reldeps)
    if get_query:
        return q
    return q.run()

def latest_per_arch(sack, patterns, ignore_case=False, include_repo=None,
                    exclude_repo=None):
    matching = _construct_result(sack, patterns, ignore_case,
                                 include_repo, exclude_repo,
                                 latest_only=True)
    latest = {} # (name, arch) -> pkg mapping
    for pkg in matching:
        key = (pkg.name, pkg.arch)
        latest[key] = pkg
    return latest

def per_arch_dict(pkg_list):
    d = {}
    for pkg in pkg_list:
        key = (pkg.name, pkg.arch)
        d.setdefault(key, []).append(pkg)
    return d

def per_pkgtup_dict(pkg_list):
    d = {}
    for pkg in pkg_list:
        d.setdefault(pkg.pkgtup, []).append(pkg)
    return d

def per_nevra_dict(pkg_list):
    return {str(pkg):pkg for pkg in pkg_list}
