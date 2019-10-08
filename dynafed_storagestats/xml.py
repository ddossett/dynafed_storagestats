"""Functions to deal with the formatting and handling  of XML data."""

import copy
import datetime
import time

import uuid

from io import BytesIO
from lxml import etree

import dynafed_storagestats.exceptions


#############
# Functions #
#############

def add_xml_getcontentlength(content):
    """Sum contentlength attribute of all files in content string.

    Iterates and sums through all the "contentlength sub-elements" returning the
    total byte count.

    Arguments:
    content -- string containing endpoint's response in XML format. Generated by
               functions in dynafed_storagestats.dav.helpers.

    Returns:
    _bytesused -- int representing sum of all files' sizes.
    _filecount -- int reprsenting sum of all files processed.

    """

    _xml = etree.fromstring(content)
    _bytesused = 0
    _filecount = 0

    for _tags in _xml.iter('{DAV:}getcontentlength'):
        if isinstance(_tags.text, str):
            _bytesused += int(_tags.text)
            _filecount += 1

    return (_bytesused, _filecount)


def create_rfc4331_request():
    """Create XML RFC4331 request.

    Creates an XML for requesting quota and free space on remote WebDAV server.
    For more information:
    https://tools.ietf.org/html/rfc4331

    Returns:
    String in XML format.

    """

    _root = etree.Element("propfind", xmlns="DAV:")
    _prop = etree.SubElement(_root, "prop")
    etree.SubElement(_prop, "quota-available-bytes")
    etree.SubElement(_prop, "quota-used-bytes")
    _tree = etree.ElementTree(_root)
    _buff = BytesIO()
    _tree.write(_buff, xml_declaration=True, encoding='UTF-8')

    return _buff.getvalue()


def format_StAR(storage_endpoints):
    """Create XML file representing Dynafed site storage stats in StAR format.

    Creates XML object with storage stats in the StAR format.
    Heavily based on the star-accounting.py script by Fabrizio Furano
    http://svnweb.cern.ch/world/wsvn/lcgdm/lcg-dm/trunk/scripts/StAR-accounting/star-accounting.py

    Arguments:
    storage_endpoints -- List of dynafed_storagestats StorageEndpoint objects.

    Returns:
    String in XML format.

    """
    SR_namespace = "http://eu-emi.eu/namespaces/2011/02/storagerecord"
    SR = "{%s}" % SR_namespace
    NSMAP = {"sr": SR_namespace}
    xmlroot = etree.Element(SR + "StorageUsageRecords", nsmap=NSMAP)

    for endpoint in storage_endpoints:
        for share in endpoint.storage_shares:
            data = etree.Element(SR + "StorageUsageRecords", nsmap=NSMAP)

            # update XML
            rec = etree.SubElement(xmlroot, SR + 'StorageUsageRecord')
            rid = etree.SubElement(rec, SR + 'RecordIdentity')
            rid.set(SR + "createTime", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(datetime.datetime.now().timestamp())))

            # StAR StorageShare field (Optional)
            if share.star_fields['storage_share']:
                sshare = etree.SubElement(rec, SR + "StorageShare")
                sshare.text = share.star_fields['storageshare']

            # StAR StorageSystem field (Required)
            if share.uri['hostname']:
                ssys = etree.SubElement(rec, SR + "StorageSystem")
                ssys.text = share.uri['hostname']

            # StAR recordID field (Required)
            recid = share.id + "-" + str(uuid.uuid1())
            rid.set(SR + "recordId", recid)

        #    subjid = etree.SubElement(rec, SR + 'SubjectIdentity')

        #    if endpoint.group:
        #      grouproles = endpoint.group.split('/')
        #      # If the last token is Role=... then we fetch the role and add it to the record
        #    tmprl = grouproles[-1]
        #    if tmprl.find('Role=') != -1:
        #      splitroles = tmprl.split('=')
        #      if (len(splitroles) > 1):
        #        role = splitroles[1]
        #        grp = etree.SubElement(subjid, SR + "GroupAttribute" )
        #        grp.set( SR + "attributeType", "role" )
        #        grp.text = role
        #      # Now drop this last token, what remains is the vo identifier
        #      grouproles.pop()
        #
        #    # The voname is the first token
        #    voname = grouproles.pop(0)
        #    grp = etree.SubElement(subjid, SR + "Group")
        #    grp.text = voname
        #
        #    # If there are other tokens, they are a subgroup
        #    if len(grouproles) > 0:
        #      subgrp = '/'.join(grouproles)
        #      grp = etree.SubElement(subjid, SR + "GroupAttribute" )
        #      grp.set( SR + "attributeType", "subgroup" )
        #      grp.text = subgrp
        #
        #    if endpoint.user:
        #      usr = etree.SubElement(subjid, SR + "User")
        #      usr.text = endpoint.user

            # StAR Site field (Optional)
            ## Review
            # if endpoint.site:
            #     st = etree.SubElement(subjid, SR + "Site")
            #     st.text = endpoint.site

            # StAR StorageMedia field (Optional)
            # too many e vars here below, wtf?
            ## Review
            # if endpoint.storagemedia:
            #     e = etree.SubElement(rec, SR + "StorageMedia")
            #     e.text = endpoint.storagemedia

            # StAR StartTime field (Required)
            e = etree.SubElement(rec, SR + "StartTime")
            e.text = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(share.stats['starttime']))

            # StAR EndTime field (Required)
            e = etree.SubElement(rec, SR + "EndTime")
            e.text = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(share.stats['endtime']))

            # StAR FileCount field (Optional)
            if share.stats['filecount']:
                e = etree.SubElement(rec, SR + "FileCount")
                e.text = str(share.stats['filecount'])

            # StAR ResourceCapacityUsed (Required)
            e1 = etree.SubElement(rec, SR + "ResourceCapacityUsed")
            e1.text = str(share.stats['bytesused'])

            # StAR ResourceCapacityAllocated (Optional)
            e3 = etree.SubElement(rec, SR + "ResourceCapacityAllocated")
            e3.text = str(share.stats['quota'])

            # if not endpoint.logicalcapacityused:
            #     endpoint.logicalcapacityused = 0
            #
            # e2 = etree.SubElement(rec, SR + "LogicalCapacityUsed")
            # e2.text = str(endpoint.logicalcapacityused)

            root = data.getroottree().getroot()
            sub_element = copy.deepcopy(root[0])
            xmlroot.append(sub_element)

    return etree.tostring(xmlroot, pretty_print=True, encoding='unicode')


def process_rfc4331_response(response, storage_share):
    """Process response from DAV server when using RFC4331 method.

    Check what was the response from a DAV server after it has been asked
    to provide used space and free space using the RFC4331, and process the
    results.

    Arguments:
    response -- string in XML format containing endpoint's response.
    storage_share -- dynafed_storagestats StorageShare object.

    """
    _tree = etree.fromstring(response.content)
    _node = _tree.find('.//{DAV:}quota-available-bytes').text

    # Check that we got the requested information. If not, then
    # the method is not supported.
    if _node is None:
        raise dynafed_storagestats.exceptions.ErrorDAVQuotaMethod(
            error="UnsupportedMethod"
        )

    # Assign the values returned by the endpoint.
    storage_share.stats['bytesused'] = int(_tree.find('.//{DAV:}quota-used-bytes').text)
    storage_share.stats['bytesfree'] = int(_tree.find('.//{DAV:}quota-available-bytes').text)

    # Determine which value to use for the quota.
    if storage_share.plugin_settings['storagestats.quota'] == 'api':
        storage_share.stats['quota'] = (storage_share.stats['bytesused']
                                        + storage_share.stats['bytesfree'])

        # If quota-available-bytes is reported as '0' could be
        # because no quota is provided, or the endpoint is
        # actually full. We warn for the operator to make a
        # decision.
        if storage_share.stats['bytesfree'] == 0:
            raise dynafed_storagestats.exceptions.DAVZeroQuotaWarning(
                debug=str(response.content)
            )

    else:
        storage_share.stats['quota'] = int(storage_share.plugin_settings['storagestats.quota'])
        # Calculate free space using pre-set quota.
        storage_share.stats['bytesfree'] = (storage_share.stats['quota']
                                            - storage_share.stats['bytesused'])
