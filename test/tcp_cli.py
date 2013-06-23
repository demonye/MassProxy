#!/usr/bin/env python2

import socket
import sys


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: {} port data".format(sys.argv[0]))
        sys.exit(1)
    port_ = int(sys.argv[1])
    HOST, PORT = "localhost", port_
    data = " ".join(sys.argv[1:])

    # Create a socket (SOCK_STREAM means a TCP socket)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Connect to server and send data
        sock.connect((HOST, PORT))
        sock.sendall(data + "\n")

        # Receive data from the server and shut down
        received = sock.recv(1024)
    finally:
        sock.close()

    print "Sent:     {}".format(data)
    print "Received: {}".format(received)
