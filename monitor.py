import sys
import threading
import datetime
import queue
import serial
import os
import serial.tools.list_ports


COLOR_NONE = '\033[0m'
COLOR_ERROR = '\033[91m'
COLOR_WHITE = '\033[97m'
STYLE_BOLD = '\033[1m'
CURSOR_SAVE = '\033[s'
CURSOR_RESTORE = '\033[u'
CURSOR_HOME = '\033[1000D'
CURSOR_CLEAR = '\033[K'

class SerialMonitor():
    DEFAULT_BAUDRATE = 115200
    DEFAULT_TIMEOUT = 5

    def __init__(self):
        self.port = None
        self.baudrate = self.DEFAULT_BAUDRATE
        self.parity = serial.PARITY_NONE

        self.input_buffer = ''
        self.total_bytes_rx = 0
        self.total_bytes_tx = 0

        self.input_queue = queue.Queue()
        self.stop_queue = queue.Queue()

        self.input_thread = threading.Thread(target=self.add_input, args=(self.input_queue, self.stop_queue))
        self.input_thread.daemon = True


    @staticmethod
    def handle_input_error(error_msg):
        def decorator(func):
            def wrapper(self, *args, **kwargs):
                while True:
                    try:
                        return func(self, *args, **kwargs)
                    except (KeyError, ValueError):
                        self.init_screen(error_msg)
            return wrapper
        return decorator


    def getch(self):
        try:
            # Windows
            import msvcrt
            return msvcrt.getch()
        except ImportError:
            # Unix/Linux/macOS
            import tty
            import termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch.encode()


    def add_input(self, input_queue, stop_queue):
        while True:
            input_char = self.getch()
            input_queue.put(input_char)


    def init_screen(self, error_msg):
        self.clear_console()
        print(COLOR_WHITE + STYLE_BOLD + 'Hex Serial Monitor ' + COLOR_NONE + COLOR_ERROR + error_msg + COLOR_NONE + '\n')


    def get_timestamp(self):
        return '[' + datetime.datetime.now().strftime('%H:%M:%S') + '] '


    def get_ports(self):
        ports = serial.tools.list_ports.comports()
        port_dict = {}

        for i, port in enumerate(ports):
            port_dict[i] = port.device
            print(f'- [{i}] {port.device} ({port.description})')
        print()

        return port_dict


    @handle_input_error('(Invalid port number. Please try again.)')
    def select_port(self):
        port_dict = self.get_ports()
        selected_index = int(input('Enter the port number to connect: '))
        selected_port = port_dict[selected_index]
        self.init_screen('')
        return selected_port


    @handle_input_error('(Invalid baudrate. Please try again.)')
    def select_baudrate(self):
        baudrate = input(f'Enter the baudrate (default {self.DEFAULT_BAUDRATE}): ')
        if not baudrate:
            baudrate = self.DEFAULT_BAUDRATE
        self.init_screen('')
        return int(baudrate)


    @handle_input_error('(Invalid parity. Please try again.)')
    def select_parity(self):
        parity = input('Enter the parity (N, E, O) (default N): ').upper()
        if parity == 'N' or not parity:
            return serial.PARITY_NONE
        elif parity == 'E':
            return serial.PARITY_EVEN
        elif parity == 'O':
            return serial.PARITY_ODD
        else:
            raise ValueError


    def open_port(self):
        try:
            self.serial = serial.Serial(port=self.port, baudrate=self.baudrate, parity=self.parity, timeout=self.DEFAULT_TIMEOUT)
            self.serial.flushInput()
            self.serial.flushOutput()
        except serial.SerialException:
            print('\n\n' + COLOR_ERROR + 'Monitor: Failed to open the selected port. Exiting now...' + COLOR_NONE + '\n')
            exit(1)


    def get_info(self):
        return f'Port: {self.port} | Baudrate: {self.baudrate} | Parity: {self.parity} | RX: {self.total_bytes_rx} | TX: {self.total_bytes_tx}'


    def clear_console(self):
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system('clear')


    def process_input(self):
        if not self.input_queue.empty():
            keyboard_input = self.input_queue.get().upper()

            # Check if the input is a valid hex character
            if all(b in b'0123456789ABCDEF' for b in keyboard_input):
                self.input_buffer += keyboard_input.decode()
                print(CURSOR_SAVE + '\n\n' + CURSOR_HOME + CURSOR_CLEAR + self.input_buffer + CURSOR_RESTORE, end='', flush=True)

            # Check if the input is a valid hex string
            if keyboard_input == b'\r':
                print(CURSOR_SAVE + '\n\n' + CURSOR_HOME + CURSOR_CLEAR + '' + CURSOR_RESTORE, end='', flush=True)
                if len(self.input_buffer) == 0:
                    print('\n\n' + self.get_timestamp() + self.get_info() + '\n')
                elif len(self.input_buffer) % 2 == 0:
                    print('\n' + self.get_timestamp() + self.input_buffer + '\n')
                    send_bytes = bytes.fromhex(self.input_buffer)

                    self.serial.write(send_bytes)
                    self.input_buffer = ''

            # Check if the input is a backspace
            if keyboard_input == b'\x7f' or keyboard_input == b'\x08':
                self.input_buffer = self.input_buffer[:-1]
                print(CURSOR_SAVE + '\n\n' + CURSOR_HOME + CURSOR_CLEAR + self.input_buffer + CURSOR_RESTORE, end='', flush=True)

            # Check if the input is a CTRL+C
            if keyboard_input == b'\x03':
                raise KeyboardInterrupt()


    def process_output(self):
        try:
            bytes_to_read = self.serial.inWaiting()
            while bytes_to_read:
                data = self.serial.read(bytes_to_read)
                self.total_bytes_rx += bytes_to_read
                bytes_to_read = 0
                print(data.hex(' '), end=' ', style='green')
        except IOError:
            raise IOError()


    def run(self):
        self.init_screen('')

        self.port = self.select_port()
        self.baudrate = self.select_baudrate()
        self.parity = self.select_parity()

        self.clear_console()

        self.open_port()

        self.input_thread.start()

        while True:
            self.process_input()
            self.process_output()


if __name__ == '__main__':
    try:
        SerialMonitor().run()
    except IOError:
        print('\n\n' + COLOR_ERROR + 'Monitor: Disconnected (I/O Error)' + COLOR_NONE + '\n')
        exit(1)
    except KeyboardInterrupt:
        print('\n\n' + COLOR_ERROR + 'Monitor: Exiting Now...' + COLOR_NONE + '\n')
        exit(1)
