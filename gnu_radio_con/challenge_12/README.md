# Challenge 12
I wanted to do this challenge first because I have yet to decode FSK signal.
I took the sigmf IQ data file and put it into [Inspectrum](https://github.com/miek/inspectrum). 
This was my first time using this tool, 
and I wanted to see if I could use it to decode the raw signal.

## Inspectrum
![inspectrum_raw](inspectrum_raw.png)
The tool is pretty easy to use. After you load your file you will see a waterfall graph on its side.
This makes it easy to finds things that you are interested in. 
This is how I originally found the signal I wanted to work on, 
but before I could do really anything I needed to set the sample rate.
I was able to find the sample rate from the included metadata file,
and once I did that more options began to unlock. 

![inspectrum_plot](inspectrum_plot.png)
Digital Frequency shift keying is where you have one frequency resent a bit and, 
the another frequency represent the opposite bit.
Decoding signals like this is what Inspectrum was designed to handle.
So in the tool I right-click on the 300 KHz range and select *Add derived plot -> Add frequency plot*.
This creates a new plot at the bottom of the tool.
You may need to scroll down to see it. 
Because this is a binary signal you can right-click on that plot and select *Add derived plot -> Add threshold plot.*
This will clear up the signal into ones and zeros.

![inspectrum_symbols](inspectrum_symbols.png)
In the past I have used digital art tools to measure each symbol and convert them into a one or zero,
but this tool has the ability to do this for you.
All you need to do is enable the cursor,
and a column will appear on the screen.
The next step is to use the sizing tools to cover one symbol of the signal. 
It is pretty important to cover the symbol exactly as some signals can have thousands symbols and being off by one pixel can add up.
After setting the symbol length I scroll to the end of signal and start to guess how many symbols are in this signal.
I find there to be 1799 symbols. I can now right-click on column and hit *Extract symbols -> Copy to clipboard.* 

## POCSAG
So after looking at this signal for a while I began to recognize it from a bunch of talks on SDRs. 
I remember seeing a talk about decoding pagers, and they talked about FSK signal that has a long preamble.
I did some quick Google searches and learned that most pagers use the POCSAG protocol. 
I looked up some documentation on it and learned that it had a preamble of 576 alternating frequencies.
The signal that I have just a little more than, but everything else about it looks the same in the diagrams.

With some good confidence that this is POCSAG I continue to read the documentation.
So, after the long preamble there is a frame sync code that is used to state the start of a frame,
and uses the follow sequence 01111100110100100001010111011000.
I took that string of ones and zeros and search the output data from Inspectrum to see if it existed.
Unfortunately no results returned, but in the past I have ran into issues where my bits are flipped, 
so I flip all the ones and zeros and do the search again. This time I get back two results, 
and one of them is right after the preamble. So I know I have a POCSAG signal.

## Decoding
I have 1799 bits and there is no way I am going to try to decode this by hand, 
but how I am going to all these bits into a useful data.
I am not the greatest program, 
but I do have some good knowledge on electronics and data moves through transistor to transistor logic. 
So, my thought was to run the signal through a shift register tell I found the frame sync code,
and the closest data model that I could think of that represents a shift register is a link list.
I could create a list that only can hold 32 bits, and if it fills up pops off the first value.
Next I will run all the bits through tell I find the FSC and from there I can process the data contained in the frames.

```python
class NodeBit(object):
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
        self.head = node
        self.tail = node

    def write_buffer(self):
        buffer = []
        for bit in self:
            buffer.append(bit)
        return buffer

    def clear_buffer(self):
        self.head = None
        self.tail = None
        self.len = 1
        return None

    def check_fsc(self):
        buffer = ''.join(self.write_buffer())
        if buffer == self.frame_sync_code:
            self.clear_buffer()
            return True
        return None

    def create_batch(self):
        self.batches.append(self.write_buffer())
        self.clear_buffer()
        return None

    def buffer_in(self, data):
        new_node = NodeBit(data)
        self.len += 1
        if not self.head:
            self.list_start(new_node)
            return None
        if self.len > 32:
            if not self.record:
                if self.check_fsc():
                    self.record = True
                    self.list_start(new_node)
                    return None
                self.buffer_out(new_node)
                return None
            else:
                self.create_batch() 
                self.list_start(new_node)
        self.tail.next_node = new_node
        self.tail = new_node
        return None

    def buffer_out(self, new_node):
        self.head = self.head.next_node
        self.tail.next_node = new_node
        self.tail = new_node
        self.len -= 1
        return None

```

I wrote out the code, and it successfully found the FSC, so it is now on to decoding the frame.
I pull back up the documentation on POCSAG and read that each frame is broken up into 16 32 bits of data.
Each block of data can be either an address or a message and the first bit is used to denote this.
So I add to my link list code to create a list of 32 bits of data after finds the FSC.
This makes it easy to work with each block of data. 
The next bit of code is to inspect the first bit and separate the addresses from the messages.

I was going to throw away the address data, but I found out that the address contains data on the format of the message.
On bit 20 and 21 tells the receiver if the message is just numeric or if it is alpha-numeric. 
I could just assume that all messages are going to alpha-numeric as I am looking for a flag, 
but I thought I might just code for it anyway.

```python
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
```

Onto decoding bits into letters, and from the documentation it looks like POCSAG uses 7 bit ASCII characters.
Each block is 32 bits, and the message blocks use some error correcting code to recover a bad bit. 
This leaves each message with 20 bits for characters. However, seven does not go into 20 very cleanly.
To solve this the protocol takes the 20 bits from the message and stacks them together to create one large stream.
This is pretty easy to solve for as I can loop throw each block of data and create one large list of bits.

## ASCII
I am so close now to having the signal decoded. 
I have a stream of ones and zeros that contain the message in ASCII.
I run through the stream of data real and try to convert to characters, but get back garbage.
I forgot that the data is 7 bit ASCII and Python uses 8 bit ASCII. 
This is not hard to fix as I can add a zero to the front of each character, however I still have garbage.
Going back to the documentation it says that each character is big endian.
I update my code to revers each character and then add the zero at the end,
and with that I finally have the flag.

```python
characters = []
for index in range(0, len(message), 7):
    char = message[index:index + 7]
    char.reverse()
    characters.append(char)

flag = ''
for char in characters:
    word = '0' + ''.join(char)
    flag = flag + chr(int(word[:8], 2))
```

