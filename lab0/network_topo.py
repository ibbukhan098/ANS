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

#!/usr/bin/python

from mininet.topo import Topo

class NetworkTopo(Topo):

    "Simple topology example."
    def __init__( self ):
        "Create custom topo."

        # Initialize topology
        Topo.__init__( self )


        h1 = self.addHost( 'h1' )
        h2 = self.addHost( 'h2' )
        h3 = self.addHost( 'h3' )
        h4 = self.addHost( 'h4' )
        # ext = self.addHost('ext')
        # ser = self.addHost('ser')

        s1 = self.addSwitch( 's1' )
        s2 = self.addSwitch( 's2' )
        # s3 = self.addSwitch( 's3' )

        self.addLink( h1, s1, bw = 15, delay = 10 )
        self.addLink( h2, s1, bw = 15, delay = 10 )
        self.addLink( s1, s2, bw = 15, delay = 10 )
        self.addLink( s2, h3, bw = 15, delay = 10 )
        self.addLink( s2, h4, bw = 15, delay = 10 )

        # self.addLink( s2, ser, bw = 15, delay = 10 )

        # self.addLink( s3, ext, bw = 15, delay = 10 )

        # self.addLink( s1, s2 )
        # self.addLink( s3, s2 )

topos = { 'mytopo': ( lambda: NetworkTopo() ) }
