import random
import socket
import sys
import logging
import time
import ctypes
import struct

from threading import Lock
from threading import Thread
from checksum import Checksum
from abc import ABC
from abc import abstractmethod
from copy import deepcopy


class SimulationClient(ABC):
    def __init__(self, socket, window_size, timeout, mss, num_packets, server_addr, logger):
        self.socket = socket
        self.window_size = window_size
        self.timeout = timeout
        self.num_packets = num_packets
        self.mss = mss
        self.server_addr = server_addr
        self.logger = logger
        
        self.send_base = 0
        self.next_seq_num = 0
        self.packets_buffer = []
        self.sequence_numbers = []
        self.sent_times = []
        
        self.packet_drop_probability = 0.05
        self.packet_corrupt_probability = 0.1
        self.header = int('0101010101010101', 2)
        self.completed = False
        self.lock = Lock()
            
    def get_next_packet(self, seq_num):
        if self.num_packets == 0:
            return None
        
        self.num_packets -= 1
        
        # Create packet
        data = 'Simulation with UDP.'.encode('ascii')
        length = len(data)
        
        # Create packet
        packet = struct.pack('IH' + str(length) + 's', seq_num, self.header, data)
        # Calculate checksum
        checksum = Checksum.calculate(packet)
        
        # Add Checksum to the packet
        packet = ctypes.create_string_buffer(length + 8)
        struct.pack_into('IHH' + str(length) + 's', packet, 0, seq_num, checksum, self.header, data)
        
        return packet
    
    def get_next_ack(self):
        message = self.socket.recv(self.mss)
        packet = struct.unpack('IHH', message)
    
        # Drop ack based on probability
        if random.random() <= self.packet_drop_probability:
            self.logger.info('Acknowledgement Number %d - Acknowledgement Dropped', packet[0])
            return False

        self.logger.info('Acknowledgement Number %d - Acknowledgement Received', packet[0])
        
        # Packet corrupted, ignore
        if not Checksum.verify(message):
            self.logger.info('Acknowledgement Number %d - Acknowledgement Corrupted', packet[0])
            return False
        
        return packet
    
    def is_timeout(self):
        current_time = time.time()
        for i, sent_time in enumerate(self.sent_times):
            if current_time >= sent_time + self.timeout:
                return i
        return None
    
    def execute(self):
        # Initialize the threads
        send_thread = Thread(target=self.send)
        receive_thread = Thread(target=self.receive)
        
        # Start and Join the threads
        send_thread.start()
        receive_thread.start()
        send_thread.join()
        receive_thread.join()
        
    @abstractmethod
    def receive(self):
        pass
    
    @abstractmethod
    def send(self):
        pass
    

class GBN(SimulationClient):
    def receive(self):
        while not self.completed:
            ack = self.get_next_ack()
            if not ack:
                continue
                
            ack_num = ack[0] - 1
            if ack_num == -1:
                ack_num = self.window_size - 1
            
            # Acquire processing lock
            self.lock.acquire()
            
            # Move the window forward
            try:
                index = self.sequence_numbers.index(ack_num)
                for i in range(index):
                    self.packets_buffer.pop(0)
                    self.sent_times.pop(0)
                    self.sequence_numbers.pop(0)
                self.send_base += index
                
                if self.num_packets == 0 and self.send_base == self.next_seq_num - 1:
                    self.completed = True
            except:
                pass
            
            # Release the lock so that send_thread can work
            self.lock.release()

    def send(self):
        while not self.completed:
            self.lock.acquire()
            
            timeout_index = self.is_timeout()
            if timeout_index is not None:
                seq_num = self.sequence_numbers[timeout_index]
                self.logger.info('Sequence Number %d - Timeout Occurred', seq_num)
                for i in range(timeout_index, self.next_seq_num - self.send_base):
                    packet = self.packets_buffer[i]
                    seq_num = self.sequence_numbers[i]
                    
                    # Corrupt packet based on the probability
                    if random.random() <= self.packet_corrupt_probability:
                        packet = deepcopy(packet)
                        packet[random.randint(0, len(packet) - 1)] = 0
                    
                    # Send the packet
                    time.sleep(1)
                    self.socket.sendto(packet, self.server_addr)
                    self.logger.info('Sequence Number %d - Packet Sent', seq_num)
                    
                    # Update the timer
                    self.sent_times[i] = time.time()
                    
            elif self.next_seq_num - self.send_base < self.window_size:
                
                # Get next packet
                seq_num = self.next_seq_num % self.window_size
                packet = self.get_next_packet(seq_num)
                
                # All the data has been transmitted
                if packet is None:
                    self.lock.release()
                    continue
                
                # Add packet to the buffer
                self.packets_buffer.append(packet)
                self.sequence_numbers.append(seq_num)

                # Corrupt packet based on the probability
                if random.random() <= self.packet_corrupt_probability:
                    packet = deepcopy(packet)
                    packet[random.randint(0, len(packet) - 1)] = 0
                
                # Send the packet
                time.sleep(1)
                self.socket.sendto(packet, self.server_addr)
                self.logger.info('Sequence Number %d - Packet Sent', seq_num)
                
                # Update the timer
                self.sent_times.append(time.time())
                self.next_seq_num = self.next_seq_num + 1
                
            self.lock.release()


class SR(SimulationClient):
    def __init__(self, socket, window_size, timeout, mss, data_file, server_addr, logger):
        super().__init__(socket, window_size, timeout, mss, data_file, server_addr, logger)
        # List to keep track of received acknowledgements
        self.ack_received = []
        
    def receive(self):
        while not self.completed:
            ack = self.get_next_ack()
            ack_num = ack[0]
            
            # Acquire processing lock
            self.lock.acquire()
            
            if self.send_base <= ack_num < self.next_seq_num:
                self.ack_received[ack_num - self.send_base] = True
                if ack_num == self.send_base:
                    i = 0
                    while self.ack_received[i]:
                        self.packets_buffer.pop(0)
                        self.sent_times.pop(0)
                        i += 1
                    
                    for j in range(i):
                        self.ack_received.pop(0)
                
                self.send_base = ack_num + 1
                
                if self.send_base == self.next_seq_num:
                    self.completed = True
            
            # Release the lock so that send_thread can work
            self.lock.release()
    
    def send(self):
        while not self.completed:
            self.lock.acquire()
            
            timeout_index = self.is_timeout()
            if timeout_index is not None:
                self.logger.info('Sequence Number %d - Timeout Occurred', self.send_base + timeout_index)
                
                i = self.send_base + timeout_index
                packet = self.packets_buffer[i]

                # Corrupt packet based on the probability
                if random.random() <= self.packet_corrupt_probability:
                    packet = deepcopy(packet)
                    packet[random.randint(0, len(packet) - 1)] = 0

                # Send the packet
                self.socket.sendto(packet, self.server_addr)
                self.logger.info('Sequence Number %d - Packet Sent', i)

                # Update the timer
                self.sent_times[i - self.send_base] = (seq_num, time.time())
                
            elif self.next_seq_num - self.send_base < self.window_size:
                # Get next packet
                seq_num = self.next_seq_num % self.window_size
                packet = self.get_next_packet(seq_num)
                
                # All the data has been transmitted
                if packet is None:
                    continue
                
                # Add packet to the buffer
                self.packets_buffer.append(packet)
                
                # Add acknowledgement buffer entry
                self.ack_received.append(False)
                
                # Corrupt packet based on the probability
                if random.random() <= self.packet_corrupt_probability:
                    packet = deepcopy(packet)
                    packet[random.randint(0, len(packet) - 1)] = 0
                
                # Send the packet
                self.socket.sendto(packet, self.server_addr)
                self.logger.info('Sequence Number %d - Packet Sent', self.next_seq_num)
                
                # Update the timer
                self.sent_times.append((seq_num, time.time()))
                self.next_seq_num += 1
            
            self.lock.release()
                

def main() :
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    
    if len(sys.argv) < 2:
        logger.error('Please provide an input file')
        sys.exit(1)
        
    if len(sys.argv) < 3:
        logger.error('Please provide a port number')
        sys.exit(1)
        
    if len(sys.argv) < 4:
        logger.error('Please provide number of packets to send')
        sys.exit(1)
        
    try:
        file_contents = open(sys.argv[1], 'r')
    except IOError:
        logger.error('File %s does not exist', sys.argv[1])
        sys.exit(1)
        
    protocol = file_contents.readline().strip()  # Protocol to be used
    window_size = int(file_contents.readline().strip())  # Window size
    timeout = int(file_contents.readline().strip())  # Timeout in seconds
    mss = int(file_contents.readline().strip())  # Maximum segment size
    port = int(sys.argv[2])  # Port to be used
    host = socket.gethostbyname('localhost')
    num_packets = int(sys.argv[3])
    
    print("---------- Connection Info ----------")
    print("Host: " + host)
    print("protocol: " + protocol)
    print("Window size: " + str(window_size))
    print("Timeout: " + str(timeout))
    print("MSS: " + str(mss))
    print("Port: " + str(port))
    print("-------------------------------------")
    
    if not protocol == 'SR' and not protocol == 'GBN':
        logger.error('Protocol %s is invalid. Must be SR (Selective Repeat) or GBN (Go-Back N)', protocol)
        sys.exit(1)

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_addr = (host, port)
    
    # Initialize the protocol implementation
    if protocol == 'SR':
        protocol = SR(client_socket, window_size, timeout, mss, num_packets, server_addr, logger)
    elif protocol == 'GBN':
        protocol = GBN(client_socket, window_size, timeout, mss, num_packets, server_addr, logger)
        
    protocol.execute()


if __name__ == '__main__':
    main()
