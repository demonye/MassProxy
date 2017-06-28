#!/usr/bin/env python

import sys
import errno
import threading
import socket
import struct
import select
import argparse
import logging
from multiprocessing import pool

import ps_util
import ps_struct

SOCKET_TIMEOUT = 3
_EPOLLRDHUP = 0x2000
READ = select.EPOLLIN | _EPOLLRDHUP
WRITE = select.EPOLLOUT
ERROR = select.EPOLLHUP | select.EPOLLERR
READMODE = READ | ERROR | select.EPOLLET
WRITEMODE = WRITE | ERROR | select.EPOLLET
BUFSIZE = 4096


def set_logger(name, verbose=2):
    level = {
        0: logging.ERROR,
        1: logging.WARNING,
        3: logging.DEBUG,
    }.get(verbose, logging.INFO)

    logging.basicConfig(
        format='[%(asctime)s] %(message)s',
        datefmt='%d/%b/%Y %H:%M:%S',
        level=level,
        handlers=[logging.StreamHandler(sys.stdout)]
    )


class Proxy(object):
    """
    Proxy class that starts a thread to accept connection
    and put working threads in pool
    """

    def __init__(self, sock):
        """
        Initialize data

        :param sock: socket object bound to host/port
        """
        self.conn_list = ps_struct.ConnList()
        self.monitor_lock = threading.Lock()
        self.ep = select.epoll()
        self.sock = sock
        self.keeprun = True

    def read_header(self, fd):
        """
        Given the socket descriptor, get ip and port from data header

        :param fd: socket descriptor to read data header
        :return: IP address, port of the server to connect
        """
        _ip = fd.recv(4)
        ip = socket.inet_ntoa(_ip)
        _port = fd.recv(2)
        port = struct.unpack('>H', _port)[0]
        return ip, port

    def add_monitor(self, fd):
        """
        Get server information from the given socket descriptor (client),
        connect and then start monitoring both client and server descriptors.

        :param fd: socket descriptor to be monitored
        """
        logging.debug('Reading data header')
        host, port = self.read_header(fd)
        logging.info('Connecting to the server %s, %d', host, port)
        opfd = ps_util.connect_to(host, port)
        with self.monitor_lock:
            if opfd:
                self.conn_list[fd.fileno()] = ps_struct.ConnItem(fd, opfd, 'C')
                fd.setblocking(0)
                opfd.setblocking(0)
                self.ep.register(fd.fileno(), READMODE)
                self.ep.register(opfd.fileno(), READMODE)
                logging.debug('Start monitoring %d, %d',
                              fd.fileno(), opfd.fileno())
            else:
                fd.close()
                logging.warning('Connecting attempt failed')

    def remove_monitor(self, fd):
        """
        Given client or server descriptor, stop monitoring both sides

        :param fd: Client or server socket descriptor
        """
        with self.monitor_lock:
            item = self.conn_list[fd.fileno()]
            opfd = item.opfd
            self.ep.unregister(opfd.fileno())
            self.ep.unregister(fd.fileno())
            del self.conn_list[fd]
            fd.close()
            opfd.close()
            logging.debug('Stop monitoring %d, %d',
                          fd.fileno(), opfd.fileno())

    def accept_process(self):
        """
        Accept the inbound connection and monitor the socket descriptor

        :raises: raise exceptiion for socket error,
                if being interrupted by signal, ignore and continue
        """
        while self.keeprun:
            try:
                fd, addr = self.sock.accept()
                logging.debug('Connectiong accepted')
                self.add_monitor(fd)
            except socket.timeout:
                logging.debug('Accept timout')
                continue
            except socket.error as ex:
                if ex.args[0] != errno.EINTR:
                    raise
                logging.error('EINTR error %s', ex)

    def read_handler(self, fd):
        """
        Given client or server descriptor, stop monitoring both sides

        :param fd: Client or server socket descriptor
        :raises Exception: raise error if not EWOULDBLOCK and EAGAIN
        """
        item = self.conn_list.get(fd, None)
        _fd = item.fd
        if item is None:
            logging.warning('Not able to get item for %d', fd.fileno())
            return
        opfd = item.opfd
        while self.keeprun:
            data = ""
            try:
                logging.debug('Reading data from %d', _fd.fileno())
                data = _fd.recv(BUFSIZE)
                if len(data) == 0:
                    logging.debug('Socket closed: %d', _fd.fileno())
                    self.remove_monitor(_fd)
                    break
                logging.debug('Writing data to %d', opfd.fileno())
                opfd.sendall(data)
                self.ep.register(fd, READMODE)
            except socket.error as e:
                if e.args[0] in (errno.EWOULDBLOCK, errno.EAGAIN):
                    logging.warning('Got EWOULDBLOCK or EAGAIN: %s', e)
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
        description="A simple proxy server for massive connections"
    )
    parser.add_argument(
        '-p', '--port', type=int, default=1234,
        help="Socket port to listen"
    )
    parser.add_argument(
        '--thread', type=int, default=4,
        help="How many working threads to handle connections"
    )
    parser.add_argument(
        '--timeout', type=int, default=-1,
        help="Timeout seconds for epoll to wait"
    )
    parser.add_argument(
        '--maxevents', type=int, default=20,
        help="Maximum events one time for epoll to wait"
    )
    parser.add_argument(
        '-v', '--verbose', type=int, default=2,
        help="Verbose level; 0, 1, 2, 3 (error, warning, info, debug)"
    )

    args = parser.parse_args()
    set_logger("proxy_serv", args.verbose)

    logging.info('Starting server on port %d...', args.port)
    sock = ps_util.bind_socket(args.port)
    logging.debug('Bound to port %d...', args.port)
    sock.settimeout(SOCKET_TIMEOUT)
    pool_ = pool.ThreadPool(args.thread)
    logging.debug('Created thread pool (%d threads)', args.thread)

    logging.info('Starting accept thread...')
    proxy = Proxy(sock)
    a_proc = threading.Thread(target=proxy.accept_process)
    a_proc.start()
    logging.debug('Accept thread started')
    logging.info('Listen to network events, press Ctrl-C to break...')
    while proxy.keeprun:
        try:
            logging.debug('Waiting for READ/ERROR events...')
            for (fd, evts) in proxy.ep.poll(args.timeout, args.maxevents):
                logging.debug('Got events: %x', evts)
                if evts & (READ | ERROR):
                    proxy.ep.unregister(fd)
                    pool_.apply(proxy.read_handler, [fd])
        except KeyboardInterrupt:
            proxy.keeprun = False
            logging.warning("KeyboardInterrupt: quitting...")

    logging.debug('Waiting for ending of accept process')
    a_proc.join()
    logging.info('See ya mate!')


if __name__ == "__main__":
    """Call main function, start proxy server"""
    main()
