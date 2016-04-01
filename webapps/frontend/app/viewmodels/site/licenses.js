// Copyright 2016 iNuron NV
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
/*global define */
define([
    'knockout', 'plugins/dialog', 'jquery',
    'ovs/shared', 'ovs/generic', 'ovs/api',
    '../containers/license', '../wizards/addlicense/index'
], function(ko, dialog, $, shared, generic, api, License, AddLicenseWizard) {
    "use strict";
    return function() {
        var self = this;

        // Variables
        self.widgets        = [];
        self.shared         = shared;
        self.guard          = { authenticated: true };
        self.generic        = generic;
        self.licensesHandle = {};
        self.licenseHeaders = [
            { key: 'component',  value: $.t('ovs:generic.component'),  width: 250       },
            { key: 'name',       value: $.t('ovs:generic.name'),       width: 250       },
            { key: 'metadata',   value: $.t('ovs:generic.metadata'),   width: undefined }
        ];

        // Observable
        self.licenses    = ko.observableArray([]);

        // Functions
        self.addLicense = function() {
            dialog.show(new AddLicenseWizard({
                modal: true
            }));
        };
        self.loadLicenses = function(options) {
            return $.Deferred(function(deferred) {
                if (generic.xhrCompleted(self.licensesHandle[options.page])) {
                    options.sort = 'component,name,valid_until';
                    options.contents = '_dynamics';
                    self.licensesHandle[options.page] = api.get('licenses', { queryparams: options })
                        .done(function(data) {
                            deferred.resolve({
                                data: data,
                                loader: function(guid) {
                                    return new License(guid);
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
        self.deactivate = function() {
            $.each(self.widgets, function(i, item) {
                item.deactivate();
            });
        };
    };
});
