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
from mininet.log import setLogLevel

import topo

class FattreeNet(Topo):
	"""
	Create a fat-tree network in Mininet
	"""


		# TODO: please complete the network generation logic here
	def __init__(self,graph_topo):
			Topo.__init__(self)
			self.k = graph_topo.k
			self.num_pods = graph_topo.k
			self.num_hosts_per_pod = (graph_topo.k // 2) ** 2
			self.num_core_switches = (graph_topo.k // 2) ** 2
			self.core_switches = []
			self.agg_switches = []
			self.edge_switches = []

			self.create_core_switches()
			self.create_pod_switches()
			self.create_hosts()
			self.create_links()

	def create_core_switches(self):
			for i in range(self.num_core_switches):
				switch = self.addSwitch(f'c{i+1}')
				self.core_switches.append(switch)

	def create_pod_switches(self):
			for pod in range(self.num_pods):
				agg_switches = []
				edge_switches = []
				for i in range(self.k // 2):
					agg_switch = self.addSwitch(f'a{pod}{i+1}')
					edge_switch = self.addSwitch(f'e{pod}{i+1}')
					agg_switches.append(agg_switch)
					edge_switches.append(edge_switch)
				self.agg_switches.append(agg_switches)
				self.edge_switches.append(edge_switches)

	def create_hosts(self):
			for pod in range(self.num_pods):
				for edge in range(self.k // 2):
					for host in range(self.k // 2):
						host_id = (pod * self.k // 2) + edge * (self.k // 2) + host + 1
						host = self.addHost(f'h{host_id}')
						self.addLink(self.edge_switches[pod][edge], host, bw=15, delay='5ms')

	def create_links(self):
			for pod in range(self.num_pods):
				for i in range(self.k // 2):
					for j in range(self.k // 2):
						self.addLink(self.agg_switches[pod][i], self.edge_switches[pod][j], bw=15, delay='5ms')

			for i in range(self.num_pods):
				for j in range(self.k // 2):
					for core in range(self.num_core_switches):
						self.addLink(self.core_switches[core], self.agg_switches[i][j], bw=15, delay='5ms')
  
  


def make_mininet_instance(graph_topo):

	net_topo = FattreeNet(graph_topo)
	net = Mininet(topo=net_topo, controller=None, autoSetMacs=True)
	net.addController('c0', controller=RemoteController, ip="127.0.0.1", port=6653)
	return net

def run(graph_topo):
	
	# Run the Mininet CLI with a given topology
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
    setLogLevel('info')
    ft_topo = topo.Fattree(4)
    print(ft_topo)
    run(ft_topo)
