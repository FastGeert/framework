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
Celery beat module
"""

import os
import time
import cPickle
import inspect
import imp
from celery.beat import Scheduler
from celery import current_app
from celery.schedules import crontab
from celery.schedules import timedelta
from ovs.extensions.storage.persistentfactory import PersistentFactory
from ovs.extensions.storage.exceptions import KeyNotFoundException
from ovs.extensions.generic.volatilemutex import volatile_mutex
from ovs.extensions.generic.system import System
from ovs.log.log_handler import LogHandler


class DistributedScheduler(Scheduler):

    """
    Distributed scheduler that can run on multiple nodes at the same time.
    """

    TIMEOUT = 60 * 30

    def __init__(self, *args, **kwargs):
        """
        Initializes the distributed scheduler
        """
        self._logger = LogHandler.get('celery', name='celery beat')
        self._persistent = PersistentFactory.get_client()
        self._namespace = 'ovs_celery_beat'
        self._mutex = volatile_mutex('celery_beat', 10)
        self._has_lock = False
        super(DistributedScheduler, self).__init__(*args, **kwargs)
        self._logger.debug('DS init')

    def setup_schedule(self):
        """
        Setups the schedule
        """
        self._logger.debug('DS setting up schedule')
        self._load_schedule()
        self.merge_inplace(DistributedScheduler._discover_schedule())
        self.install_default_entries(self.schedule)
        for entry in self.schedule:
            self._logger.debug('* {0}'.format(entry))
        self._logger.debug('DS setting up schedule - done')

    @staticmethod
    def _discover_schedule():
        schedule = {}
        path = '/'.join([os.path.dirname(__file__), 'lib'])
        for filename in os.listdir(path):
            if os.path.isfile('/'.join([path, filename])) and filename.endswith('.py') and filename != '__init__.py':
                name = filename.replace('.py', '')
                module = imp.load_source(name, '/'.join([path, filename]))
                for member in inspect.getmembers(module):
                    if inspect.isclass(member[1]) \
                            and member[1].__module__ == name \
                            and 'object' in [base.__name__ for base in member[1].__bases__]:
                        for submember in inspect.getmembers(member[1]):
                            if hasattr(submember[1], 'schedule') and (isinstance(submember[1].schedule, crontab) or
                                                                      isinstance(submember[1].schedule, timedelta)):
                                schedule[submember[1].name] = {'task': submember[1].name,
                                                               'schedule': submember[1].schedule,
                                                               'args': []}
        return schedule

    def _load_schedule(self):
        """
        Loads the most recent schedule from the persistent store
        """
        self.schedule = {}
        try:
            self._logger.debug('DS loading schedule entries')
            self._mutex.acquire(wait=10)
            try:
                self.schedule = cPickle.loads(str(self._persistent.get('{0}_entries'.format(self._namespace))))
            except:
                # In case an exception occurs during loading the schedule, it is ignored and the default schedule
                # will be used/restored.
                pass
        finally:
            self._mutex.release()

    def sync(self):
        if self._has_lock is True:
            try:
                self._logger.debug('DS syncing schedule entries')
                self._mutex.acquire(wait=10)
                self._persistent.set('{0}_entries'.format(
                    self._namespace), cPickle.dumps(self.schedule))
            finally:
                self._mutex.release()
        else:
            self._logger.debug('DS skipping sync: lock is not ours')

    def tick(self):
        """
        Runs one iteration of the scheduler. This is guarded with a distributed lock
        """
        self._logger.debug('DS executing tick')
        try:
            self._has_lock = False
            with self._mutex:
                node_now = current_app._get_current_object().now()
                node_timestamp = time.mktime(node_now.timetuple())
                node_name = System.get_my_machine_id()
                try:
                    lock = self._persistent.get('{0}_lock'.format(self._namespace))
                except KeyNotFoundException:
                    lock = None
                if lock is None:
                    # There is no lock yet, so the lock is acquired
                    self._has_lock = True
                    self._logger.debug('DS there was no lock in tick')
                else:
                    if lock['name'] == node_name:
                        # The current node holds the lock
                        self._logger.debug('DS keeps own lock')
                        self._has_lock = True
                    elif node_timestamp - lock['timestamp'] > DistributedScheduler.TIMEOUT:
                        # The current lock is timed out, so the lock is stolen
                        self._logger.debug('DS last lock refresh is {0}s old'.format(node_timestamp - lock['timestamp']))
                        self._logger.debug('DS stealing lock from {0}'.format(lock['name']))
                        self._load_schedule()
                        self._has_lock = True
                    else:
                        self._logger.debug('DS lock is not ours')
                if self._has_lock is True:
                    lock = {'name': node_name,
                            'timestamp': node_timestamp}
                    self._logger.debug('DS refreshing lock')
                    self._persistent.set('{0}_lock'.format(self._namespace), lock)

            if self._has_lock is True:
                self._logger.debug('DS executing tick workload')
                remaining_times = []
                try:
                    for entry in self.schedule.itervalues():
                        next_time_to_run = self.maybe_due(entry, self.publisher)
                        if next_time_to_run:
                            remaining_times.append(next_time_to_run)
                except RuntimeError:
                    pass
                self._logger.debug('DS executing tick workload - done')
                return min(remaining_times + [self.max_interval])
            else:
                return self.max_interval
        except Exception as ex:
            self._logger.debug('DS got error during tick: {0}'.format(ex))
            return self.max_interval
