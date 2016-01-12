# Copyright 2015 iNuron NV
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

"""
Module providing access to an Etcd messagequeue
"""

import json
import time
import etcd
from subprocess import check_output,CalledProcessError
from ovs.log.logHandler import LogHandler

logger = LogHandler.get('extensions', name='etcdqueue')


def log_slow_calls(f):
    def new_function(*args, **kwargs):
        start = time.time()
        try:
            return f(*args, **kwargs)
        finally:
            key_info = ''
            if 'key' in kwargs:
                key_info = ' (key: {0})'.format(kwargs['key'])
            elif len(args) > 0:
                key_info = ' (key: {0})'.format(args[0])
            duration = time.time() - start
            if duration > 1:
                logger.warning('Call to {0}{1} took {2}s'.format(f.__name__, key_info, duration))
    new_function.__name__ = f.__name__
    new_function.__module__ = f.__module__
    return new_function


class MessageQueue(object):
    """
    Messagequeue handler using Etcd as backend

    The data passing though the message"bus" is a JSON serialized dict. This dict consists out of 4 keys:
    * request: The a set of data that contains all information for the destination of the queue
    * response: A set of data that contains all information for the source of the message. it should be None if not answered
    * acknowledged: A boolean indicating whether a response has been processed by the caller
    * _version: The version of this data format.

    The queue is an Etcd directory under /ovs/queues/<queue name> where queue can be any name (even a path).

    Messages are posted to the queue by appending the above data format to the queue directory. The poster should keep track
    of the reported key and creation index, and it should then start to watch this key starting from the given index + 1.

    The destination of the queue should watch the queue itself. It can either keep track of the starting index, or load the entire queue
    and search for all messages that are not yet processed first. As soon as a message is received, it can keep track of the index
    to wait for the next message posted to the queue. It should handle all messages with an empty response.

    The reponse parameter cannot be None. If for example an action must be taken for which None is a valid return value, it must
    be part of a response data structure, for example {'success': True, 'data': None}. Making use of such "success" flag is a good
    idea anyway, since there should be a way of exception handling as well.

    Example usages below

    Consuming side:

        from ... import MessageQueue
        for message in MessageQueue.watch('myqueue'):
            print message.request
            message.response = 'Response to {0}!'.format(message.request)
            MessageQueue.respond(message)
            # This for-loop is never ending, it will yield new messages as they arrive

    Sending side:

        from ... import MessageQueue
        token = MessageQueue.request('myqueue', 'foobar')
        response = MessageQueue.wait(token)  # Optional, an acknowledge=True flag can be passed as well
        # The above line will block until the request is answered
        print response  # Prints 'Response to foobar!
        MessageQueue.acknowledge(token)
    """

    QUEUES = '/ovs/queues/{0}'
    VERSION = 1

    def __init__(self):
        """
        Dummy init method
        """
        _ = self

    @staticmethod
    @log_slow_calls
    def request(queue, data):
        client = MessageQueue._get_client()
        result = client.write(MessageQueue.QUEUES.format(queue), json.dumps({'request': data,
                                                                             'response': None,
                                                                             'acknowledged': False,
                                                                             '_version': MessageQueue.VERSION}), append=True)
        logger.debug('Added message to queue. Got key {0}'.format(result.key))
        return type('Token', (), {'index': result.createdIndex,
                                  'key': result.key,
                                  'version': MessageQueue.VERSION})

    @staticmethod
    def wait(token, timeout=60, acknowledge=False):
        if token.version != MessageQueue.VERSION:
            logger.error('Token for {0} has old version. {1} vs {2}'.format(token.key, token.version, MessageQueue.VERSION))
            raise RuntimeError('Queue version mismatch')
        client = MessageQueue._get_client()
        data = None
        found = False
        start = time.time()
        while found is False and time.time() - start < timeout:
            try:
                client.watch(token.key, token.index + 1)
                result = client.get(token.key)  # Get the latest version
                data = json.loads(result.value)
                if data['response'] is not None:
                    found = True
                    logger.debug('Received response for {0}'.format(token.key))
                else:
                    logger.debug('Key {0} got updated, but no response yet, retrying'.format(token.key))
            except etcd.EtcdConnectionFailed:
                logger.debug('Watch timed out fetching {0}, retrying'.format(token.key))
                pass
        if found is False:
            logger.error('No answer for {0} was received withing specified timestamp'.format(token.key))
            raise RuntimeError('No answer received')
        if data['_version'] != MessageQueue.VERSION:
            logger.error('Received message {0} has old version. {1} vs {2}'.format(token.key, data['_version'], MessageQueue.VERSION))
            raise RuntimeError('Queue version mismatch')
        if acknowledge is True:
            data['acknowledged'] = True
            client.write(token.key, json.dumps(data))
            logger.debug('Acknowledged message {0}'.format(token.key))
        return data['response']

    @staticmethod
    @log_slow_calls
    def acknowledge(token):
        if token.version != MessageQueue.VERSION:
            logger.error('Token for {0} has old version. {1} vs {2}'.format(token.key, token.version, MessageQueue.VERSION))
            raise RuntimeError('Queue version mismatch')
        client = MessageQueue._get_client()
        result = client.get(token.key)
        data = json.loads(result.value)
        if data['_version'] != MessageQueue.VERSION:
            logger.error('Received message {0} has old version. {1} vs {2}'.format(token.key, data['_version'], MessageQueue.VERSION))
            raise RuntimeError('Queue version mismatch')
        data['acknowledged'] = True
        client.write(token.key, json.dumps(data))
        logger.debug('Acknowledged message {0}'.format(token.key))

    @staticmethod
    def watch(queue):
        client = MessageQueue._get_client()
        try:
            check_output('etcdctl mkdir {0} 2> /dev/null'.format(MessageQueue.QUEUES.format(queue)), shell=True)
            logger.debug('Created queue {0}'.format(queue))
        except CalledProcessError:
            pass
        last_index = 0
        while True:
            try:
                result = client.watch(MessageQueue.QUEUES.format(queue), last_index + 1, recursive=True)
                if result.action == 'create':
                    key = result.key
                    result = client.get(key)  # Get the latest version
                    if result.value is not None:
                        data = json.loads(result.value)
                        if data.get('_version', -1) == MessageQueue.VERSION and data.get('response', None) is None:
                            logger.debug('Yielding an unanswered request {0}'.format(result.key))
                            yield type('Message', (), {'version': data['_version'],
                                                       'key': result.key,
                                                       'request': data['request'],
                                                       'response': data['response'],
                                                       'acknowledged': data['acknowledged']})
                last_index = result.createdIndex
            except etcd.EtcdConnectionFailed:
                logger.debug('Watch timed out on queue {0}'.format(MessageQueue.QUEUES.format(queue)))
                pass

    @staticmethod
    @log_slow_calls
    def respond(message):
        if message.version != MessageQueue.VERSION:
            logger.error('Message {0} has old version. {1} vs {2}'.format(message.key, message.version, MessageQueue.VERSION))
            raise RuntimeError('Queue version mismatch')
        client = MessageQueue._get_client()
        client.write(message.key, json.dumps({'request': message.request,
                                              'response': message.response,
                                              'acknowledged': message.acknowledged,
                                              '_version': message.version}))
        logger.debug('Response on {0} has been posted'.format(message.key))

    @staticmethod
    def _get_client():
        return etcd.Client(port=2379, use_proxies=True)
