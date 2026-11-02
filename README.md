# Hormiguero

Ejecutar con Python 3 y Tkinter:

```sh
python3 juego.py
```

Crea obreras para recolectar alimento, soldados que patrullan y persiguen arañas y
universales para ambas tareas. Construye colonias adicionales con el botón y
un clic en el terreno. El progreso se guarda al cerrar y cada 30 segundos en
`~/.local/share/vida-hormigas-local/partida.json` (o bajo `XDG_DATA_HOME`).
Al construir una colonia se muestra una vista previa junto al cursor; pulsa
Escape para cancelar.
Mantén Shift al hacer clic en un botón de hormigas para crear diez de ese tipo;
necesitas alimento suficiente para el grupo completo.
Las hormigas se crean en el nido propio seleccionado, o en el primero si no
hay ningún nido propio seleccionado.
Para que las hormigas puedan agruparse otra vez, cambia `ANTS_SPREAD_OUT = True`
por `ANTS_SPREAD_OUT = False` al principio de `juego.py` y reinicia el juego.
El botón «Atacar nido» envía soldados y universales hacia el nido rival.
Usa «Crear nido enemigo» para colocar nidos gratis. Selecciona uno para crear
arañas, mantis o avispones gratis; Shift+clic crea diez.
Tras vencer, aparece otro nido rival más resistente y se recibe alimento.
El minimapa muestra nidos, hormigas, alimento y enemigos. Las hormigas avanzan
horizontal y verticalmente.
Arrastra el terreno o usa las flechas para mover la cámara. Haz clic en el
minimapa para ir a una zona; el rectángulo claro indica la vista actual. El mapa
es más grande que la pantalla, pero tiene límites.
También puedes mantener pulsado y arrastrar dentro del minimapa para navegar.
Usa la rueda del ratón sobre el terreno para acercar o alejar la vista.
Las barras verdes muestran la vida de las hormigas; las rojas, la vida de los
enemigos; y las amarillas, el alimento restante en cada fuente.
Haz clic en una entidad para consultar su información, actualizada en tiempo real.
Las barras de vida están ocultas por defecto. Cambia `SHOW_HEALTH_BARS = False`
a `True` al principio de `juego.py` para mostrarlas y reinicia el juego.
Las barras de alimento también están ocultas; usa `SHOW_FOOD_BARS = True`
para volver a mostrarlas.
Las teclas 1, 2 y 3 ajustan la velocidad de la simulación a 1x, 2x y 3x.
Los botones permiten guardar y cargar archivos, reembolsar una hormiga,
destruir una colonia seleccionada, activar efectos y activar música. Para el
audio se usan `paplay` y `ffplay`, si están disponibles. Los gráficos animados
de las hormigas usan Pillow si está instalado; sin él se dibujan figuras simples.
Las preferencias de sonido y música se guardan en `ajustes.json`, junto a la
partida automática, y se conservan al iniciar una nueva partida.
El alimento aparece cerca de las colonias; se generan más fuentes al aumentar
el número de obreras y hormigas universales.

Es una reinterpretación independiente a partir de textos del APK. La simulación,
los costes y el combate son aproximaciones. La progresión de
nidos es una interpretación y no reproduce el modo de batalla por niveles del
original. Las imágenes de hormigas y los sonidos incluidos proceden del APK.
