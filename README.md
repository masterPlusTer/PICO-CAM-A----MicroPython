# PICO-CAM-A----MicroPython

PICO-Cam-A con MicroPython 📷
Una cámara monocromática con vista en vivo, hecha en MicroPython sobre la PICO-Cam-A de WaveShare (RP2040 + HM01B0 + ST7789).
Este proyecto nació de una pregunta bastante sencilla: ¿podemos controlar directamente la cámara y la pantalla desde MicroPython, sin depender de un programa completo escrito en C? La respuesta es sí. Conseguimos inicializar el sensor, capturar imágenes usando PIO y DMA, mostrarlas en la pantalla y ejecutar una vista en vivo. No es una cámara de cine, pero para aprender cómo funciona el hardware es mucho más interesante. 😄
Estado: fotografía y vista en vivo confirmadas en hardware. Existe una versión optimizada (FAST-2, con Viper) preparada para mejorar la velocidad del LCD, pero todavía no tenemos una medición de FPS verificada para esa versión.

¿Qué hace?
- Inicializa el sensor Himax HM01B0 por I²C y comprueba su identificación (0x01B0).
- Captura fotogramas de 324 × 324 píxeles, en escala de grises de 8 bits.
- Recibe los datos mediante PIO + DMA del RP2040, sin tener que leer cada píxel con un bucle de Python.
- Muestra imágenes en la pantalla ST7789 de 240 × 135 píxeles, a través de SPI.
- Ofrece fotografía individual, vista en vivo, barras de prueba del sensor y prueba de colores del LCD.
- Permite elegir entre tres encuadres: crop, fit y stretch.
- Permite invertir verticalmente la imagen y guardar el último cuadro en formato PGM.
- Funciona con el firmware MicroPython estándar para Raspberry Pi Pico, siempre que incluya rp2.DMA. No requiere compilar un MicroPython propio.
Hardware y conexiones
Hardware utilizado en las pruebas:
Componente	Descripción
Placa	WaveShare PICO-Cam-A, basada en RP2040 (tambien comercializada por SpotPear)
Sensor	Himax HM01B0 monocromático
Pantalla	ST7789, 240 × 135, RGB565
Procesador	RP2040 (dos núcleos Cortex-M0+)
Firmware probado	MicroPython v1.29.0, compilación del 24-08-2026
Frecuencia usada para captura	250 MHz (overclock experimental)


Pines utilizados por este proyecto
Función	GPIO RP2040
Cámara I²C SDA	GP4
Cámara I²C SCL	GP5
Cámara DATA (entrada PIO)	GP6
Cámara PCLK	GP14
Cámara HREF	GP15
Cámara VSYNC	GP16
LCD RESET	GP7
LCD DC	GP9
LCD SPI SCK	GP10
LCD SPI MOSI	GP11
LCD CS	GP13


Importante: este mapa corresponde a la configuración que funcionó en nuestra PICO-Cam-A. Revisá el esquema de tu propia revisión de placa antes de adaptarlo a otro modelo. No conectamos cables externos para estas señales: forman parte de la placa.
Para empezar (paso a paso)
1. Instalar MicroPython
Usá el firmware estándar de Raspberry Pi Pico (RP2040). En nuestras pruebas funcionó MicroPython v1.29.0 y, específicamente, su API rp2.DMA.
En Thonny, elegí el intérprete MicroPython (Raspberry Pi Pico) y comprobá:
import rp2
print(hasattr(rp2, "DMA"))
El resultado debe ser True. Si aparece False, ese firmware no tiene la API DMA que usa nuestro controlador.
No hace falta modificar las particiones ni compilar un firmware especial para hacer funcionar la cámara.
2. Copiar los archivos
La versión básica y la versión rápida comparten el mismo controlador de cámara:
/
├── demo_camera.py         # Aplicación que ejecutamos
└── lib/
    ├── picocam.py         # Cámara HM01B0, PIO, DMA y LCD básico
    └── picocam_fast.py    # Renderizado acelerado con Viper (FAST-2)
En Thonny, abrí cada archivo y elegí File → Save as → MicroPython device. Creá la carpeta /lib si todavía no existe.
Si estás usando la versión LIVE-AUTO-1 de demo_camera.py, solo necesitás picocam.py. La versión FAST-2 utiliza además picocam_fast.py.

3. Ejecutar
Abrí demo_camera.py desde Thonny y presioná Run. La aplicación de vista en vivo comienza automáticamente: no hay que introducir v para que empiece a capturar.
Al iniciar, deberías ver mensajes parecidos a estos:
Sensor: 0x01B0
Register 0x3010: 0x00
Register 0x3059: 0x22
Register 0x3060: 0x30
DMA channel: 0
Camera ready
LCD initialized: 240x135
Si estás ejecutando el programa automático, después aparece VIDEO ACTIVO o VIDEO AUTOMATICO ACTIVO según la versión.
4. Pausar y usar el menú
Mientras corre la vista en vivo, presioná Ctrl+C en la consola de Thonny. Aparecerá el menú. Enter reanuda la vista en vivo; q sale y restaura la frecuencia original de la CPU.
Comando	Acción
Enter o v	Reanudar vista en vivo
f	Tomar una fotografía
s	Guardar el último cuadro como captura_000.pgm, etc.
crop	Llenar la pantalla recortando la imagen sin deformarla
fit	Mostrar el cuadro cuadrado completo, con bandas laterales
stretch	Llenar la pantalla estirando la imagen (se deforma)
flip	Invertir la imagen verticalmente
b	Mostrar el patrón de prueba del sensor
lcdtest	Mostrar colores sólidos para comprobar el LCD
info o gc	Consultar memoria/información del sistema
q	Salir


En FAST-2 también existe espera N (de 0 a 200 ms), para añadir una pausa entre el inicio del sensor y la captura de cada cuadro. El valor inicial es 0.
5. Abrir las fotos
Las fotografías se guardan en el sistema de archivos de la placa como PGM (P5), con resolución 324 × 324 y 8 bits por píxel. Podés descargarlas desde Thonny. Programas como GIMP e ImageMagick pueden abrir o convertir PGM.
Guardar un PGM no equivale a grabar un vídeo. Por ahora, la vista en vivo aparece en la pantalla del dispositivo; no generamos archivos AVI, MP4 ni GIF.
¿Por qué se ve en blanco y negro?
Porque el sensor HM01B0 de esta placa es monocromático. La pantalla ST7789 sí puede mostrar colores, pero cada píxel capturado por el sensor representa únicamente un nivel de luminosidad entre 0 y 255.
La conversión actual produce píxeles RGB565 grises para la pantalla. Podemos añadir filtros de color artificial (sepia, verde, azul o pseudocolor), pero no recuperar colores reales que el sensor no registró. Un filtro que imite una cámara térmica tampoco medirá temperatura.
Cómo funciona (sin ponerse demasiado académico)
        Cámara HM01B0
         324 x 324
             |
     DATA / PCLK / HREF / VSYNC
             |
           PIO (RP2040)
             |
      DMA a memoria RAM
             |
    Fotograma de 104.976 bytes
             |
   Conversión gris → RGB565
             |
          SPI1 → ST7789
             |
        LCD 240 x 135
1. I²C sirve para configurar el sensor y activar la captura. La dirección utilizada es 0x24.
2. PIO (Programmable I/O) espera las señales del sensor y recibe los bits de cada píxel.
3. DMA (Direct Memory Access) mueve los bytes recibidos a un bytearray sin que Python tenga que copiar uno por uno.
4. MicroPython decide qué parte de la imagen mostrar y convierte el gris a RGB565.
5. SPI transmite los datos convertidos a la pantalla.
Una imagen de 324 × 324 × 1 byte ocupa 104.976 bytes de RAM. El código básico también utiliza un buffer temporal de una fila de pantalla. La versión FAST-2 prepara franjas de nueve filas y utiliza @micropython.viper, una característica del propio MicroPython, para acelerar la conversión. No introduce una dependencia externa.
Los tres modos de pantalla
- crop (predeterminado): utiliza una región central de 320 × 180 para llenar los 240 × 135 píxeles de la pantalla. Respeta la proporción, pero descarta parte de la imagen original.
- fit: reduce los 324 × 324 píxeles a 135 × 135; quedan bandas negras laterales.
- stretch: escala el cuadro cuadrado a 240 × 135. Ocupa toda la pantalla, pero modifica las proporciones.
Resultados que obtuvimos realmente
Estos resultados proceden de las ejecuciones observadas en nuestra placa, no de una estimación ni de una prueba de la versión nueva.
Detección e inicialización
Sensor: 0x01B0
Register 0x3010: 0x00
Register 0x3059: 0x22
Register 0x3060: 0x30
DMA channel: 0
Camera ready
LCD initialized: 240x135
Fotografía individual
Captured 104976 bytes in 49 ms
La captura de una foto individual funcionó y la pantalla mostró la imagen.
Capturas consecutivas
Realizamos 15 capturas sucesivas con firmas calculadas a partir de muestras del buffer:
- Todas terminaron sin timeout ni error de DMA.
- Las 15 firmas fueron distintas, lo que indica que el buffer recibió datos diferentes. Por sí solo, esto no prueba movimiento en la escena, porque también puede existir ruido.
- La primera captura tardó 103 ms, y las siguientes 62 ms cada una, con settle_ms=100 en la prueba original reportada. Estos fueron los tiempos informados por elapsed_ms en esa ejecución, no el tiempo total transcurrido entre fotogramas.
Primera vista en vivo confirmada: LIVE-AUTO-1
El programa quedó funcionando continuamente, mostró movimiento entre fotografías y permitió pausarlo con Ctrl+C. Sus mediciones fueron aproximadamente:
Medida	Resultado observado
Velocidad	1,49–1,54 FPS
Adquisición reportada por cuadro	163–165 ms
Conversión + visualización en LCD	486–507 ms


El principal cuello de botella fue dibujar en el LCD desde bucles Python, no el DMA. En esa versión la adquisición incluía una espera intencional de 100 ms por cuadro.
Optimización preparada: FAST-2
Desarrollamos una variante con estas diferencias:
- Elimina los 100 ms de espera por cuadro (configurable desde el menú).
- Sustituye la conversión RGB565 píxel a píxel en Python normal por una función Viper.
- Precalcula las coordenadas del escalado cuando cambiamos el modo de visualización.
- Envía franjas de nueve filas dentro de una escritura continua al LCD.
- Conserva el controlador de cámara existente, los tres encuadres y el guardado PGM.
Pendiente de medir en la placa: el FPS efectivo y la compatibilidad final de la función Viper. No declaramos que ya alcance 10, 15 ni 20 FPS; publicaremos una cifra cuando exista una medición real.
¿Y los 16 MB de flash?
La PICO-Cam-A dispone de flash externa en la placa, pero el firmware genérico puede exponer solo una parte para el sistema de archivos. En nuestra instalación se observó un sistema de archivos de 1.441.792 bytes (~1,38 MiB).
Eso no significa que el sensor o el LCD estén limitados a 2 MB, ni que el resto de la memoria flash se convierta en RAM. Son dos recursos distintos:
- Flash: guarda firmware, programas y fotografías.
- RAM: contiene los fotogramas y buffers mientras el programa se ejecuta.
No hace falta compilar MicroPython ni cambiar la partición flash para ejecutar este proyecto. De momento preferimos mantener el firmware estándar y concentrarnos en el rendimiento de la vista en vivo. El aprovechamiento completo de la flash queda como mejora futura y deberá hacerse con copias de seguridad.
Para consultar el almacenamiento disponible desde Thonny:
import os

fs = os.statvfs("/")
block = fs[1] or fs[0]

print("Total MiB:", fs[2] * block / 1048576)
print("Libres MiB:", fs[4] * block / 1048576)
Problemas frecuentes
Veo CAM> y la imagen no se mueve.
Estás usando una versión del programa que espera comandos. Escribí v, o mejor utilizá el demo_camera.py automático (LIVE-AUTO-1 o FAST-2). Si el terminal espera dentro de input(), no se está actualizando la pantalla.
La pantalla se actualiza, pero muy lentamente.
Comprobá qué versión aparece al arrancar. LIVE-AUTO-1 dio aproximadamente 1,53 FPS. FAST-2 intenta acelerar el procesamiento, pero requiere una medición real en tu hardware.
Aparece ImportError: no module named 'picocam'.
Asegurate de que el archivo se llame exactamente picocam.py y esté dentro de /lib en el dispositivo, no solamente abierto en la computadora.
Aparece un error relacionado con rp2.DMA.
Comprobá hasattr(rp2, "DMA"). Necesitás una versión de MicroPython para RP2040 que incluya esa API.
Aparece un error de DMA o un timeout.
Probá el programa con la configuración original de 250 MHz, reiniciá la placa y verificá que no haya otro script usando PIO/DMA. El overclock no está garantizado en todas las placas.
La imagen parece estirada o recortada.
Usá fit para mostrar el campo completo o crop para llenar el LCD sin deformaciones.
No puedo abrir un archivo .pgm.
Descargalo desde Thonny y abrilo con un programa compatible, como GIMP o ImageMagick. Es un formato de imagen sencillo, no un vídeo.
No aparecen colores reales.
Es normal: el HM01B0 utilizado es monocromático. Los filtros de color artificial son una posible ampliación.
Próximos pasos
- [x] Detectar y configurar el HM01B0 por I²C.
- [x] Recibir cuadros mediante PIO + DMA.
- [x] Mostrar fotografías en el ST7789.
- [x] Implementar crop, fit, stretch y flip.
- [x] Guardar fotografías en PGM.
- [x] Implementar la vista en vivo automática.
- [x] Medir el cuello de botella de la versión básica (~1,5 FPS).
- [x] Preparar una variante con renderizado Viper (FAST-2).
- [ ] Validar y publicar los FPS reales de FAST-2.
- [ ] Añadir filtros de pseudocolor (sepia, verde, azul, etc.).
- [ ] Investigar grabación de vídeo en almacenamiento externo.
- [ ] Explorar otras funciones del sensor y del RP2040.
- [ ] Evaluar un firmware con sistema de archivos ampliado, más adelante.
Referencias y agradecimientos
- PICO-CAM-A, proyecto de referencia en C con PIO/DMA: https://github.com/fhswf/PICO-CAM-A. Su código fue un punto de partida fundamental para comprender la secuencia de captura que funciona en la placa.
- Documentación de MicroPython para RP2.
- Optimización de velocidad en MicroPython, incluidas funciones nativas y Viper.
- Especificaciones oficiales del RP2040.
Este repositorio es un experimento de aprendizaje y no una implementación oficial del fabricante. Los ejemplos y resultados corresponden a la placa y al firmware indicados arriba. Cuando una mejora todavía está pendiente de prueba, lo indicamos expresamente.
La idea: poder abrir el código, entender qué hace cada parte y modificarlo sin tener que empezar escribiendo drivers enteros en C. Si recién estás descubriendo I²C, SPI, PIO y DMA, este proyecto es una buena excusa para meterse en todo eso de una vez. 📷
