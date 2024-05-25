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