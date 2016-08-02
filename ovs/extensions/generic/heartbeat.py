# Copyright 2014 iNuron NV
#
# Licensed under the Open vStorage Modified Apache License (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.openvstorage.org/license
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import time
from subprocess import check_output, CalledProcessError
from ovs.dal.lists.storagerouterlist import StorageRouterList
from ovs.extensions.generic.system import System
from ovs.extensions.generic.configuration import Configuration
from ovs.extensions.os.os import OSManager

from ovs.log.logHandler import LogHandler
logger = LogHandler.get('extensions', name='heartbeat')

ARP_TIMEOUT = 30
current_time = int(time.time())
machine_id = System.get_my_machine_id()
amqp = '{0}://{1}:{2}@{3}//'.format(Configuration.get('ovs.core.broker.protocol'),
                                    Configuration.get('ovs.core.broker.login'),
                                    Configuration.get('ovs.core.broker.password'),
                                    Configuration.get('ovs.grid.ip'))

celery_path = OSManager.get_path('celery')
worker_states = check_output("{0} inspect ping -b {1} --timeout=5 2> /dev/null | grep OK | perl -pe 's/\x1b\[[0-9;]*m//g' || true".format(celery_path, amqp), shell=True)
domain = check_output(["hostname", "-d"]).splitlines()[0]
routers = StorageRouterList.get_storagerouters()
for node in routers:
    if node.heartbeats is None:
        node.heartbeats = {}
    for s in worker_states.splitlines():
        found = False
        if re.match("^-> celery@{0}:".format(node.name), s):
            if re.match("^-> celery@{0}: OK$".format(node.name), s):
                found = True
        if found:
            node.heartbeats['celery'] = current_time
            continue
        else:
            if len(domain) == 0:
                continue

            if re.match("^-> celery@{0}.{1}:".format(node.name, domain), s):
                node.heartbeats['celery'] = current_time

    if node.machine_id == machine_id:
        node.heartbeats['process'] = current_time
    else:
        try:
            # check timeout of other nodes and clear arp cache
            if node.heartbeats and 'process' in node.heartbeats:
                if current_time - node.heartbeats['process'] >= ARP_TIMEOUT:
                    check_output("/usr/sbin/arp -d {0}".format(node.name), shell=True)
        except CalledProcessError:
            logger.exception('Error clearing ARP cache')
    node.save()
