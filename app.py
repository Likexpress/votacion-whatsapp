from flask import Flask, request, render_template, redirect
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import os
import requests

# ---------------------------
# Configuración
# ---------------------------
app = Flask(__name__)
SECRET_KEY = os.environ.get("SECRET_KEY", "clave-secreta-segura")
serializer = URLSafeTimedSerializer(SECRET_KEY)
IPQUALITY_API_KEY = os.environ.get("IPQUALITY_API_KEY")
RATE_LIMIT_WINDOW = timedelta(seconds=60)  # Límite de 1 minuto entre accesos por IP

# ---------------------------
# Configuración de la base de datos PostgreSQL
# ---------------------------
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------------------
# Modelo de tabla: Voto
# ---------------------------
class Voto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), unique=True, nullable=False)
    candidato = db.Column(db.String(100), nullable=False)
    pais = db.Column(db.String(100), nullable=False)
    ciudad = db.Column(db.String(100), nullable=False)
    ip = db.Column(db.String(50), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

class IPLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ---------------------------
# Función: Verificación de VPN
# ---------------------------
def ip_es_vpn(ip):
    if not IPQUALITY_API_KEY or not ip:
        return False
    try:
        url = f"https://ipqualityscore.com/api/json/ip/{IPQUALITY_API_KEY}/{ip}"
        res = requests.get(url)
        data = res.json()
        print("Verificando IP:", ip)  # ← Para depuración
        print("Respuesta de IPQualityScore:", data)  # ← VER LA RESPUESTA COMPLETA
        return data.get("proxy") or data.get("vpn") or data.get("tor")
    except Exception as e:
        print("Error en verificación de IP:", e)
        return False


# ---------------------------
# Función: Verificación de rate limit
# ---------------------------
def esta_dentro_de_limite(ip):
    ultima = IPLog.query.filter_by(ip=ip).order_by(IPLog.timestamp.desc()).first()
    ahora = datetime.utcnow()
    if ultima and ahora - ultima.timestamp < RATE_LIMIT_WINDOW:
        return False
    db.session.add(IPLog(ip=ip, timestamp=ahora))
    db.session.commit()
    return True

# ---------------------------
# Página de inicio
# ---------------------------
@app.route('/')
def index():
    return "Bienvenido al sistema de votación. Este enlace debe ser accedido desde WhatsApp."

# ---------------------------
# Página de votación protegida
# ---------------------------
@app.route('/votar')
def votar():
    token = request.args.get('token')
    if not token:
        return "Acceso no válido."

    try:
        numero = serializer.loads(token, max_age=3600)  # Enlace válido por 1 hora
    except SignatureExpired:
        return "Este enlace ha expirado. Solicita uno nuevo."
    except BadSignature:
        return "Enlace inválido o alterado."

    if Voto.query.filter_by(numero=numero).first():
        return "Este número ya ha votado. Gracias por participar."

    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if ip_es_vpn(ip):
        return "No se permite votar desde conexiones VPN o proxy."

    if not esta_dentro_de_limite(ip):
        return "Por favor espera un momento antes de volver a intentarlo."

    if Voto.query.filter_by(ip=ip).count() >= 10:
        return "Se ha alcanzado el límite de votos permitidos desde esta conexión."

    return render_template("votar.html", numero=numero)

# ---------------------------
# Enviar voto
# ---------------------------
@app.route('/enviar_voto', methods=['POST'])
def enviar_voto():
    numero = request.form.get('numero')
    candidato = request.form.get('candidato')
    pais = request.form.get('pais')
    ciudad = request.form.get('ciudad')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if Voto.query.filter_by(numero=numero).first():
        return "Ya registramos tu voto."

    if ip_es_vpn(ip):
        return "Voto denegado. No se permite votar desde una VPN o proxy."

    if not esta_dentro_de_limite(ip):
        return "Por favor espera un momento antes de intentar votar."

    if Voto.query.filter_by(ip=ip).count() >= 10:
        return "Se ha alcanzado el límite de votos permitidos desde esta conexión."

    nuevo_voto = Voto(numero=numero, candidato=candidato, pais=pais, ciudad=ciudad, ip=ip)
    db.session.add(nuevo_voto)
    db.session.commit()

    return f"Gracias por tu voto. Has elegido: {candidato}.<br>Ubicación: {ciudad}, {pais}"

# ---------------------------
# Enviar mensaje por WhatsApp con token cifrado
# ---------------------------
@app.route('/whatsapp', methods=['POST'])
def whatsapp_reply():
    sender = request.values.get('From', '')
    numero = sender.replace("whatsapp:", "").strip()

    token = serializer.dumps(numero)
    link_votacion = f"https://primariasbunker.org/votar?token={token}"

    response = MessagingResponse()
    msg = response.message()
    msg.body(f"Hola, gracias por participar en la votación.\n\nHaz clic para votar:\n{link_votacion}")
    return str(response)

# ---------------------------
# Borrar voto manualmente (solo para pruebas)
# ---------------------------
@app.route('/borrar_voto')
def borrar_voto():
    numero = request.args.get('numero')
    if not numero:
        return "Falta el número. Usa /borrar_voto?numero=whatsapp:+59167692624"

    voto = Voto.query.filter_by(numero=numero).first()
    if voto:
        db.session.delete(voto)
        db.session.commit()
        return f"Voto del número {numero} eliminado correctamente."
    else:
        return "No se encontró ningún voto con ese número."

# ---------------------------
# Ejecutar localmente
# ---------------------------
if __name__ == '__main__':
    app.run(debug=True)
