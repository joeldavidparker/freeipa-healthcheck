#
# Copyright (C) 2019 FreeIPA Contributors see COPYING for license
#

from base import BaseTest
from unittest.mock import Mock, patch
from util import capture_results, CAInstance

from ipahealthcheck.core import config, constants
from ipahealthcheck.ipa.plugin import registry
from ipahealthcheck.ipa.certs import IPARAAgent

from ipalib import errors
from ipapython.dn import DN
from ipapython.ipaldap import LDAPClient, LDAPEntry

from ldap import OPT_X_SASL_SSF_MIN


class IPACertificate:
    def __init__(self, serial_number=1):
        self.subject = 'CN=RA AGENT'
        self.issuer = 'CN=ISSUER'
        self.serial_number = serial_number


class mock_ldap:
    SCOPE_BASE = 1
    SCOPE_ONELEVEL = 2
    SCOPE_SUBTREE = 4

    def __init__(self, ldapentry):
        """Initialize the results that we will return from get_entries"""
        self.results = ldapentry

    def get_entries(self, base_dn, scope=SCOPE_SUBTREE, filter=None,
                    attrs_list=None, get_effective_rights=False, **kwargs):
        if self.results is None:
            raise errors.NotFound(reason='test')
        return self.results


class mock_ldap_conn:
    def set_option(self, option, invalue):
        pass

    def get_option(self, option):
        if option == OPT_X_SASL_SSF_MIN:
            return 256

    def search_s(self, base, scope, filterstr=None,
                 attrlist=None, attrsonly=0):
        return tuple()


class TestNSSAgent(BaseTest):
    cert = IPACertificate()
    patches = {
        'ipaserver.install.installutils.check_server_configuration':
        Mock(return_value=None),
        'ldap.initialize':
        Mock(return_value=mock_ldap_conn()),
        'ipaserver.install.cainstance.CAInstance':
        Mock(return_value=CAInstance()),
        'ipalib.x509.load_certificate_from_file':
        Mock(return_value=cert),
    }

    def test_nss_agent_ok(self):

        attrs = dict(
            description=['2;1;CN=ISSUER;CN=RA AGENT'],
            usercertificate=[self.cert],
        )
        fake_conn = LDAPClient('ldap://localhost')
        ldapentry = LDAPEntry(fake_conn, DN('uid=ipara,ou=people,o=ipaca'))
        for attr, values in attrs.items():
            ldapentry[attr] = values

        framework = object()
        registry.initialize(framework)
        f = IPARAAgent(registry)

        f.conn = mock_ldap([ldapentry])
        f.config = config.Config()
        self.results = capture_results(f)

        # A valid call relies on a success to be set by core
        assert len(self.results) == 0

    def test_nss_agent_no_description(self):

        attrs = dict(
            usercertificate=[self.cert],
        )
        fake_conn = LDAPClient('ldap://localhost')
        ldapentry = LDAPEntry(fake_conn, DN('uid=ipara,ou=people,o=ipaca'))
        for attr, values in attrs.items():
            ldapentry[attr] = values

        framework = object()
        registry.initialize(framework)
        f = IPARAAgent(registry)

        f.conn = mock_ldap([ldapentry])
        f.config = config.Config()
        self.results = capture_results(f)
        result = self.results.results[0]

        assert result.severity == constants.ERROR
        assert result.kw.get('msg') == 'RA agent is missing description'

    @patch('ipalib.x509.load_certificate_from_file')
    def test_nss_agent_load_failure(self, mock_load_cert):

        mock_load_cert.side_effect = IOError('test')

        framework = object()
        registry.initialize(framework)
        f = IPARAAgent(registry)

        f.config = config.Config()
        self.results = capture_results(f)
        result = self.results.results[0]

        assert result.severity == constants.ERROR
        assert result.kw.get('msg') == 'Unable to load RA cert: test'

    def test_nss_agent_no_entry_found(self):

        framework = object()
        registry.initialize(framework)
        f = IPARAAgent(registry)

        f.conn = mock_ldap(None)  # None == NotFound
        f.config = config.Config()
        self.results = capture_results(f)
        result = self.results.results[0]

        assert result.severity == constants.ERROR
        assert result.kw.get('msg') == 'RA agent not found in LDAP'

    def test_nss_agent_too_many(self):

        attrs = dict(
            description=['2;1;CN=ISSUER;CN=RA AGENT'],
            usercertificate=[self.cert],
        )
        fake_conn = LDAPClient('ldap://localhost')
        ldapentry = LDAPEntry(fake_conn, DN('uid=ipara,ou=people,o=ipaca'))
        for attr, values in attrs.items():
            ldapentry[attr] = values

        ldapentry2 = LDAPEntry(fake_conn, DN('uid=ipara2,ou=people,o=ipaca'))
        for attr, values in attrs.items():
            ldapentry[attr] = values

        framework = object()
        registry.initialize(framework)
        f = IPARAAgent(registry)

        f.conn = mock_ldap([ldapentry, ldapentry2])
        f.config = config.Config()
        self.results = capture_results(f)
        result = self.results.results[0]

        assert result.severity == constants.ERROR
        assert result.kw.get('msg') == 'Too many RA agent entries found, 2'

    def test_nss_agent_nonmatching_cert(self):

        cert2 = IPACertificate(2)

        attrs = dict(
            description=['2;1;CN=ISSUER;CN=RA AGENT'],
            usercertificate=[cert2],
        )
        fake_conn = LDAPClient('ldap://localhost')
        ldapentry = LDAPEntry(fake_conn, DN('uid=ipara,ou=people,o=ipaca'))
        for attr, values in attrs.items():
            ldapentry[attr] = values

        framework = object()
        registry.initialize(framework)
        f = IPARAAgent(registry)

        f.conn = mock_ldap([ldapentry])
        f.config = config.Config()
        self.results = capture_results(f)
        result = self.results.results[0]

        assert result.severity == constants.ERROR
        assert result.kw.get('msg') == 'RA agent certificate not found in LDAP'

    def test_nss_agent_multiple_certs(self):

        cert2 = IPACertificate(2)

        attrs = dict(
            description=['2;1;CN=ISSUER;CN=RA AGENT'],
            usercertificate=[cert2, self.cert],
        )
        fake_conn = LDAPClient('ldap://localhost')
        ldapentry = LDAPEntry(fake_conn, DN('uid=ipara,ou=people,o=ipaca'))
        for attr, values in attrs.items():
            ldapentry[attr] = values

        framework = object()
        registry.initialize(framework)
        f = IPARAAgent(registry)

        f.conn = mock_ldap([ldapentry])
        f.config = config.Config()
        self.results = capture_results(f)

        assert len(self.results) == 0
