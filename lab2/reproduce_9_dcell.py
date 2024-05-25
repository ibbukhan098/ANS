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

import topo
import random
import matplotlib
matplotlib.use('Agg')  # Or 'Qt5Agg', 'GTK3Agg', etc., depending on what's installed
import matplotlib.pyplot as plt
import heapq

# Initialize DCell topology
num_switches = 4
num_ports = 2
num_servers = 20

dcell_topo = topo.DCell(num_servers, num_switches, num_ports)

# TODO: code for reproducing Figure 9 in the DCell paper
# Helper functions
def dijkstra(start_node, nodes_dict):
    distances = {node_id: float('inf') for node_id in nodes_dict}
    distances[start_node.id] = 0
    priority_queue = [(0, start_node.id)]
    visited = set()

    while priority_queue:
        current_distance, current_node_id = heapq.heappop(priority_queue)
        if current_node_id in visited:
            continue
        visited.add(current_node_id)

        current_node = nodes_dict[current_node_id]

        for edge in current_node.edges:
            neighbor = edge.rnode if edge.lnode == current_node else edge.lnode
            if neighbor.id not in visited:
                distance = current_distance + 1
                if distance < distances[neighbor.id]:
                    distances[neighbor.id] = distance
                    heapq.heappush(priority_queue, (distance, neighbor.id))

    return distances

def yen_k_shortest_paths(graph, traffic_pairs, K=8):
    A = []
    B = []
    
    source = traffic_pairs[0]
    target = traffic_pairs[1]
    

    def reconstruct_path(previous_nodes, start, end):
        path = []
        current = end
        while current is not None:
            path.insert(0, current)
            current = previous_nodes[current]
        return path

    def dijkstra_path(graph, source, target):
        distances, previous_nodes = dijkstra(source, graph)
        path = reconstruct_path(previous_nodes, source.id, target.id)
        return path if path[0] == source.id else []

    shortest_path = dijkstra_path(graph, source, target)
    A.append(shortest_path)

    for k in range(1, K):
        for i in range(len(A[-1]) - 1):
            spur_node = A[-1][i]
            root_path = A[-1][:i+1]

            edges_removed = []
            for path in A:
                if len(path) > i and root_path == path[:i+1]:
                    edge_start = path[i]
                    edge_end = path[i+1]
                    for node in graph:
                        if node.id == edge_start:
                            try:
                                edge = next(edge for edge in node.edges if (edge.rnode.id == edge_end or edge.lnode.id == edge_end))
                                node.edges.remove(edge)
                                edges_removed.append(edge)
                            except StopIteration:
                                continue

            spur_path = dijkstra_path(graph, next(node for node in graph if node.id == spur_node), target)

            if spur_path:
                total_path = root_path[:-1] + spur_path
                if total_path not in B:
                    heapq.heappush(B, (len(total_path), total_path))

            for edge in edges_removed:
                edge.lnode.edges.append(edge)
                edge.rnode.edges.append(edge)

        if not B:
            break

        A.append(heapq.heappop(B)[1])

    return A

def yen_k_ecmp_shortest_paths(graph, traffic_pairs, K=8):
    A = []
    B = []
    
    source = traffic_pairs[0]
    target = traffic_pairs[1]

    def reconstruct_path(previous_nodes, start, end):
        path = []
        current = end
        while current is not None:
            path.insert(0, current)
            current = previous_nodes[current]
        return path

    def dijkstra_path(graph, source, target):
        distances, previous_nodes = dijkstra(source, graph)
        path = reconstruct_path(previous_nodes, source.id, target.id)
        return path if path[0] == source.id else []

    shortest_path = dijkstra_path(graph, source, target)
    A.append(shortest_path)

    for k in range(1, K):
        for i in range(len(A[-1]) - 1):
            spur_node = A[-1][i]
            root_path = A[-1][:i+1]

            edges_removed = []
            for path in A:
                if len(path) > i and root_path == path[:i+1]:
                    edge_start = path[i]
                    edge_end = path[i+1]
                    for node in graph:
                        if node.id == edge_start:
                            try:
                                edge = next(edge for edge in node.edges if (edge.rnode.id == edge_end or edge.lnode.id == edge_end))
                                node.edges.remove(edge)
                                edges_removed.append(edge)
                            except StopIteration:
                                continue

            spur_path = dijkstra_path(graph, next(node for node in graph if node.id == spur_node), target)

            if spur_path:
                total_path = root_path[:-1] + spur_path
                if len(total_path) == len(shortest_path) and total_path not in B:
                    heapq.heappush(B, (len(total_path), total_path))

            for edge in edges_removed:
                edge.lnode.edges.append(edge)
                edge.rnode.edges.append(edge)

        if not B:
            break

        A.append(heapq.heappop(B)[1])

    return A

def dijkstra_path(graph, start, end):
    shortest_paths = dijkstra(graph, start)
    path = []
    node = end

    while node is not None:
        path.append(node)
        next_node = shortest_paths[node][0]
        node = next_node

    path = path[::-1]
    return path if path[0] == start else None

# Create adjacency list from DCell topology
graph = {}
for node in dcell_topo.all_nodes:
    graph[node.id] = {}
for node in dcell_topo.all_nodes:
    for edge in node.edges:
        graph[edge.lnode.id][edge.rnode.id] = 1
        graph[edge.rnode.id][edge.lnode.id] = 1

# Generate random permutation traffic
servers = [node.id for node in dcell_topo.servers]
permutation = servers[:]
random.shuffle(permutation)
traffic_pairs = list(zip(servers, permutation))


# Count link occurrences
def count_link_occurrences(all_paths):
    link_occurrences = {}
    for path in all_paths:
        links_in_path = list(zip(path, path[1:]))
        for link in links_in_path:
            if link not in link_occurrences:
                link_occurrences[link] = 1
            else:
                link_occurrences[link] += 1
    return link_occurrences

# Evaluate and count paths
all_paths_8_shortest = yen_k_shortest_paths(graph, traffic_pairs, 8)
all_paths_8_ecmp = yen_k_ecmp_shortest_paths(graph, traffic_pairs, 8)
all_paths_64_ecmp = yen_k_ecmp_shortest_paths(graph, traffic_pairs, 64)

link_occurrences_8_shortest = count_link_occurrences(all_paths_8_shortest)
link_occurrences_8_ecmp = count_link_occurrences(all_paths_8_ecmp)
link_occurrences_64_ecmp = count_link_occurrences(all_paths_64_ecmp)

# Rank links
def rank_links(link_occurrences):
    return sorted(link_occurrences.items(), key=lambda item: item[1])

links_ranked_8_shortest = rank_links(link_occurrences_8_shortest)
links_ranked_8_ecmp = rank_links(link_occurrences_8_ecmp)
links_ranked_64_ecmp = rank_links(link_occurrences_64_ecmp)

# Extract ranks and occurrences for plotting
ranked_links_8_shortest = [link[0] for link in links_ranked_8_shortest]
ranked_occurrences_8_shortest = [link[1] for link in links_ranked_8_shortest]

ranked_links_8_ecmp = [link[0] for link in links_ranked_8_ecmp]
ranked_occurrences_8_ecmp = [link[1] for link in links_ranked_8_ecmp]

ranked_links_64_ecmp = [link[0] for link in links_ranked_64_ecmp]
ranked_occurrences_64_ecmp = [link[1] for link in links_ranked_64_ecmp]

# Plot the graph
plt.figure(figsize=(10, 6))
plt.step(range(1, len(ranked_links_64_ecmp) + 1), ranked_occurrences_64_ecmp, where='mid', label='64 way ECMP')
plt.step(range(1, len(ranked_links_8_ecmp) + 1), ranked_occurrences_8_ecmp, where='mid', label='8 way ECMP')
plt.step(range(1, len(ranked_links_8_shortest) + 1), ranked_occurrences_8_shortest, where='mid', label='8 Shortest Path')

plt.xlabel('Rank of Links')
plt.ylabel('Number of Distinct Paths')
plt.title('d-cell-ecmp')
plt.legend()
plt.show()