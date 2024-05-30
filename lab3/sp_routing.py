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

import logging
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import packet, ethernet, ipv4, arp, ether_types
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link
from collections import defaultdict, deque

import network_awareness
import network_monitor
import setting

# Set up logging
logging.basicConfig(level=logging.INFO)

class SPRouter(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {
		"network_awareness": network_awareness.NetworkAwareness,
		"network_monitor": network_monitor.NetworkMonitor}
    WEIGHT_MODEL = {'hop': 'weight', 'bw': 'bw'}

    def __init__(self, *args, **kwargs):
        super(SPRouter, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.switches = {}
        self.network = defaultdict(dict)
        self.arp_table = {}  # ARP table for IP to MAC resolution

    @set_ev_cls(event.EventSwitchEnter)
    def get_topology_data(self, ev):
        switch_list = get_switch(self, None)
        self.switches = {switch.dp.id: switch.dp for switch in switch_list}
        links_list = get_link(self, None)
        self.network = self.create_network(links_list)
        logging.info("Topology data acquired: %s", self.network)

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
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        logging.info("Table-miss flow entry installed for switch %s", datapath.id)

    def add_flow(self, datapath, priority, match, actions, buffer_id=ofproto_v1_3.OFP_NO_BUFFER):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match,
                                instructions=instructions, buffer_id=buffer_id,
                                idle_timeout=30, hard_timeout=50, flags=ofproto.OFPFF_SEND_FLOW_REM)
        datapath.send_msg(mod)
        logging.info("Flow added with priority %s on switch %s for match %s", priority, datapath.id, match)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocols(ipv4.ipv4)[0]
            self.handle_ip_packet(datapath, in_port, eth, ip_pkt, msg)
        elif eth.ethertype == ether_types.ETH_TYPE_ARP:
            arp_pkt = pkt.get_protocols(arp.arp)[0]
            self.handle_arp_packet(datapath, in_port, eth, arp_pkt)

    def handle_ip_packet(self, datapath, in_port, eth, ip_pkt, msg):
        dst_mac = eth.dst
        self.mac_to_port.setdefault(datapath.id, {})
        self.mac_to_port[datapath.id][eth.src] = in_port
        logging.info("Handling IP packet: %s -> %s on switch %s", eth.src, eth.dst, datapath.id)

        if dst_mac in self.mac_to_port[datapath.id]:
            self.forward_packet(datapath, in_port, eth, dst_mac, msg.data)
        else:
            self.forward_packet(datapath, in_port, eth, None, msg.data)

    def handle_arp_packet(self, datapath, in_port, eth, arp_pkt):
        src_ip = arp_pkt.src_ip
        src_mac = arp_pkt.src_mac
        dst_ip = arp_pkt.dst_ip
        self.arp_table[src_ip] = src_mac
        logging.info("Handling ARP packet from %s to %s on switch %s", src_ip, dst_ip, datapath.id)

        if arp_pkt.opcode == arp.ARP_REQUEST:
            if dst_ip in self.arp_table:
                self.send_arp_reply(datapath, arp_pkt, eth.src, in_port)
            else:
                self.flood_arp_request(datapath, in_port, eth, arp_pkt)

    def send_arp_reply(self, datapath, arp_pkt, eth_src, in_port):
        src_ip = arp_pkt.dst_ip
        dst_ip = arp_pkt.src_ip
        src_mac = self.arp_table[src_ip]
        dst_mac = eth_src
        arp_reply_pkt = packet.Packet()
        arp_reply_pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_ARP,
                                                    dst=dst_mac, src=src_mac))
        arp_reply_pkt.add_protocol(arp.arp(opcode=arp.ARP_REPLY,
                                           src_mac=src_mac, src_ip=src_ip,
                                           dst_mac=dst_mac, dst_ip=dst_ip))
        self.send_packet(datapath, in_port, arp_reply_pkt)
        logging.info("ARP reply sent from %s to %s on switch %s", src_ip, dst_ip, datapath.id)

    def flood_arp_request(self, datapath, in_port, eth, arp_pkt):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=eth.ethertype,
                                           dst='ff:ff:ff:ff:ff:ff',  # Broadcast MAC address
                                           src=eth.src))
        pkt.add_protocol(arp_pkt)
        pkt.serialize()
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=in_port, actions=actions, data=pkt.data)
        datapath.send_msg(out)
        logging.info("ARP request flooded on switch %s", datapath.id)

    def send_packet(self, datapath, port, pkt):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt.serialize()
        data = pkt.data
        actions = [parser.OFPActionOutput(port)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=ofproto.OFPP_CONTROLLER, actions=actions, data=data)
        datapath.send_msg(out)
        logging.info("Packet sent through port %s on switch %s", port, datapath.id)

    def forward_packet(self, datapath, in_port, eth, dst_mac, data):
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        if dst_mac and dst_mac in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst_mac]
        else:
            out_port = ofproto.OFPP_FLOOD
        actions = [parser.OFPActionOutput(out_port)]
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac)
            self.add_flow(datapath, 1, match, actions)
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
        logging.info("Forwarding packet: %s -> %s on switch %s via port %s", eth.src, eth.dst, dpid, out_port)

if __name__ == '__main__':
    from ryu.cmd import manager
    manager.main()