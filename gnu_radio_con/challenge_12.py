
# Sync codes
FRAME_SYNC_CODE = '01111100110100100001010111011000'
IDLE_SYNC_CODE = '01111010100010011100000110010111'


class NodeBit(object):
    """
    This is the link list node
    """
    def __init__(self, data):
        self.data = data
        self.next_node = None


class FrameSyncBuffer(object):
    def __init__(self, fcs):
        self.frame_sync_code = fcs
        self.head = None
        self.tail = None
        self.len = 0
        self.batches = []
        self.record = False
        self.current_node = self.head

    def __iter__(self):
        self.current_node = self.head
        return self

    def __next__(self):
        if self.current_node is None:
            raise StopIteration
        data = self.current_node.data
        self.current_node = self.current_node.next_node
        return data

    def list_start(self, node):
        """
        This is used to start the link list or restart it
        """
        self.head = node
        self.tail = node

    def write_buffer(self):
        """
        This walks through the link list and writes down all the values
        """
        buffer = []
        for bit in self:
            buffer.append(bit)
        return buffer

    def clear_buffer(self):
        """
        This resets the link list
        """
        self.head = None
        self.tail = None
        self.len = 1
        return None

    def check_fsc(self):
        """
        I use this method to find the first instance of FCS and clear out
        the link list
        """
        buffer = ''.join(self.write_buffer())
        if buffer == self.frame_sync_code:
            self.clear_buffer()
            return True
        return None

    def create_batch(self):
        """
        I use this to write the link list to the batch attribute
        """
        self.batches.append(self.write_buffer())
        self.clear_buffer()
        return None

    def buffer_in(self, data):
        """
        This is used to add to the link list and detect the FCS along with
        creating batches
        """
        new_node = NodeBit(data)
        self.len += 1
        if not self.head:
            self.list_start(new_node)
            return None
        if self.len > 32:
            if not self.record:
                if self.check_fsc():  # This is used while the FCS is unknown
                    self.record = True
                    self.list_start(new_node)
                    return None
                self.buffer_out(new_node)
                return None
            else:
                self.create_batch()  # This is used when the FCS is known
                self.list_start(new_node)
        self.tail.next_node = new_node
        self.tail = new_node
        return None

    def buffer_out(self, new_node):
        """
        This is used while the FCS has not been found. It replaces the head
        with the next item keeping the list only 32 bits long
        """
        self.head = self.head.next_node
        self.tail.next_node = new_node
        self.tail = new_node
        self.len -= 1
        return None


# Input signal
signal_bits = '01010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101001111100110100100001010111011000000001111000100100011000001011101110010110010111110010111111001011011101110000110011000101000000111000001010010110010001111100111011101001101110110011000010011110111100101101100111001111101010101011110001110000110010100001111010111100101111110111101101100110111011000001011000111100010101110001011100001100110101000001101110011011101001101111100100000110111110011101001100001010110000100101100010100011001011101001001001100101110000001000011100110111100110011011100001101100110101111100111101111010001111001100010111110011010010000101011101100011001011011000111101011010101100101111110100101111111000101110001011111110100001111000011100010110011111001111001101100000010111111101000011001110111000001010011100110101111110000000011111000001111010100010011100000110010111011110101000100111000001100101110111101010001001110000011001011101111010100010011100000110010111011110101000100111000001100101110111101010001001110000011001011101111010100010011100000110010111011110101000100111000001100101110111101010001001110000011001011101111010100010011100000110010111'
pocsag = FrameSyncBuffer(FRAME_SYNC_CODE)

# Creates each individual frames
for bit in signal_bits:
    pocsag.buffer_in(bit)

# Creates the one long message from all the frames
message = []
for frame in pocsag.batches:
    if frame[0] == '0':
        if ''.join(frame) == FRAME_SYNC_CODE or ''.join(frame) == IDLE_SYNC_CODE:
            continue
        address_bits = ''.join(frame[1:19])
        address = int(address_bits, 2)
        if ''.join(frame[19:21]) == '11':
            message_type = 'alpha_numeric'
        elif ''.join(frame[19:21]) == '00':
            message_type = 'numeric'
    else:
        message.extend(frame[1:21])

# Converts the long message into individual characters
characters = []
for index in range(0, len(message), 7):
    char = message[index:index + 7]
    char.reverse()
    characters.append(char)

# Creates the flag
flag = ''
for char in characters:
    word = '0' + ''.join(char)
    flag = flag + chr(int(word[:8], 2))
    
