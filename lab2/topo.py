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
import networkx as nx

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
    def __init__(self, num_switches, num_ports, num_servers):
        self.switches = [Node(f"Switch{i}", "switch") for i in range(num_switches)]
        self.servers = [Node(f"Server{i}", "server") for i in range(num_servers)]
        self.all_nodes = self.switches + self.servers
        self.generate_topology(num_ports)

    def generate_topology(self, num_ports):
        # Connect servers to switches
        servers_per_switch = len(self.servers) // len(self.switches)
        extra_servers = len(self.servers) % len(self.switches)
        server_index = 0

        for switch in self.switches:
            for _ in range(servers_per_switch + (extra_servers > 0)):
                if server_index < len(self.servers):
                    switch.add_edge(self.servers[server_index])
                    server_index += 1
            extra_servers -= 1 if extra_servers > 0 else 0

        # Randomly connect switches until all ports are used
        available_ports = {switch: num_ports - servers_per_switch - (extra_servers > 0) for switch in self.switches}

        while True:
            free_switches = [switch for switch, ports in available_ports.items() if ports > 0]
            if len(free_switches) < 2:
                break
            s1, s2 = random.sample(free_switches, 2)
            if not s1.is_neighbor(s2):
                s1.add_edge(s2)
                available_ports[s1] -= 1
                available_ports[s2] -= 1

class Fattree:
    def __init__(self, k):
        self.k = k
        self.nodes = {}
        self.servers = []
        self.generate_fattree(k)

    def generate_fattree(self, k):
        num_pods = k
        num_core_switches = (k // 2) ** 2
        num_agg_switches_per_pod = k // 2
        num_edge_switches_per_pod = k // 2
        num_hosts_per_edge_switch = k // 2

        # Creating core switches
        cores = {f"Core{i}": Node(f"Core{i}", "core") for i in range(num_core_switches)}
        self.nodes.update(cores)

        for p in range(num_pods):
            aggs = {f"Agg{p}-{a}": Node(f"Agg{p}-{a}", "agg") for a in range(num_agg_switches_per_pod)}
            edges = {f"Edge{p}-{e}": Node(f"Edge{p}-{e}", "edge") for e in range(num_edge_switches_per_pod)}
            hosts = {f"Host{p}-{e}-{h}": Node(f"Host{p}-{e}-{h}", "host") for e in range(num_edge_switches_per_pod) for h in range(num_hosts_per_edge_switch)}
            self.nodes.update(aggs)
            self.nodes.update(edges)
            self.nodes.update(hosts)
            self.servers.extend(hosts.values())

            # Connect edges to hosts and aggregation switches
            for edge in edges.values():
                # Connect each edge to its hosts
                for h in range(num_hosts_per_edge_switch):
                    host_id = f"Host{p}-{edge.id[-1]}-{h}"  # `edge.id[-1]` takes the last character from `edge.id` which is the edge index
                    edge.add_edge(hosts[host_id])

                # Connect each edge to all aggregation switches
                for agg in aggs.values():
                    edge.add_edge(agg)

            # Connect aggregation switches to core switches
            for i, agg in enumerate(aggs.values()):
                step = num_core_switches // num_agg_switches_per_pod
                for j in range(step):
                    core_index = (i * step + j) % num_core_switches
                    agg.add_edge(cores[f"Core{core_index}"])
                    
                    
                    
class BCube:
    def __init__(self, k, n):
        self.k = k
        self.n = n
        self.servers = []
        self.switches = []
        self.generate(k, n)

    def generate(self, k, n):
        # Initialize servers and switches
        self.servers = [Node(f'S{i}', 'server') for i in range(n**(k+1))]
        self.switches = [Node(f'Sw{level}_{i}', 'switch') for level in range(k+1) for i in range(n**k)]

        # Connect servers to switches
        for level in range(k+1):
            for switch in range(n**k):
                for port in range(n):
                    server_index = switch * n + port
                    switch_index = level * n**k + switch
                    self.servers[server_index].add_edge(self.switches[switch_index])
    # def display_connections(self):
    #     for server in self.servers:
    #         connections = [(edge.lnode.id, edge.rnode.id) for edge in server.edges]
    #         print(f"{server.id} connections: {connections}")

# Example input for BCube with k=1 and n=4
# bcube = BCube(k=2, n=7)
# bcube.display_connections()

                    
                    
class DCell:
    def __init__(self, num_servers, num_switches, num_ports):
        self.servers = [Node(i, 'server') for i in range(num_servers)]
        self.switches = [Node(i, 'switch') for i in range(num_switches)]
        self.generate(num_servers, num_switches, num_ports)

    def generate(self, num_servers, num_switches, num_ports):
        for switch in self.switches:
            for server in self.servers:
                switch.add_edge(server)
        for i in range(len(self.servers)):
            for j in range(i + 1, len(self.servers)):
                self.servers[i].add_edge(self.servers[j])
#     def visualize(self):
#         G = nx.Graph()
        
#         # We now use the nodes and edges directly from Node and Edge instances
#         for node in self.servers + self.switches:
#             G.add_node(node.id, label=f'{node.id} ({node.type})', type=node.type)
#             for edge in node.edges:
#                 G.add_edge(edge.lnode.id, edge.rnode.id)

#         pos = nx.spring_layout(G)  # Node position layout for visualization
#         node_colors = ['blue' if G.nodes[node]['type'] == 'server' else 'red' for node in G.nodes]

#         # Draw nodes and edges
#         nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=700)
#         nx.draw_networkx_edges(G, pos, alpha=0.5)
#         labels = {node: G.nodes[node]['label'] for node in G.nodes()}
#         nx.draw_networkx_labels(G, pos, labels)

#         plt.title('DCell Network Topology')
#         plt.axis('off')
#         plt.show()

# # Example to instantiate and display connections
# dcell_network = DCell(num_servers=5, num_switches=1, num_ports=2)
# dcell_network.visualize()


