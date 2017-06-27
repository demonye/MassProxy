import fcntl
import socket


def set_close_exec(fd):
    """
    Set FD_CLOEXEC flag to the socket descriptor

    :param fd: socket descriptor
    """
    flags = fcntl.fcntl(fd, fcntl.F_GETFD)
    fcntl.fcntl(fd, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)


def connect_to(host, port):
    """
    Connect to a server

    :param host: host/ip to connect
    :param port: the port to connect
    :returns: socket descriptor which is connected
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    return sock


def bind_socket(port, host="0.0.0.0", backlog=128):
    """
    Bind and listen to port and host/ip and return socket object

    :param port: the port to be bound
    :param host: the host/ip to be bound
    :param backlog: how many connections can be hold in queue

    :returns: the socket object bound to the given port
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    set_close_exec(sock.fileno())
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(backlog)
    return sock

# def ip2long(ip):
#     struct.unpack('>L', socket.inet_aton(ip))[0]

# def long2ip(num):
#     socket.inet_ntoa(struct.pack('>L', num))

# def port2short(port):
#     struct.unpack('>H', port)[0]

# def short2port(num):
#     struct.pack('>H', num)
