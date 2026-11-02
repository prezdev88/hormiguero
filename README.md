# Hormiguero 🐜

Un pequeño simulador de colonias para jugar en tu computador. Cría hormigas,
recoge alimento, construye nuevos nidos y defiende tu territorio de arañas,
mantis y avispones. Puedes jugar sin conexión y sin anuncios.

Hormiguero es una reinterpretación de **La vida de las hormigas**: sus reglas,
combates y progresión son aproximaciones, no una reproducción exacta.

## Comenzar

Necesitas **Python 3** con **Tkinter**. Para usar las imágenes animadas necesitas
también [Pillow](https://python-pillow.org/); sin él, el juego utiliza gráficos
simples. En Linux, los efectos usan `paplay` y la música usa `ffplay`, si están
disponibles.

```bash
git clone git@github.com:prezdev88/hormiguero.git
cd hormiguero
python3 -m pip install Pillow
python3 juego.py
```

Si `pip` no te permite instalar paquetes en el Python del sistema, crea primero
un entorno virtual con `python3 -m venv .venv` y actívalo con
`source .venv/bin/activate`. Si falta Tkinter, instálalo con el gestor de
paquetes de tu distribución.

## Cómo jugar

1. Crea **obreras** desde el menú lateral. Saldrán a recolectar insectos y
   llevarán el alimento al nido.
2. Usa ese alimento para aumentar la colonia. Los **soldados** combaten y
   patrullan; las hormigas **universales** pueden recolectar y combatir.
3. Construye colonias adicionales para acercarte a nuevas zonas. Selecciona un
   nido propio antes de crear hormigas para que salgan de él; si no seleccionas
   ninguno, saldrán del primero.
4. Pulsa **Atacar nido** para enviar soldados y universales contra las colonias
   rivales. Al derrotar el nido principal aparece otro más resistente y recibes
   una recompensa de alimento.

También puedes colocar nidos enemigos gratis. Al seleccionar uno aparecen
controles para crear arañas, mantis y avispones; los nidos generan enemigos
automáticamente. Selecciona una hormiga para reembolsarla o una colonia propia
para destruirla desde el menú superior.

## Controles

| Acción | Control |
| --- | --- |
| Mover el mapa | Arrastrar el terreno o usar las flechas |
| Acercar o alejar | Rueda del mouse sobre el terreno |
| Navegar por el mapa | Clic o arrastre en el minimapa |
| Ver información | Clic en una hormiga, insecto o nido |
| Crear diez unidades | Shift + clic en un botón de creación |
| Cambiar velocidad | `1`, `2` o `3` |
| Cancelar construcción | `Escape` |

Para crear diez hormigas necesitas alimento suficiente para todo el grupo. El
mapa es más grande que la ventana, pero tiene límites.

## Partidas y ajustes

La partida se guarda automáticamente cada 30 segundos y al cerrar la ventana.
También puedes usar **Guardar como** y **Cargar** para administrar archivos de
partida manualmente. Las preferencias de música y efectos se recuerdan entre
sesiones.

Por defecto, los archivos están en `~/.local/share/vida-hormigas-local/`:

- `partida.json`: partida automática.
- `ajustes.json`: preferencias de audio.

Si tienes definida la variable `XDG_DATA_HOME`, se usa su carpeta
`vida-hormigas-local` en lugar de `~/.local/share/vida-hormigas-local`.

Al principio de `juego.py` hay tres opciones que puedes cambiar a `True` o
`False`. Reinicia el juego después de modificarlas:

```python
ANTS_SPREAD_OUT = True    # Las hormigas intentan mantener distancia.
SHOW_HEALTH_BARS = False  # Barras de vida sobre las entidades.
SHOW_FOOD_BARS = False    # Barras y cantidades sobre el alimento.
```

## Sobre los recursos

Las imágenes y los sonidos incluidos proceden del APK de *La vida de las
hormigas*. La simulación en Python es una reinterpretación independiente y no
incluye anuncios ni servicios en línea.
