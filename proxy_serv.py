#!/usr/bin/env python2

import errno
import threading
import socket
import struct
import select
import argparse
from multiprocessing import pool

import ps_util
import ps_struct

conn_list = ps_struct.ConnList()
monitor_lock = threading.Lock()
ep = select.epoll()

_EPOLLRDHUP = 0x2000
READ = select.EPOLLIN | _EPOLLRDHUP
WRITE = select.EPOLLOUT
ERROR = select.EPOLLHUP | select.EPOLLERR
READMODE = READ | ERROR | select.EPOLLET
WRITEMODE = WRITE | ERROR | select.EPOLLET
BUFSIZE = 4096


def read_header(fd):
    """
    Given the socket descriptor, get ip and port from data header

    :param fd: socket descriptor to read data header
    :returns: IP address, port of the server to connect
    """
    _ip = fd.recv(4)
    ip = socket.inet_ntoa(_ip)
    _port = fd.recv(2)
    port = struct.unpack('>H', _port)[0]
    return ip, port


def add_monitor(fd):
    """
    Get server information from the given socket descriptor (client),
    connect and then start monitoring both client and server descriptors.

    :param fd: socket descriptor to be monitored
    """
    host, port = read_header(fd)
    opfd = ps_util.connect_to(host, port)
    with monitor_lock:
        if opfd:
            conn_list[fd.fileno()] = ps_struct.ConnItem(fd, opfd, 'C')
            fd.setblocking(0)
            opfd.setblocking(0)
            ep.register(fd.fileno(), READMODE)
            ep.register(opfd.fileno(), READMODE)
        else:
            fd.close()


def remove_monitor(fd):
    """
    Given client or server descriptor, stop monitoring both sides

    :param fd: Client or server socket descriptor
    """
    with monitor_lock:
        item = conn_list[fd.fileno()]
        opfd = item.opfd
        ep.unregister(opfd.fileno())
        ep.unregister(fd.fileno())
        del conn_list[fd]
        fd.close()
        opfd.close()


def accept_process(sock):
    """
    Accept the inbound connection and monitor the socket descriptor

    :param sock: the socket object which has been bound
    :raises: raise exceptiion for socket error,
             if being interrupted by signal, ignore and continue
    """
    while True:
        try:
            fd, addr = sock.accept()
            add_monitor(fd)
        except socket.error as ex:
            if ex.args[0] != errno.EINTR:
                raise


def read_handler(fd_):
    """
    Given client or server descriptor, stop monitoring both sides

    :param fd_: Client or server socket descriptor
    :raises Exception: raise error if not EWOULDBLOCK and EAGAIN
    """
    item = conn_list.get(fd_, None)
    fd = item.fd
    if item is None:
        return
    opfd = item.opfd
    while True:
        data = ""
        try:
            data = fd.recv(BUFSIZE)
            if len(data) == 0:
                remove_monitor(fd)
                break
            opfd.sendall(data)
            ep.register(fd_, READMODE)
        except socket.error as e:
            if e.args[0] in (errno.EWOULDBLOCK, errno.EAGAIN):
                break
            else:
                raise


def main():
    """Main entry of the application, including 5 steps
        1) parse the arguments
        2) bind the port
        3) create the thread pool
        4) start the accept thread
        5) start epoll loop
    """

    parser = argparse.ArgumentParser(
        description="A simple proxy server for massive connections")
    parser.add_argument(
        '-p', '--port', type=int, default=1234,
        help="Socket port to listen")
    parser.add_argument(
        '--thread', type=int, default=4,
        help="How many working threads to handle connections")
    parser.add_argument(
        '--timeout', type=int, default=-1,
        help="Timeout seconds for epoll to wait")
    parser.add_argument(
        '--maxevents', type=int, default=20,
        help="Maximum events one time for epoll to wait")
    args = parser.parse_args()
    thds, tmout, maxevts = args.thread, args.timeout, args.maxevents

    sock = ps_util.bind_socket(args.port)
    pool = pool.ThreadPool(thds)

    a_proc = threading.Thread(target=accept_process, args=(sock,))
    a_proc.start()
    while True:
        for (fd, evts) in ep.poll(tmout, maxevts):
            if evts & (READ | ERROR):
                ep.unregister(fd)
                pool.apply(read_handler, [fd])


if __name__ == "__main__":
    """Call main function, start proxy server"""
    main()
