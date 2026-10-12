"""
Presentacion rapida para el picocam.py que ya funciona.

No cambia la inicializacion de la HM01B0, el PIO ni el DMA.
Usa Viper y un buffer de nueve filas.
No necesita bibliotecas externas.
"""

import micropython
from array import array

from picocam import CameraLCD, FRAME_BYTES


@micropython.viper
def _convert_stripe(source, target, mapping, colors):
    """
    Convertir una franja de gris a RGB565.

    Esta funcion usa punteros nativos.
    Los limites se preparan y validan antes de llamarla.
    """
    src = ptr8(source)
    dst = ptr8(target)
    m = ptr32(mapping)
    lut = ptr8(colors)

    width = int(m[0])
    first_y = int(m[1])
    rows = int(m[2])

    out = 0
    y = 0

    # m[3:243]: coordenadas X de origen.
    # m[243:378]: desplazamientos de las filas de origen.
    while y < rows:
        base = int(m[243 + first_y + y])
        x = 0

        while x < width:
            color = int(
                src[base + int(m[3 + x])]
            ) << 1

            dst[out] = lut[color]
            dst[out + 1] = lut[color + 1]

            out += 2
            x += 1

        y += 1


class FastLCD(CameraLCD):
    """
    Sustituye solamente la presentacion del cuadro.

    Conserva:
        init()
        show(frame, flip_y=True, mode="crop")
        test_screen()
        close()
    """

    def __init__(self):
        super().__init__()

        # Nueve filas RGB565: 240 x 9 x 2 = 4320 bytes.
        self._stripe = bytearray(240 * 9 * 2)
        self._stripe_memory = memoryview(self._stripe)
        self._stripe_view = None

        # Tres parametros, 240 columnas y 135 filas.
        self._mapping = array("I", [0] * 378)

        self._key = None
        self._dst_x = 0
        self._dst_width = 240

    def _prepare(self, mode, flip_y):
        if mode == "crop":
            sx, sy, sw, sh = 2, 72, 320, 180
            dx, dw = 0, 240

        elif mode == "fit":
            sx, sy, sw, sh = 0, 0, 324, 324
            dx, dw = 52, 135

        elif mode == "stretch":
            sx, sy, sw, sh = 0, 0, 324, 324
            dx, dw = 0, 240

        else:
            raise ValueError(
                "Usa crop, fit o stretch"
            )

        m = self._mapping

        m[0] = dw
        m[2] = 9

        # Estas divisiones se hacen al cambiar el encuadre,
        # no por cada pixel de cada fotograma.
        for x in range(dw):
            m[3 + x] = sx + x * sw // dw

        for y in range(135):
            relative_y = y * sh // 135

            if flip_y:
                source_y = sy + sh - 1 - relative_y
            else:
                source_y = sy + relative_y

            m[243 + y] = source_y * 324

        self._dst_x = dx
        self._dst_width = dw

        self._stripe_view = self._stripe_memory[
            :dw * 9 * 2
        ]

        # Eliminar restos al cambiar entre crop y fit.
        self.clear()

        self._key = (mode, bool(flip_y))

    def show(self, frame, flip_y=True, mode="crop"):
        # Viper no comprueba limites automaticamente.
        # Por eso restringimos el formato antes de entrar.
        if (
            not isinstance(frame, (bytes, bytearray))
            or len(frame) != FRAME_BYTES
        ):
            raise ValueError(
                "Se esperaba un buffer de 324x324 bytes"
            )

        if FRAME_BYTES != 324 * 324:
            raise ValueError(
                "Esta version requiere geometria 324x324"
            )

        if self._key != (mode, bool(flip_y)):
            self._prepare(mode, flip_y)

        # Una ventana de escritura para todo el cuadro.
        self.window(
            self._dst_x,
            0,
            self._dst_x + self._dst_width - 1,
            134
        )

        self.command(0x2C)

        self.cs(0)
        self.dc(1)

        try:
            # 15 franjas de 9 filas = 135 filas.
            for y in range(0, 135, 9):
                self._mapping[1] = y

                _convert_stripe(
                    frame,
                    self._stripe,
                    self._mapping,
                    self.gray
                )

                self.spi.write(self._stripe_view)

        finally:
            self.cs(1)
