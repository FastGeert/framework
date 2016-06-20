// Copyright (C) 2016 iNuron NV
//
// This file is part of Open vStorage Open Source Edition (OSE),
// as available from
//
//      http://www.openvstorage.org and
//      http://www.openvstorage.com.
//
// This file is free software; you can redistribute it and/or modify it
// under the terms of the GNU Affero General Public License v3 (GNU AGPLv3)
// as published by the Free Software Foundation, in version 3 as it comes
// in the LICENSE.txt file of the Open vStorage OSE distribution.
//
// Open vStorage is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY of any kind.
/*global define */
define([
    'jquery', 'knockout', 'ovs/shared',
    'ovs/generic', 'ovs/api',
    'viewmodels/containers/backendtype', 'viewmodels/containers/vdisk', 'viewmodels/containers/vmachine'
], function($, ko, shared, generic, api, BackendType, VDisk, VMachine) {
    "use strict";
    return function(guid) {
        var self = this;

        // Variables
        self.shared = shared;

        // Handles
        self.loadHandle          = undefined;
        self.diskHandle          = undefined;
        self.loadConfig          = undefined;
        self.machineHandle       = undefined;
        self.storageRouterHandle = undefined;

        // Observables
        self.backendConnection  = ko.observable();
        self.backendPreset      = ko.observable();
        self.backendLogin       = ko.observable();
        self.backendRead        = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatBytes });
        self.backendReadSpeed   = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatSpeed });
        self.backendType        = ko.observable();
        self.backendTypeGuid    = ko.observable();
        self.backendWriteSpeed  = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatSpeed });
        self.backendWritten     = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatBytes });
        self.bandwidthSaved     = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatBytes });
        self.cacheHits          = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatNumber });
        self.cacheMisses        = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatNumber });
        self.configuration      = ko.observable();
        self.guid               = ko.observable(guid);
        self.iops               = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatNumber });
        self.loaded             = ko.observable(false);
        self.loading            = ko.observable(false);
        self.metadata           = ko.observable();
        self.name               = ko.observable();
        self.rdmaEnabled        = ko.observable();
        self.readSpeed          = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatSpeed });
        self.size               = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatBytes });
        self.status             = ko.observable();
        self.storageDriverGuids = ko.observableArray([]);
        self.storageRouterGuids = ko.observableArray([]);
        self.storedData         = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatBytes });
        self.totalCacheHits     = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatNumber });
        self.vDisks             = ko.observableArray([]);
        self.vMachines          = ko.observableArray([]);
        self.writeSpeed         = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatSpeed });

        // Computed
        self.bandwidth = ko.computed(function() {
            if (self.readSpeed() === undefined || self.writeSpeed() === undefined) {
                return undefined;
            }
            var total = (self.readSpeed.raw() || 0) + (self.writeSpeed.raw() || 0);
            return generic.formatSpeed(total);
        });

        // Functions
        self.fillData = function(data, options) {
            options = options || {};
            generic.trySet(self.name, data, 'name');
            generic.trySet(self.status, data, 'status');
            generic.trySet(self.storedData, data, 'stored_data');
            generic.trySet(self.size, data, 'size');
            generic.trySet(self.metadata, data, 'metadata');
            generic.trySet(self.backendConnection, data, 'connection');

            if (self.metadata.hasOwnProperty('backend') && self.metadata.backend.hasOwnProperty('preset')) {
                self.backendPreset(self.metadata.backend.preset);
            }

            generic.trySet(self.backendLogin, data, 'login');
            generic.trySet(self.rdmaEnabled, data, 'rdma_enabled');
            if (data.hasOwnProperty('backend_type_guid')) {
                self.backendTypeGuid(data.backend_type_guid);
            } else {
                self.backendTypeGuid(undefined);
            }
            if (data.hasOwnProperty('vdisks_guids') && !generic.tryGet(options, 'skipDisks', false)) {
                generic.crossFiller(
                    data.vdisks_guids, self.vDisks,
                    function(guid) {
                        return new VDisk(guid);
                    }, 'guid'
                );
            }
            if (data.hasOwnProperty('storagedrivers_guids')) {
                self.storageDriverGuids(data.storagedrivers_guids);
            }
            if (data.hasOwnProperty('statistics')) {
                var stats = data.statistics;
                self.iops(stats['4k_operations_ps']);
                self.cacheHits(stats.cache_hits_ps);
                self.cacheMisses(stats.cache_misses_ps);
                self.totalCacheHits(stats.cache_hits);
                self.readSpeed(stats.data_read_ps);
                self.writeSpeed(stats.data_written_ps);
                self.backendWritten(stats.backend_data_written);
                self.backendRead(stats.backend_data_read);
                self.bandwidthSaved(Math.max(0, stats.data_read - stats.backend_data_read));
                self.backendReadSpeed(stats.backend_data_read_ps);
                self.backendWriteSpeed(stats.backend_data_written_ps);
            }

            self.loaded(true);
            self.loading(false);
        };
        self.load = function(contents, options) {
            options = options || {};
            self.loading(true);
            return $.Deferred(function(deferred) {
                var calls = [
                    $.Deferred(function(mainDeferred) {
                        if (generic.xhrCompleted(self.loadHandle)) {
                            var listOptions = {};
                            if (contents !== undefined) {
                                listOptions.contents = contents;
                            }
                            self.loadHandle = api.get('vpools/' + self.guid(), { queryparams: listOptions })
                                .done(function(data) {
                                    self.fillData(data, options);
                                    mainDeferred.resolve();
                                })
                                .fail(mainDeferred.reject);
                        } else {
                            mainDeferred.resolve();
                        }
                    }).promise(),
                    $.Deferred(function(machineDeferred) {
                        if (generic.xhrCompleted(self.machineHandle)) {
                            var options = {
                                sort: 'name',
                                vpoolguid: self.guid(),
                                contents: ''
                            };
                            self.machineHandle = api.get('vmachines', { queryparams: options })
                                .done(function(data) {
                                    var guids = [], vmdata = {};
                                    $.each(data.data, function(index, item) {
                                        guids.push(item.guid);
                                        vmdata[item.guid] = item;
                                    });
                                    generic.crossFiller(
                                        guids, self.vMachines,
                                        function(guid) {
                                            var vmachine = new VMachine(guid);
                                            if ($.inArray(guid, guids) !== -1) {
                                                vmachine.fillData(vmdata[guid]);
                                            }
                                            vmachine.loading(true);
                                            return vmachine;
                                        }, 'guid'
                                    );
                                    machineDeferred.resolve();
                                })
                                .fail(machineDeferred.reject);
                        } else {
                            machineDeferred.resolve();
                        }
                    }).promise()];
                $.when.apply($, calls)
                    .done(function() {
                        self.loaded(true);
                        deferred.resolve();
                    })
                    .fail(deferred.reject)
                    .always(function() {
                        self.loading(false);
                    });
            }).promise();
        };
        self.loadConfiguration = function() {
            return $.Deferred(function(deferred) {
                self.loadConfig = api.get('vpools/' + self.guid() + '/get_configuration')
                    .then(self.shared.tasks.wait)
                    .done(function(data) {
                        self.configuration(data);
                        deferred.resolve();
                    })
                    .fail(deferred.reject);
            }).promise();
        };
        self.loadStorageRouters = function() {
            return $.Deferred(function(deferred) {
                if (generic.xhrCompleted(self.storageRouterHandle)) {
                    self.storageRouterHandle = api.get('vpools/' + self.guid() + '/storagerouters')
                        .done(function(data) {
                            self.storageRouterGuids(data.data);
                            deferred.resolve();
                        })
                        .fail(deferred.reject);
                } else {
                    deferred.resolve();
                }
            }).promise();
        };
        self.loadBackendType = function(refresh) {
            refresh = !!refresh;
            return $.Deferred(function(deferred) {
                if (self.backendTypeGuid() !== undefined) {
                    if (self.backendType() === undefined || self.backendTypeGuid() !== self.backendType().guid()) {
                        var backendType = new BackendType(self.backendTypeGuid());
                        backendType.load()
                            .then(deferred.resolve)
                            .fail(deferred.reject);
                        self.backendType(backendType);
                    } else if (refresh) {
                        self.backendType().load()
                            .then(deferred.resolve)
                            .fail(deferred.reject);
                    } else {
                        deferred.resolve();
                    }
                } else {
                    self.backendType(undefined);
                    deferred.resolve();
                }
            }).promise();
        };
    };
});
