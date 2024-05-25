class FattreeNet(Topo):
    """
    Create a fat-tree network in Mininet
    """

    def __init__(self, ft_topo):
        Topo.__init__(self)

        # Create core switches
        core_switches = {}
        for i in range(ft_topo.k // 2):
            core_switches[f'c{i}'] = self.addSwitch(f'c{i}')

        # Create aggregation and edge switches
        agg_switches = {}
        edge_switches = {}
        for pod in range(ft_topo.k):
            for j in range(ft_topo.k // 2):
                agg_switches[f'a{pod}{j}'] = self.addSwitch(f'a{pod}{j}')
                edge_switches[f'e{pod}{j}'] = self.addSwitch(f'e{pod}{j}')

        # Connect core switches to aggregation switches
        for i in range(ft_topo.k // 2):
            for j in range(ft_topo.k):
                self.addLink(core_switches[f'c{i}'], agg_switches[f'a{j}{i}'] )

        # Connect aggregation switches to edge switches
        for pod in range(ft_topo.k):
            for i in range(ft_topo.k // 2):
                for j in range(ft_topo.k // 2):
                    self.addLink(agg_switches[f'a{pod}{i}'], edge_switches[f'e{pod}{j}'])

        # Connect edge switches to hosts
        for pod in range(ft_topo.k):
            for i in range(ft_topo.k // 2):
                for j in range(ft_topo.k // 2):
                    for h in range(ft_topo.k // 2):
                        self.addLink(edge_switches[f'e{pod}{j}'], topo.servers[h])

def make_mininet_instance(graph_topo):
    net_topo = FattreeNet(graph_topo)
    net = Mininet(topo=net_topo, controller=None, autoSetMacs=True, link=TCLink)
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
    ft_topo = topo.Fattree(4)
    run(ft_topo)
