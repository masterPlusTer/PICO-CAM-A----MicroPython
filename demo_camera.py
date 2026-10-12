"""
PICO-Cam-A FAST-2:
vista continua y mediciones de captura y dibujo.

Requiere:
    /lib/picocam.py
    /lib/picocam_fast.py

No formatea ni modifica la distribucion de flash.
"""

import machine
import time
import gc
import os
import sys
import rp2

from picocam import PicoCam
from picocam_fast import FastLCD


VERSION = "FAST-2"
CPU_HZ = 250_000_000


def memory_info():
    gc.collect()

    print(
        "RAM libre:",
        gc.mem_free(),
        "bytes"
    )

    fs = os.statvfs("/")
    unit = fs[1] or fs[0]

    print(
        "Filesystem total: %.3f MiB"
        % (fs[2] * unit / 1048576)
    )

    print(
        "Filesystem disponible: %.3f MiB"
        % (fs[4] * unit / 1048576)
    )

    flash = rp2.Flash()

    size = (
        flash.ioctl(4, 0)
        * flash.ioctl(5, 0)
    )

    print(
        "Region de almacenamiento configurada: %.3f MiB"
        % (size / 1048576)
    )

    print(
        "Lo anterior NO mide la capacidad fisica del chip."
    )


def show_help():
    print()
    print("MENU EN PAUSA")
    print("ENTER / v        Reanudar video")
    print("f                Nueva foto")
    print("s                Guardar ultima captura PGM")
    print("crop/fit/stretch Cambiar encuadre")
    print("flip             Invertir verticalmente")
    print("b                Barras del sensor")
    print("lcdtest          Prueba de colores del LCD")
    print("espera 0..200    Espera por cuadro en ms")
    print("info / gc        Memoria y almacenamiento")
    print("q                Salir")
    print()
    print("La espera inicial por cuadro es 0 ms.")
    print("Ctrl+C durante el video vuelve a este menu.")
    print()


def paused_menu(cam, lcd, mode, flip_y, delay):
    cam.stop()
    show_help()

    while True:
        command = input(
            "PAUSA> "
        ).strip().lower()

        if command in ("q", "quit"):
            return None

        if command in ("", "v"):
            return mode, flip_y, delay

        try:
            redraw = False

            if command in ("f", "b"):
                cam.test_pattern(command == "b")
                cam.capture(settle_ms=500)
                redraw = True

            elif command == "s":
                if cam.valid:
                    print(
                        "Guardado:",
                        cam.save()
                    )
                else:
                    print(
                        "La ultima captura se interrumpio."
                    )
                    print("Usa f primero.")

            elif command in (
                "crop", "fit", "stretch"
            ):
                mode = command
                redraw = True

            elif command == "flip":
                flip_y = not flip_y
                redraw = True

            elif command == "lcdtest":
                lcd.test_screen()
                redraw = True

            elif command in ("info", "gc"):
                print(
                    "CPU:",
                    machine.freq(),
                    "Hz"
                )

                print(
                    "Encuadre:", mode,
                    "| Espera:", delay, "ms"
                )

                memory_info()

            elif command.startswith("espera "):
                new_delay = int(
                    command.split()[1]
                )

                if not 0 <= new_delay <= 200:
                    raise ValueError(
                        "La espera debe ser 0..200 ms"
                    )

                delay = new_delay

                print(
                    "Espera por cuadro:",
                    delay,
                    "ms"
                )

            elif command in ("help", "h", "?"):
                show_help()

            else:
                print(
                    "Comando desconocido; usa help"
                )

            if redraw and cam.valid:
                lcd.show(
                    cam.frame,
                    flip_y=flip_y,
                    mode=mode
                )

        except Exception as exc:
            sys.print_exception(exc)


def live(cam, lcd, mode, flip_y, delay):
    cam.test_pattern(False)

    print()
    print("VIDEO ACTIVO -", VERSION)
    print(
        "Ctrl+C pausa. "
        "No se guardan fotogramas automaticamente."
    )

    # Esperar al comenzar, no en cada fotograma.
    frame = cam.capture(settle_ms=800)

    lcd.show(
        frame,
        flip_y=flip_y,
        mode=mode
    )

    print(
        "Primer cuadro mostrado; comienza la medicion."
    )

    count = 0
    total_capture = 0
    total_lcd = 0

    interval_start = time.ticks_ms()

    while True:
        t0 = time.ticks_ms()

        frame = cam.capture(
            settle_ms=delay
        )

        t1 = time.ticks_ms()

        lcd.show(
            frame,
            flip_y=flip_y,
            mode=mode
        )

        t2 = time.ticks_ms()

        count += 1

        total_capture += time.ticks_diff(
            t1, t0
        )

        total_lcd += time.ticks_diff(
            t2, t1
        )

        elapsed = time.ticks_diff(
            t2, interval_start
        )

        if elapsed >= 2000:
            print(
                "EN VIVO | %.2f FPS | "
                "captura %.1f ms | LCD %.1f ms"
                % (
                    count * 1000 / elapsed,
                    total_capture / count,
                    total_lcd / count
                )
            )

            count = 0
            total_capture = 0
            total_lcd = 0

            interval_start = time.ticks_ms()


def main():
    old_hz = machine.freq()

    cam = None
    lcd = None

    mode = "crop"
    flip_y = True
    delay = 0

    try:
        print()
        print("PICO-Cam-A /", VERSION)

        print(
            "AVISO: mantiene el overclock "
            "experimental de 250 MHz."
        )

        machine.freq(CPU_HZ)
        gc.collect()

        cam = PicoCam()
        cam.init()

        lcd = FastLCD()
        lcd.init()

        memory_info()

        while True:
            try:
                live(
                    cam,
                    lcd,
                    mode,
                    flip_y,
                    delay
                )

            except KeyboardInterrupt:
                print()
                print("Video pausado.")

                result = paused_menu(
                    cam,
                    lcd,
                    mode,
                    flip_y,
                    delay
                )

                if result is None:
                    break

                mode, flip_y, delay = result

    except (KeyboardInterrupt, EOFError):
        print()
        print("Saliendo.")

    except Exception as exc:
        sys.print_exception(exc)

    finally:
        try:
            if cam is not None:
                cam.close()

        finally:
            try:
                if lcd is not None:
                    lcd.close()

            finally:
                machine.freq(old_hz)

                print(
                    "CPU restaurada:",
                    machine.freq(),
                    "Hz"
                )


if __name__ == "__main__":
    main()
