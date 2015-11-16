from mock import Mock, patch, call
from contextlib import nested
import io
import os
import os.path
import shutil
import filecmp
import pytest

import sshuttle.firewall


def setup_daemon():
    stdin = io.StringIO(u"""ROUTES
2,24,0,1.2.3.0
2,32,1,1.2.3.66
10,64,0,2404:6800:4004:80c::
10,128,1,2404:6800:4004:80c::101f
NSLIST
2,1.2.3.33
10,2404:6800:4004:80c::33
PORTS 1024,1025,1026,1027
GO 1
""")
    stdout = Mock()
    return stdin, stdout


def test_rewrite_etc_hosts():
    if not os.path.isdir("tmp"):
        os.mkdir("tmp")

    with open("tmp/hosts.orig", "w") as f:
        f.write("1.2.3.3 existing\n")

    shutil.copyfile("tmp/hosts.orig", "tmp/hosts")

    sshuttle.firewall.HOSTSFILE = "tmp/hosts"
    sshuttle.firewall.hostmap = {
        'myhost': '1.2.3.4',
        'myotherhost': '1.2.3.5',
    }
    sshuttle.firewall.rewrite_etc_hosts(10)
    with open("tmp/hosts") as f:
        line = f.next()
        s = line.split()
        assert s == ['1.2.3.3', 'existing']

        line = f.next()
        s = line.split()
        assert s == ['1.2.3.4', 'myhost',
                     '#', 'sshuttle-firewall-10', 'AUTOCREATED']

        line = f.next()
        s = line.split()
        assert s == ['1.2.3.5', 'myotherhost',
                     '#', 'sshuttle-firewall-10', 'AUTOCREATED']

        with pytest.raises(StopIteration):
            line = f.next()

    sshuttle.firewall.restore_etc_hosts(10)
    assert filecmp.cmp("tmp/hosts.orig", "tmp/hosts", shallow=False) is True


def test_main():
    with nested(
            patch('sshuttle.firewall.setup_daemon'),
            patch('sshuttle.firewall.get_method')
            ) as (mock_setup_daemon, mock_get_method):
        stdin, stdout = setup_daemon()
        mock_setup_daemon.return_value = stdin, stdout

        sshuttle.firewall.main("test", False)

        stdout.mock_calls == [
            call.write('READY test\n'),
            call.flush(),
            call.write('STARTED\n'),
            call.flush()
        ]
        mock_setup_daemon.mock_calls == [call()]
        mock_get_method.mock_calls == [
            call('test'),
            call().setup_firewall(
                1024, 1026,
                [(10, u'2404:6800:4004:80c::33')],
                10,
                [(10, 64, False, u'2404:6800:4004:80c::'),
                    (10, 128, True, u'2404:6800:4004:80c::101f')],
                True),
            call().setup_firewall(
                1025, 1027,
                [(2, u'1.2.3.33')],
                2,
                [(2, 24, False, u'1.2.3.0'), (2, 32, True, u'1.2.3.66')],
                True),
            call().setup_firewall()(),
            call().setup_firewall(1024, 0, [], 10, [], True),
            call().setup_firewall(1025, 0, [], 2, [], True),
        ]
