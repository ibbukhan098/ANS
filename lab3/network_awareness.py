# Copyright (C) 2016 Li Cheng at Beijing University of Posts
# and Telecommunications. www.muzixing.com
# Copyright (C) 2016 Huang MaChi at Chongqing University
# of Posts and Telecommunications, China.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import networkx as nx
import matplotlib.pyplot as plt
import time
import heapq

from ryu import cfg
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4
from ryu.lib.packet import arp
from ryu.lib import hub
from ryu.topology import event
from ryu.topology.api import get_switch, get_link

from itertools import count

import setting


CONF = cfg.CONF

class PathBuffer:
    def __init__(self):
        self.paths = set()
        self.sortedpaths = []
        self.counter = count()

    def __len__(self):
        return len(self.sortedpaths)

    def push(self, cost, path):
        hashable_path = tuple(path)
        if hashable_path not in self.paths:
            heapq.heappush(self.sortedpaths, (cost, next(self.counter), path))
            self.paths.add(hashable_path)

    def pop(self):
        (cost, num, path) = heapq.heappop(self.sortedpaths)
        hashable_path = tuple(path)
        self.paths.remove(hashable_path)
        return path


class NetworkAwareness(app_manager.RyuApp):
	"""
		NetworkAwareness is a Ryu app for discovering topology information.
		This App can provide many data services for other App, such as
		link_to_port, access_table, switch_port_table, access_ports,
		interior_ports, topology graph and shortest paths.
	"""
	OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

	# List the event list should be listened.
	events = [event.EventSwitchEnter,
			  event.EventSwitchLeave, event.EventPortAdd,
			  event.EventPortDelete, event.EventPortModify,
			  event.EventLinkAdd, event.EventLinkDelete]

	def __init__(self, *args, **kwargs):
		super(NetworkAwareness, self).__init__(*args, **kwargs)
		self.topology_api_app = self
		self.name = "awareness"
		self.link_to_port = {}                 # {(src_dpid,dst_dpid):(src_port,dst_port),}
		self.access_table = {}                # {(sw,port):(ip, mac),}
		self.switch_port_table = {}      # {dpid:set(port_num,),}
		self.access_ports = {}                # {dpid:set(port_num,),}
		self.interior_ports = {}              # {dpid:set(port_num,),}
		self.switches = []                         # self.switches = [dpid,]
		self.shortest_paths = {}            # {dpid:{dpid:[[path],],},}
		self.pre_link_to_port = {}
		self.pre_access_table = {}

		# Directed graph can record the loading condition of links more accurately.
		# self.graph = nx.Graph()
		self.graph = nx.DiGraph()
		# Get initiation delay.
		self.initiation_delay = self.get_initiation_delay(CONF.fanout)
		self.start_time = time.time()

		# Start a green thread to discover network resource.
		self.discover_thread = hub.spawn(self._discover)

	def _discover(self):
		i = 0
		while True:
			self.show_topology()
			if i == 2:   # Reload topology every 20 seconds.
				self.get_topology(None)
				i = 0
			hub.sleep(setting.DISCOVERY_PERIOD)
			i = i + 1

	def add_flow(self, dp, priority, match, actions, idle_timeout=0, hard_timeout=0):
		ofproto = dp.ofproto
		parser = dp.ofproto_parser
		inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
											 actions)]
		mod = parser.OFPFlowMod(datapath=dp, priority=priority,
								idle_timeout=idle_timeout,
								hard_timeout=hard_timeout,
								match=match, instructions=inst)
		dp.send_msg(mod)

	@set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
	def switch_features_handler(self, ev):
		"""
			Install table-miss flow entry to datapaths.
		"""
		datapath = ev.msg.datapath
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser
		self.logger.info("switch:%s connected", datapath.id)

		# Install table-miss flow entry.
		match = parser.OFPMatch()
		actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
										  ofproto.OFPCML_NO_BUFFER)]
		self.add_flow(datapath, 0, match, actions)

	@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
	def _packet_in_handler(self, ev):
		"""
			Handle the packet_in packet, and register the access info.
		"""
		msg = ev.msg
		datapath = msg.datapath
		in_port = msg.match['in_port']
		pkt = packet.Packet(msg.data)
		arp_pkt = pkt.get_protocol(arp.arp)
		ip_pkt = pkt.get_protocol(ipv4.ipv4)

		if arp_pkt:
			arp_src_ip = arp_pkt.src_ip
			mac = arp_pkt.src_mac
			# Record the access infomation.
			self.register_access_info(datapath.id, in_port, arp_src_ip, mac)
		elif ip_pkt:
			ip_src_ip = ip_pkt.src
			eth = pkt.get_protocols(ethernet.ethernet)[0]
			mac = eth.src
			# Record the access infomation.
			self.register_access_info(datapath.id, in_port, ip_src_ip, mac)
		else:
			pass

	@set_ev_cls(events)
	def get_topology(self, ev):
		"""
			Get topology info and calculate shortest paths.
			Note: In looped network, we should get the topology
			20 or 30 seconds after the network went up.
		"""
		present_time = time.time()
		if present_time - self.start_time < self.initiation_delay:
			return

		self.logger.info("[GET NETWORK TOPOLOGY]")
		switch_list = get_switch(self.topology_api_app, None)
		self.create_port_map(switch_list)
		self.switches = [sw.dp.id for sw in switch_list]
		links = get_link(self.topology_api_app, None)
		self.create_interior_links(links)
		self.create_access_ports()
		self.graph = self.get_graph(self.link_to_port.keys())
		self.shortest_paths = self.all_k_shortest_paths(
			self.graph, weight='weight', k=CONF.k_paths)

	def get_host_location(self, host_ip):
		"""
			Get host location info ((datapath, port)) according to the host ip.
			self.access_table = {(sw,port):(ip, mac),}
		"""
		for key in self.access_table.keys():
			if self.access_table[key][0] == host_ip:
				return key
		self.logger.info("%s location is not found." % host_ip)
		return None

	def get_graph(self, link_list):
		"""
			Get Adjacency matrix from link_to_port.
		"""
		_graph = self.graph.copy()
		for src in self.switches:
			for dst in self.switches:
				if src == dst:
					_graph.add_edge(src, dst, weight=0)
				elif (src, dst) in link_list:
					_graph.add_edge(src, dst, weight=1)
				else:
					pass
		return _graph

	def get_initiation_delay(self, fanout):
		"""
			Get initiation delay.
		"""
		if fanout == 4:
			delay = 20
		elif fanout == 8:
			delay = 30
		else:
			delay = 30
		return delay

	def create_port_map(self, switch_list):
		"""
			Create interior_port table and access_port table.
		"""
		for sw in switch_list:
			dpid = sw.dp.id
			self.switch_port_table.setdefault(dpid, set())
			# switch_port_table is equal to interior_ports plus access_ports.
			self.interior_ports.setdefault(dpid, set())
			self.access_ports.setdefault(dpid, set())
			for port in sw.ports:
				# switch_port_table = {dpid:set(port_num,),}
				self.switch_port_table[dpid].add(port.port_no)

	def create_interior_links(self, link_list):
		"""
			Get links' srouce port to dst port  from link_list.
			link_to_port = {(src_dpid,dst_dpid):(src_port,dst_port),}
		"""
		for link in link_list:
			src = link.src
			dst = link.dst
			self.link_to_port[(src.dpid, dst.dpid)] = (src.port_no, dst.port_no)
			# Find the access ports and interior ports.
			if link.src.dpid in self.switches:
				self.interior_ports[link.src.dpid].add(link.src.port_no)
			if link.dst.dpid in self.switches:
				self.interior_ports[link.dst.dpid].add(link.dst.port_no)

	def create_access_ports(self):
		"""
			Get ports without link into access_ports.
		"""
		for sw in self.switch_port_table:
			all_port_table = self.switch_port_table[sw]
			interior_port = self.interior_ports[sw]
			# That comes the access port of the switch.
			print("self.access_ports ",self.access_ports)
			self.access_ports[sw] = all_port_table - interior_port
   
	def _weight_function(G, weight):
		if callable(weight):
			return weight
		# If the weight keyword argument is not callable, we assume it is a
		# string representing the edge attribute containing the weight of
		# the edge.
		if G.is_multigraph():
			return lambda u, v, d: min(attr.get(weight, 1) for attr in d.values())
		return lambda u, v, data: data.get(weight, 1)
	
		
   
	def _bidirectional_dijkstra(self,G, source, target, weight="weight", ignore_nodes=None, ignore_edges=None):
		if ignore_nodes and (source in ignore_nodes or target in ignore_nodes):
			raise nx.NetworkXNoPath(f"No path between {source} and {target}.")
		if source == target:
			if source not in G:
				raise nx.NodeNotFound(f"Node {source} not in graph")
			return (0, [source])

		if G.is_directed():
			Gpred = G.predecessors
			Gsucc = G.successors
		else:
			Gpred = G.neighbors
			Gsucc = G.neighbors

		if ignore_nodes:
			def filter_iter(nodes):
				def iterate(v):
					for w in nodes(v):
						if w not in ignore_nodes:
							yield w
				return iterate
			Gpred = filter_iter(Gpred)
			Gsucc = filter_iter(Gsucc)

		if ignore_edges:
			if G.is_directed():
				def filter_pred_iter(pred_iter):
					def iterate(v):
						for w in pred_iter(v):
							if (w, v) not in ignore_edges:
								yield w
					return iterate

				def filter_succ_iter(succ_iter):
					def iterate(v):
						for w in succ_iter(v):
							if (v, w) not in ignore_edges:
								yield w
					return iterate
				Gpred = filter_pred_iter(Gpred)
				Gsucc = filter_succ_iter(Gsucc)
			else:
				def filter_iter(nodes):
					def iterate(v):
						for w in nodes(v):
							if (v, w) not in ignore_edges and (w, v) not in ignore_edges:
								yield w
					return iterate
				Gpred = filter_iter(Gpred)
				Gsucc = filter_iter(Gsucc)

		push = heapq.heappush
		pop = heapq.heappop
		dists = [{}, {}]
		paths = [{source: [source]}, {target: [target]}]
		fringe = [[], []]
		seen = [{source: 0}, {target: 0}]
		c = count()

		push(fringe[0], (0, next(c), source))
		push(fringe[1], (0, next(c), target))

		neighs = [Gsucc, Gpred]

		finalpath = []
		dir = 1
		while fringe[0] and fringe[1]:
			dir = 1 - dir
			(dist, _, v) = pop(fringe[dir])
			if v in dists[dir]:
				continue
			dists[dir][v] = dist
			if v in dists[1 - dir]:
				return (finaldist, finalpath)

			wt = self._weight_function(G, weight)
			for w in neighs[dir](v):
				if dir == 0:
					minweight = wt(v, w, G.get_edge_data(v, w))
					vwLength = dists[dir][v] + minweight
				else:
					minweight = wt(w, v, G.get_edge_data(w, v))
					vwLength = dists[dir][v] + minweight

				if w in dists[dir]:
					if vwLength < dists[dir][w]:
						raise ValueError("Contradictory paths found: negative weights?")
				elif w not in seen[dir] or vwLength < seen[dir][w]:
					seen[dir][w] = vwLength
					push(fringe[dir], (vwLength, next(c), w))
					paths[dir][w] = paths[dir][v] + [w]
					if w in seen[0] and w in seen[1]:
						totaldist = seen[0][w] + seen[1][w]
						if finalpath == [] or finaldist > totaldist:
							finaldist = totaldist
							revpath = paths[1][w][:]
							revpath.reverse()
							finalpath = paths[0][w] + revpath[1:]
		raise nx.NetworkXNoPath(f"No path between {source} and {target}.")

	def shortest_simple_paths(self, G, source, target, weight=None):
		if source not in G:
			raise nx.NodeNotFound(f"source node {source} not in graph")
		if target not in G:
			raise nx.NodeNotFound(f"target node {target} not in graph")
		if weight is None:
			length_func = len
			shortest_path_func = self._bidirectional_shortest_path
		else:
			wt = self._weight_function(G, weight)
			def length_func(path):
				return sum(
					wt(u, v, G.get_edge_data(u, v)) for (u, v) in zip(path, path[1:])
				)
			shortest_path_func = self._bidirectional_dijkstra
		listA = []
		listB = PathBuffer()
		prev_path = None
		while True:
			if not prev_path:
				length, path = shortest_path_func(G, source, target, weight=weight)
				listB.push(length, path)
			else:
				ignore_nodes = set()
				ignore_edges = set()
				for i in range(1, len(prev_path)):
					root = prev_path[:i]
					root_length = length_func(root)
					for path in listA:
						if path[:i] == root:
							ignore_edges.add((path[i - 1], path[i]))
					try:
						length, spur = shortest_path_func(
							G,
							root[-1],
							target,
							ignore_nodes=ignore_nodes,
							ignore_edges=ignore_edges,
							weight=weight,
						)
						path = root[:-1] + spur
						listB.push(root_length + length, path)
					except nx.NetworkXNoPath:
						pass
					ignore_nodes.add(root[-1])
			if listB:
				path = listB.pop()
				yield path
				listA.append(path)
				prev_path = path
			else:
				break

	def k_shortest_paths(self, graph, src, dst, weight='weight', k=5):
		"""
			Creat K shortest paths from src to dst.
			generator produces lists of simple paths, in order from shortest to longest.
		"""
		generator = self.shortest_simple_paths(graph, source=src, target=dst, weight=weight)
		shortest_paths = []
		try:
			for path in generator:
				if k <= 0:
					break
				shortest_paths.append(path)
				k -= 1
			return shortest_paths
		except:
			self.logger.debug("No path between %s and %s" % (src, dst))

	def all_k_shortest_paths(self, graph, weight='weight', k=5):
		"""
			Creat all K shortest paths between datapaths.
			Note: We get shortest paths for bandwidth-sensitive
			traffic from bandwidth-sensitive switches.
		"""
		_graph = graph.copy()
		paths = {}
		# Find k shortest paths in graph.
		for src in _graph.nodes():
			paths.setdefault(src, {src: [[src] for i in range(k)]})
			for dst in _graph.nodes():
				if src == dst:
					continue
				paths[src].setdefault(dst, [])
				paths[src][dst] = self.k_shortest_paths(_graph, src, dst, weight=weight, k=k)
		return paths

	def register_access_info(self, dpid, in_port, ip, mac):
		"""
			Register access host info into access table.
		"""
		if in_port in self.access_ports[dpid]:
			if (dpid, in_port) in self.access_table:
				if self.access_table[(dpid, in_port)] == (ip, mac):
					return
				else:
					self.access_table[(dpid, in_port)] = (ip, mac)
					return
			else:
				self.access_table.setdefault((dpid, in_port), None)
				self.access_table[(dpid, in_port)] = (ip, mac)
				return

	def show_topology(self):
		if self.pre_link_to_port != self.link_to_port and setting.TOSHOW:
			# It means the link_to_port table has changed.
			_graph = self.graph.copy()
			print("\n---------------------Link Port---------------------")
			print('%6s' % ('switch'))
			for node in sorted([node for node in _graph.nodes()], key=lambda node: node):
				print('%6d' % node)
			print()
			for node1 in sorted([node for node in _graph.nodes()], key=lambda node: node):
				print('%6d' % node1)
				for node2 in sorted([node for node in _graph.nodes()], key=lambda node: node):
					if (node1, node2) in self.link_to_port.keys():
						print('%6s' % str(self.link_to_port[(node1, node2)]))
					else:
						print('%6s' % '/')
				print()
			print()
			self.pre_link_to_port = self.link_to_port.copy()

		if self.pre_access_table != self.access_table and setting.TOSHOW:
			# It means the access_table has changed.
			print("\n----------------Access Host-------------------")
			print('%10s' % 'switch', '%10s' % 'port', '%22s' % 'Host')
			if not self.access_table.keys():
				print("    NO found host")
			else:
				for sw in sorted(self.access_table.keys()):
					print('%10d' % sw[0], '%10d      ' % sw[1], self.access_table[sw])
			print()
			self.pre_access_table = self.access_table.copy()

		# nx.draw(self.graph)
		# plt.savefig("/home/huangmc/exe/matplotlib/%d.png" % int(time.time()))