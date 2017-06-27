import threading
import socket


class ConnItem(object):
    _types = ('C', 'S')

    def __init__(self, fd, opfd, ctype):
        """
        Create connection item and validate value

        :param fd: socket descriptor
        :param opfd: socket ddescriptor of the other peer
        :param ctype: connection type (C)lient or (S)erver
        """
        self.fd = fd
        self.opfd = opfd
        self.ctype = ctype
        self.valid_value()

    def valid_value(self):
        """Validate socket descriptors"""
        if type(self.fd) != socket.socket:
            raise ValueError
        if type(self.opfd) != socket.socket:
            raise ValueError
        if self.ctype not in ConnItem._types:
            raise ValueError

    def is_client(self):
        """Check if the type is (C)lient"""
        return self.ctype == 'C'


class ConnList(dict):
    """List of connection items, inherited from dictionary"""

    _lock = threading.Lock()

    def revert_type(self, tp):
        """
        Return the opposite type

        :param tp: connection type
        :return: the opposite type
        """
        try:
            types = ConnItem._types
            return types[1 - types.index(tp)]
        except ValueError:
            pass
        return None

    def __setitem__(self, k, item):
        """
        Set item value with the key k, set the related item as well

        :param k: the key
        :param item: the value
        """
        item.valid_value()
        fd, opfd, ctype = item.fd, item.opfd, item.ctype
        rt = self.revert_type(ctype)

        with self._lock:
            super(ConnList, self).__setitem__(k, item)
            super(ConnList, self).__setitem__(
                opfd.fileno(),
                ConnItem(opfd, fd, rt)
            )

    def __delitem__(self, k):
        """
        Delete k and the related item from the list

        :param k: the key
        """
        item = self.get(k, None)
        if item is None:
            return
        opfd = item.opfd
        with self._lock:
            super(ConnList, self).__delitem__(k)
            super(ConnList, self).__delitem__(opfd.fileno())
