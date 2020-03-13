
from ansible_host import AnsibleHost
import pytest
import os
import time
import re
import struct
import random
from qos_fixtures import lossless_prio_dscp_map, conn_graph_facts, leaf_fanouts
from qos_helpers import ansible_stdout_to_str, eos_to_linux_intf, check_mac_table, config_testbed_t0

PFC_GEN_FILE = 'pfc_gen.py'
PFC_GEN_FILE_RELATIVE_PATH = '../../ansible/roles/test/files/helpers/pfc_gen.py'
PFC_GEN_FILE_DEST = '~/pfc_gen.py'
PFC_PKT_COUNT = 1000000000

PTF_FILE_RELATIVE_PATH = '../../ansible/roles/test/files/ptftests/pfc_pause_test.py'
PTF_FILE_DEST = '~/pfc_pause_test.py'
PTF_PKT_COUNT = 50
PTF_PKT_INTVL_SEC = 0.1
PTF_PASS_RATIO_THRESH = 0.75

""" Maximum number of interfaces to test on a DUT """
MAX_TEST_INTFS_COUNT = 4
             
def setup_testbed(ansible_adhoc, testbed, leaf_fanouts):
    """
    @Summary: Set up the testbed
    @param ansible_adhoc: Fixture provided by the pytest-ansible package. Source of the various device objects. It is
    mandatory argument for the class constructors.
    @param testbed: Testbed information
    @param leaf_fanouts: Leaf fanout switches
    """
    
    """ Copy the PFC generator to leaf fanout switches """
    for peer_device in leaf_fanouts:
        peerdev_ans = AnsibleHost(ansible_adhoc, peer_device)
        cmd = "sudo kill -9 $(pgrep -f %s) </dev/null >/dev/null 2>&1 &" % (PFC_GEN_FILE)
        peerdev_ans.shell(cmd)
        file_src = os.path.join(os.path.dirname(__file__), PFC_GEN_FILE_RELATIVE_PATH)
        peerdev_ans.copy(src=file_src, dest=PFC_GEN_FILE_DEST, force=True)
   
    """ Stop PFC storm at the leaf fanout switches """
    for peer_device in leaf_fanouts:
        peerdev_ans = AnsibleHost(ansible_adhoc, peer_device)
        cmd = "sudo kill -9 $(pgrep -f %s) </dev/null >/dev/null 2>&1 &" % (PFC_GEN_FILE) 
        peerdev_ans.shell(cmd) 
                       
    """ Remove existing python scripts on PTF """
    ptf_hostname = testbed['ptf']
    ptf_ans = AnsibleHost(ansible_adhoc, ptf_hostname)
    result = ptf_ans.find(paths=['~/'], patterns="*.py")['files']
    files = [ansible_stdout_to_str(x['path']) for x in result]
    
    for file in files:
        ptf_ans.file(path=file, mode="absent")

    """ Copy the PFC test script to the PTF container """  
    file_src = os.path.join(os.path.dirname(__file__), PTF_FILE_RELATIVE_PATH)
    ptf_ans.copy(src=file_src, dest=PTF_FILE_DEST, force=True)
            
def run_test_t0(ansible_adhoc, 
                testbed, 
                conn_graph_facts, 
                leaf_fanouts, 
                dscp, 
                dscp_bg, 
                queue_paused, 
                send_pause, 
                pfc_pause, 
                pause_prio, 
                pause_time=65535, 
                max_test_intfs_count=128):
    """ 
    @Summary: Run a series of tests on a T0 topology.
    For the T0 topology, we only test Vlan (server-faced) interfaces.    
    @param ansible_adhoc: Fixture provided by the pytest-ansible package. Source of the various device objects. It is
    mandatory argument for the class constructors.
    @param testbed: Testbed information
    @param conn_graph_facts: Testbed topology
    @param leaf_fanouts: Leaf fanout switches
    @param dscp: DSCP value of test data packets
    @param dscp_bg: DSCP value of background data packets
    @param queue_paused: if the queue is expected to be paused
    @param send_pause: send pause frames or not
    @param pfc_pause: send PFC pause frames or not
    @param pause_prio: priority of PFC franme
    @param pause_time: pause time quanta. It is 65535 (maximum pause time quanta) by default.
    @param max_test_intfs_count: maximum count of interfaces to test. By default, it is a very large value to cover all the interfaces.  
    return: Return # of iterations and # of passed iterations for each tested interface.   
    """
    dut_hostname = testbed['dut']
    dut_ans = AnsibleHost(ansible_adhoc, dut_hostname)
    
    ptf_hostname = testbed['ptf']
    ptf_ans = AnsibleHost(ansible_adhoc, ptf_hostname)
    
    """ Clear DUT's PFC counters """
    dut_ans.sonic_pfc_counters(method="clear")
    
    """ Disable DUT's PFC wd """
    dut_ans.shell('sudo pfcwd stop')
    
    """ Configure T0 tesbted and return testbed information """
    dut_intfs, ptf_intfs, ptf_ip_addrs, ptf_mac_addrs = config_testbed_t0(ansible_adhoc, testbed)
    
    results = dict()

    for i in range(min(max_test_intfs_count, len(ptf_intfs))):
        src_index = i
        dst_index = (i + 1) % len(ptf_intfs)
        
        src_intf = ptf_intfs[src_index]
        dst_intf = ptf_intfs[dst_index]
        
        src_ip = ptf_ip_addrs[src_index]
        dst_ip = ptf_ip_addrs[dst_index]
        
        src_mac = ptf_mac_addrs[src_index]
        dst_mac = ptf_mac_addrs[dst_index]
       
        """ DUT interface to pause """
        dut_intf_paused = dut_intfs[dst_index]
                                
        """ Clear MAC table in DUT (host memory and ASIC) """
        dut_ans.shell('sonic-clear fdb all </dev/null >/dev/null 2>&1 &')
        dut_ans.shell('sudo ip -s -s neigh flush all </dev/null >/dev/null 2>&1 &')
        time.sleep(2)
        
        """ Populate the MAC table """
        dut_ans.shell('ping -c 2 %s </dev/null >/dev/null 2>&1 &' % (src_ip))
        dut_ans.shell('ping -c 2 %s </dev/null >/dev/null 2>&1 &' % (dst_ip))
        time.sleep(2)
        
        """ Ensure the MAC table is correct """
        if not check_mac_table(dut_ans, [src_mac, dst_mac]):
            print 'MAC table of DUT is incorrect'
            continue 
        
        if send_pause:            
            peer_device = conn_graph_facts['device_conn'][dut_intf_paused]['peerdevice']
            peer_port = conn_graph_facts['device_conn'][dut_intf_paused]['peerport']
            peer_port_name = eos_to_linux_intf(peer_port)
            peerdev_ans = AnsibleHost(ansible_adhoc, peer_device)
        
            cmd = "nohup sudo python %s -i %s -g -t %d -n %d </dev/null >/dev/null 2>&1 &" % (PFC_GEN_FILE_DEST, peer_port_name, pause_time, PFC_PKT_COUNT)
        
            if pfc_pause:
                cmd = "nohup sudo python %s -i %s -p %d -t %d -n %d </dev/null >/dev/null 2>&1 &" % (PFC_GEN_FILE_DEST, peer_port_name, 2**pause_prio, pause_time, PFC_PKT_COUNT)
                
            """ Start PFC / FC storm """
            peerdev_ans.shell(cmd)
       
            """ Wait for PFC pause frame generation """
            time.sleep(2)
        
        """ Run PTF test """
        intf_info = '--interface %d@%s --interface %d@%s' % (src_index, src_intf, dst_index, dst_intf)
        test_params = 'mac_src=\'%s\';mac_dst=\'%s\';ip_src=\'%s\';ip_dst=\'%s\';dscp=%d;dscp_bg=%d;pkt_count=%d;pkt_intvl=%f;port_src=%d;port_dst=%d;queue_paused=%s' % (src_mac, dst_mac, src_ip, dst_ip, dscp, dscp_bg, PTF_PKT_COUNT, PTF_PKT_INTVL_SEC, src_index, dst_index, queue_paused)
        cmd = 'ptf --test-dir ~/ %s --test-params="%s"' % (intf_info, test_params)
        print cmd 
        stdout = ansible_stdout_to_str(ptf_ans.shell(cmd)['stdout'])
        words = stdout.split()
        
        """ 
        Expected format: "Passes: a / b" 
        where a is # of passed iterations and b is total # of iterations
        """
        if len(words) != 4:
            print 'Unknown PTF test result format'
            results[dut_intf_paused] = [0, 0]

        else:
            results[dut_intf_paused] = [int(words[1]), int(words[3])] 
        time.sleep(1)

        if send_pause:
            """ Stop PFC / FC storm """
            cmd = "sudo kill -9 $(pgrep -f %s) </dev/null >/dev/null 2>&1 &" % (PFC_GEN_FILE)
            peerdev_ans.shell(cmd)
            time.sleep(1)
                    
    return results


def run_test(ansible_adhoc, 
             testbed, 
             conn_graph_facts, 
             leaf_fanouts, 
             dscp, 
             dscp_bg, 
             queue_paused, 
             send_pause, 
             pfc_pause, 
             pause_prio, 
             pause_time=65535, 
             max_test_intfs_count=128):
    """ 
    @Summary: Run a series of tests (only support T0 topology)
    @param ansible_adhoc: Fixture provided by the pytest-ansible package. Source of the various device objects. It is
    mandatory argument for the class constructors.
    @param testbed: Testbed information
    @param conn_graph_facts: Testbed topology
    @param leaf_fanouts: Leaf fanout switches
    @param dscp: DSCP value of test data packets
    @param dscp_bg: DSCP value of background data packets
    @param queue_paused: if the queue is expected to be paused
    @param send_pause: send pause frames or not
    @param pfc_pause: send PFC pause frames or not
    @param pause_prio: priority of PFC franme
    @param pause_time: pause time quanta. It is 65535 (maximum pause time quanta) by default.
    @param max_test_intfs_count: maximum count of interfaces to test. By default, it is a very large value to cover all the interfaces.  
    return: Return # of iterations and # of passed iterations for each tested interface.   
    """
    
    print testbed 
    if testbed['topo']['name'].startswith('t0'):
        return run_test_t0(ansible_adhoc=ansible_adhoc,       
                           testbed=testbed, 
                           conn_graph_facts=conn_graph_facts, leaf_fanouts=leaf_fanouts, 
                           dscp=dscp, 
                           dscp_bg=dscp_bg, 
                           queue_paused=queue_paused, 
                           send_pause=send_pause,
                           pfc_pause=pfc_pause,
                           pause_prio=pause_prio,
                           pause_time=pause_time, 
                           max_test_intfs_count=max_test_intfs_count)
            
    else:
        return None 
    
def test_pfc_pause_lossless(ansible_adhoc,
                            testbed, 
                            conn_graph_facts, 
                            leaf_fanouts, lossless_prio_dscp_map):
    
    """ @Summary: Test if PFC pause frames can pause a lossless priority without affecting the other priorities """    
    setup_testbed(ansible_adhoc, testbed, leaf_fanouts)

    errors = []
    
    """ DSCP vlaues for lossless priorities """
    lossless_dscps = [int(dscp) for prio in lossless_prio_dscp_map for dscp in lossless_prio_dscp_map[prio]]
    """ DSCP values for lossy priorities """
    lossy_dscps = list(set(range(64)) - set(lossless_dscps))
    
    for prio in lossless_prio_dscp_map:
        """ DSCP values of the other lossless priorities """
        other_lossless_dscps = list(set(lossless_dscps) - set(lossless_prio_dscp_map[prio]))
        """ We also need to test some DSCP values for lossy priorities """
        other_dscps = other_lossless_dscps + random.sample(lossy_dscps, k=2)
        
        for dscp in lossless_prio_dscp_map[prio]:
            for dscp_bg in other_dscps:
                results = run_test(ansible_adhoc=ansible_adhoc, 
                                   testbed=testbed,
                                   conn_graph_facts=conn_graph_facts,
                                   leaf_fanouts=leaf_fanouts, 
                                   dscp=dscp,
                                   dscp_bg=dscp_bg,
                                   queue_paused=True,
                                   send_pause=True,
                                   pfc_pause=True,
                                   pause_prio=prio,
                                   pause_time=65535,
                                   max_test_intfs_count=MAX_TEST_INTFS_COUNT)

                """ results should not be none """
                if results is None:
                    assert 0 
            
                errors = dict()
                for intf in results:
                    if len(results[intf]) != 2:
                        continue
                
                    pass_count = results[intf][0]
                    total_count = results[intf][1]

                    if total_count == 0:
                        continue
            
                    if pass_count < total_count * PTF_PASS_RATIO_THRESH:
                        errors[intf] = results[intf]

                if len(errors) > 0:
                    print "errors occured:\n{}".format("\n".join(errors))
                    assert 0 

def test_no_pfc(ansible_adhoc,
                testbed, 
                conn_graph_facts, 
                leaf_fanouts, 
                lossless_prio_dscp_map):
    
    """ @Summary: Test if lossless and lossy priorities can forward packets in the absence of PFC pause frames """
    setup_testbed(ansible_adhoc, testbed, leaf_fanouts)

    errors = []
    
    """ DSCP vlaues for lossless priorities """
    lossless_dscps = [int(dscp) for prio in lossless_prio_dscp_map for dscp in lossless_prio_dscp_map[prio]]
    """ DSCP values for lossy priorities """
    lossy_dscps = list(set(range(64)) - set(lossless_dscps))
    
    for prio in lossless_prio_dscp_map:
        """ DSCP values of the other lossless priorities """
        other_lossless_dscps = list(set(lossless_dscps) - set(lossless_prio_dscp_map[prio]))
        """ We also need to test some DSCP values for lossy priorities """
        other_dscps = other_lossless_dscps + random.sample(lossy_dscps, k=2)
        
        for dscp in lossless_prio_dscp_map[prio]:
            for dscp_bg in other_dscps:
                results = run_test(ansible_adhoc=ansible_adhoc, 
                                   testbed=testbed,
                                   conn_graph_facts=conn_graph_facts,
                                   leaf_fanouts=leaf_fanouts, 
                                   dscp=dscp,
                                   dscp_bg=dscp_bg,
                                   queue_paused=False,
                                   send_pause=False,
                                   pfc_pause=None,
                                   pause_prio=None,
                                   pause_time=None,
                                   max_test_intfs_count=MAX_TEST_INTFS_COUNT)

                """ results should not be none """
                if results is None:
                    assert 0 
            
                errors = dict()
                for intf in results:
                    if len(results[intf]) != 2:
                        continue
                
                    pass_count = results[intf][0]
                    total_count = results[intf][1]

                    if total_count == 0:
                        continue
            
                    if pass_count < total_count * PTF_PASS_RATIO_THRESH:
                        errors[intf] = results[intf]

                if len(errors) > 0:
                    print "errors occured:\n{}".format("\n".join(errors))
                    assert 0 