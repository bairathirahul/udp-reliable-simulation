1
import socket

2
3
UDP_IP = "127.0.0.1"
4
UDP_PORT = 5005
5
6
sock = socket.socket(socket.AF_INET,  # Internet
                     7
socket.SOCK_DGRAM)  # UDP
8
sock.bind((UDP_IP, UDP_PORT))
9
10
while True:
    11
    data, addr = sock.recvfrom(1024)  # buffer size is 1024 bytes
12
print
"received message:", data