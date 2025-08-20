# NMEA Serial to IP Gateway

สคริปต์ Python สำหรับอ่านข้อมูล **NMEA 0183** จากพอร์ต Serial (เช่น GPS, AIS, Radar) แล้วส่งต่อออกไปทาง **UDP / UDP Broadcast / UDP Multicast / TCP Server**  
ทำให้สามารถใช้งานกับโปรแกรมแผนที่เดินเรือ เช่น **OpenCPN**, TimeZero, ฯลฯ ได้สะดวก

---

## คุณสมบัติ

- อ่านข้อมูล NMEA จาก Serial port (4800 / 38400 bps)
- ส่งออกได้หลายรูปแบบ:
  - UDP (Unicast)
  - UDP Broadcast
  - UDP Multicast
  - TCP Server (ให้หลาย client มารับพร้อมกัน)
- รองรับหลายปลายทางพร้อมกัน
- ตรวจสอบ/ตัดทิ้งข้อมูลที่ checksum ไม่ถูกต้อง (เลือกเปิด/ปิดได้)
- Reconnect อัตโนมัติหาก serial หลุด

---

## การติดตั้ง

pip install pyserial

⸻

การใช้งาน

รันสคริปต์หลัก:

python nmea_serial_to_ip.py -p <serial_port> -b <baudrate> [options...]

ตัวเลือกหลัก

ตัวเลือก	คำอธิบาย
-p, --serial-port	พอร์ต serial (เช่น COM3, /dev/ttyUSB0)
-b, --baudrate	baudrate (ค่าเริ่มต้น 4800, AIS มัก 38400)
-u, --udp host:port	ส่งข้อมูลไปยัง UDP ปลายทาง (ระบุได้หลายครั้ง)
--udp-broadcast	เปิดโหมด broadcast สำหรับ UDP
--mcast group:port	ส่งข้อมูลเป็น multicast (เช่น 239.255.0.1:10110)
--mcast-if <ip>	ระบุ IP ของ network interface ที่ใช้ส่ง multicast
--mcast-ttl <n>	TTL สำหรับ multicast (ค่าเริ่มต้น 1)
--tcp-listen host:port	เปิด TCP server ให้ client เชื่อมต่อเข้ามารับสตรีม
--drop-bad-checksum	ตัดทิ้งประโยคที่ checksum ไม่ถูกต้อง
--echo	แสดงข้อความ NMEA บนหน้าจอ


⸻

ตัวอย่างการใช้งาน

1) ส่งไปยัง OpenCPN (UDP Localhost)

python nmea_serial_to_ip.py -p COM3 -b 4800 -u 127.0.0.1:10110 --echo

ตั้ง OpenCPN ให้ฟัง Network → UDP → Port 10110

⸻

2) ส่งไปยังเครื่องอื่นใน LAN (UDP Unicast)

python nmea_serial_to_ip.py -p /dev/ttyUSB0 -b 4800 -u 192.168.1.20:10110


⸻

3) ส่งแบบ Broadcast ทั้งวงแลน

python nmea_serial_to_ip.py -p /dev/ttyUSB0 -b 4800 -u 192.168.1.255:10110 --udp-broadcast


⸻

4) ส่งเป็น Multicast

python nmea_serial_to_ip.py -p /dev/ttyUSB0 -b 4800 \
  --mcast 239.255.0.1:10110 \
  --mcast-if 192.168.1.50 \
  --mcast-ttl 1


⸻

5) เปิด TCP Server

python nmea_serial_to_ip.py -p /dev/ttyUSB0 -b 38400 --tcp-listen 0.0.0.0:10110

จากปลายทาง ให้เชื่อมต่อ TCP ไปที่ IP-เครื่อง:10110

⸻

ทิปส์
	•	GPS ใช้ baudrate 4800
	•	AIS ใช้ baudrate 38400
	•	หากไม่มี checksum หรือ checksum ผิดปกติ ให้ลองปิด --drop-bad-checksum
	•	ถ้าไม่ได้ระบุปลายทางใด ๆ จะส่งไปที่ 127.0.0.1:10110 (UDP) โดยอัตโนมัติ

⸻

License

MIT

---


## Topology

### Overview (Mermaid)

+----------------------+         +--------------------+         +---------------------------+
| GPS / AIS / Radar    |  NMEA   |  Python Gateway    |  UDP    | OpenCPN / TimeZero / Apps |
| (0183 talker)        | ======> |  (serial → IP)     | ======> | (UDP Unicast/Bcast/Mcast) |
+----------------------+ (COM/   |  - checksum check  |         +---------------------------+
                              \  |  - CRLF normalize  |
                               \ |  - fan-out         |  TCP    +---------------------------+
                                \+--------------------+ ======> | Clients connect to TCP    |
                                                                | server and receive NMEA   |
                                                                +---------------------------+

```mermaid
flowchart LR
  subgraph A[Sensors / Talkers]
    S1["GPS / GNSS\nNMEA 0183"]
    S2["AIS Receiver\nNMEA 0183"]
    S3["Radar / Others\nNMEA-like"]
  end

  S1 --> G
  S2 --> G
  S3 --> G

  subgraph G[Python NMEA Serial → IP Gateway]
    P1["Read Serial (pyserial)"]
    P2["Validate & Normalize\n(checksum, CRLF)"]
    P3["Fan-out\nUDP / UDP Broadcast / Multicast / TCP"]
  end

  P1 --> P2
  P2 --> P3

  subgraph N[Network]
    U1["UDP Unicast\n127.0.0.1:10110"]
    U2["UDP Broadcast\n192.168.1.255:10110"]
    U3["UDP Multicast\n239.255.0.1:10110"]
    T1["TCP Server\n0.0.0.0:10110"]
  end

  P3 --> U1
  P3 --> U2
  P3 --> U3
  P3 --> T1

  subgraph C[Consumers / Chartplotters]
    C1[OpenCPN]
    C2[TimeZero / Others]
    C3[Custom Apps]
  end

  U1 --> C1
  U2 --> C1
  U3 --> C1
  T1 --> C1

  U1 -. optional .-> C2
  U3 -. optional .-> C2
  T1 -. optional .-> C3\n

#Data Flow (Mermaid Sequence)

sequenceDiagram
    participant DEV as Device (GPS/AIS/Radar)
    participant SER as Serial Port (/dev/ttyUSB0)
    participant GW as Python Gateway
    participant NET as Network (UDP/TCP)
    participant APP as OpenCPN/Apps

    DEV->>SER: NMEA sentence<br/>$GPGGA,...*CS\\r\\n
    SER->>GW: read()
    GW->>GW: checksum validate & normalize
    alt UDP/Unicast/Broadcast/Multicast
        GW-->>NET: UDP packet(s)
        NET-->>APP: UDP payload (NMEA line)
    else TCP Server
        APP->>GW: TCP connect
        GW-->>APP: stream NMEA lines
    end
