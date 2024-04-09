import sys
import threading
import datetime
import queue
import serial
import os
import serial.tools.list_ports
from rich.console import Console
from rich.panel import Panel

console = Console()

class SerialMonitor():
    def __init__(self):
        self.port = None
        self.baudrate = 115200
        self.parity = serial.PARITY_NONE

        self.input_buffer = ''
        self.total_bytes_rx = 0
        self.total_bytes_tx = 0

        self.input_queue = queue.Queue()
        self.stop_queue = queue.Queue()

        self.input_thread = threading.Thread(target=self.add_input, args=(self.input_queue,self.stop_queue,))
        self.input_thread.daemon = True

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

    def init_screen(self):
        self.clear_screen()
        console.print(Panel("Serial Monitor", width=64, padding=(1,8)), style="bold", justify="center")
        console.print()

    def get_timestamp(self):
        return '[' + datetime.datetime.now().strftime("%H:%M:%S") + '] '


    def get_ports(self):
        ports = serial.tools.list_ports.comports()
        port_dict = {}

        for i, port in enumerate(ports):
            port_dict[i] = port.device
            console.print(f"- [{i}] {port.device}")
        console.print()

        return port_dict

    def select_port(self):
        while True:
            try:
                self.init_screen()
                port_dict = self.get_ports()
                selected_index = int(input("Enter the port number to connect: "))
                selected_port = port_dict[selected_index]
                return selected_port
            except (ValueError, KeyError):
                console.print("Invalid port number. Please try again.", style="bold red")

    def select_baudrate(self):
        while True:
            try:
                self.init_screen()
                baudrate = int(input("Enter the baudrate: "))
                return baudrate
            except ValueError:
                console.print("\033[91m" + "Invalid baudrate. Please try again.\033[0m\n")

    def select_parity(self):
        while True:
            try:
                self.init_screen()
                parity = input("Enter the parity (N, E, O): ").upper()
                if parity == "N":
                    return serial.PARITY_NONE
                elif parity == "E":
                    return serial.PARITY_EVEN
                elif parity == "O":
                    return serial.PARITY_ODD
                else:
                    console.print("Invalid parity. Please try again.", style="bold red")
            except ValueError:
                console.print("Invalid parity. Please try again.", style="bold red")

    def open_port(self):
        try:
            self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, parity=self.parity, timeout=5)
            self.ser.flushInput()
            self.ser.flushOutput()
        except serial.SerialException:
            console.print("Failed to open the selected port. Please try again.", style="bold red")

    def get_info(self):
        return f"Port: {self.port} | Baudrate: {self.baudrate} | Parity: {self.parity} | RX: {self.total_bytes_rx} | TX: {self.total_bytes_tx}"

    def clear_screen(self):
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system('clear')

    def process_input(self, status):
        if not self.input_queue.empty():
            keyboard_input = self.input_queue.get().upper()

            if all(b in b'0123456789ABCDEF' for b in keyboard_input):
                self.input_buffer += keyboard_input.decode()

                if status:
                    status.update('[bold blue]' + self.input_buffer)

            if keyboard_input == b'\r':
                if len(self.input_buffer) == 0:
                    console.print('\n\n' + self.get_timestamp() + self.get_info() + '\n', style='blue')
                elif len(self.input_buffer) % 2 == 0:
                    console.print('\n' + self.get_timestamp() + self.input_buffer + '\n', style='blue')
                    send_bytes = bytes.fromhex(self.input_buffer)

                    self.ser.write(send_bytes)
                    self.input_buffer = ''

            if keyboard_input == b'\x7f':
                self.input_buffer = self.input_buffer[:-1]

                if status:
                    status.update('[bold blue]' + self.input_buffer)

            if keyboard_input == b'\x03':
                raise KeyboardInterrupt()

    def process_output(self, status):
        try:
            bytes_to_read = self.ser.inWaiting()
            while bytes_to_read:
                data = self.ser.read()
                bytes_to_read = bytes_to_read - 1
                console.print(data.hex(), end='', style='green')
                self.total_bytes_rx += len(data)

        except IOError:
            raise IOError()


    def run(self):
        self.port = self.select_port()
        self.baudrate = self.select_baudrate()
        self.parity = self.select_parity()

        self.open_port()

        self.input_thread.start()
        self.clear_screen()

        while True:
            if self.input_buffer:
                with console.status('[bold blue]' + self.input_buffer, spinner='arc', spinner_style='blue') as status:
                    while True:
                        self.process_input(status)
                        self.process_output(status)
                        if not self.input_buffer:
                            break
            else:
                while True:
                    self.process_input(None)
                    self.process_output(None)
                    if self.input_buffer:
                        break

if __name__ == "__main__":
    try:
        SerialMonitor().run()
    except IOError:
        console.print("\n\nMonitor: Disconnected (I/O Error)", style='bold red')
    except KeyboardInterrupt:
        console.print("\n\nMonitor: Exiting Now...", style='bold red')
        sys.exit(1)
