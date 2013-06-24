#!/usr/bin/env python2

import sys
import errno
import threading
from select import *
from ps_util import *
from ps_struct import *
from argparse import ArgumentParser
from multiprocessing.pool import ThreadPool

conn_list = ConnList()
monitor_lock = threading.Lock()
ep = epoll()

_EPOLLRDHUP = 0x2000
READ = EPOLLIN | _EPOLLRDHUP
WRITE = EPOLLOUT
ERROR = EPOLLHUP | EPOLLERR
READMODE = READ | ERROR | EPOLLET
WRITEMODE = WRITE | ERROR | EPOLLET
BUFSIZE = 4096

def read_header(fd):
    _ip = fd.recv(4)
    ip = socket.inet_ntoa(_ip)
    _port = fd.recv(2)
    port = struct.unpack('>H', _port)[0]
    return ip, port

def add_monitor(fd):
    host, port = read_header(fd)
    opfd = connect_to(host, port)
    with monitor_lock:
        if opfd:
            conn_list[fd.fileno()] = ConnItem(fd, opfd, 'C')
            fd.setblocking(0)
            opfd.setblocking(0)
            ep.register(fd.fileno(), READMODE)
            ep.register(opfd.fileno(), READMODE)
        else:
            fd.close()

def remove_monitor(fd):
    with monitor_lock:
        item = conn_list[fd.fileno()]
        opfd = item.opfd
        ep.unregister(opfd.fileno())
        ep.unregister(fd.fileno())
        del conn_list[fd]
        fd.close()
        opfd.close()

def accept_process(sock):
    while True:
        try:
            fd, addr = sock.accept()
            add_monitor(fd)
        except socket.error as ex:
            if ex.args[0] != errno.EINTR:
                raise

def read_handler(fd_):
    thd = threading.currentThread()
    item = conn_list.get(fd_, None)
    fd = item.fd
    if item == None:
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
    parser = ArgumentParser(description="A simple proxy server for massive connections")
    parser.add_argument('-p', '--port', type=int, default=1234,
            help="Socket port to listen" )
    parser.add_argument('--thread', type=int, default=4,
            help="How many working threads to handle connections" )
    parser.add_argument('--timeout', type=int, default=-1,
            help="Timeout seconds for epoll to wait" )
    parser.add_argument('--maxevents', type=int, default=20,
            help="Maximum events one time for epoll to wait" )
    args = parser.parse_args()
    port, thds, tmout, maxevts = args.port, args.thread, args.timeout, args.maxevents

    sock = bind_socket(args.port)
    pool = ThreadPool(thds)

    a_proc = threading.Thread(target=accept_process, args=(sock,))
    a_proc.start()
    while True:
        for (fd, evts) in ep.poll(tmout, maxevts):
            if evts & (READ | ERROR):
                ep.unregister(fd)
                pool.apply(read_handler, [fd])


if __name__ == "__main__":
    main()

