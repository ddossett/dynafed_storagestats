"""
Module intended to hold SubClasses, methods and functions to deal with storage
shares in S3 storage types.
"""

import logging

import dynafed_storagestats.base
import dynafed_storagestats.s3.helpers as s3helpers

#############
## Classes ##
#############

class S3StorageShare(dynafed_storagestats.base.StorageShare):
    """
    Subclass that defines methods for obtaining storage stats of S3 endpoints.
    """
    def __init__(self, *args, **kwargs):

        # First we call the super function to initialize the initial attributes
        # given by the StorageShare class.
        super().__init__(*args, **kwargs)

        self.storageprotocol = "S3"

        self.validators.update({
            's3.alternate': {
                'default': 'false',
                'required': False,
                'status_code': '020',
                'valid': ['true', 'false', 'yes', 'no']
            },
            'storagestats.api': {
                'default': 'generic',
                'required': False,
                'status_code': '070',
                'valid': ['ceph-admin', 'generic', 'list-objects'],
            },
            's3.priv_key': {
                'required': True,
                'status_code': '021',
            },
            's3.pub_key': {
                'required': True,
                'status_code': '022',
            },
            's3.region': {
                'default': 'us-east-1',
                'required': False,
                'status_code': '023',
            },
            's3.signature_ver': {
                'default': 's3v4',
                'required': False,
                'status_code': '024',
                'valid': ['s3', 's3v4'],
            },
        })

        # Invoke the validate_plugin_settings() method
        self.validate_plugin_settings()

        # Invoke the validate_schema() method
        self.validate_schema()

        # Obtain bucket name
        if self.plugin_settings['s3.alternate'].lower() == 'true'\
        or self.plugin_settings['s3.alternate'].lower() == 'yes':
            self.uri['bucket'] = self.uri['path'].rpartition("/")[-1]

        else:
            self.uri['bucket'], self.uri['domain'] = self.uri['netloc'].partition('.')[::2]

        self.star_fields['storage_share'] = self.uri['bucket']


    def get_storagestats(self):
        """
        Connect to the storage endpoint with the defined or generic API's
        to obtain the storage status.
        """
        ############# Creating loggers ################

        ###############################################

        # Getting the storage Stats CephS3's Admin API
        if self.plugin_settings['storagestats.api'].lower() == 'ceph-admin':
            s3helpers.ceph_admin(self)

        # Getting the storage Stats AWS S3 API
        #elif self.plugin_settings['storagestats.api'].lower() == 'aws-cloudwatch':

        # Generic list all objects and add sizes using list-objectsv2 AWS-Boto3
        # API, should work for any compatible S3 endpoint.
        elif self.plugin_settings['storagestats.api'].lower() == 'generic' \
        or   self.plugin_settings['storagestats.api'].lower() == 'list-objects':
            s3helpers.list_objects(self)


    def validate_schema(self):
        """
        Used to translate s3 into http/https since requests doesn't
        support the former schema.
        """
        ############# Creating loggers ################
        _logger = logging.getLogger(__name__)
        ###############################################

        _logger.debug(
            "[%s]Validating URN schema: %s",
            self.id,
            self.uri['scheme']
        )

        if self.uri['scheme'] == 's3':
            if self.plugin_settings['ssl_check']:
                _logger.debug(
                    "[%s]Using URN schema: https",
                    self.id
                )
                self.uri['scheme'] = 'https'

            else:
                _logger.debug(
                    "[%s]Using URN schema: http",
                    self.id
                )
                self.uri['scheme'] = 'http'

        else:
            _logger.debug(
                "[%s]Using URN schema: %s",
                self.id,
                self.uri['scheme']
            )
