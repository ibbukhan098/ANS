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


import random
# Class for an edge in the graph
class Edge:
	def __init__(self):
		self.lnode = None
		self.rnode = None
	
	def remove(self):
		self.lnode.edges.remove(self)
		self.rnode.edges.remove(self)
		self.lnode = None
		self.rnode = None

# Class for a node in the graph
class Node:
	def __init__(self, id, type):
		self.edges = []
		self.id = id
		self.type = type

	# Add an edge connected to another node
	def add_edge(self, node):
		edge = Edge()
		edge.lnode = self
		edge.rnode = node
		self.edges.append(edge)
		node.edges.append(edge)
		return edge

	# Remove an edge from the node
	def remove_edge(self, edge):
		self.edges.remove(edge)

	# Decide if another node is a neighbor
	def is_neighbor(self, node):
		for edge in self.edges:
			if edge.lnode == node or edge.rnode == node:
				return True
		return False


class Jellyfish:

	def __init__(self, num_servers, num_switches, num_ports):
		self.servers = []
		self.switches = []
		self.generate(num_servers, num_switches, num_ports)

	def generate(self, num_servers, num_switches, num_ports):
        	# Initialize switches
			for i in range(num_switches):
				self.switches.append(Node(f"switch-{i}", "switch"))

			# Initialize servers
			for i in range(num_servers):
				self.servers.append(Node(f"server-{i}", "server"))

			# Connect each switch with random links until all ports are used
			available_switches = [s for s in self.switches if len(s.edges) < num_ports]
			while available_switches:
				s1 = random.choice(available_switches)
				potential_s2 = [s for s in available_switches if s != s1 and not s1.is_neighbor(s)]

				# Only proceed if there is at least one valid s2
				if potential_s2:
					s2 = random.choice(potential_s2)
					s1.add_edge(s2)
					# Update available_switches directly after adding an edge
					if len(s1.edges) >= num_ports:
						available_switches.remove(s1)
					if len(s2.edges) >= num_ports:
						available_switches.remove(s2)
				else:
					# Remove s1 from available_switches if no valid s2 can be found
					available_switches.remove(s1)

			# Re-check to ensure no switch exceeds its port limit (optional sanity check)
			assert all(len(s.edges) <= num_ports for s in self.switches), "Some switches exceed port limit"

class Fattree:

	def __init__(self, num_ports):
		self.servers = []
		self.switches = []
		self.generate(num_ports)

	def generate(self, num_ports):

		# TODO: code for generating the fat-tree topology
		k = num_ports  # 'k' is the number of ports in the fat-tree
		num_pods = k
		num_core_switches = (k // 2) ** 2
		num_agg_switches_per_pod = k // 2
		num_edge_switches_per_pod = k // 2
		num_servers_per_edge_switch = k // 2

		# Create core switches
		core_switches = [Node(f"core-{i}", "switch") for i in range(num_core_switches)]

		# Create pods with aggregation and edge switches
		pods = []
		for i in range(num_pods):
			agg_switches = [Node(f"agg-{i}-{j}", "switch") for j in range(num_agg_switches_per_pod)]
			edge_switches = [Node(f"edge-{i}-{j}", "switch") for j in range(num_edge_switches_per_pod)]
			servers = [Node(f"server-{i}-{j}-{l}", "server") for j in range(num_edge_switches_per_pod) for l in range(num_servers_per_edge_switch)]
			
			# Connect edge switches to servers
			for es, sv in zip(edge_switches, servers):
				es.add_edge(sv)
			
			# Connect edge switches to aggregation switches
			for es in edge_switches:
				for asw in agg_switches:
					es.add_edge(asw)
			
			# Connect aggregation switches to core switches
			for asw in agg_switches:
				for cs in core_switches:
					asw.add_edge(cs)
			
			pods.append((agg_switches, edge_switches, servers))
   
		self.servers = [server for pod in pods for server in pod[2]]
		self.switches = core_switches + [sw for pod in pods for sws in pod[:2] for sw in sws]