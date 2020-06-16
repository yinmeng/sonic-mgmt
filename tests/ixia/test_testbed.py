import logging
import time
import pytest
from common.utilities import wait_until
from common.fixtures.conn_graph_facts import conn_graph_facts
from common.platform.interface_utils import check_interface_information
from common.platform.daemon_utils import check_pmon_daemon_status
from common.reboot import *
from common.platform.device_utils import fanout_switch_port_lookup
from common.helpers import assertions
from ixia_fixtures import ixia_api_serv_ip, ixia_dev_ip

pytestmark = [pytest.mark.disable_loganalyzer]

def test_testbed(testbed, conn_graph_facts, duthost, ixia_api_serv_ip, ixia_dev_ip):
    print "==== testbed: {}".format(testbed)
    print "==== conn_graph_facts: {}".format(conn_graph_facts)
    print "==== IXIA API server IP: {}".format(ixia_api_serv_ip)
    print "==== IXIA chassis IP: {}".format(ixia_dev_ip)
    print "==== DUT hostname: {}".format(duthost.hostname)
    assert 0