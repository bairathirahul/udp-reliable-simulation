import logging
import random
import socket
import sys
import time
import struct
import ctypes

from abc import ABC
from abc import abstractmethod

from checksum import Checksum


class SimulationServer(ABC):
    def __init__(self, server_socket, num_bits, window_size, logger):
        """
        Initialize the protocol
        :param server_socket: Server server_socket
        """
        self.server_socket = server_socket
        self.max_seq_num = 2 ** (num_bits - 1)
        self.window_size = window_size
        self.logger = logger
        
        self.packet_drop_probability = 0.1
        self.packet_corrupt_probability = 0.1
        
        self.header = int('1010101010101010', 2)
    
    def send_ack(self, seq_num, client_addr):
        # Prepare Acknowledgement
        packet = struct.pack('IH', seq_num, self.header)
        # Calculate checksum
        checksum = Checksum.calculate(packet)
        
        # Add Checksum to the packet
        packet = ctypes.create_string_buffer(8)
        struct.pack_into('IHH', packet, 0, seq_num, checksum, self.header)

        # Corrupt packet based on the probability
        if random.random() <= self.packet_corrupt_probability:
            packet[random.randint(0, len(packet) - 1)] = 0
        
        # Send ACK
        time.sleep(1)
        self.server_socket.sendto(packet, client_addr)
        self.logger.info('Sequence Number %d - Acknowledgement Sent', seq_num)
    
    def execute(self):
        # Read packets and process
        while True:
            message, client_addr = self.server_socket.recvfrom(5000)
            
            packet = struct.unpack('IHH' + str(len(message) - 8) + 's', message)
            
            # Drop packet
            if random.random() <= self.packet_drop_probability:
                self.logger.info('Sequence Number %d - Packet Dropped', packet[0])
                continue
            
            self.logger.info('Sequence Number %d - Packet Received', packet[0])
            
            # Verify packet checksum
            if not Checksum.verify(message):
                self.logger.info('Sequence Number %d - Packet is Corrupt', packet[0])
                continue
            
            self.process(packet, client_addr)
    
    @abstractmethod
    def process(self, packet, client_addr):
        pass


class GBN(SimulationServer):
    def __init__(self, server_socket, num_bits, window_size, logger):
        super().__init__(server_socket, num_bits, window_size, logger)
        self.expected_seq_num = 0
        
    def process(self, packet, client_addr):
        seq_num = packet[0]
        
        if seq_num == self.expected_seq_num:
            self.expected_seq_num = (self.expected_seq_num + 1) % self.max_seq_num
        else:
            self.logger.info('Sequence Number %d - Out of order, discarded', seq_num)
        self.send_ack(self.expected_seq_num, client_addr)


class SR(SimulationServer):
    def __init__(self, server_socket, num_bits, window_size, logger):
        super().__init__(server_socket, num_bits, window_size, logger)
        
        self.receiver_buffer = [None] * self.window_size
        self.base_seq_num = -1
    
    def process(self, packet, client_addr):
        seq_num = packet[0]
        
        if self.base_seq_num == -1:
            self.receiver_buffer[0] = packet
            self.base_seq_num = packet[0]
        
        index = self.sequence_numbers.index(seq_num)
        self.receiver_buffer[index] = packet
        if index == 0:
            try:
                first_none = self.receiver_buffer.index(None)
            except:
                first_none
            i = first_none
            self.sequence_numbers = self.sequence_numbers[first_none:] + self.sequence_numbers[:first_none]
            while i < self.window_size:
                self.receiver_buffer[i - first_none] = self.receiver_buffer[i]
                i += 1
                
        self.send_ack(seq_num, client_addr)


def main():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    if len(sys.argv) < 2:
        logger.error('Please provide an input file')
        sys.exit(1)

    if len(sys.argv) < 3:
        logger.error('Please provide a port number')
        sys.exit(1)

    try:
        file_contents = open(sys.argv[1], 'r')
    except IOError:
        logger.error('File %s does not exist', sys.argv[1])
        sys.exit(1)

    protocol = file_contents.readline().strip()  # Protocol to be used
    num_bits, window_size = file_contents.readline().strip().split(' ')  # Window size
    num_bits = int(num_bits)
    window_size = int(window_size)
    
    # server_socket parameters
    port = int(sys.argv[2])
    host = socket.gethostbyname('localhost')
    
    print("---------------- Receiver info ----------------")
    print("Hostname: " + host)
    print("Port: " + str(port))
    print("Protocol: " + protocol)
    print("Window Size: " + str(window_size))
    print("-----------------------------------------------")
    
    # Invalid protocol, throw error
    if not protocol == 'SR' and not protocol == 'GBN':
        logger.error('Protocol %s is invalid. Must be SR (Selective Repeat) or GBN (Go-Back N)', protocol)
        sys.exit(1)
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        server_socket.bind((host, port))
        
        # Initialize the protocol implementation
        if protocol == 'SR':
            protocol = SR(server_socket, num_bits, window_size, logger)
        elif protocol == 'GBN':
            protocol = GBN(server_socket, num_bits, window_size, logger)
        
        protocol.execute()
    except KeyboardInterrupt:
        logging.info('Server shutting down')
        server_socket.close()
        sys.exit(0)


if __name__ == '__main__':
    main()
