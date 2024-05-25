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
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ether_types, ipv4, arp
from ryu.topology import event
from ryu.topology.api import get_switch, get_link

import networkx as nx
import topo

class SPRouter(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SPRouter, self).__init__(*args, **kwargs)
        self.topo_net = topo.Fattree(4)
        self.graph = nx.Graph()
        self.paths = {}

    def get_topology_data(self):
        switches = get_switch(None, None)
        links = get_link(None, None)
        return switches, links

    def build_network_graph(self):
        switches, links = self.get_topology_data()
        self.graph.add_nodes_from([switch.dp.id for switch in switches])
        for link in links:
            self.graph.add_edge(link.src.dpid, link.dst.dpid)

    def calculate_shortest_paths(self):
        self.paths = dict(nx.all_pairs_shortest_path(self.graph))

    @staticmethod
    def add_flow(datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)

    @staticmethod
    def handle_arp(datapath, in_port, pkt, arp_pkt):
        src_ip = arp_pkt.src_ip
        src_mac = arp_pkt.src_mac
        SPRouter.topo_net.hosts[src_ip] = {'switch': datapath.id, 'port': in_port}

    def handle_ipv4(self, datapath, in_port, pkt, ip_pkt):
        dst_ip = ip_pkt.dst
        src_ip = ip_pkt.src

        if dst_ip in self.topo_net.hosts and src_ip in self.topo_net.hosts:
            src_dpid = self.topo_net.hosts[src_ip]['switch']
            dst_dpid = self.topo_net.hosts[dst_ip]['switch']
            path = self.paths[src_dpid][dst_dpid][1:]  # Exclude source switch
            out_port = self.graph[src_dpid][path[0]]['port']

            actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
            match = datapath.ofproto_parser.OFPMatch(eth_type=0x0800, ipv4_dst=dst_ip)
            self.add_flow(datapath, 1, match, actions)

            data = None
            if pkt.buffer_id == datapath.ofproto.OFP_NO_BUFFER:
                data = pkt.data

            out = datapath.ofproto_parser.OFPPacketOut(datapath=datapath, buffer_id=pkt.buffer_id,
                                                       in_port=in_port, actions=actions, data=data)
            datapath.send_msg(out)

    @staticmethod
    def handle_packet_in(msg):
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(packet.ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            arp_pkt = pkt.get_protocol(arp.arp)
            SPRouter.handle_arp(msg.datapath, msg.match['in_port'], pkt, arp_pkt)

        elif eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            SPRouter.handle_ipv4(msg.datapath, msg.match['in_port'], pkt, ip_pkt)

    @staticmethod
    def switch_features_handler(event):
        datapath = event.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        SPRouter.add_flow(datapath, 0, match, actions)

    @staticmethod
    def event_switch_enter(event):
        SPRouter.build_network_graph()
        SPRouter.calculate_shortest_paths()

    @staticmethod
    def packet_in_handler(event):
        msg = event.msg
        SPRouter.handle_packet_in(msg)