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

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import *
from ipaddress import IPv4Address, IPv4Network
from datetime import datetime, timedelta


class LearningSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(LearningSwitch, self).__init__(*args, **kwargs)

        # Here you can initialize the data structures you want to keep at the controller

        # Routing Table for Hope
        self.ROUTING_TABLE = {
            'ROUTER_MAC_ADD': {
                1: "00:00:00:00:01:01",
                2: "00:00:00:00:01:02",
                3: "00:00:00:00:01:03",
            },
            'ROUTER_IP': {
                1: IPv4Address("10.0.1.1"),
                2: IPv4Address("10.0.2.1"),
                3: IPv4Address("192.168.1.1"),
            },
            'SUBNETS': {
                1: IPv4Network("10.0.1.0/24"),
                2: IPv4Network("10.0.2.0/24"),
                3: IPv4Network("192.168.1.0/24"),
            }
        }

        # Default Router S2 MAC address
        self.DEFAULT_MAC = "ff:ff:ff:ff:ff:ff"
        self.MAC = {}
        self.PORT_TO_MAC = {}

    # Switch handler
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Initial flow entry for matching misses
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, match, actions, priority=0)

    # Add a flow entry to the flow-table
    def add_flow(self, datapath, match, actions, **kwargs):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Construct flow_mod message and send it
        inst = [parser.OFPInstructionActions(
            ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath,
                                match=match, instructions=inst, **kwargs)
        datapath.send_msg(mod)

    # packet forwarding
    def packet_forward(self, datapath, out_port, data):

        datapath.send_msg(
            datapath.ofproto_parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                in_port=datapath.ofproto.OFPP_CONTROLLER,
                actions=[
                    datapath.ofproto_parser.OFPActionOutput(out_port)],
                data=data))

    # ARP Packet handler
    def arp_packet_handler(
            self,
            datapath,
            arp_packet,
            ethernet_packet,
            in_port):
        self.logger.info(
            "DATAPATH ID : %s ARP src %s; : dest %s",
            datapath.id,
            arp_packet.src_ip,
            arp_packet.dst_ip)

        self.MAC[IPv4Address(arp_packet.src_ip)] = (
            arp_packet.src_mac, datetime.now() + timedelta(seconds=10))

        if arp_packet.opcode == arp.ARP_REQUEST and IPv4Address(
                arp_packet.dst_ip) == self.ROUTING_TABLE['ROUTER_IP'][in_port]:
            response_pkt = packet.Packet()
            response_pkt.add_protocol(
                ethernet.ethernet(
                    src=self.ROUTING_TABLE['ROUTER_MAC_ADD'][in_port],
                    dst=ethernet_packet.src,
                    ethertype=ethernet_packet.ethertype))
            response_pkt.add_protocol(
                arp.arp(
                    opcode=arp.ARP_REPLY,
                    src_mac=self.ROUTING_TABLE['ROUTER_MAC_ADD'][in_port],
                    src_ip=self.ROUTING_TABLE['ROUTER_IP'][in_port],
                    dst_mac=arp_packet.src_mac,
                    dst_ip=arp_packet.src_ip))
            self.packet_forward(datapath, in_port, response_pkt)

    # Handle the packet_in event
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto

        ofp_parser = datapath.ofproto_parser

        in_port = msg.match["in_port"]
        pack = packet.Packet(msg.data)
        ethernet_packet = pack.get_protocol(ethernet.ethernet)

        if datapath.id in [1, 2]:
            self.logger.info(
                "DATAPATH ID : %s ETHERNET src %s; : dest %s",
                datapath.id,
                ethernet_packet.src,
                ethernet_packet.dst)

            self.PORT_TO_MAC[ethernet_packet.src] = (
                in_port, datetime.now() + timedelta(seconds=10))

            if ethernet_packet.dst == self.DEFAULT_MAC:
                self.packet_forward(datapath, ofp.OFPP_FLOOD, pack)
                self.add_flow(
                    datapath,
                    ofp_parser.OFPMatch(eth_dst=self.DEFAULT_MAC),
                    [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD)],
                    priority=1
                )
                return

            if ethernet_packet.dst in self.PORT_TO_MAC:
                out_port, deadline = self.PORT_TO_MAC[ethernet_packet.dst]
                if deadline >= datetime.now():
                    self.add_flow(datapath, ofp_parser.OFPMatch(eth_dst=ethernet_packet.src), [
                                  ofp_parser.OFPActionOutput(in_port)], priority=1, hard_timeout=10)
                    self.add_flow(datapath, ofp_parser.OFPMatch(eth_dst=ethernet_packet.dst), [
                                  ofp_parser.OFPActionOutput(out_port)], priority=1, hard_timeout=10)
                else:
                    out_port = ofp.OFPP_FLOOD
                    del self.PORT_TO_MAC[ethernet_packet.dst]

            else:
                out_port = ofp.OFPP_FLOOD

            self.packet_forward(datapath, out_port, pack)

        else:
            arp_pkt = pack.get_protocol(arp.arp)
            ip_pkt = pack.get_protocol(ipv4.ipv4)

            if arp_pkt is not None:

                self.arp_packet_handler(
                    datapath, arp_pkt, ethernet_packet, in_port)

            elif ip_pkt is not None:
                packet_source = IPv4Address(ip_pkt.src)
                packet_destination = IPv4Address(ip_pkt.dst)

                self.logger.info(
                    "DATAPATH ID : %s IP src %s; : dest %s",
                    datapath.id,
                    ethernet_packet.src,
                    ethernet_packet.dst)

                ip_pkt.ttl -= 1
                if ip_pkt.ttl == 0:
                    return

                src_port, src_subnet = next(
                    filter(lambda item: packet_source in item[1], self.ROUTING_TABLE['SUBNETS'].items()))
                dst_port, dst_subnet = next(
                    filter(lambda item: packet_destination in item[1], self.ROUTING_TABLE['SUBNETS'].items()))
                icmp_packet: icmp.icmp = pack.get_protocol(icmp.icmp)

                # Add MAC to IP-MAC translation table.
                if packet_source in self.ROUTING_TABLE['SUBNETS'][in_port]:
                    self.MAC[packet_source] = (
                        ethernet_packet.src, datetime.now() + timedelta(seconds=10))

                # This packet is not meant for the router
                # Deny communication between external and datacenter hosts
                # Deny pings between external hosts and workstations
                # Pings to datacenter hosts already excluded
                if (ethernet_packet.dst != self.ROUTING_TABLE['ROUTER_MAC_ADD'][src_port]) \
                        or ({src_port, dst_port} == {2, 3}) \
                        or ({src_port, dst_port} == {1, 3} and icmp_packet is not None and icmp_packet.type == icmp.ICMP_ECHO_REQUEST):
                    return

                # ICMP request to the router
                if packet_destination == self.ROUTING_TABLE['ROUTER_IP'][dst_port]:
                    icmp_packet = pack.get_protocol(icmp.icmp)
                    if icmp_packet is None or icmp_packet.type != icmp.ICMP_ECHO_REQUEST or packet_source not in dst_subnet:
                        return

                    ip_pkt.src, ip_pkt.dst = ip_pkt.dst, ip_pkt.src
                    ethernet_packet.src, ethernet_packet.dst = ethernet_packet.dst, ethernet_packet.src
                    icmp_packet.type = icmp.ICMP_ECHO_REPLY
                    icmp_packet.csum = 0
                    ip_pkt.csum = 0
                    self.packet_forward(datapath, dst_port, pack)

                else:
                    if packet_destination in self.MAC:
                        dst_mac, deadline = self.MAC[packet_destination]

                        self.add_flow(datapath, ofp_parser.OFPMatch(
                            eth_type=ethernet.ether.ETH_TYPE_IP,
                            ipv4_src=(src_subnet.network_address,
                                      src_subnet.netmask),
                            ipv4_dst=packet_destination
                        ), [
                            ofp_parser.OFPActionDecNwTtl(),
                            ofp_parser.OFPActionSetField(
                                eth_src=self.ROUTING_TABLE['ROUTER_MAC_ADD'][dst_port]),
                            ofp_parser.OFPActionSetField(eth_dst=dst_mac),
                            ofp_parser.OFPActionOutput(dst_port),
                        ], hard_timeout=10)
                        ethernet_packet.dst = dst_mac

                    else:
                        ethernet_packet.dst = self.DEFAULT_MAC

                    ethernet_packet.src = self.ROUTING_TABLE['ROUTER_MAC_ADD'][dst_port]
                    self.packet_forward(datapath, dst_port, pack)

                    if ethernet_packet.dst == self.DEFAULT_MAC:
                        # Broadcast the message as destination MAC is unknow to us.
                        # in the hope that it's useful to someone, and make an ARP request to be prepared next time.
                        arp_request_pkt = packet.Packet()
                        arp_request_pkt.add_protocol(
                            ethernet.ethernet(
                                src=self.ROUTING_TABLE['ROUTER_MAC_ADD'][dst_port],
                                ethertype=ethernet.ether.ETH_TYPE_ARP))
                        arp_request_pkt.add_protocol(
                            arp.arp(
                                src_mac=self.ROUTING_TABLE['ROUTER_MAC_ADD'][dst_port],
                                src_ip=self.ROUTING_TABLE['ROUTER_IP'][dst_port],
                                dst_ip=packet_destination))

                        self.packet_forward(
                            datapath, dst_port, arp_request_pkt)
