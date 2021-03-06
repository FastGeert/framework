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
StorageDriver module
"""

import volumedriver.storagerouter.VolumeDriverEvents_pb2 as VolumeDriverEvents
from celery.schedules import crontab
from ovs.celery_run import celery
from ovs.dal.hybrids.diskpartition import DiskPartition
from ovs.dal.hybrids.j_storagedriverpartition import StorageDriverPartition
from ovs.dal.hybrids.service import Service
from ovs.dal.hybrids.servicetype import ServiceType
from ovs.dal.hybrids.storagerouter import StorageRouter
from ovs.dal.lists.servicetypelist import ServiceTypeList
from ovs.dal.lists.storagerouterlist import StorageRouterList
from ovs.dal.lists.vdisklist import VDiskList
from ovs.extensions.db.arakoon.ArakoonInstaller import ArakoonInstaller, ArakoonClusterConfig
from ovs.extensions.generic.configuration import Configuration
from ovs.extensions.generic.sshclient import SSHClient
from ovs.extensions.services.service import ServiceManager
from ovs.extensions.storageserver.storagedriver import StorageDriverClient, StorageDriverConfiguration
from ovs.lib.helpers.decorators import add_hooks, ensure_single, log
from ovs.lib.mdsservice import MDSServiceController
from ovs.log.log_handler import LogHandler


class StorageDriverController(object):
    """
    Contains all BLL related to Storage Drivers
    """
    _logger = LogHandler.get('lib', name='storagedriver')

    @staticmethod
    @celery.task(name='ovs.storagedriver.mark_offline')
    def mark_offline(storagerouter_guid):
        """
        Marks all StorageDrivers on this StorageRouter offline
        :param storagerouter_guid: Guid of the Storage Router
        :type storagerouter_guid: str

        :return: None
        """
        storagedrivers = StorageRouter(storagerouter_guid).storagedrivers
        if len(storagedrivers) > 0:
            storagedriver_client = StorageDriverClient.load(storagedrivers[0].vpool)
            for storagedriver in storagedrivers:
                storagedriver_client.mark_node_offline(str(storagedriver.storagedriver_id))

    @staticmethod
    @celery.task(name='ovs.storagedriver.volumedriver_error')
    @log('VOLUMEDRIVER_TASK')
    def volumedriver_error(code, volume_id):
        """
        Handles error messages/events from the volumedriver
        :param code: Volumedriver error code
        :type code: int

        :param volume_id: Name of the volume throwing the error
        :type volume_id: str

        :return: None
        """
        if code == VolumeDriverEvents.MDSFailover:
            disk = VDiskList.get_vdisk_by_volume_id(volume_id)
            if disk is not None:
                MDSServiceController.ensure_safety(disk)

    @staticmethod
    @add_hooks('setup', 'demote')
    def on_demote(cluster_ip, master_ip, offline_node_ips=None):
        """
        Handles the demote for the StorageDrivers
        :param cluster_ip: IP of the node to demote
        :type cluster_ip: str

        :param master_ip: IP of the master node
        :type master_ip: str

        :param offline_node_ips: IPs of nodes which are offline
        :type offline_node_ips: list

        :return: None
        """
        _ = master_ip
        if offline_node_ips is None:
            offline_node_ips = []
        client = SSHClient(cluster_ip, username='root') if cluster_ip not in offline_node_ips else None
        servicetype = ServiceTypeList.get_by_name(ServiceType.SERVICE_TYPES.ARAKOON)
        current_service = None
        remaining_ips = []
        for service in servicetype.services:
            if service.name == 'arakoon-voldrv' and service.is_internal is True:  # Externally managed arakoon cluster service does not have storage router
                if service.storagerouter.ip == cluster_ip:
                    current_service = service
                elif service.storagerouter.ip not in offline_node_ips:
                    remaining_ips.append(service.storagerouter.ip)
        if current_service is not None:
            if len(remaining_ips) == 0:
                raise RuntimeError('Could not find any remaining arakoon nodes for the voldrv cluster')
            StorageDriverController._logger.debug('* Shrink StorageDriver cluster')
            cluster_name = str(Configuration.get('/ovs/framework/arakoon_clusters|voldrv'))
            ArakoonInstaller.shrink_cluster(deleted_node_ip=cluster_ip,
                                            remaining_node_ip=remaining_ips[0],
                                            cluster_name=cluster_name,
                                            offline_nodes=offline_node_ips)
            if client is not None and ServiceManager.has_service(current_service.name, client=client) is True:
                ServiceManager.stop_service(current_service.name, client=client)
                ServiceManager.remove_service(current_service.name, client=client)
            ArakoonInstaller.restart_cluster_remove(cluster_name, remaining_ips, filesystem=False)
            current_service.delete()
            StorageDriverController._configure_arakoon_to_volumedriver(cluster_name=cluster_name)

    @staticmethod
    @celery.task(name='ovs.storagedriver.scheduled_voldrv_arakoon_checkup', schedule=crontab(minute='15', hour='*'))
    def scheduled_voldrv_arakoon_checkup():
        """
        Makes sure the volumedriver arakoon is on all available master nodes
        """
        StorageDriverController._voldrv_arakoon_checkup(False)

    @staticmethod
    @celery.task(name='ovs.storagedriver.manual_voldrv_arakoon_checkup')
    def manual_voldrv_arakoon_checkup():
        """
        Creates a new Arakoon Cluster if required and extends cluster if possible on all available master nodes
        """
        StorageDriverController._voldrv_arakoon_checkup(True)

    @staticmethod
    @ensure_single(task_name='ovs.storagedriver.voldrv_arakoon_checkup')
    def _voldrv_arakoon_checkup(create_cluster):
        def add_service(service_storagerouter, arakoon_ports):
            """
            Add a service to the storage router
            :param service_storagerouter: Storage Router to add the service to
            :param arakoon_ports: Port information
            :return: The newly created and added service
            """
            new_service = Service()
            new_service.name = service_name
            new_service.type = service_type
            new_service.ports = arakoon_ports
            new_service.storagerouter = service_storagerouter
            new_service.save()
            return new_service

        service_name = 'arakoon-voldrv'
        service_type = ServiceTypeList.get_by_name(ServiceType.SERVICE_TYPES.ARAKOON)

        current_ips = []
        current_services = []
        for service in service_type.services:
            if service.name == service_name:
                current_services.append(service)
                if service.is_internal is True:
                    current_ips.append(service.storagerouter.ip)

        all_sr_ips = [storagerouter.ip for storagerouter in StorageRouterList.get_slaves()]
        available_storagerouters = {}
        for storagerouter in StorageRouterList.get_masters():
            storagerouter.invalidate_dynamics(['partition_config'])
            if len(storagerouter.partition_config[DiskPartition.ROLES.DB]) > 0:
                available_storagerouters[storagerouter] = DiskPartition(storagerouter.partition_config[DiskPartition.ROLES.DB][0])
            all_sr_ips.append(storagerouter.ip)

        if create_cluster is True and len(current_services) == 0:  # Create new cluster
            metadata = ArakoonInstaller.get_unused_arakoon_metadata_and_claim(cluster_type=ServiceType.ARAKOON_CLUSTER_TYPES.SD)
            if metadata is None:  # No externally managed cluster found, we create 1 ourselves
                if not available_storagerouters:
                    raise RuntimeError('Could not find any Storage Router with a DB role')

                storagerouter, partition = available_storagerouters.items()[0]
                result = ArakoonInstaller.create_cluster(cluster_name='voldrv',
                                                         cluster_type=ServiceType.ARAKOON_CLUSTER_TYPES.SD,
                                                         ip=storagerouter.ip,
                                                         base_dir=partition.folder,
                                                         filesystem=False)
                ports = [result['client_port'], result['messaging_port']]
                metadata = result['metadata']
                ArakoonInstaller.restart_cluster_add(cluster_name='voldrv',
                                                     current_ips=current_ips,
                                                     new_ip=storagerouter.ip,
                                                     filesystem=False)
                ArakoonInstaller.claim_cluster(cluster_name='voldrv',
                                               master_ip=storagerouter.ip,
                                               filesystem=False,
                                               metadata=metadata)
                current_ips.append(storagerouter.ip)
            else:
                ports = []
                storagerouter = None

            cluster_name = metadata['cluster_name']
            Configuration.set('/ovs/framework/arakoon_clusters|voldrv', cluster_name)
            StorageDriverController._logger.info('Claiming {0} managed arakoon cluster: {1}'.format('externally' if storagerouter is None else 'internally', cluster_name))
            StorageDriverController._configure_arakoon_to_volumedriver(cluster_name=cluster_name)
            current_services.append(add_service(service_storagerouter=storagerouter, arakoon_ports=ports))

        cluster_name = Configuration.get('/ovs/framework/arakoon_clusters').get('voldrv')
        if cluster_name is None:
            return
        metadata = ArakoonInstaller.get_arakoon_metadata_by_cluster_name(cluster_name=cluster_name)
        if 0 < len(current_services) < len(available_storagerouters) and metadata['internal'] is True:
            for storagerouter, partition in available_storagerouters.iteritems():
                if storagerouter.ip in current_ips:
                    continue
                result = ArakoonInstaller.extend_cluster(master_ip=current_services[0].storagerouter.ip,
                                                         new_ip=storagerouter.ip,
                                                         cluster_name=cluster_name,
                                                         base_dir=partition.folder)
                add_service(storagerouter, [result['client_port'], result['messaging_port']])
                current_ips.append(storagerouter.ip)
                ArakoonInstaller.restart_cluster_add(cluster_name=cluster_name,
                                                     current_ips=current_ips,
                                                     new_ip=storagerouter.ip,
                                                     filesystem=False)
            StorageDriverController._configure_arakoon_to_volumedriver(cluster_name=cluster_name)

    @staticmethod
    def _configure_arakoon_to_volumedriver(cluster_name):
        StorageDriverController._logger.info('Update existing vPools')
        config = ArakoonClusterConfig(cluster_id=cluster_name, filesystem=False)
        config.load_config()
        arakoon_nodes = []
        for node in config.nodes:
            arakoon_nodes.append({'host': node.ip,
                                  'port': node.client_port,
                                  'node_id': node.name})
        if Configuration.dir_exists('/ovs/vpools'):
            for vpool_guid in Configuration.list('/ovs/vpools'):
                for storagedriver_id in Configuration.list('/ovs/vpools/{0}/hosts'.format(vpool_guid)):
                    storagedriver_config = StorageDriverConfiguration('storagedriver', vpool_guid, storagedriver_id)
                    storagedriver_config.load()
                    storagedriver_config.configure_volume_registry(vregistry_arakoon_cluster_id=cluster_name,
                                                                   vregistry_arakoon_cluster_nodes=arakoon_nodes)
                    storagedriver_config.configure_distributed_lock_store(dls_type='Arakoon',
                                                                          dls_arakoon_cluster_id=cluster_name,
                                                                          dls_arakoon_cluster_nodes=arakoon_nodes)
                    storagedriver_config.save(reload_config=True)

    @staticmethod
    def add_storagedriverpartition(storagedriver, partition_info):
        """
        Stores new storagedriver partition object with correct number
        :param storagedriver: Storagedriver to create the partition for
        :type storagedriver: StorageDriver

        :param partition_info: Partition information containing, role, size, sub_role, disk partition, MDS service
        :type partition_info: dict

        :return: Newly created storage driver partition
        :rtype: StorageDriverPartition
        """
        role = partition_info['role']
        size = partition_info.get('size')
        sub_role = partition_info.get('sub_role')
        partition = partition_info['partition']
        mds_service = partition_info.get('mds_service')
        highest_number = 0
        for existing_sdp in storagedriver.partitions:
            if existing_sdp.partition_guid == partition.guid and existing_sdp.role == role and existing_sdp.sub_role == sub_role:
                highest_number = max(existing_sdp.number, highest_number)
        sdp = StorageDriverPartition()
        sdp.role = role
        sdp.size = size
        sdp.number = highest_number + 1
        sdp.sub_role = sub_role
        sdp.partition = partition
        sdp.mds_service = mds_service
        sdp.storagedriver = storagedriver
        sdp.save()
        return sdp
