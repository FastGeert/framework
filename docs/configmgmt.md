## Configuration Manegement
As Open vStorage is completely distributed it uses a distributed configuration management system.
There are 2 option as configuration management system:
* Arakoon, the preferred and advised system.
* ETCD

#### Set, get and list configuration keys
The [OVS commandline](https://openvstorage.gitbooks.io/administration/content/Administration/usingthecli/configmgmt.html) allows to easily list and change the configuration parameters of the cluster:
* `ovs config edit some/key`: Edit that key in your `$EDITOR`. If it doesn't exist, the key is created.
* `ovs config list some`: List all keys with the given prefix.
* `ovs config get some/key`: Print the content of the given key.


#### Framework
All framework keys stated below are relative to ```/ovs/framework```. E.g. ```cluster_id``` will be ```/ovs/framework/cluster_id```.

##### Clusterwide key-values
```
arakoon_clusters = {"ovsdb": "$framework_arakoon_cluster_name",
                    "voldrv": "$storagedriver_arakoon_cluster_name"}
cluster_id = "$cluster_id"
external_etcd = "$external_etcd"
install_time = "$epoch"
rdma = true|false
logging = {"type": "console|file|redis"}
memcache = {"endpoints": ["$endpoint_1", "$endpoint2"],
            "metadata": {"internal": True|False}}
messagequeue = {"endpoints": ["$endpoint_3", "$endpoint_4"],
                "protocol": "amqp",
                "user": "ovs",
                "password": "$unencrypted_password",
                "queues": {"storagedriver": "volumerouter"},
                "metadata": {"internal": True|False}}
paths = {"cfgdir": "/opt/OpenvStorage/config",
         "basedir": "/opt/OpenvStorage",
         "ovsdb": "/opt/OpenvStorage/db"}
plugins/installed = {"backends": ["$plugin_a"],
                     "generic": ["$plugin_b", "$plugin_c"]},
plugins/$plugin_a/config = {"nsm": {"safety": 3,
                                    "maxload": 75}}
storagedriver = {"mds_safety": 3,
                 "mds_tlogs": 100,
                 "mds_maxload": 75}
stores = {"persistent": "pyrakoon",
          "volatile": "memcache"}
support = {"enablesupport": True|False,
           "enabled": True|False,
           "interval": 60}
webapps = {"html_endpoint": "/",
           "oauth2": {"mode": "local|remote",
                      "authorize_uri": "$autorize_url_for_remote",
                      "client_id": "$client_id_for_remote",
                      "client_secret": "$client_secret_for_remote",
                      "scope": "$scope_for_remote",
                      "token_uri": "$token_uri_for_remote"}}
```
The ```/ovs/framework/webapps/oauth2``` mode can be either ```local``` or ```remote```. When using ```remote```, certain extra keys on how to reach the remote authentication platform should be given.

* authorize_uri: If a user is not logged in, he will be redirected to this page for authenitcation
* client_id: OVS client identification towards remote oauth2 platform
* client_secret: OVS client password for authenitcation to remote oauth2 platform
* scope: Requested scope for OVS users
* token_uri: URI where OVS can request the token


##### Cluster node specific key-values

```
hosts/$host_id/ip = "$host_ip"
hosts/$host_id/paths = {"celery": "/usr/bin/celery"}
hosts/$host_id/ports = {"storagedriver": [[26200, 26299]],
                        "mds": [[26300, 26399]],
                        "arakoon": [26400]}
hosts/$host_id/promotecompleted = True|False
hosts/$host_id/setupcompleted = True|False
hosts/$host_id/storagedriver = {"rsp": "/var/rsp",
                                "vmware_mode": "ganesha"}
hosts/$host_id/type = "MASTER|EXTRA|UNCONFIGURED"
hosts/$host_id/versions = {"ovs": 4,
                           "$plugin_a": $plugin_a_version}
```

The ```$host_id``` in above keys can be found on the respective node in ```/etc/openvstorage_id```

#### Arakoon
All arakoon keys stated below are relative to ```/ovs/arakoon```. E.g. ```ovsdb``` will be ```/ovs/arakoon/ovsdb```.

```
$clustername/metadata = {"internal": True|False,
                         "type": "SD|FWK|ABM|NSM",
                         "in_use": True|False}
$clustername/config = "$raw_arakoon_config_format"
```
