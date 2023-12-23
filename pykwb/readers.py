import socket
import time
import threading
import serial

class SerialByteReader:
    """Reads bytes from a serial TTY"""

    def __init__(self, dev='/dev/ttyUSB0', baud=19200):
        self._dev = dev
        self._baud = baud

    def open(self):
        self.ser = serial.Serial(self._dev, self._baud)

    def read(self) -> bytes:
        return self.ser.read()

    def close(self) -> None:
        self.ser.close()


class TCPByteReader:
    """Reads bytes over TCP connection"""

    def __init__(self, ip: str, port: int):
        self._ip = ip
        self._port = port
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    def open(self):
        self._socket.connect((self._ip, self._port))

    def read(self) -> bytes:
        return self._socket.recv(1)

    def close(self) -> None:
        self._socket.close()


class FileByteReader:
    
    def __init__(self, path="", encoding='utf8'):
        self._path = path
        self._encoding = encoding

    def open(self):
        self._file = open(self._path, "r", encoding=self._encoding)

    def read(self) -> bytes:
        return struct.pack("B", int(self._file.readline()))

    def close(self) -> None:
        self._file.close()

