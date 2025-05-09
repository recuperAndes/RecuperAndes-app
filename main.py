from flask import Flask, request, render_template
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuración Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credenciales = Credentials.from_service_account_file("/etc/secrets/recuperandes-558ed1af7700.json", scopes=scope)
cliente = gspread.authorize(credenciales)

hoja_objetos = cliente.open("Objetos_Reportados_RecuperAndes").sheet1
hoja_registro = cliente.open("Registro_Notificaciones").sheet1

# Configurar app Flask
app = Flask(__name__)

# Ruta principal
@app.route("/")
def inicio():
    return render_template("index.html")

# Formulario de reporte
@app.route("/formulario-reportar", methods=["GET"])
def mostrar_formulario_reportar():
    return render_template("reportar_objeto.html")

# Formulario de registro
@app.route("/formulario-registrar", methods=["GET"])
def mostrar_formulario_registro():
    return render_template("registro_estudiante.html")

# Galería dinámica
@app.route("/galeria", methods=["GET"])
def mostrar_galeria():
    filas = hoja_objetos.get_all_values()
    objetos = []

    for fila in filas[1:]:  # Saltar encabezado
        tipo, descripcion, lugar, fecha, hora, foto = fila
        objetos.append({
            "tipo": tipo,
            "descripcion": descripcion,
            "lugar": lugar,
            "fecha": fecha,
            "hora": hora,
            "foto": foto if foto != "Sin foto" else "https://via.placeholder.com/250x180.png?text=Sin+foto"
        })

    return render_template("galeria_perdidos.html", objetos=objetos)

# Guardar reporte de objeto
@app.route("/reportar", methods=["POST"])
def recibir_reporte():
    tipo = request.form.get("tipo")
    descripcion = request.form.get("descripcion")
    lugar = request.form.get("ubicacion")
    fecha = request.form.get("fecha")
    hora = request.form.get("hora")
    foto = request.form.get("foto") or "Sin foto"

    hoja_objetos.append_row([tipo, descripcion, lugar, fecha, hora, foto])
    return "¡Reporte recibido correctamente!"

# Guardar registro de estudiante
@app.route("/registrar", methods=["POST"])
def registrar_estudiante():
    nombre = request.form.get("nombre")
    correo = request.form.get("correo")
    genero = request.form.get("genero")
    zonas = request.form.getlist("zona")
    intereses = request.form.getlist("interes")
    acepta = request.form.get("acepta") or "No"

    hoja_registro.append_row([
        nombre,
        correo,
        genero,
        ", ".join(zonas),
        ", ".join(intereses),
        acepta
    ])

    enviar_correo_confirmacion(nombre, correo)
    return "¡Registro exitoso!"

# Enviar correo
def enviar_correo_confirmacion(nombre, destinatario):
    emisor = "recuperandes@gmail.com"
    clave = "sfesfddxvfjkvomc"  # Contraseña de aplicación

    mensaje = MIMEMultipart()
    mensaje["From"] = emisor
    mensaje["To"] = destinatario
    mensaje["Subject"] = "Confirmación de registro - RecuperAndes"

    cuerpo = f"""
    Hola {nombre},

    Te has registrado correctamente en RecuperAndes.
    A partir de ahora recibirás alertas si se encuentra un objeto que coincida con tus intereses y zonas frecuentadas.

    ¡Gracias por usar nuestro sistema!

    - Equipo RecuperAndes
    """
    mensaje.attach(MIMEText(cuerpo, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
        servidor.login(emisor, clave)
        servidor.send_message(mensaje)