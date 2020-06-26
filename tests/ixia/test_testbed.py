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
from lib.ixia_fixtures import ixia_api_serv_ip, ixia_api_serv_user, ixia_api_serv_passwd, ixia_dev
from lib.ixia_helpers import get_neigh_ixia_mgmt_ip, get_neigh_ixia_card, get_neigh_ixia_port 
from lib.common_helpers import get_vlan_subnet, get_addrs_in_subnet
from lib.qos_fixtures import lossless_prio_dscp_map

pytestmark = [pytest.mark.disable_loganalyzer]

def test_testbed(testbed, conn_graph_facts, duthost, ixia_dev, ixia_api_serv_ip, ixia_api_serv_user, ixia_api_serv_passwd, lossless_prio_dscp_map):
    print "==== testbed: {}".format(testbed)
    print "==== conn_graph_facts: {}".format(conn_graph_facts)
    print "==== IXIA API server IP: {}".format(ixia_api_serv_ip)
    print "==== IXIA API server username: {}".format(ixia_api_serv_user)
    print "==== IXIA API server password: {}".format(ixia_api_serv_passwd)
    print "==== IXIA chassis info: {}".format(ixia_dev)
    print "==== DUT hostname: {}".format(duthost.hostname)
    print "==== Vlan Subnet: {}".format(get_vlan_subnet(duthost))
    print "==== Lossless priorities and DSCPs: {}".format(lossless_prio_dscp_map)
        
    print "==== Testbed info"
    device_conn = conn_graph_facts['device_conn']
    for intf in device_conn:
        ixia_mgmt_ip = get_neigh_ixia_mgmt_ip(intf=intf, conn_graph_facts=conn_graph_facts, ixia_dev=ixia_dev)
        ixia_card = get_neigh_ixia_card(intf=intf, conn_graph_facts=conn_graph_facts)
        ixia_port = get_neigh_ixia_port(intf=intf, conn_graph_facts=conn_graph_facts)
        
        print "\tDUT interface: {}".format(intf)
        print "\tIXIA management IP: {}".format(ixia_mgmt_ip)
        print "\tIXIA card: {}".format(ixia_card)
        print "\tIXIA port: {}".format(ixia_port)
        print ""
    
    assert 0