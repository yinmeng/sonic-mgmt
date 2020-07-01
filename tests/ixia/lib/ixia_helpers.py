import re 
# Import the RestPy module
from ixnetwork_restpy import SessionAssistant, Files

DEFAULT_LOG_FILE_NAME = 'restpy.log'

"""
@summary: given a DUT interface, return the management IP address of its neighbor IXIA device
@param intf: DUT interface
@param conn_graph_facts: testbed connectivity graph
@param ixia_dev: the mapping of hostname to IP address of IXIA devices
@return the management IP address of its neighbor IXIA device or None if we cannot find it
"""
def get_neigh_ixia_mgmt_ip(intf, conn_graph_facts, ixia_dev):
    device_conn = conn_graph_facts['device_conn']
    if intf not in device_conn:
        return None 
    
    ixia_dev_hostname = device_conn[intf]['peerdevice']
    if ixia_dev_hostname not in ixia_dev:
        return None 
    
    return ixia_dev[ixia_dev_hostname]

"""
@summary: given a DUT interface, return the card of its neighbor IXIA device
@param intf: DUT interface
@param conn_graph_facts: testbed connectivity graph
@return the card of its neighbor IXIA device or None if we cannot find it
"""
def get_neigh_ixia_card(intf, conn_graph_facts):
    device_conn = conn_graph_facts['device_conn']
    if intf not in device_conn:
        return None 
    
    ixia_intf = device_conn[intf]['peerport']
    pattern = r'Card(\d+)/Port(\d+)'
    m = re.match(pattern, ixia_intf)

    if m is None:
        return None 
    else:
        return m.group(1)    

"""
@summary: given a DUT interface, return the port of its neighbor IXIA device
@param intf: DUT interface
@param conn_graph_facts: testbed connectivity graph
@return the port of its neighbor IXIA device or None if we cannot find it
"""
def get_neigh_ixia_port(intf, conn_graph_facts):
    device_conn = conn_graph_facts['device_conn']
    if intf not in device_conn:
        return None
    
    ixia_intf = device_conn[intf]['peerport']
    pattern = r'Card(\d+)/Port(\d+)'
    m = re.match(pattern, ixia_intf)

    if m is None:
        return None 
    else:
        return m.group(2)  


def create_session(server_ip, username, password, log_file=DEFAULT_LOG_FILE_NAME):
    
    return SessionAssistant(IpAddress=server_ip, RestPort=None, UserName=username, Password=password, 
                            SessionName=None, SessionId=None, ApiKey=None, ClearConfig=True, 
                            LogLevel='all', LogFilename=log_file)


def remove_session(session):
    session.Session.remove()

  
"""
Configure ports of the IXIA chassis

@param session: IXIA session
@param port_list: List of port locations. Each entry has four keys: 'ip', 'card_id', 'port_id', 'speed'
@return the list of ports if the configuration succeeds. Otherwise return None 
"""
def config_ports(session, port_list):
    port_map = session.PortMapAssistant()
    vports = list()
        
    index = 1
    for port in port_list:        
        port_name = 'Port_{}'.format(index)
        index += 1
        """ Map a test port location (ip, card, port) to a virtual port (name) """
        vports.append(port_map.Map(IpAddress=port['ip'], CardId=port['card_id'], 
                                   PortId=port['port_id'], Name=port_name))
    
    """ Connect all mapped virtual ports to test port locations """
    port_map.Connect()
    
    ixnetwork = session.Ixnetwork
    i = 0
    for vport in ixnetwork.Vport.find():
        vport.L1Config.CurrentType = 'novusHundredGigLanFcoe'
        vport.L1Config.NovusHundredGigLan.Fcoe.PfcPriorityGroups = [0,1,2,3,4,5,6,7]
        vport.L1Config.NovusHundredGigLan.IeeeL1Defaults = False
        vport.L1Config.NovusHundredGigLan.EnableAutoNegotiation = False
        vport.L1Config.NovusHundredGigLan.Speed = 'speed{}g'.format(port_list[i]['speed']/1000)
        i += 1
        
    return vports

"""
Configure capturing packets on a IXIA port

@param session: IXIA session
@param port: port to configure
@param capture_control_pkt: if enable capturing control plane packets
@param capture_data_pkt: if enable capturing data plane packets 
"""
def config_port_capture_pkt(session, port, capture_control_pkt, capture_data_pkt):
    if capture_control_pkt or capture_data_pkt:
        port.RxMode = 'captureAndMeasure'
        port.Capture.SoftwareEnabled = capture_control_pkt
        port.Capture.HardwareEnabled = capture_data_pkt

"""
Create a topology 

@param session: IXIA session
@param name: Topology name
@param ports: List of ports
@param ip_start: Start value of IPv4 addresses, e.g., 192.168.1.1
@param ip_incr_step: Increment step of IPv4 addresses, e.g., 0.0.0.1
@param gw_start: Start value of gateway IPv4 addresses, e.g., 192.168.1.1
@param gw_incr_step: Increment step of gateway IPv4 addresses, e.g., 0.0.0.0 (no increment)    
@return the topology
"""
def create_topology(session, name, ports, ip_start, ip_incr_step, gw_start, gw_incr_step):
    ixnetwork = session.Ixnetwork
    
    topology = ixnetwork.Topology.add(Name=name, Ports=ports)
    ixnetwork.info('Creating Topology Group {}'.format(name))
    
    device_group = topology.DeviceGroup.add(Name=name+' DG', Multiplier='1')
    ethernet = device_group.Ethernet.add(Name='Ethernet')
    
    ipv4 = ethernet.Ipv4.add(Name='Ipv4')
    ipv4.Address.Increment(start_value=ip_start, step_value=ip_incr_step)
    ipv4.Address.Steps.Step = ip_incr_step
    
    ipv4.GatewayIp.Increment(start_value=gw_start, step_value=gw_incr_step)
    ipv4.GatewayIp.Steps.Step = gw_incr_step
    
    ixnetwork.info('Configure IPv4')
    
    return topology


"""
Start protocols (e.g., IP and Ethernet)

@param session: IXIA session
"""
def start_protocols(session):
    ixnetwork = session.Ixnetwork
    ixnetwork.StartAllProtocols(Arg1='sync')

    ixnetwork.info('Verify protocol sessions\n')
    protocolSummary = session.StatViewAssistant('Protocols Summary')
    protocolSummary.CheckCondition('Sessions Not Started', protocolSummary.EQUAL, 0)
    protocolSummary.CheckCondition('Sessions Down', protocolSummary.EQUAL, 0)
    ixnetwork.info(protocolSummary)


""" 
Create a raw Ethernet/IP traffic item 

@param session: IXIA session
@param name: name of traffic item
@param source: source endpoint
@param destination: destination endpoint
@param src_mac: source MAC address
@param dst_mac: destination MAC address
@param src_ip: source IP address
@param dst_ip: destination IP address
@param dscp_list: list of DSCPs 
@param pkt_size: packet size 
@param pkt_count: packet count (can be None if you want to keep running the traffic)
@param rate_percent: percentage of line rate
@param start_delay: start delay in second
@return the created traffic item
"""
def create_raw_traffic(session, name, source, destination, src_mac=None, dst_mac=None, src_ip=None, 
                       dst_ip=None, dscp_list=None, pkt_size=64, pkt_count=None, rate_percent=100, 
                       start_delay=0):
    
    ixnetwork = session.Ixnetwork
    traffic_item = ixnetwork.Traffic.TrafficItem.add(Name=name, BiDirectional=False, TrafficType='raw')
    
    traffic_item.EndpointSet.add(Sources=source.Protocols.find(), Destinations=destination.Protocols.find())
    
    traffic_config = traffic_item.ConfigElement.find()[0]
    traffic_config.FrameRate.update(Type='percentLineRate', Rate=rate_percent)
    traffic_config.FrameRateDistribution.PortDistribution = 'splitRateEvenly'
    traffic_config.FrameSize.FixedSize = pkt_size
    
    if pkt_count is not None and pkt_count > 0:
        traffic_config.TransmissionControl.update(Type='fixedFrameCount', FrameCount=pkt_count)
    else:
        traffic_config.TransmissionControl.update(Type='continuous')
    
    if start_delay > 0:
        traffic_config.TransmissionControl.update(StartDelayUnits='nanoseconds', 
                                                  StartDelay=start_delay*(10**6))
    
    """ Add IP header """
    ip_stack_obj = create_pkt_hdr(ixnetwork=ixnetwork, traffic_item=traffic_item, 
                                  pkt_hdr_to_add='^IPv4', append_to_stack='Ethernet II') 
    
    eth_stack_obj = traffic_item.ConfigElement.find().Stack.find('Ethernet II').Field.find()
    set_eth_fields(eth_stack_obj=eth_stack_obj, src_mac=src_mac, dst_mac=dst_mac)
    set_ip_fields(ip_stack_obj=ip_stack_obj, src_ip=src_ip, dst_ip=dst_ip, dscp_list=dscp_list)    

    traffic_item.Tracking.find()[0].TrackBy = ['flowGroup0']
    
    """ Push ConfigElement settings down to HighLevelStream resources """
    traffic_item.Generate()
    
    return traffic_item


"""
Create an IPv4 traffic item 

@param session: IXIA session
@param name: name of traffic item
@param source: source endpoints
@param destination: destination endpoints
@param pkt_size: packet size 
@param pkt_count: packet count 
@param duration: traffic duration in second (positive integer only!)  
@param rate_percent: percentage of line rate 
@param start_delay: start delay in second 
@param dscp_list: list of DSCPs 
@param lossless_prio_list: list of lossless priorities
@param ecn_capable: if packets can get ECN marked 
@return the created traffic item 
"""
def create_ipv4_traffic(session, name, source, destination, pkt_size=64, pkt_count=None, duration=None, 
                        rate_percent=100, start_delay=0, dscp_list=None, lossless_prio_list=None, 
                        ecn_capable=False):
    
    ixnetwork = session.Ixnetwork
    
    traffic_item = ixnetwork.Traffic.TrafficItem.add(Name=name, BiDirectional=False, TrafficType='ipv4')
    traffic_item.EndpointSet.add(Sources=source, Destinations=destination)
    
    traffic_config  = traffic_item.ConfigElement.find()[0]
    """ Todo: add sending rate support """
    traffic_config.FrameRate.update(Type='percentLineRate', Rate=rate_percent)
    traffic_config.FrameRateDistribution.PortDistribution = 'splitRateEvenly'
    traffic_config.FrameSize.FixedSize = pkt_size
    
    if pkt_count is not None and duration is not None:
        print 'You can only specify either pkt_count or duration'
        return None 
        
    if pkt_count is not None:
        traffic_config.TransmissionControl.update(Type='fixedFrameCount', FrameCount=pkt_count)
            
    elif duration is not None:
        if type(duration) != int or duration <= 0:
            print 'Invalid duration value {} (positive integer only)'.format(duration)
            return None
        else:
            traffic_config.TransmissionControl.update(Type='fixedDuration', Duration=duration)
    
    else:
        traffic_config.TransmissionControl.update(Type='continuous')
    
    if start_delay > 0:
        traffic_config.TransmissionControl.update(StartDelayUnits='nanoseconds', 
                                                  StartDelay=start_delay*(10**6))
    
    if dscp_list is not None and len(dscp_list) > 0:
        phb_field = traffic_item.ConfigElement.find().Stack.find('IPv4').Field.\
                    find(DisplayName='Default PHB')
        
        phb_field.ActiveFieldChoice = True
        phb_field.ValueType = 'valueList'
        phb_field.ValueList = dscp_list 
    
    """ Set ECN bits to 10 (ECN capable) """
    if ecn_capable:
        phb_field = traffic_item.ConfigElement.find().Stack.find('IPv4').\
                    Field.find(FieldTypeId='ipv4.header.priority.ds.phb.defaultPHB.unused')
        phb_field.ActiveFieldChoice = True
        phb_field.ValueType = 'singleValue'
        phb_field.SingleValue = 2 
    
    if lossless_prio_list is not None and len(lossless_prio_list) > 0:
        eth_stack = traffic_item.ConfigElement.find()[0].Stack.find(DisplayName='Ethernet II')
        pfc_queue = eth_stack.Field.find(DisplayName='PFC Queue')
        pfc_queue.ValueType = 'valueList'
        pfc_queue.ValueList = lossless_prio_list
    
    traffic_item.Tracking.find()[0].TrackBy = ['flowGroup0']
    
    """ Push ConfigElement settings down to HighLevelStream resources """
    traffic_item.Generate()
    
    return traffic_item
    
"""
Create a pause traffic item 

@param session: IXIA session
@param name: Name of traffic item
@param source: source endpoint
@param pkt_per_sec: packets per second 
@param pkt_count: packet count 
@param duration: traffic duration in second (positive integer only!) 
@param start_delay: start delay in second
@param global_pause: if the generated packets are global pause (IEEE 802.3X PAUSE)
@param pause_prio_list: list of priorities to pause. Only valid when global_pause is False
@return the created traffic item or None if any errors happen
"""
def create_pause_traffic(session, name, source, pkt_per_sec, pkt_count=None, duration=None, 
                         start_delay=0, global_pause=False, pause_prio_list=[]):
        
    if pause_prio_list is not None:
        for prio in pause_prio_list:
            if prio < 0 or prio > 7:
                print 'Invalid pause priorities {}'.format(pause_prio_list)
                return None 
    
    ixnetwork = session.Ixnetwork
    traffic_item = ixnetwork.Traffic.TrafficItem.add(Name=name, BiDirectional=False, TrafficType='raw')
    
    """ Since PFC packets will not be forwarded by the switch, so destinations are actually not used """
    traffic_item.EndpointSet.add(Sources=source.Protocols.find(), Destinations=source.Protocols.find())
    
    traffic_config = traffic_item.ConfigElement.find()[0]
    traffic_config.FrameRate.update(Type='framesPerSecond', Rate=pkt_per_sec)
    traffic_config.FrameRateDistribution.PortDistribution = 'splitRateEvenly'
    traffic_config.FrameSize.FixedSize = 64
    
    if pkt_count is not None and duration is not None:
        print 'You can only specify either pkt_count or duration'
        return None 
    
    if pkt_count is not None:
        traffic_config.TransmissionControl.update(Type='fixedFrameCount', FrameCount=pkt_count)
            
    elif duration is not None:
        if type(duration) != int or duration <= 0:
            print 'Invalid duration value {} (positive integer only)'.format(duration)
            return None
        else:
            traffic_config.TransmissionControl.update(Type='fixedDuration', Duration=duration)
            
    else:
        traffic_config.TransmissionControl.update(Type='continuous')
    
    if start_delay > 0:
        traffic_config.TransmissionControl.update(StartDelayUnits='nanoseconds', 
                                                  StartDelay=start_delay*(10**6))
    
    """ Add PFC header """
    pfc_stack_obj = create_pkt_hdr(ixnetwork=ixnetwork, 
                                   traffic_item=traffic_item, 
                                   pkt_hdr_to_add='^PFC PAUSE \(802.1Qbb\)', 
                                   append_to_stack='Ethernet II')      
    
    """ Construct global pause and PFC packets """
    if global_pause:
        set_global_pause_fields(pfc_stack_obj)
    else:
        set_pfc_fields(pfc_stack_obj, pause_prio_list)
    
    """ Remove Ethernet header """
    traffic_item.ConfigElement.find()[0].Stack.find(DisplayName="Ethernet II").Remove()

    traffic_item.Tracking.find()[0].TrackBy = ['flowGroup0']
    
    """ Push ConfigElement settings down to HighLevelStream resources """
    traffic_item.Generate()
    
    return traffic_item


def set_global_pause_fields(pfc_stack_obj):
    code = pfc_stack_obj.find(DisplayName='Control opcode')
    code.ValueType = 'singleValue'
    code.SingleValue = '1'
    
    """ This field is pause duration in global pause packet """
    prio_enable_vector = pfc_stack_obj.find(DisplayName='priority_enable_vector')
    prio_enable_vector.ValueType = 'singleValue'
    prio_enable_vector.SingleValue = 'ffff'
        
    """ pad bytes """
    for i in range(8):
        pause_duration = pfc_stack_obj.find(DisplayName='PFC Queue {}'.format(i))
        pause_duration.ValueType = 'singleValue'
        pause_duration.SingleValue = '0'


def set_eth_fields(eth_stack_obj, src_mac, dst_mac):
    if src_mac is not None:
        src_mac_field = eth_stack_obj.find(DisplayName='Source MAC Address')
        src_mac_field.ValueType = 'singleValue'
        src_mac_field.SingleValue = src_mac
    
    if dst_mac is not None:
        dst_mac_field = eth_stack_obj.find(DisplayName='Destination MAC Address')
        dst_mac_field.ValueType = 'singleValue'
        dst_mac_field.SingleValue = dst_mac


def set_ip_fields(ip_stack_obj, src_ip, dst_ip, dscp_list):
    if src_ip is not None:
        src_ip_field = ip_stack_obj.find(DisplayName='Source Address')
        src_ip_field.ValueType = 'singleValue'
        src_ip_field.SingleValue = src_ip
    
    if dst_ip is not None:
        dst_ip_field = ip_stack_obj.find(DisplayName='Destination Address')
        dst_ip_field.ValueType = 'singleValue'
        dst_ip_field.SingleValue = dst_ip
        
    if dscp_list is not None and len(dscp_list) > 0:
        phb_field = ip_stack_obj.find(DisplayName='Default PHB')
        phb_field.ActiveFieldChoice = True
        phb_field.ValueType = 'valueList'
        phb_field.ValueList = dscp_list 
    
        
def set_pfc_fields(pfc_stack_obj, pause_prio_list):
    code = pfc_stack_obj.find(DisplayName='Control opcode')
    code.ValueType = 'singleValue'
    code.SingleValue = '101'
    
    prio_enable_vector = pfc_stack_obj.find(DisplayName='priority_enable_vector')
    prio_enable_vector.ValueType = 'singleValue'
    val = 0
    for prio in pause_prio_list:
        val += (1 << prio)
    prio_enable_vector.SingleValue = hex(val)
        
    for i in range(8):
        pause_duration = pfc_stack_obj.find(DisplayName='PFC Queue {}'.format(i))
        pause_duration.ValueType = 'singleValue'
        
        if i in pause_prio_list:
            pause_duration.SingleValue = 'ffff'     
        else:
            pause_duration.SingleValue = '0'


def create_pkt_hdr(ixnetwork, traffic_item, pkt_hdr_to_add, append_to_stack): 
    #Add new packet header in traffic item
    config_element = traffic_item.ConfigElement.find()[0]

    # Do the followings to add packet headers on the new traffic item

    # Uncomment this to show a list of all the available protocol templates to create (packet headers)
    #for protocolHeader in ixNetwork.Traffic.ProtocolTemplate.find():
    #    ixNetwork.info('Protocol header: -- {} --'.format(protocolHeader.DisplayName))

    # 1> Get the <new packet header> protocol template from the ProtocolTemplate list.
    pkt_hdr_proto_template = ixnetwork.Traffic.ProtocolTemplate.find(DisplayName=pkt_hdr_to_add)
    #ixNetwork.info('protocolTemplate: {}'.format(packetHeaderProtocolTemplate))

    # 2> Append the <new packet header> object after the specified packet header stack.
    append_to_stack_obj = config_element.Stack.find(DisplayName=append_to_stack)
    #ixNetwork.info('appendToStackObj: {}'.format(appendToStackObj))
    append_to_stack_obj.Append(Arg2=pkt_hdr_proto_template)

    # 3> Get the new packet header stack to use it for appending an IPv4 stack after it.
    # Look for the packet header object and stack ID.
    pkt_hdr_stack_obj = config_element.Stack.find(DisplayName=pkt_hdr_to_add)

    # 4> In order to modify the fields, get the field object
    pkt_hdr_field_obj = pkt_hdr_stack_obj.Field.find()
    #ixNetwork.info('packetHeaderFieldObj: {}'.format(packetHeaderFieldObj))

    # 5> Save the above configuration to the base config file.
    #ixNetwork.SaveConfig(Files('baseConfig.ixncfg', local_file=True))

    return pkt_hdr_field_obj


"""
Get statistics

@param session: IXIA session
@return statistics information
"""
def get_statistics(session):
    ixnetwork = session.Ixnetwork
    flow_statistics = session.StatViewAssistant('Flow Statistics')
    ixnetwork.info('{}\n'.format(flow_statistics))
    return flow_statistics


"""
Start all the traffic items  

@param session: IXIA session
"""
def start_traffc(session):
    ixnetwork = session.Ixnetwork
    """ Apply traffic to hardware """
    ixnetwork.Traffic.Apply()
    """ Run traffic """
    ixnetwork.Traffic.StartStatelessTrafficBlocking()


"""
Stop all the traffic items

@param session: IXIA session
"""
def stop_traffic(session):
    ixnetwork = session.Ixnetwork
    ixnetwork.Traffic.StopStatelessTrafficBlocking()
    
"""
Start capturing traffic

@param session: IXIA session
"""
def start_capture(session):
    ixnetwork = session.Ixnetwork
    ixnetwork.StartCapture()
    
"""
Stop capturing traffic

@param session: IXIA session
"""
def stop_capture(session):
    ixnetwork = session.Ixnetwork
    ixnetwork.StopCapture()   

"""
Save the captured packets to a new user specifided location on the API server

@param session: IXIA session
@param dir: directory
@return the list of relative paths of all the captures saves
"""
def save_capture_pkts(session, dir=''):
    ixnetwork = session.Ixnetwork
    capture_files = ixnetwork.SaveCaptureFiles(Arg1=dir)
    ixnetwork.info('Capture files: {}'.format(capture_files))
    return capture_files

"""
Download a file from the API server

@param session: IXIA session
@param remote_filename: the name of the remote file
@param local_filename: the name that the remote contents will be saved to
@return the local file name
"""
def download_file(session, remote_filename, local_filename):
    return session.Session.DownloadFile(remote_filename, local_filename)
    
"""
Get all data packets captured in this port.
For each captured data packets, this function parses its every packet header
(e.g., Ethernet and IP) and every packet field (e.g., destination IP and ECN) 

@param session: IXIA session
@param port: port where we capture pdata ackets
@return the list of parsed data packets.  
"""
def get_captured_data_pkts(session, port):
    result = list()
    pkt_count = port.Capture.DataPacketCounter
    ixnetwork = session.Ixnetwork
    
    ixnetwork.info('Total data packets captured: {}'.format(pkt_count))
    
    for i in range(pkt_count):
        pkt = dict()
        
        port.Capture.CurrentPacket.GetPacketFromDataCapture(Arg2=i)
        pkt_hdr_stacks = port.Capture.CurrentPacket.Stack.find()
        
        for pkt_hdr in pkt_hdr_stacks.find():
            ixnetwork.info('\nPacketHeaderName: {}'.format(pkt_hdr.DisplayName))
            pkt[pkt_hdr.DisplayName] = dict()
            
            for field in pkt_hdr.Field.find():
                ixnetwork.info('\t{}: {}'.format(field.DisplayName, field.FieldValue)) 
                pkt[pkt_hdr.DisplayName][field.DisplayName] = field.FieldValue
        
        result.append(pkt)
        
    return result 

"""
Get the value of a specific field of the packet

@param pkt: packet
@param header: header name, e.g., "Internet Protocol"
@param field: field name, e.g., 'Explicit Congestion Notification'
@return the field value of None if the packet does not have this field
"""
def get_pkt_field(pkt, header, field):
    if header not in pkt:
        return None 
    
    pkt_hdr = pkt[header]
    if field not in pkt_hdr:
        return None 
    
    return pkt[header][field]

"""
Get the ECN field value of the packet

@param pkt: packet
@return the ECN value 
"""
def get_ecn(pkt):
    return get_pkt_field(pkt=pkt, header='Internet Protocol', field='Explicit Congestion Notification')

"""
Get the DSCP field value of the packet

@param pkt: packet
@return the DSCP value (or None the packets does not have this field)
"""
def get_dscp(pkt):
    return get_pkt_field(pkt=pkt, header='Internet Protocol', field='Differentiated Services Codepoint')