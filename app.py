from flask import Flask, request, render_template
import pandas as pd
import os

app = Flask(__name__)

INVENTARIO_FILE = 'inventario.csv'
VENTAS_FILE = 'ventas.csv'

# Cargar inventario desde CSV
def cargar_inventario():
    return pd.read_csv(INVENTARIO_FILE)

# Guardar inventario actualizado
def guardar_inventario(df):
    df.to_csv(INVENTARIO_FILE, index=False)

# Registrar venta
def registrar_venta(codigo, descripcion, precio, cantidad):
    venta = pd.DataFrame([{
        'codigo': codigo,
        'descripcion': descripcion,
        'precio': precio,
        'cantidad': cantidad,
        'total': precio * cantidad
    }])
    if os.path.exists(VENTAS_FILE):
        venta.to_csv(VENTAS_FILE, mode='a', header=False, index=False)
    else:
        venta.to_csv(VENTAS_FILE, index=False)

@app.route('/', methods=['GET', 'POST'])
def buscar_producto():
    resultado = None
    error = None

    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip().lower()
        descripcion = request.form.get('descripcion', '').strip().lower()

        inventario = cargar_inventario()
        if codigo:
            resultado = inventario[inventario['codigo'].astype(str).str.lower() == codigo]
        elif descripcion:
            resultado = inventario[inventario['descripcion'].str.lower().str.contains(descripcion)]
        
        if resultado is not None and resultado.empty:
            error = "Producto no encontrado."

    return render_template('buscar.html', productos=resultado, error=error)

@app.route('/vender', methods=['POST'])
def vender_producto():
    codigo = request.form['codigo']
    cantidad_vendida = int(request.form['cantidad'])

    inventario = cargar_inventario()
    idx = inventario[inventario['codigo'].astype(str) == codigo].index

    if not idx.empty:
        i = idx[0]
        disponible = int(inventario.loc[i, 'cantidad'])
        if disponible >= cantidad_vendida:
            inventario.at[i, 'cantidad'] = disponible - cantidad_vendida
            guardar_inventario(inventario)

            registrar_venta(
                inventario.at[i, 'codigo'],
                inventario.at[i, 'descripcion'],
                inventario.at[i, 'precio'],
                cantidad_vendida
            )

            return f"Venta realizada: {cantidad_vendida} unidades de {inventario.at[i, 'descripcion']}."
        else:
            return "No hay suficiente inventario."
    return "Producto no encontrado."

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
