// Copyright 2014 iNuron NV
//
// Licensed under the Open vStorage Non-Commercial License, Version 1.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.openvstorage.org/OVS_NON_COMMERCIAL
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
/*global define */
define([
    'jquery', 'knockout', './data', 'ovs/api', 'ovs/generic', '../../containers/storagerouter'
], function ($, ko, data, api, generic, StorageRouter) {
    "use strict";
    return function() {
        var self = this;

        // Variables
        self.data = data;

        // Handles
        self.loadStorageRoutersHandle = undefined;

        // Computed
        self.canContinue = ko.computed(function () {
            return { value: true, reasons: [], fields: [] };
        });

        // Functions
        self.next = function() {
            return true;
        };

        // Durandal
        self.activate = function() {
            self.loadStorageRoutersHandle = api.get('storagerouters', { queryparams: {
                    contents: 'storagedrivers',
            }})
                .done(function(data) {
                    var guids = [], srdata = {};
                    $.each(data.data, function(index, item) {
                        guids.push(item.guid);
                        srdata[item.guid] = item;
                    });
                    generic.crossFiller(
                        guids, self.data.storageRouters,
                        function(guid) {
                            return new StorageRouter(guid);
                        }, 'guid'
                    );
                    $.each(self.data.storageRouters(), function(index, storageRouter) {
                        storageRouter.fillData(srdata[storageRouter.guid()]);
                    });
                });
            $.each(self.data.storageRouters(), function(index, storageRouter) {
                if (storageRouter === self.data.target()) {
                    $.each(self.data.dtlTransportModes(), function (i, key) {
                        if (key.name === 'rdma') {
                            self.data.dtlTransportModes()[i].disabled = storageRouter.rdmaCapable() === undefined ? true : !storageRouter.rdmaCapable();
                            return false;
                        }
                    });
                }
            });
        }
    };
});
