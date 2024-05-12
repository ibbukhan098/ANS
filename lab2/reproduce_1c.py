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
 
import matplotlib
matplotlib.use('TkAgg')  # Or 'Qt5Agg', 'GTK3Agg', etc., depending on what's installed
import matplotlib.pyplot as plt
import numpy as np
import random
import heapq
import networkx as nx

import topo

# Same setup for Jellyfish and fat-tree
num_servers = 686
num_switches = 245
num_ports = 14

ft_topo = topo.Fattree(num_ports)
jf_topo = topo.Jellyfish(num_servers, num_switches, num_ports)

# TODO: code for reproducing Figure 1(c) in the jellyfish paper
# Function to implement Dijkstra's shortest path algorithm
def dijkstra(graph, start):
    distances = {node: float('infinity') for node in graph}
    distances[start] = 0
    priority_queue = [(0, start)]

    while priority_queue:
        current_distance, current_node = heapq.heappop(priority_queue)

        if current_distance > distances[current_node]:
            continue

        # Process each neighbor; graph[current_node] should be a dictionary
        for neighbor, weight in graph[current_node].items():
            distance = current_distance + weight
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                heapq.heappush(priority_queue, (distance, neighbor))

    return distances

# Function to create a graph from topology data
def create_graph(topology):
    graph = {}
    for node in topology.servers + topology.switches:
        graph[node.id] = {}
    for node in topology.servers + topology.switches:
        for edge in node.edges:
            neighbor = edge.rnode if edge.lnode == node else edge.lnode
            graph[node.id][neighbor.id] = 1
            graph[neighbor.id][node.id] = 1  # Ensure bidirectional connectivity for undirected graph

    # Debugging output
    # for node_id, connections in graph.items():
    #     print(f"Node {node_id} connections: {len(connections)}")
    return graph

# Create graphs
ft_graph = create_graph(ft_topo)
jf_graph = create_graph(jf_topo)

# Calculate shortest paths for all server pairs
def calculate_path_lengths(graph):
    path_lengths = {}
    for server in graph:
        # Pass the server ID, not the server object
        path_lengths[server] = dijkstra(graph, server)
        # print(f"Calculated path lengths from {server}: {path_lengths[server]}")
    return path_lengths

ft_paths = calculate_path_lengths(ft_graph)
jf_paths = calculate_path_lengths(jf_graph)

# Calculate path length distributions
def path_length_distribution(paths):
    dist = {}
    for start in paths:
        for end, length in paths[start].items():
            if length == float('inf'):
                # print(f"Unreachable path from {start} to {end}")
                continue
            if length in dist:
                dist[length] += 1
            else:
                dist[length] = 1
    return dist

ft_dist = path_length_distribution(ft_paths)
jf_dist = path_length_distribution(jf_paths)

# Normalize distributions
def normalize_distribution(dist, total_pairs):
    for length in list(dist.keys()):  # Use list to avoid dictionary size change during iteration
        if length == float('inf'):
            del dist[length]  # Remove infinite lengths from distribution
            continue
        dist[length] /= total_pairs
    return dist

total_pairs = num_servers * (num_servers - 1)  # Exclude self-pairs
ft_dist = normalize_distribution(ft_dist, total_pairs)
jf_dist = normalize_distribution(jf_dist, total_pairs)

# Plotting
print(ft_dist.keys(), ft_dist.values())
print(jf_dist.keys(), jf_dist.values())
plt.bar(ft_dist.keys(), ft_dist.values(), width=0.4, label='Fat-tree', alpha=0.6)
plt.bar(jf_dist.keys(), jf_dist.values(), width=0.4, label='Jellyfish', alpha=0.6, color='r')
plt.xlabel('Path Length')
plt.ylabel('Fraction of Server Pairs')
plt.title('Path Length Distribution')
plt.legend()
plt.show()
# print(matplotlib.rcsetup.all_backends)

# G = nx.Graph()
# for node in ft_topo.servers + ft_topo.switches:
#     for edge in node.edges:
#         G.add_edge(edge.lnode.id, edge.rnode.id)
# nx.draw(G, with_labels=True)
# plt.show()