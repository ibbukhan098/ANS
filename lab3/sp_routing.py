"""
 Copyright 2024 Computer Networks Group @ UPB

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 """

#!/usr/bin/env python3

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import packet, ethernet, ipv4, arp, ether_types
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link
from collections import defaultdict, deque
import heapq

class SPRouter(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SPRouter, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.switches = {}
        self.network = defaultdict(dict)

    # Topology discovery
    @set_ev_cls(event.EventSwitchEnter)
    def get_topology_data(self, ev):
        switch_list = get_switch(self, None)
        self.switches = {switch.dp.id: switch.dp for switch in switch_list}
        links_list = get_link(self, None)
        self.network = self.create_network(links_list)

    def create_network(self, links_list):
        graph = defaultdict(dict)
        for link in links_list:
            src = link.src.dpid
            dst = link.dst.dpid
            self.network[src][dst] = link.src.port_no
        return graph

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Install the table-miss flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=ofproto_v1_3.OFP_NO_BUFFER):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match,
                                instructions=instructions, buffer_id=buffer_id,
                                idle_timeout=30, hard_timeout=50, flags=ofproto.OFPFF_SEND_FLOW_REM)
        datapath.send_msg(mod)


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Determine the received port
        in_port = msg.match['in_port']

        # Learn a mac address to avoid FLOOD next time.
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][eth.src] = in_port

        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocols(ipv4.ipv4)[0]
            self.handle_ip_packet(datapath, in_port, eth, ip_pkt)
        elif eth.ethertype == ether_types.ETH_TYPE_ARP:
            arp_pkt = pkt.get_protocols(arp.arp)[0]
            self.handle_arp_packet(datapath, in_port, eth, arp_pkt)

    def find_shortest_path(self, src_dpid, dst_dpid):
        # Dijkstra's algorithm
        dist = {node: float('inf') for node in self.switches}
        previous = {node: None for node in self.switches}
        dist[src_dpid] = 0
        pq = [(0, src_dpid)]

        while pq:
            current_distance, current_node = heapq.heappop(pq)

            if current_distance > dist[current_node]:
                continue

            for neighbor in self.network[current_node]:
                distance = current_distance + 1
                if distance < dist[neighbor]:
                    dist[neighbor] = distance
                    previous[neighbor] = current_node
                    heapq.heappush(pq, (distance, neighbor))

        # Build the path
        path = deque()
        step = dst_dpid
        while previous[step] is not None:
            path.appendleft((previous[step], step))
            step = previous[step]
        return list(path)

    def handle_ip_packet(self, datapath, in_port, eth, ip_pkt):
        src = eth.src
        dst = eth.dst

        dst_dpid = None
        for dpid, mac_table in self.mac_to_port.items():
            if dst in mac_table:
                dst_dpid = dpid
                break

        if dst_dpid:
            path = self.find_shortest_path(datapath.id, dst_dpid)
            self.install_path(datapath, path, in_port, eth, ip_pkt)

    def handle_arp_packet(self, datapath, port, pkt_ethernet, pkt_arp):
        if pkt_arp.opcode == arp.ARP_REQUEST:
            # Generate an ARP reply
            pkt = packet.Packet()
            pkt.add_protocol(ethernet.ethernet(ethertype=pkt_ethernet.ethertype,
                                            dst=pkt_ethernet.src,
                                            src=self.arp_table[pkt_arp.dst_ip]))
            pkt.add_protocol(arp.arp(opcode=arp.ARP_REPLY,
                                    src_mac=self.arp_table[pkt_arp.dst_ip],
                                    src_ip=pkt_arp.dst_ip,
                                    dst_mac=pkt_arp.src_mac,
                                    dst_ip=pkt_arp.src_ip))
            self.send_packet(datapath, port, pkt)


    def install_path(self, datapath, path, in_port, eth, ip_pkt):
        # Assuming the path is a list of tuples (src_dpid, dst_dpid)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        for src_dpid, dst_dpid in path:
            match = parser.OFPMatch(in_port=in_port, eth_dst=eth.dst, eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=ip_pkt.dst)
            actions = [parser.OFPActionOutput(self.network[src_dpid][dst_dpid])]
            self.add_flow(self.switches[src_dpid], 100, match, actions)
            in_port = self.network[dst_dpid][src_dpid]  # Reverse direction for the next hop

# Start the controller application
if __name__ == '__main__':
    from ryu.cmd import manager
    manager.main()