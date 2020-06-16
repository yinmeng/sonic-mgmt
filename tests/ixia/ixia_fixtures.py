import pytest

@pytest.fixture(scope = "module")
def ixia_api_serv_ip(testbed):
    """ 
    In an IXIA testbed, there is no PTF docker. 
    Hence, we use ptf_ip field to store IXIA API server. 
    This fixture returns the IP address of the IXIA API server.
    """
    return testbed['ptf_ip']

@pytest.fixture(scope = "module")
def ixia_dev_ip(duthost, fanouthosts):
    """
    There should be only one IXIA chassis (traffic generator) in an IXIA testbed.
    This IXIA chassis should be the only fanout devce.
    This fixture returns the IP address of the IXIA chassis.
    """
    if len(fanouthosts) != 1:
        return None 
    
    ixia_dev_hostname = fanouthosts.keys()[0]
    return duthost.host.options['inventory_manager'].get_host(ixia_dev_hostname).get_vars()['ansible_host']
    
    
    
    
    
    