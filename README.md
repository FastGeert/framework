# Open vStorage

Open vStorage is an open-source, scale-out, reliable, high performance, software based storage platform which offers a block & file interface on top of ethernet drives (Seagate Kinetic), object storage or a pool of traditional SATA drives.

Open vStorage is licensed under the [Modified Apache License](http://www.openvstorage.org/license).

The Open vStorage Framework takes care of the communication between the different hosts in the Open vStorage cluster and the storage backends. The Framework allows to manage Open vStorage through an intuitive GUI and a complete REST API. It integrates with OpenStack (Cinder) and VMware vSphere.

This repo is your starting point to experiment with Open vStorage.

The Open vStorage Framework is built using python (Django, Celery) and javascript.

[![Build Status](https://travis-ci.org/openvstorage/openvstorage.svg?branch=master)](https://travis-ci.org/openvstorage/openvstorage)

## Get started

On our community website you can find [more information](https://www.openvstorage.org) and [how to get started with an installation](https://openvstorage.gitbooks.io/openvstorage/content/Installation/index.html).

## Support
* For community support, please visit our [community support forum](https://groups.google.com/forum/#!forum/open-vstorage)
* For commercial support, please [contact Open vStorage](https://www.openvstorage.com/en/#footer)

## Contribution & Packaging

We welcome contributions.
Packaging your own changes for testing can be done using the [packager module](https://github.com/openvstorage/framework-tools/blob/master/packaging/packager.py)

## File a bug
Open vStorage is quality checked to the highest level. Unfortunately we might have overlooked some tiny topics here or there. The Open vStorage Project maintains a [public issue tracker](https://github.com/openvstorage/openvstorage/issues) where you can report bugs and request features. This issue tracker is not a customer support forum but an error, flaw, failure, or fault in the Open vStorage software.

## Nightly tests

A view on the different sets of Nightly test runs can be found [here](http://testrail.openvstorage.com/index.php?/runs/overview/10).
Email address ovs-guest@openvstorage.com with password 0vsgu3st should allow you to login and view the results
