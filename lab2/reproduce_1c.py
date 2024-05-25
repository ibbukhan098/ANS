"""
 Copyright 2024 Computer Networks Group @ UPB

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, soft_topoware
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 """
 
import matplotlib
matplotlib.use('Agg')  # Or 'Qt5Agg', 'GTK3Agg', etc., depending on what's installed
import matplotlib.pyplot as plt
import heapq
import time
import topo
import networkx as nx

# Function to implement Dijkstra's shortest path algorithm
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

# Initialize Fat-tree topology
k = 4  # Fat-tree parameter
ft_topo = topo.Fattree(k)

# Compute shortest paths for Fat-tree
path_lengths_ft_topo = []

start_time = time.time()
for server1 in ft_topo.servers:
    distances = dijkstra(server1, ft_topo.nodes)
    for server2 in ft_topo.servers:
        if server1 != server2:
            path_length = distances.get(server2.id, float('inf'))
            path_lengths_ft_topo.append(path_length)
end_time = time.time()
print(f"Fat-tree shortest paths computation took {end_time - start_time} seconds.")

# Initialize Jellyfish topology parameters
num_switches = 245
num_ports = 14
num_servers = 686
num_trials = 10  # Number of trials for Jellyfish topology

# Compute shortest paths for Jellyfish over multiple trials
all_histograms_jf_topo = []

for trial in range(num_trials):
    print(f"Trial {trial + 1}/{num_trials} for Jellyfish topology")
    jf_topo = topo.Jellyfish(num_switches, num_ports, num_servers)
    path_lengths_jf_topo = []

    start_time = time.time()
    for server1 in jf_topo.servers:
        distances = dijkstra(server1, {node.id: node for node in jf_topo.all_nodes})
        for server2 in jf_topo.servers:
            if server1 != server2:
                path_length = distances.get(server2.id, float('inf'))
                path_lengths_jf_topo.append(path_length)
    end_time = time.time()
    print(f"Jellyfish shortest paths computation for trial {trial + 1} took {end_time - start_time} seconds.")

    # Create histogram for the current trial
    max_length = max(path_lengths_jf_topo) if path_lengths_jf_topo else 0
    histogram_jf_topo = [0] * (max_length + 1)

    for length in path_lengths_jf_topo:
        histogram_jf_topo[length] += 1
    
    all_histograms_jf_topo.append(histogram_jf_topo)

# Average the histograms over all trials
max_length_jf = max(max(len(hist) for hist in all_histograms_jf_topo), max(path_lengths_ft_topo))
average_histogram_jf_topo = [0] * (max_length_jf + 1)

for hist in all_histograms_jf_topo:
    for i, count in enumerate(hist):
        average_histogram_jf_topo[i] += count

average_histogram_jf_topo = [count / num_trials for count in average_histogram_jf_topo]

# Prepare Fat-tree histogram
max_length_ft = max(path_lengths_ft_topo)
histogram_ft_topo = [0] * (max_length_ft + 1)

for length in path_lengths_ft_topo:
    histogram_ft_topo[length] += 1

# Normalize the histograms to fractions of server pairs
total_pairs_ft_topo = len(ft_topo.servers) * (len(ft_topo.servers) - 1)
fractions_ft_topo = [count / total_pairs_ft_topo for count in histogram_ft_topo]

total_pairs_jf_topo = len(jf_topo.servers) * (len(jf_topo.servers) - 1)
fractions_jf_topo = [count / total_pairs_jf_topo for count in average_histogram_jf_topo]

# Plotting the histograms in one plot
# plt.figure(figsize=(12, 6))
# plt.bar(range(len(fractions_ft_topo)), fractions_ft_topo, color='skyblue', alpha=0.7, label='Fat-tree')
# plt.bar(range(len(fractions_jf_topo)), fractions_jf_topo, color='lightgreen', alpha=0.5, label='Jellyfish')

# plt.xlabel('Path Length')
# plt.ylabel('Fraction of Server Pairs')
# plt.title('Shortest Path Length Distribution: Fat-tree vs. Jellyfish')
# plt.legend()
# plt.grid(True)
# plt.savefig('images/reproduce_1c.png')  # Save the plot as a PNG file
# plt.close()

dcell_topo = topo.DCell
G = nx.Graph()
for node in dcell_topo.servers + dcell_topo.switches:
    for edge in node.edges:
        G.add_edge(edge.lnode.id, edge.rnode.id)
nx.draw(G, with_labels=True)
plt.show()