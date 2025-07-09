from flask import Flask, render_template, request, redirect, session, url_for
import mysql.connector
import openai
import json
import re
import random
import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
app.secret_key = 'secreta123'
openai.api_key = OPENAI_API_KEY


# Crear base de datos y tabla si no existen
def crear_base_de_datos_y_tabla():
    conexion = mysql.connector.connect(
        host='database-1.cbmc846qcmg5.sa-east-1.rds.amazonaws.com',
        user='admin',
        password='Vamosperu10_'
    )
    cursor = conexion.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS juega_y_aprende CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    conexion.database = 'juega_y_aprende'
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INT AUTO_INCREMENT PRIMARY KEY,
            curso VARCHAR(100) NOT NULL,
            tema VARCHAR(100) NOT NULL,
            tipo VARCHAR(50) NOT NULL,
            dificultad VARCHAR(50) NOT NULL,
            puntaje INT NOT NULL,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conexion.close()

crear_base_de_datos_y_tabla()

def conectar_mysql():
    return mysql.connector.connect(
        host='database-1.cbmc846qcmg5.sa-east-1.rds.amazonaws.com',
        user='admin',
        password='Vamosperu10_',
        database='juega_y_aprende'
    )

def guardar_en_historial(curso, tema, tipo, dificultad, puntaje):
    conn = conectar_mysql()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO historial (curso, tema, tipo, dificultad, puntaje) VALUES (%s, %s, %s, %s, %s)''',
                   (curso, tema, tipo, dificultad, puntaje))
    conn.commit()
    conn.close()

def obtener_historial():
    conn = conectar_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT curso, tema, tipo, dificultad, puntaje, fecha FROM historial ORDER BY fecha DESC")
    historial = cursor.fetchall()
    conn.close()
    return historial

def generar_preguntas():
    preguntas = []
    intentos = 0
    temas_usados = set()

    while len(preguntas) < 5 and intentos < 25:
        prompt = f"""
        Genera SOLO UNA pregunta tipo {session['tipo']} para estudiantes del curso {session['curso']},
        sobre el tema "{session['tema']}", con nivel de dificultad {session['dificultad']}.

        Incluye en la explicación:
        - Contexto amplio del tema.
        - Procedimiento detallado.
        - Teoremas o reglas usadas.

        Devuélvela estrictamente en formato JSON y sin texto adicional:

        {{
          "pregunta": "Texto de la pregunta",
          "opciones": ["Opción A", "Opción B", "Opción C", "Opción D"],
          "respuesta_correcta": "Texto EXACTO de la opción correcta",
          "explicacion": "Explicación completa, detallada y clara del procedimiento, incluyendo teoremas y ejemplos."
        }}
        """

        try:
            respuesta = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4
            )
            contenido = respuesta.choices[0].message.content.strip()
            match = re.search(r"\{.*\}", contenido, re.DOTALL)
            if match:
                pregunta = json.loads(match.group(0))
                texto_normalizado = pregunta["pregunta"].strip().lower()
                if (
                    "pregunta" in pregunta and
                    "opciones" in pregunta and
                    "respuesta_correcta" in pregunta and
                    "explicacion" in pregunta and
                    isinstance(pregunta["opciones"], list) and
                    pregunta["respuesta_correcta"] in pregunta["opciones"] and
                    texto_normalizado not in temas_usados
                ):
                    preguntas.append(pregunta)
                    temas_usados.add(texto_normalizado)
        except Exception as e:
            print("⚠️ Error generando pregunta:", e)

        intentos += 1

    session['preguntas'] = preguntas

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/comenzar', methods=['POST'])
def comenzar():
    session['curso'] = request.form['curso']
    session['tema'] = request.form['tema']
    session['tipo'] = request.form['tipo']
    session['dificultad'] = request.form['dificultad']
    session['preguntas'] = []
    session['actual'] = 0
    session['puntaje'] = 0

    generar_preguntas()

    if len(session['preguntas']) < 5:
        return render_template('error.html', mensaje="❌ No se pudieron generar 5 preguntas desde OpenAI. Intenta con otro curso o tema más general.")

    return redirect('/juego')

@app.route('/juego', methods=['GET', 'POST'])
def juego():
    if 'preguntas' not in session or session['actual'] >= len(session['preguntas']):
        return redirect('/resultado')

    if request.method == 'POST':
        seleccion = request.form['respuesta']
        pregunta = session['preguntas'][session['actual']]
        correcta = pregunta['respuesta_correcta']

        if seleccion == correcta:
            session['puntaje'] += 1
            mensaje = random.choice(["¡Muy bien! 🎉", "¡Correcto! Sigue así.", "¡Excelente respuesta! 💪"])
            correcta_respuesta = True
        else:
            mensaje = random.choice(["No fue correcto, pero sigue intentando.", "¡Casi! No te rindas.", "Respuesta incorrecta, ¡vamos a la siguiente!"])
            correcta_respuesta = False

        session['actual'] += 1

        if session['actual'] >= len(session['preguntas']):
            guardar_en_historial(session['curso'], session['tema'], session['tipo'], session['dificultad'], session['puntaje'])
            return redirect('/resultado')

        return render_template('juego.html',
                               pregunta=session['preguntas'][session['actual']],
                               mensaje=mensaje,
                               correcta=correcta_respuesta)

    return render_template('juego.html',
                           pregunta=session['preguntas'][session['actual']],
                           mensaje=None,
                           correcta=None)

@app.route('/resultado')
def resultado():
    return render_template('resultado.html',
                           puntaje=session.get('puntaje', 0),
                           curso=session.get('curso'),
                           tema=session.get('tema'),
                           tipo=session.get('tipo'),
                           dificultad=session.get('dificultad'))

@app.route('/solucionario')
def solucionario():
    if 'preguntas' not in session:
        return redirect('/')
    return render_template('solucionario.html', preguntas=session['preguntas'])

@app.route('/historial')
def historial():
    data = obtener_historial()
    return render_template('historial.html', historial=data)

if __name__ == '__main__':
    app.run(debug=True)


