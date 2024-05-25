from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSSwitch, Controller, RemoteController, OVSController
from mininet.cli import CLI
from mininet.log import setLogLevel, info

class FatTreeTopo(Topo):
    def __init__(self, k):
        Topo.__init__(self)
        self.k = k
        self.num_pods = k
        self.num_hosts_per_pod = (k // 2) ** 2
        self.num_core_switches = (k // 2) ** 2
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
                    host_id = (pod * self.k // 2) + edge * self.k // 2 + host + 1
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

def run():
    topo = FatTreeTopo(k=4)
    net = Mininet(topo=topo, switch=OVSSwitch, controller=OVSController)
    # net.addController(
    #     'c1', 
    #     controller=RemoteController, 
    #     ip="127.0.0.1", 
    #     port=6653)
    net.start()
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
