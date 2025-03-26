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
SECRET_KEY = os.environ.get("SECRET_KEY", "Likexpress-000")
serializer = URLSafeTimedSerializer(SECRET_KEY)
IPQUALITY_API_KEY = "uFo2UB4b1rdgKaYnPJ6ZUrUKjSxX0r60"  # tu API KEY real
RATE_LIMIT_WINDOW = timedelta(seconds=60)

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

# ---------------------------
# Modelo para control de IPs (rate limiting)
# ---------------------------
class IPLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------------------
# Crear las tablas si no existen
# ---------------------------
with app.app_context():
    db.create_all()

# ---------------------------
# Verificar si una IP es VPN o proxy
# ---------------------------
def ip_es_vpn(ip):
    if not IPQUALITY_API_KEY or not ip:
        print("IPQualityScore: API Key o IP faltante.")
        return False
    try:
        url = f"https://ipqualityscore.com/api/json/ip/{IPQUALITY_API_KEY}/{ip}"
        print(f"Consultando IPQualityScore para IP: {ip}")
        res = requests.get(url)
        data = res.json()
        print("Respuesta IPQualityScore:", data)
        return data.get("proxy") or data.get("vpn") or data.get("tor")
    except Exception as e:
        print("Error al verificar IP con IPQualityScore:", e)
        return False


# ---------------------------
# Verificar si una IP accedió recientemente (rate limit)
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
# Página de votación
# ---------------------------
@app.route('/votar')
def votar():
    token = request.args.get('token')
    if not token:
        return "Acceso no válido."

    try:
        numero = serializer.loads(token, max_age=3600)  # Token válido por 1 hora
    except SignatureExpired:
        return "Este enlace ha expirado. Solicita uno nuevo."
    except BadSignature:
        return "Enlace inválido o alterado."

    if Voto.query.filter_by(numero=numero).first():
        return "Este número ya ha votado. Gracias por participar."

    ip = (request.headers.get('X-Forwarded-For') or request.remote_addr).split(',')[0].strip()

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
    ip = (request.headers.get('X-Forwarded-For') or request.remote_addr).split(',')[0].strip()

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
# WhatsApp: Enviar link con token cifrado
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
# Ruta para borrar un voto (para pruebas)
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
