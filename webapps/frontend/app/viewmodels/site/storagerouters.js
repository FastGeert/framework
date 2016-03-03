// Copyright 2014 iNuron NV
//
// Licensed under the Open vStorage Modified Apache License (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.openvstorage.org/license
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
/*global define*/
define([
    'jquery', 'knockout', 'plugins/dialog',
    'ovs/shared', 'ovs/generic', 'ovs/refresher', 'ovs/api',
    '../containers/vpool', '../containers/storagerouter', '../containers/pmachine', '../containers/failuredomain'
], function($, ko, dialog, shared, generic, Refresher, api, VPool, StorageRouter, PMachine, FailureDomain) {
    "use strict";
    return function() {
        var self = this;

        // Variables
        self.shared                = shared;
        self.guard                 = { authenticated: true, registered: true };
        self.refresher             = new Refresher();
        self.widgets               = [];
        self.pMachineCache         = {};
        self.fdCache               = {};
        self.storageRoutersHeaders = [
            { key: 'status',                       value: $.t('ovs:generic.status'),                      sort: true,  width: 90        },
            { key: 'name',                         value: $.t('ovs:generic.name'),                        sort: true,  width: 100       },
            { key: 'ip',                           value: $.t('ovs:generic.ip'),                          sort: true,  width: 100       },
            { key: 'pmachine.name',                value: $.t('ovs:generic.host'),                        sort: true,  width: 55        },
            { key: 'pmachine.hvtype',              value: $.t('ovs:generic.type'),                        sort: true,  width: 70        },
            { key: 'vdisks',                       value: $.t('ovs:generic.vdisks'),                      sort: false, width: 55        },
            { key: 'stored_data',                  value: $.t('ovs:generic.storeddata_short'),            sort: true,  width: 96        },
            { key: 'cacheRatio',                   value: $.t('ovs:generic.cache'),                       sort: false, width: 80        },
            { key: 'statistics[4k_operations_ps]', value: $.t('ovs:generic.iops'),                        sort: true,  width: 85        },
            { key: 'statistics[data_read_ps]',     value: $.t('ovs:generic.read'),                        sort: true,  width: 100       },
            { key: 'statistics[data_written_ps]',  value: $.t('ovs:generic.write'),                       sort: true,  width: 100       },
            { key: 'primary_failure_domain.name',  value: $.t('ovs:generic.failure_domain_short'),        sort: true,  width: 100       },
            { key: 'secondaryFD',                  value: $.t('ovs:generic.backup_failure_domain_short'), sort: false, width: 100       },
            { key: 'scrub',                        value: $.t('ovs:generic.scrub'),                       sort: false, width: undefined }
        ];

        // Observables
        self.vPools         = ko.observableArray([]);
        self.failureDomains = ko.observableArray([]);
        self.storageRouters = ko.observableArray([]);

        // Handles
        self.storageRoutersHandle = {};
        self.vPoolsHandle         = undefined;
        self.failureDomainHandle  = undefined;
        self.storageRouterHandle  = undefined;

        // Functions
        self.loadStorageRouters = function(page, sort) {
            return $.Deferred(function(deferred) {
                if (generic.xhrCompleted(self.storageRoutersHandle[page])) {
                    var options = {
                        sort: 'name',
                        page: page,
                        contents: '_relations,statistics,stored_data,vdisks_guids,status,partition_config'
                    };
                    if (sort !== undefined) {
                        options.sort = sort;
                    }
                    self.storageRoutersHandle[page] = api.get('storagerouters', { queryparams: options })
                        .done(function(data) {
                            deferred.resolve({
                                data: data,
                                loader: function(guid) {
                                    return new StorageRouter(guid);
                                },
                                dependencyLoader: function(item) {
                                    var pMachineGuid = item.pMachineGuid(), pm, pfd, sfd,
                                        primaryFailureDomainGuid = item.primaryFailureDomainGuid(),
                                        secondaryFailureDomainGuid = item.secondaryFailureDomainGuid();
                                    if (pMachineGuid && (item.pMachine() === undefined || item.pMachine().guid() !== pMachineGuid)) {
                                        if (!self.pMachineCache.hasOwnProperty(pMachineGuid)) {
                                            pm = new PMachine(pMachineGuid);
                                            pm.load();
                                            self.pMachineCache[pMachineGuid] = pm;
                                        }
                                        item.pMachine(self.pMachineCache[pMachineGuid]);
                                    } else if (pMachineGuid && item.pMachine() !== undefined && item.pMachine().loaded() === false) {
                                        if (!self.pMachineCache.hasOwnProperty(item.pMachine().guid())) {
                                            self.pMachineCache[item.pMachine().guid()] = item.pMachine();
                                        }
                                        item.pMachine().load();
                                    }
                                    if (primaryFailureDomainGuid && (item.primaryFailureDomain() === undefined || item.primaryFailureDomainGuid() !== primaryFailureDomainGuid)) {
                                        if (!self.fdCache.hasOwnProperty(primaryFailureDomainGuid)) {
                                            pfd = new FailureDomain(primaryFailureDomainGuid);
                                            pfd.load();
                                            self.fdCache[primaryFailureDomainGuid] = pfd;
                                        }
                                        item.primaryFailureDomain(self.fdCache[primaryFailureDomainGuid]);
                                    }
                                    if (secondaryFailureDomainGuid && (item.secondaryFailureDomain() === undefined || item.secondaryFailureDomainGuid() !== secondaryFailureDomainGuid)) {
                                        if (!self.fdCache.hasOwnProperty(secondaryFailureDomainGuid)) {
                                            sfd = new FailureDomain(secondaryFailureDomainGuid);
                                            sfd.load();
                                            self.fdCache[secondaryFailureDomainGuid] = sfd;
                                        }
                                        item.secondaryFailureDomain(self.fdCache[secondaryFailureDomainGuid]);
                                    }
                                }
                            });
                        })
                        .fail(function() { deferred.reject(); });
                } else {
                    deferred.resolve();
                }
            }).promise();
        };

        // Durandal
        self.activate = function() {
            self.refresher.init(function() {
                if (generic.xhrCompleted(self.failureDomainHandle)) {
                    self.failureDomainHandle = api.get('failure_domains', { queryparams: { contents: '', sort: 'name' } })
                        .done(function(data) {
                            var guids = [], fdData = {};
                            $.each(data.data, function(index, item) {
                                guids.push(item.guid);
                                fdData[item.guid] = item;
                            });
                            generic.crossFiller(
                                guids, self.failureDomains,
                                function(guid) {
                                    if (!self.fdCache.hasOwnProperty(guid)) {
                                        self.fdCache[guid] = new FailureDomain(guid);
                                    }
                                    return self.fdCache[guid];
                                }, 'guid'
                            );
                            $.each(self.failureDomains(), function(index, item) {
                                if (fdData.hasOwnProperty(item.guid())) {
                                    item.fillData(fdData[item.guid()]);
                                }
                            });
                        });
                }
            }, 60000);
            self.refresher.start();
            self.refresher.run();
            self.shared.footerData(self.vPools);
        };
        self.deactivate = function() {
            $.each(self.widgets, function(index, item) {
                item.deactivate();
            });
            self.refresher.stop();
            self.shared.footerData(ko.observable());
        };
    };
});
