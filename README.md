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

```bash
git clone https://github.com/your-repo/nmea-serial-to-ip.git
cd nmea-serial-to-ip
pip install -r requirements.txt
