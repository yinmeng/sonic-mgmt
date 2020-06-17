import pytest

""" 
In an IXIA testbed, there is no PTF docker. 
Hence, we use ptf_ip field to store IXIA API server. 
This fixture returns the IP address of the IXIA API server.
"""
@pytest.fixture(scope = "module")
def ixia_api_serv_ip(testbed):
    return testbed['ptf_ip']

"""
IXIA chassis are leaf fanout switches in the testbed.
This fixture returns the hostnames and IP addresses of the IXIA chassis in the dictionary format.
"""  
@pytest.fixture(scope = "module")
def ixia_dev(duthost, fanouthosts):
    result = dict()
    ixia_dev_hostnames = fanouthosts.keys()
    for hostname in ixia_dev_hostnames:
        result[hostname] = duthost.host.options['inventory_manager'].get_host(hostname).get_vars()['ansible_host']
    
    return result
    