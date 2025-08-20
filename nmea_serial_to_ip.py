#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import socket
import struct
import sys
import threading
import time
import select
import serial

def nmea_checksum_ok(line_bytes: bytes) -> bool:
    """
    ตรวจสอบ checksum ของประโยค NMEA (เช่น $GPGGA,...*5C)
    คืนค่า True ถ้าถูกต้อง หรือไม่มี *checksum
    """
    line = line_bytes.strip(b"\r\n")
    if not line:
        return False
    if line[0:1] not in (b"$", b"!"):
        # อนุญาตข้อมูลอื่นผ่านได้ถ้าต้องการ แต่ปกติ NMEA จะขึ้นต้นด้วย $ หรือ !
        return False
    try:
        star_idx = line.rindex(b"*")
    except ValueError:
        # บางอุปกรณ์อาจไม่มี checksum -> ถือว่าผ่าน
        return True

    payload = line[1:star_idx]  # ไม่รวม $/! และไม่รวม *HH
    given = line[star_idx+1:star_idx+3]
    try:
        given_val = int(given.decode("ascii"), 16)
    except Exception:
        return False

    calc = 0
    for b in payload:
        calc ^= b
    return calc == given_val


def normalize_nmea_line(line_bytes: bytes) -> bytes:
    """
    ตัด \r\n เก่าออก และเติม CRLF ใหม่ให้เป็นมาตรฐาน
    """
    return line_bytes.strip(b"\r\n") + b"\r\n"


class UDPOutput:
    def __init__(self, host: str, port: int, broadcast: bool = False):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # เปิด broadcast ถ้าระบุ หรือ host เป็นบรอดแคสต์ทั่วไป
        if broadcast or host.endswith(".255") or host == "255.255.255.255":
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def send(self, data: bytes):
        self.sock.sendto(data, (self.host, self.port))

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


class UDPMulticastOutput:
    def __init__(self, group: str, port: int, iface_ip: str = None, ttl: int = 1):
        self.group = group
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        # ตั้ง TTL ของ multicast (ปกติ 1 ให้อยู่ใน LAN เดียวกัน)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', ttl))
        if iface_ip:
            # ส่ง multicast ออกทาง interface ที่กำหนด (ต้องเป็น IPv4 ของการ์ดนั้น)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(iface_ip))

    def send(self, data: bytes):
        self.sock.sendto(data, (self.group, self.port))

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


class TCPServer(threading.Thread):
    """
    TCP server ง่าย ๆ ให้ไคลเอนต์หลายตัวต่อเข้ามารับสตรีม NMEA ได้พร้อมกัน
    """
    def __init__(self, host: str, port: int):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.clients = []
        self.lock = threading.Lock()
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                rlist, _, _ = select.select([self.sock], [], [], 1.0)
                if self.sock in rlist:
                    conn, addr = self.sock.accept()
                    conn.setblocking(False)
                    with self.lock:
                        self.clients.append(conn)
                    print(f"[TCP] Client connected: {addr}")
            except Exception:
                # ป้องกันลูปหลุดเพราะข้อผิดพลาดชั่วคราว
                continue

    def broadcast(self, data: bytes):
        with self.lock:
            dead = []
            for c in self.clients:
                try:
                    c.sendall(data)
                except Exception:
                    dead.append(c)
            for c in dead:
                try:
                    peer = c.getpeername()
                except Exception:
                    peer = "?"
                print(f"[TCP] Client disconnected: {peer}")
                try:
                    c.close()
                except Exception:
                    pass
                self.clients.remove(c)

    def close(self):
        self._stop.set()
        try:
            self.sock.close()
        except Exception:
            pass
        with self.lock:
            for c in self.clients:
                try:
                    c.close()
                except Exception:
                    pass
            self.clients.clear()


def read_and_forward(serial_port: str,
                     baudrate: int,
                     outputs,
                     tcp_server: TCPServer = None,
                     drop_bad_checksum: bool = False,
                     echo: bool = False):
    while True:
        try:
            print(f"[SERIAL] Opening {serial_port} @ {baudrate} bps")
            with serial.Serial(serial_port, baudrate, timeout=1) as ser:
                while True:
                    raw = ser.readline()
                    if not raw:
                        continue
                    if drop_bad_checksum and not nmea_checksum_ok(raw):
                        # ข้ามบรรทัดที่ checksum ผิด
                        if echo:
                            sys.stdout.write(f"[DROP] {raw.decode('ascii', errors='ignore').strip()}\n")
                        continue

                    line = normalize_nmea_line(raw)

                    # Echo จอ
                    if echo:
                        try:
                            sys.stdout.write(line.decode("ascii", errors="ignore"))
                        except Exception:
                            pass

                    # ส่งออก UDP/Multicast ทั้งหมด
                    for out in outputs:
                        try:
                            out.send(line)
                        except Exception as e:
                            print(f"[WARN] UDP send failed: {e}")

                    # กระจายผ่าน TCP (ถ้ามี)
                    if tcp_server:
                        tcp_server.broadcast(line)

        except serial.SerialException as e:
            print(f"[SERIAL] Error: {e}. Reconnecting in 2s...")
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n[INFO] Stopping.")
            break
        except Exception as e:
            print(f"[ERROR] {e}. Reopening in 2s...")
            time.sleep(2)


def parse_hostport(s: str):
    if ":" not in s:
        raise argparse.ArgumentTypeError("ต้องเป็นรูปแบบ host:port เช่น 127.0.0.1:10110")
    host, port = s.rsplit(":", 1)
    try:
        port = int(port)
    except ValueError:
        raise argparse.ArgumentTypeError("port ต้องเป็นตัวเลข")
    return host, port


def main():
    ap = argparse.ArgumentParser(
        description="อ่าน NMEA จาก Serial แล้วส่งต่อทาง IP (UDP/TCP/Multicast)"
    )
    ap.add_argument("-p", "--serial-port", required=True, help="เช่น COM3 หรือ /dev/ttyUSB0")
    ap.add_argument("-b", "--baudrate", type=int, default=4800, help="ค่าเริ่มต้น 4800 (AIS มัก 38400)")
    ap.add_argument("-u", "--udp", action="append", default=[],
                    help="ปลายทาง UDP แบบ host:port (ระบุซ้ำได้หลายครั้ง)")
    ap.add_argument("--udp-broadcast", action="store_true",
                    help="ตั้งค่าส่งแบบ broadcast สำหรับปลายทาง UDP ที่ระบุ")
    ap.add_argument("--mcast", help="ส่ง UDP multicast แบบ group:port เช่น 239.255.0.1:10110")
    ap.add_argument("--mcast-if", help="IPv4 ของ interface ที่จะใช้ส่ง multicast (เช่น 192.168.1.50)")
    ap.add_argument("--mcast-ttl", type=int, default=1, help="TTL สำหรับ multicast (ค่าเริ่มต้น 1)")
    ap.add_argument("--tcp-listen", help="เปิด TCP server รับการเชื่อมต่อ เช่น 0.0.0.0:10110")
    ap.add_argument("--drop-bad-checksum", action="store_true", help="ทิ้งประโยคที่ checksum ผิด")
    ap.add_argument("--echo", action="store_true", help="แสดงบรรทัด NMEA บนหน้าจอ")
    args = ap.parse_args()

    outputs = []

    # ถ้ามี UDP ปลายทาง
    for entry in args.udp:
        host, port = parse_hostport(entry)
        outputs.append(UDPOutput(host, port, broadcast=args.udp_broadcast))

    # ถ้าระบุ multicast
    if args.mcast:
        g, p = parse_hostport(args.mcast)
        outputs.append(UDPMulticastOutput(g, p, iface_ip=args.mcast_if, ttl=args.mcast_ttl))

    # ถ้าไม่ระบุปลายทางใดเลย ให้ default ไปที่ UDP localhost:10110
    tcp_server = None
    if not outputs and not args.tcp_listen:
        print("[INFO] ไม่ได้ระบุปลายทางใด ๆ -> ใช้ค่าเริ่มต้น UDP 127.0.0.1:10110")
        outputs.append(UDPOutput("127.0.0.1", 10110, broadcast=False))

    # เปิด TCP server ถ้าต้องการ
    if args.tcp_listen:
        host, port = parse_hostport(args.tcp_listen)
        tcp_server = TCPServer(host, port)
        tcp_server.start()
        print(f"[TCP] Listening on {host}:{port}")

    try:
        read_and_forward(
            serial_port=args.serial_port,
            baudrate=args.baudrate,
            outputs=outputs,
            tcp_server=tcp_server,
            drop_bad_checksum=args.drop_bad_checksum,
            echo=args.echo
        )
    finally:
        for o in outputs:
            try:
                o.close()
            except Exception:
                pass
        if tcp_server:
            tcp_server.close()


if __name__ == "__main__":
    main()
