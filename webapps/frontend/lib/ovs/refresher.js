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
/*global define, window */
define(['jquery'], function($){
    "use strict";
    return function() {
        var self = this;

        self.refreshTimeout = undefined;
        self.skipPause = false;

        self.init = function(load, interval) {
            self.load = load;
            self.interval = interval;
            self.running = false;
        };
        self.start = function() {
            self.stop();
            self.refreshTimeout = window.setInterval(function() {
                self.run();
            }, self.interval);
        };
        self.stop = function() {
            if (self.refreshTimeout !== undefined) {
                window.clearInterval(self.refreshTimeout);
                self.refreshTimeout = undefined;
            }
        };
        self.setInterval = function(interval) {
            self.interval = interval;
            if (self.refreshTimeout !== undefined) {
                self.stop();
                self.start();
            }
        };
        self.setLoad = function(load) {
            self.load = load;
        };
        self.run = function() {
            var chainDeferred = $.Deferred(), chainPromise = chainDeferred.promise();
            chainDeferred.resolve();
            chainPromise.then(function() {
                    self.running = true;
                })
                .then(self.load)
                .always(function() {
                    self.running = false;
                    if (self.skipPause === true) {
                        self.skipPause = false;
                        self.run();
                    }
                });
        };
    };
});
