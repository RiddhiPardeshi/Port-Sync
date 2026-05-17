"""
notify.py — Member 2
Notification service: WhatsApp → SMS fallback → QR pre-load.
Real Twilio integration. Sends to actual driver phone.
"""

import os
import io
import cloudinary
import cloudinary.uploader
import logging
import time
import qrcode
import jwt
import json
from datetime import datetime, timedelta
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from deep_translator import GoogleTranslator
from data.fixtures import MSG_TEMPLATES

logger = logging.getLogger("notify_service")

LANG_MAP = {
    "hi": "hindi",
    "ta": "tamil",
    "te": "telugu",
    "ar": "arabic",
    "en": "english",
}


class NotifyService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
        #self.wa_from     = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
        self.wa_from = f"whatsapp:{os.getenv('TWILIO_WHATSAPP_FROM', '+14155238886')}"
        self.sms_from    = os.getenv("TWILIO_SMS_FROM", "")
        self.dry_run     = not bool(self.account_sid)
        # cloudinary.config(
        #   cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        #   api_key=os.getenv("CLOUDINARY_API_KEY"),
        #   api_secret=os.getenv("CLOUDINARY_API_SECRET")
        # )
        print("Cloud Name:", os.getenv("CLOUDINARY_CLOUD_NAME"))
        

        if self.dry_run:
            logger.warning("Twilio credentials not set — running in DRY RUN mode (logs only)")
        else:
            self.client = Client(self.account_sid, self.auth_token)

    def send(self, phone: str, template_key: str, instructions: dict):
        """
        Main entry. Tries WhatsApp first, falls back to SMS.
        Always generates QR card.
        """
        if not phone:
            logger.warning("No driver phone set — skipping notification")
            return

        # Build message text from template
        template = MSG_TEMPLATES.get(template_key, MSG_TEMPLATES["slot_updated"])
        message_en = template.format(**instructions)

        # Translate to driver language
        lang = instructions.get("language", "hi")
        message = self._translate(message_en, lang)

        # Generate QR
        qr_path = self._generate_qr(instructions)

        # Send WhatsApp with QR
        sent = self._send_whatsapp(phone, message, qr_path)

        # Fallback to SMS if WhatsApp failed
        if not sent:
            logger.warning("WhatsApp failed — falling back to SMS")
            self._send_sms(phone, message)

        logger.info(f"Notification complete for {phone} | template={template_key}")

    def _translate(self, text: str, lang: str) -> str:
        if lang == "en":
            return text
        try:
            translated = GoogleTranslator(source="en", target=lang).translate(text)
            return translated
        except Exception as e:
            logger.warning(f"Translation failed ({lang}): {e} — using English")
            return text
    def _send_whatsapp(self, phone: str, message: str, qr_path: str) -> bool:
     to = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone

     if self.dry_run:
        logger.info(f"[DRY RUN] WhatsApp → {to}:\n{message}")
        return True

     try:
        full_message = f"{message}\n\n📎 Scan your QR Code: {qr_path}"
        self.client.messages.create(
            from_=self.wa_from,
            to=to,
            body=full_message
        )
        logger.info(f"WhatsApp sent to {to} | QR: {qr_path}")
        return True
     except TwilioRestException as e:
        logger.error(f"WhatsApp send failed: {e}")
        return False
#     def _send_whatsapp(self, phone: str, message: str, qr_path: str) -> bool:
#         to = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone

#         if self.dry_run:
#             logger.info(f"[DRY RUN] WhatsApp → {to}:\n{message}")
#             return True

#         try:
#             # Send text message
#             # self.client.messages.create(
#             #     from_=self.wa_from,
#             #     to=to,
#             #     body=message,
#             # )
#             # Send text message
#             self.client.messages.create(
#                from_=self.wa_from,
#                to=to,
#                body=message
#             )

# # Send QR image as media (hosted URL required)
#             media_url = self._host_qr(qr_path)
#             self.client.messages.create(
#               from_=self.wa_from,
#               to=to,
#               media_url=[media_url]
#             )
#             # Send QR image as media
#             # Note: in production host the QR on a public URL (e.g. Railway static)
#             # For demo, we log the QR path
#             logger.info(f"WhatsApp sent to {to} | QR at {qr_path}")
#             return True
#         except TwilioRestException as e:
#             logger.error(f"WhatsApp send failed: {e}")
#             return False
    # def _host_qr(self, path: str) -> str:
    # # """
    # # In production, upload QR to a public URL.
    # # For demo, simulate with a placeholder image.
    # # """
    # # Replace with actual hosting logic if needed
    #  filename = os.path.basename(path)
    #  return f"https://portsync-demo.up.railway.app/static/qr_codes/{filename}"
    def _host_qr(self, path: str) -> str:
      filename = os.path.basename(path)
      return f"https://portsync-production.up.railway.app/static/qr_codes/{filename}"

     # return "https://via.placeholder.com/300.png?text=PortSync+QR"
    def _send_sms(self, phone: str, message: str) -> bool:
        if self.dry_run:
            logger.info(f"[DRY RUN] SMS → {phone}:\n{message[:160]}")
            return True

        if not self.sms_from:
            logger.warning("SMS_FROM not set — skipping SMS")
            return False

        try:
            self.client.messages.create(
                from_=self.sms_from,
                to=phone,
                body=message[:160],  # SMS limit
            )
            logger.info(f"SMS sent to {phone}")
            return True
        except TwilioRestException as e:
            logger.error(f"SMS send failed: {e}")
            return False
       
    def _generate_qr(self, instructions: dict) -> str:
        """
        Generates a QR code PNG encoding a signed JWT token.
        Saves to ./qr_codes/portsync_qr_{token}.png
        """
        os.makedirs("static/qr_codes", exist_ok=True)  # 🔥 ADD THIS

        payload = {
            "token": instructions["token"],
            "gate": instructions["gate"],
            "start": instructions["start_time"],
            "end": instructions["end_time"],
            "container": instructions.get("container_id", ""),
            "issued": datetime.now().isoformat(),
            "valid_until": (datetime.now() + timedelta(hours=24)).isoformat(),
            "exp": datetime.utcnow() + timedelta(hours=24)  # 🔥 IMPORTANT
        }

        # Sign payload as JWT
        secret = os.getenv("JWT_SECRET", "default_secret")
        jwt_token = jwt.encode(payload, secret, algorithm="HS256")

        # Generate QR with JWT string
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(jwt_token)
        # qr_data = f"https://portsync-production.up.railway.app/verify?token={jwt_token}"
        # qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Save QR image
        #path = f"./qr_codes/portsync_qr_{instructions['token']}.png"
        #path = f"static/qr_codes/portsync_qr_{instructions['token']}.png"
        # path = f"./static/qr_codes/portsync_qr_{instructions['token']}.png"
     
        # os.makedirs("static/qr_codes", exist_ok=True)
        # img.save(path)
        # logger.info(f"JWT QR generated: {path}")
        # return path
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        upload_result = cloudinary.uploader.upload(
        buffer,
        folder="portsync_qr"
        )

        qr_url = upload_result["secure_url"]

        logger.info(f"QR uploaded to Cloudinary: {qr_url}")

        return qr_url

    

    def verify_qr(jwt_token: str):
     secret = os.getenv("JWT_SECRET", "default_secret")
     try:
        payload = jwt.decode(jwt_token, secret, algorithms=["HS256"])
        return payload  # valid slot info
     except jwt.ExpiredSignatureError:
        return {"error": "Token expired"}
     except jwt.InvalidTokenError:
        return {"error": "Invalid token"}
    # def _generate_qr(self, instructions: dict) -> str:
    #     """
    #     Generates a QR code PNG encoding the slot token data.
    #     Saves to /tmp/portsync_qr_{token}.png
    #     """
    #     payload = {
    #         "token": instructions["token"],
    #         "gate": instructions["gate"],
    #         "start": instructions["start_time"],
    #         "end": instructions["end_time"],
    #         "container": instructions.get("container_id", ""),
    #         "issued": datetime.now().isoformat(),
    #         "valid_until": (datetime.now() + timedelta(hours=24)).isoformat(),
    #     }
    #     qr = qrcode.QRCode(version=1, box_size=10, border=4)
    #     qr.add_data(json.dumps(payload))
    #     qr.make(fit=True)
    #     img = qr.make_image(fill_color="black", back_color="white")
    #     #path = f"/tmp/portsync_qr_{instructions['token']}.png"
    #     path = f"./qr_codes/portsync_qr_{instructions['token']}.png"
    #     img.save(path)
    #     logger.info(f"QR generated: {path}")
    #     return path
