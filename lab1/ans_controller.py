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
from ryu.lib.packet import packet, ethernet, ipv4, icmp


class RouterController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(RouterController, self).__init__(*args, **kwargs)
        self.port_to_own_mac = {
            1: "00:00:00:00:01:01",
            2: "00:00:00:00:01:02",
            3: "00:00:00:00:01:03"
        }
        self.port_to_own_ip = {
            1: "10.0.1.1",
            2: "10.0.2.1",
            3: "192.168.1.1"
        }

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Add flow entries for known routes
        for port, own_ip in self.port_to_own_ip.items():
            match = parser.OFPMatch(
                eth_type=0x0800,
                ipv4_dst=own_ip
            )
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(datapath, 100, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst
        )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        ip = pkt.get_protocol(ipv4.ipv4)
        icmp_pkt = pkt.get_protocol(icmp.icmp)

        if eth.ethertype == 0x0800 and ip:
            if ip.dst == self.port_to_own_ip[3]:
                # Drop packets destined to external host
                return
            if icmp_pkt:
                # ICMP packet, handle accordingly
                self._handle_icmp(datapath, msg, eth, ip, icmp_pkt, ofproto, parser)

    def _handle_icmp(self, datapath, msg, eth, ip, icmp_pkt, ofproto, parser):
        # Check if it's an ICMP echo request (ping)
        if icmp_pkt.type == icmp.ICMP_ECHO_REQUEST:
            # Extract ICMP payload (original packet)
            icmp_data = icmp_pkt.data
            # Construct ICMP echo reply packet
            icmp_reply = icmp.icmp(
                type_=icmp.ICMP_ECHO_REPLY,
                code=icmp.ICMP_ECHO_REPLY_CODE,
                csum=0,
                data=icmp_data
            )
            # Construct IPv4 packet containing the ICMP echo reply
            ip_reply = ipv4.ipv4(
                src=ip.dst,
                dst=ip.src,
                proto=ip.proto
            )
            # Construct Ethernet packet containing the IPv4 packet
            eth_reply = ethernet.ethernet(
                ethertype=eth.ethertype,
                dst=eth.src,
                src=self.port_to_own_mac[datapath.id]
            )
            # Assemble the packets into a Packet object
            pkt_reply = packet.Packet()
            pkt_reply.add_protocol(eth_reply)
            pkt_reply.add_protocol(ip_reply)
            pkt_reply.add_protocol(icmp_reply)
            pkt_reply.serialize()

            # Send the ICMP echo reply packet out through the appropriate port
            actions = [parser.OFPActionOutput(msg.in_port)]
            out = parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=ofproto.OFP_NO_BUFFER,
                in_port=ofproto.OFPP_CONTROLLER,
                actions=actions,
                data=pkt_reply.data
            )
            datapath.send_msg(out)
