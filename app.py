from flask import Flask, request, render_template
import sqlite3
import os
import shutil

app = Flask(__name__)

# Ruta segura para Render
DB_ORIGEN = 'inventario.db'
DB_PATH = os.path.join('/tmp', 'inventario.db')

# Copiar la base si no existe en /tmp
if not os.path.exists(DB_PATH):
    shutil.copyfile(DB_ORIGEN, DB_PATH)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/', methods=['GET', 'POST'])
def buscar_producto():
    producto = None
    error = None

    if request.method == 'POST':
        codigo = request.form['codigo']
        conn = get_db_connection()
        producto = conn.execute('SELECT * FROM productos WHERE codigo = ?', (codigo,)).fetchone()
        conn.close()
        if not producto:
            error = "Producto no encontrado."

    return render_template('buscar.html', producto=producto, error=error)

@app.route('/vender', methods=['POST'])
def vender_producto():
    codigo = request.form['codigo']
    cantidad_vendida = int(request.form['cantidad'])

    conn = get_db_connection()
    producto = conn.execute('SELECT * FROM productos WHERE codigo = ?', (codigo,)).fetchone()

    if producto and producto['cantidad'] >= cantidad_vendida:
        nueva_cantidad = producto['cantidad'] - cantidad_vendida
        conn.execute('UPDATE productos SET cantidad = ? WHERE codigo = ?', (nueva_cantidad, codigo))
        conn.commit()
        conn.close()
        return f"Venta realizada: {cantidad_vendida} unidades de {producto['descripcion']}. Stock restante: {nueva_cantidad}."
    else:
        conn.close()
        return "No hay suficiente inventario."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
