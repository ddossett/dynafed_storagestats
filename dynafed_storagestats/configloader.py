"""
This module includes functions to deal with reading the configuration files from
UGR.
"""

import logging
import glob
import os
import sys

from dynafed_storagestats.azure import base as azure
from dynafed_storagestats.base import StorageShare, StorageEndpoint
from dynafed_storagestats.dav import base as dav
from dynafed_storagestats.s3 import base as s3
from dynafed_storagestats import exceptions

#############
# Functions #
#############

def factory(plugin):
    """
    Return StorageShare sub-class to use based on the plugin specified in the
    UGR's configuration files.
    """

    _plugin_dict = {
        'libugrlocplugin_dav.so': dav.DAVStorageShare,
        'libugrlocplugin_http.so': dav.DAVStorageShare,
        'libugrlocplugin_s3.so': s3.S3StorageShare,
        'libugrlocplugin_azure.so': azure.AzureStorageShare,
        #'libugrlocplugin_davrucio.so': RucioStorageShare,
        #'libugrlocplugin_dmliteclient.so': DMLiteStorageShare,
    }

    if plugin in _plugin_dict:
        return _plugin_dict.get(plugin)

    else:
        raise exceptions.DSSUnsupportedPluginError(
            error="UnsupportedPlugin",
            plugin=plugin,
        )


def get_conf_files(config_path):
    """
    Returns a list of all files "*.conf" found at the path(s) given by the
    config_path list.
    """
    ############# Creating loggers ################
    _logger = logging.getLogger(__name__)
    ###############################################

    _config_files = []

    # We add UGR's main configuration file if it exists, logs Warning if not.
    if os.path.isfile("/etc/ugr/ugr.conf"):
        _config_files.append("/etc/ugr/ugr.conf")

    else:
        _logger.warning(
            "UGR's '/etc/ugr/ugr.conf' file not found, will be skipped. " \
            "This is normal if script is run on a host that does not run " \
            "Dynafed."
        )

    # We add any other files in the path(s) defined by cli.
    for _element in config_path:
        if os.path.isdir(_element):
            _config_files = _config_files + sorted(glob.glob(_element + "/" + "*.conf"))

        elif os.path.isfile(_element):
            _config_files.append(_element)

        else:
            _logger.error(
                'Element "%s" provided is an invalid directory or file name ' \
                'and will be ignored.',
                _element
            )

    if not _config_files:
        raise exceptions.DSSConfigFileErrorNoConfigFilesFound(
            config_path=config_path,
        )

    return _config_files


def get_storage_endpoints(storage_share_objects, storage_shares_mask=True):
    """
    Gets a list of StorageShare objects, usually obtained after using the
    'get_storage_share_objects'. Checks for unique URL's in them and creates
    a StorageEndpoint object for each and appends each StorageShare which share
    the same URL.
    """
    ############# Creating loggers ################
    _logger = logging.getLogger(__name__)
    ###############################################

    _storage_endpoints = []
    _urls_dict = {}

    # Populate _urls_dict using storage_share_objects URL's as the keys
    # and each StorageShare as a list under these keys.
    for _storage_share_object in storage_share_objects:
        if _storage_share_object.id == storage_shares_mask or storage_shares_mask is True:
            _urls_dict.setdefault(_storage_share_object.uri['url'], [])
            _urls_dict[_storage_share_object.uri['url']].append(_storage_share_object)

    _logger.debug(
        "Dictionary of URL's and associated StorageShares: %s",
        _urls_dict
    )

    # Generate a StorageEnpoint object from the URL and attach any StorageShares
    # that share this URL.
    for _url in _urls_dict:
        _storage_endpoint = StorageEndpoint(_url)

        for _storage_share in _urls_dict[_url]:
            _storage_endpoint.add_storage_share(_storage_share)

        _storage_endpoints.append(_storage_endpoint)

    return _storage_endpoints


def get_storage_shares(config_path):
    """
    Function that returns a list of StorageShare objects generated by calling
    get_storage_share_objects() from the list of storageshares/endpoints
    in UGR's configuration files/directories.
    """
    ############# Creating loggers ################
    _logger = logging.getLogger(__name__)
    ###############################################

    # If no config_path specified set it to UGR's default configurations directory.
    _logger.info(
        "Looking for storage share configuration files in '%s'",
        config_path
    )

    # Obtain configuration files from the given paths in "config_path"
    try:
        _config_files = get_conf_files(config_path)

    except exceptions.DSSConfigFileErrorNoConfigFilesFound as ERR:
        _logger.critical("%s", ERR.debug)
        print("[CRITICAL]%s" % (ERR.debug))
        sys.exit(1)

    # Parse the files for Storage Shares, exit if any issues are detected.
    try:
        _storage_shares = parse_conf_files(_config_files)

    except exceptions.DSSConfigFileErrorIDMismatch as ERR:
        _logger.critical("[%s]%s", ERR.storage_share, ERR.debug)
        print("[CRITICAL][%s]%s" % (ERR.storage_share, ERR.debug))
        sys.exit(1)

    # Storage Shares found.
    return get_storage_share_objects(_storage_shares)


def get_storage_share_objects(storage_shares):
    """
    Returns list of StorageShare objects whose class is defined by the protocol
    plugin configured in UGR's configuration files out of a dictionary of
    storage shares obtained with parse_conf_files().
    """
    ############# Creating loggers ################
    _logger = logging.getLogger(__name__)
    ###############################################

    _storage_share_objects = []

    for _storage_share in storage_shares:
        _logger.debug(
            "[%s]Requesting object class",
            storage_shares[_storage_share]['id']
        )

        # Generate StorageShare objects through factory().
        try:
            _storage_share_object = factory(storage_shares[_storage_share]['plugin'])(storage_shares[_storage_share])
            _logger.debug(
                "[%s]Object class returned: %s",
                storage_shares[_storage_share]['id'],
                type(_storage_share_object)
            )
            _logger.debug(
                "[%s]Object.plugin: %s",
                storage_shares[_storage_share]['id'],
                storage_shares[_storage_share]['plugin']
            )

        except exceptions.DSSUnsupportedPluginError as ERR:
            _logger.error("[%s]%s", storage_shares[_storage_share]['id'], ERR.debug)
            _storage_share_object = StorageShare(storage_shares[_storage_share])
            _storage_share_object.debug.append("[ERROR]" + ERR.debug)
            _storage_share_object.status.append("[ERROR]" + ERR.error_code)

        _storage_share_objects.append(_storage_share_object)

    return _storage_share_objects


def parse_conf_files(config_files):
    """
    Extract storage shares/endpoints and their plugin_settings from the given
    list of UGR's configuration files and return a dictionary where each storage
    share's ID field is the key.
    All the glb.locplugin settings defined for each are stored as dictionary
    keys under each parent SE key, and the locplugin as keys for the dictionary
    "plugin_settings" under each parent SE key.
    """
    ############# Creating loggers ################
    _logger = logging.getLogger(__name__)
    ###############################################

    _storage_shares = {}
    _global_settings = {}

    for _config_file in config_files:
        _logger.info("Reading file '%s'", os.path.realpath(_config_file))

        with open(_config_file, "r") as _file:
            for _line_number, _line in enumerate(_file):
                _line = _line.strip()

                if not _line.startswith("#"):
                    if "glb.locplugin[]" in _line:
                        _plugin, _id, _concurrency, _url = _line.split()[1::]
                        _storage_shares.setdefault(_id, {})
                        _storage_shares[_id].update({'id':_id.strip()})
                        _storage_shares[_id].update({'url':_url.strip()})
                        _storage_shares[_id].update({'plugin':_plugin.split("/")[-1]})

                        _logger.info(
                            "Found storage share '%s' using plugin '%s'. " \
                            "Reading configuration.", \
                            _storage_shares[_id]['id'], _storage_shares[_id]['plugin']
                        )

                    elif "locplugin" in _line:
                        _key, _value = _line.partition(":")[::2]
                        _locid = _key.split('.')[1]

                        # Match an _id in _locid
                        if _locid == '*':
                        # Add any global settings to its own dictionary.
                            _setting = _key.split('*'+'.')[-1]
                            _global_settings.update({_setting:_value.strip()})
                            _logger.info(
                                "Found global setting '%s': %s.",
                                _key,
                                _value
                            )

                        elif _id == _locid:
                            _setting = _key.split(_id+'.')[-1]
                            _storage_shares.setdefault(_id, {})
                            _storage_shares[_id].setdefault('plugin_settings', {})
                            _storage_shares[_id]['plugin_settings'].update({_setting:_value.strip()})
                            _logger.debug(
                                "Found local ID setting '%s'",
                                _key.split(_id+'.')[-1],
                            )

                        else:
                            raise exceptions.DSSConfigFileErrorIDMismatch(
                                storage_share=_id,
                                error="SettingIDMismatch",
                                line_number=_line_number,
                                config_file=_config_file,
                                line=_line.split(":")[0],
                            )

                    else:
                        # Ignore any other lines
                        #print( "I don't know what to do with %s", _line)
                        pass

    # If any global settings were found, apply them to any storage share missing
    # that particular setting. Endpoint specific settings supersede global ones.
    for _setting, _value in _global_settings.items():
        for storage_share in _storage_shares:
            if _setting not in _storage_shares[storage_share]['plugin_settings']:
                _storage_shares[storage_share]['plugin_settings'].update({_setting:_value})
                _logger.debug(
                    "[%s]Applying global setting '%s': %s",
                    _storage_shares[storage_share]['id'],
                    _setting,
                    _value
                )

    return _storage_shares
