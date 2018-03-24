class Checksum:
    @staticmethod
    def carry_around(a, b):
        c = a + b
        return (c & 0xffff) + (c >> 16)

    @staticmethod
    def calculate(packet):
        """
        Calculate checksum
        :param packet:
        :return:
        """
        
        s = 0
        for i in range(0, len(packet), 2):
            w = packet[i] + (packet[i + 1] << 8)
            s = Checksum.carry_around(s, w)
        return ~s & 0xffff
    
    @staticmethod
    def verify(packet):
        checksum = Checksum.calculate(packet)
        return checksum == 0