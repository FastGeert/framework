# Copyright (C) 2016 iNuron NV
#
# This file is part of Open vStorage Open Source Edition (OSE),
# as available from
#
#      http://www.openvstorage.org and
#      http://www.openvstorage.com.
#
# This file is free software; you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License v3 (GNU AGPLv3)
# as published by the Free Software Foundation, in version 3 as it comes
# in the LICENSE.txt file of the Open vStorage OSE distribution.
#
# Open vStorage is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY of any kind.

"""
Disk module
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ovs.dal.lists.disklist import DiskList
from ovs.dal.hybrids.disk import Disk
from ovs.dal.hybrids.storagerouter import StorageRouter
from backend.decorators import required_roles, load, return_list, return_object, log


class DiskViewSet(viewsets.ViewSet):
    """
    Information about disks
    """
    permission_classes = (IsAuthenticated,)
    prefix = r'disks'
    base_name = 'disks'

    @log()
    @required_roles(['read'])
    @return_list(Disk)
    @load()
    def list(self, storagerouterguid=None):
        """
        Overview of all disks
        """
        if storagerouterguid is not None:
            storagerouter = StorageRouter(storagerouterguid)
            return storagerouter.disks
        return DiskList.get_disks()

    @log()
    @required_roles(['read'])
    @return_object(Disk)
    @load(Disk)
    def retrieve(self, disk):
        """
        Load information about a given disk
        """
        return disk
