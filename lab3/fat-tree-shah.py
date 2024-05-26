#!/usr/bin/env python3

import os
import subprocess
import time

import mininet
import mininet.clean
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import lg, info
from mininet.link import TCLink
from mininet.node import Node, OVSKernelSwitch, RemoteController
from mininet.topo import Topo
from mininet.util import waitListening, custom

import topo

class FattreeNet(Topo):
    """
    Create a fat-tree network in Mininet
    """

    def __init__(self, ft_topo):
        Topo.__init__(self)

        # Add core switches
        cores = {}
        for i in range((ft_topo.k // 2) ** 2):
            core_switch = self.addSwitch(f"C{i+1}", dpid=f"{i+1}")
            cores[f"C{i+1}"] = core_switch

        # Add aggregation switches and connect them to core switches
        aggs = {}
        for pod in range(ft_topo.k):
            for a in range(ft_topo.k // 2):
                agg_switch = self.addSwitch(f"A{pod+1}{a+1}", dpid=f"{pod+1}{a+1}")
                aggs[f"A{pod+1}{a+1}"] = agg_switch
                for core in cores.values():
                    self.addLink(core, agg_switch, bw=15, delay='5ms')

        # Add edge switches and connect them to aggregation switches
        edges = {}
        for pod in range(ft_topo.k):
            for e in range(ft_topo.k // 2):
                edge_switch = self.addSwitch(f"E{pod+1}{e+1}", dpid=f"{pod+1}{e+1}")
                edges[f"E{pod+1}{e+1}"] = edge_switch
                for agg in aggs.values():
                    self.addLink(agg, edge_switch, bw=15, delay='5ms')

        # Add hosts and connect them to edge switches with appropriate IP addresses
        for pod in range(ft_topo.k):
            for e in range(ft_topo.k // 2):
                for h in range(ft_topo.k // 2):
                    host_name = f"H{pod+1}{e+1}{h+1}"
                    host = self.addHost(host_name, ip=f"10.{pod+1}.{e+1}.{h+2}/24")
                    self.addLink(edges[f"E{pod+1}{e+1}"], host, bw=15, delay='5ms')

def make_mininet_instance(graph_topo):
    net_topo = FattreeNet(graph_topo)
    net = Mininet(topo=net_topo, controller=None, autoSetMacs=True)
    net.addController('c0', controller=RemoteController, ip="127.0.0.1", port=6653)
    return net

def run(graph_topo):
    lg.setLogLevel('info')
    mininet.clean.cleanup()
    net = make_mininet_instance(graph_topo)
    info('*** Starting network ***\n')
    net.start()
    info('*** Running CLI ***\n')
    CLI(net)
    info('*** Stopping network ***\n')
    net.stop()

if __name__ == '__main__':
    lg.setLogLevel('info')
    ft_topo = topo.Fattree(4)
    run(ft_topo)