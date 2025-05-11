from flask import Flask, request, render_template
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import tempfile

# Configuración Google Sheets y Drive
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credenciales = Credentials.from_service_account_file("/etc/secrets/recuperandes-558ed1af7700.json", scopes=scope)
cliente = gspread.authorize(credenciales)

hoja_objetos = cliente.open("Objetos_Reportados_RecuperAndes").sheet1
hoja_registro = cliente.open("Registro_Notificaciones").sheet1

# ID de la carpeta de Google Drive
carpeta_id = "1baKpSUxvWnHSkChIII1IK06P4rQc-_vN"

# Función para subir imagen a Drive
def subir_imagen_a_drive(nombre_archivo, archivo_stream, carpeta_id):
    servicio = build("drive", "v3", credentials=credenciales)
    temp = tempfile.NamedTemporaryFile(delete=False)
    archivo_stream.save(temp.name)

    media = MediaFileUpload(temp.name, resumable=True)
    metadata = {
        "name": nombre_archivo,
        "parents": [carpeta_id]
    }

    archivo = servicio.files().create(
        body=metadata,
        media_body=media,
        fields="id"
    ).execute()

    # Hacer el archivo público
    servicio.permissions().create(
        fileId=archivo["id"],
        body={"role": "reader", "type": "anyone"}
    ).execute()

    return f"https://drive.google.com/uc?export=view&id={archivo['id']}"

# Configurar app Flask
app = Flask(__name__)

@app.route("/")
def inicio():
    return render_template("index.html")

@app.route("/formulario-reportar", methods=["GET"])
def mostrar_formulario_reportar():
    return render_template("reportar_objeto.html")

@app.route("/formulario-registrar", methods=["GET"])
def mostrar_formulario_registro():
    return render_template("registro_estudiante.html")

@app.route("/galeria", methods=["GET"])
def mostrar_galeria():
    filas = hoja_objetos.get_all_values()
    objetos = []

    for fila in filas[1:]:  # Saltar encabezado
        if len(fila) < 6:
            continue  # Si faltan columnas básicas, saltar

        tipo = fila[0]
        descripcion = fila[1]
        lugar = fila[2]
        fecha = fila[3]
        hora = fila[4]
        foto = fila[6] if len(fila) > 6 else ""

        objetos.append({
            "tipo": tipo,
            "descripcion": descripcion,
            "lugar": lugar,
            "fecha": fecha,
            "hora": hora,
            "foto": foto if foto.strip() else "https://via.placeholder.com/250x180.png?text=Sin+foto"
        })

    objetos.reverse()  # Mostrar los más recientes primero
    return render_template("galeria_perdidos.html", objetos=objetos)

@app.route("/reportar", methods=["POST"])
def recibir_reporte():
    tipo = request.form.get("tipo")
    descripcion = request.form.get("descripcion")
    lugar = request.form.get("ubicacion")
    fecha = request.form.get("fecha")
    hora = request.form.get("hora")
    genero_objeto = request.form.get("genero_objeto") or "No especificado"

    archivo = request.files.get("foto")
    if archivo and archivo.filename:
        enlace_foto = subir_imagen_a_drive(archivo.filename, archivo, carpeta_id)
    else:
        enlace_foto = "https://via.placeholder.com/250x180.png?text=Sin+foto"

    hoja_objetos.append_row([
        tipo,
        descripcion,
        lugar,
        fecha,
        hora,
        "archivo",
        enlace_foto,
        genero_objeto
    ])

    notificar_estudiantes_si_coincide(tipo, lugar, genero_objeto, enlace_foto)
    return "¡Reporte recibido correctamente!"

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

# Función para enviar notificaciones si hay coincidencias
def notificar_estudiantes_si_coincide(tipo, lugar, genero_estimado, foto_url):
    registros = hoja_registro.get_all_records()
    for registro in registros:
        correo = registro.get("Correo Institucional", "").strip()
        genero_estudiante = registro.get("Género", "").strip()
        zonas = registro.get("Zonas que frecuenta", "").upper().split(", ")
        intereses = registro.get("Categorías de interés", "").split(", ")
        acepta = registro.get("Acepta notificaciones", "No").strip().lower()

        # Verificar si acepta notificaciones
        if acepta != "on":
            continue

        # Verificar coincidencia por lugar
        if lugar not in zonas:
            continue

        # Verificar coincidencia por categoría de objeto
        if tipo not in intereses:
            continue

        # Verificar coincidencia de género si se conoce
        if genero_estimado and genero_estimado != "No estoy seguro" and genero_estimado != genero_estudiante:
            continue

        # Si cumple todo, enviar correo
        enviar_correo_aviso(correo, tipo, lugar, foto_url)

# Función para enviar el correo de aviso de coincidencia
def enviar_correo_aviso(destinatario, tipo, lugar, foto_url):
    emisor = "recuperandes@gmail.com"
    clave = "sfesfddxvfjkvomc"

    mensaje = MIMEMultipart("alternative")
    mensaje["From"] = emisor
    mensaje["To"] = destinatario
    mensaje["Subject"] = "¡Nuevo objeto perdido que puede ser tuyo!"

    html = f"""
    <html>
      <body>
        <p>Hola,</p>
        <p>Se ha reportado un objeto del tipo <strong>{tipo}</strong> en el lugar <strong>{lugar}</strong>, que coincide con tus intereses y zonas frecuentadas.</p>
        <p>Puedes revisarlo en la <a href="https://recuperandes-app.onrender.com/galeria">galería de objetos perdidos</a> o acercarte al punto físico en el edificio ML.</p>
        <p><strong>Imagen del objeto:</strong></p>
        <img src="{foto_url}" alt="Objeto perdido" style="max-width:400px; border-radius:10px;">
        <p>¡Esperamos que sea tuyo!</p>
        <p>— Equipo RecuperAndes</p>
      </body>
    </html>
    """

    mensaje.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
        servidor.login(emisor, clave)
        servidor.send_message(mensaje)
