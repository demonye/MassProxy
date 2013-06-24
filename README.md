MassProxy
=========

A Simple Proxy Server to maintain massive connections esitablished between clients and servers

Introduction
------------
The main issue of MassProxy to resolve is for massive clients connecting to a bunch of servers via a single (or few) entries. MassProxy is trying to maintain lots of network connections and transparently transfer data between clients and servers. To approach this, MassProxy is using scalable event notification mechanism (say, epoll in Linux 2.6+ for now and intended to be ported to other platforms in the future, like kqueue in FreeBSD).



Event notification
------------------


Connections list
----------------


Thread pool
-----------
