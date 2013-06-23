import threading
import socket


class ConnItem(object):
    _types = ('C', 'S')

    def __init__(self, fd, opfd, ctype):
        self.fd = fd
        self.opfd = opfd
        self.ctype = ctype
        self.valid_value()

    def valid_value(self):
        if type(self.fd) != socket.socket:
            raise ValueError
        if type(self.opfd) != socket.socket:
            raise ValueError
        if self.ctype not in ConnItem._types:
            raise ValueError

    def is_client(self):
        return self.ctype == 'C'


class ConnList(dict):
    _lock = threading.Lock()

    def revert_type(self, t):
        if t == ConnItem._types[0]:
            return ConnItem._types[1]
        if t == ConnList._types[1]:
            return ConnItem._types[0]
        return None

    def __setitem__(self, k, item):
        item.valid_value()
        fd, opfd, t = item.fd, item.opfd, item.ctype
        rt = self.revert_type(t)

        with ConnList._lock:
            super(ConnList, self).__setitem__(k, item)
            super(ConnList, self).__setitem__(
                    opfd.fileno(),
                    ConnItem(opfd, fd, rt)
                    )


    def __delitem__(self, k):
        item = self.get(k, None)
        if item == None:
            return
        print "item", item
        opfd = item.opfd
        print "opfd", opfd.fileno()
        print "opfd.fileno()", self.get(opfd.fileno(), None)
        with ConnList._lock:
            super(ConnList, self).__delitem__(k)
            super(ConnList, self).__delitem__(opfd.fileno())

