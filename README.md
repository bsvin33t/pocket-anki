# Pocket Anki: flashcards on an ESP32-S3 device

This project turns a SpotPear ESP32-S3 1.54" "muma" board into a handheld flashcard device for Anki. The device shows your due cards on its screen, and you grade each card with one button. It gets the cards from the Anki desktop app on your laptop over Wi-Fi. When the laptop is not reachable, the device shows cards from an offline cache and sends your grades at the next sync.

[![Demo of the device](demo.gif)](demo.mp4)

Click the animation to open the full-quality video.

## Requirements

- A SpotPear ESP32-S3 1.54" "muma" board: 240x240 ST7789 screen, ES8311 audio chip, and battery. The version without a touch screen is enough.
- CircuitPython 10.3.1 for the board `espressif_esp32s3_devkitc_1_n8r8`, in the German (`de_DE`) build. Its built-in font has the letters ä, ö, ü, and ß. The English build does not.
- The Anki desktop app on a laptop that is on the same Wi-Fi network as the device. The device supports only 2.4 GHz Wi-Fi.
- The AnkiConnect add-on in that Anki instance. The next section tells you how to add it.

## Set up AnkiConnect on the laptop

[AnkiConnect](https://git.sr.ht/~foosoft/anki-connect) is an Anki add-on that lets other programs read and grade cards over HTTP. The device uses it for all communication with Anki. Without AnkiConnect, the device works only from its offline cache.

1. In Anki, choose Tools, then Add-ons, then Get Add-ons.
2. Enter the code `2055492159`, and then click OK.
3. Restart Anki.
4. Choose Tools, then Add-ons, select AnkiConnect, and then click `Config`.
5. Replace all of the text with these settings, and then click OK:

   ```json
   {
       "apiKey": null,
       "apiLogPath": null,
       "webBindAddress": "0.0.0.0",
       "webBindPort": 8766,
       "webCorsOriginList": ["http://localhost"],
       "ignoreOriginList": []
   }
   ```

6. Quit Anki with Cmd+Q, and then open it again.
7. If macOS asks whether Anki can accept incoming connections, click Allow.

With the default settings, AnkiConnect listens only on `127.0.0.1`, so the device cannot reach it. The value `0.0.0.0` makes AnkiConnect listen on all network interfaces. Port 8766 replaces the default port 8765, which another program uses on the original laptop. You can use a different free port, but `ANKI_PORT` in `settings.toml` must have the same value.

With `"apiKey": null`, any device on your network can read and change your Anki collection while Anki is open. To limit access, set `apiKey` to a random string, and put the same string in `ANKI_KEY` in `settings.toml`.

To make sure that AnkiConnect works, run this command on the laptop. The output must be `{"result": 6, "error": null}`.

```sh
curl -s http://localhost:8766 -d '{"action": "version", "version": 6}'
```

## Install the program on the device

1. Download the CircuitPython image `adafruit-circuitpython-espressif_esp32s3_devkitc_1_n8r8-de_DE-10.3.1.bin` from [circuitpython.org](https://circuitpython.org/board/espressif_esp32s3_devkitc_1_n8r8/).
2. Connect the device to the laptop with a USB data cable.
3. Write the image with `esptool`. Replace `PORT` with the serial port of the device, for example `/dev/cu.usbmodem1101`.

   ```sh
   esptool --port PORT erase-flash
   esptool --port PORT write-flash 0x0 adafruit-circuitpython-espressif_esp32s3_devkitc_1_n8r8-de_DE-10.3.1.bin
   ```

4. Restart the device. A drive with the name `CIRCUITPY` appears on the laptop.
5. Copy `.env.example` to `.env` in this folder, and enter your Wi-Fi name and password:

   ```sh
   WIFI_SSID="YourNetwork"
   WIFI_PASSWORD="YourPassword"
   ```

6. Edit `settings.toml` in this folder. Set `ANKI_HOST` to the IP address of the laptop, and set `ANKI_DECK` to your decks.
7. Copy these files to the `CIRCUITPY` drive: `code.py`, `hw.py`, `anki.py`, `button.py`, `text.py`, `settings.toml`, and `.env`.

If `esptool` cannot connect while CircuitPython runs, send the 1200-baud signal. CircuitPython then restarts in download mode:

```sh
python3 -c "import serial; serial.Serial('PORT', 1200).close()"
```

Do not use the names `CIRCUITPY_WIFI_SSID` and `CIRCUITPY_WIFI_PASSWORD` for the Wi-Fi values. With those names, CircuitPython connects to Wi-Fi before the program starts. If you release the power button during that time, the device turns off again.

`.gitignore` excludes `.env`, so your Wi-Fi password stays out of git.

## Settings

| Name | File | Meaning |
|---|---|---|
| `WIFI_SSID` | `.env` | Name of the Wi-Fi network |
| `WIFI_PASSWORD` | `.env` | Password of the Wi-Fi network |
| `ANKI_HOST` | `settings.toml` | IP address of the laptop that runs Anki |
| `ANKI_PORT` | `settings.toml` | AnkiConnect port. If it is not set, the program uses 8766. |
| `ANKI_KEY` | `settings.toml` | AnkiConnect API key. If `apiKey` is `null`, leave it empty. |
| `ANKI_DECK` | `settings.toml` | Deck names, with commas between them. If it is empty, the program uses the current deck in Anki. |

## Use the device

The device has two buttons, one on each side of the USB port. One is BOOT, and the other is the power button.

| Action | What happens |
|---|---|
| Hold the power button for about 2 seconds | The device turns on, plays a C-E-G chime, and syncs with Anki. |
| Tap BOOT on the front of a card | The device shows the answer. |
| Tap BOOT on the answer | The device grades the card as Good and shows the next card. |
| Hold BOOT for 2 seconds on the answer | The device grades the card as Again and shows the next card at once. |
| Hold BOOT for 6 seconds | The device saves your progress and turns off. |

During a sync, the device sends the saved grades to Anki. Then it saves as many cards as fit in its 8 KB cache, about 180. Due reviews come first in mixed order, and new cards come after them. The device syncs at startup and after the last saved card.

If Anki is not reachable, the footer shows "offline" instead of "left". You can study the saved cards, and the device sends your grades at the next sync.

## Files

| File | Contents |
|---|---|
| `code.py` | The study loop. CircuitPython starts this file. |
| `hw.py` | Board hardware: power latch, screen, chime, and BOOT button pin |
| `anki.py` | AnkiConnect client, offline cache, and sync |
| `button.py` | Button gestures: tap, 2-second hold, and 6-second hold |
| `text.py` | Text helpers: HTML cleanup, line wrapping, font fallback, and the `.env` parser |
| `settings.toml` | Anki settings |
| `.env` | Wi-Fi settings. Git ignores this file. |
| `test_*.py` | Tests that you run on the laptop |

The board has a power latch on pin IO3. The power button supplies power only while you hold it. `hw.py` sets IO3 high in its first lines to keep the board on. `code.py` imports `hw.py` first for that reason.

## Run the tests

Run the tests on the laptop with Python 3. They do not need the device.

```sh
python3 test_text.py
python3 test_press.py
python3 test_anki.py
```

Each test prints `ok`. `test_anki.py` replaces the CircuitPython modules with fakes, so it also runs without the board.

## Known limits

- The device shows at most 8 lines of text per side. It cuts longer text.
- Images and audio on cards do not show or play.
- The program does not apply the Anki daily limit for new cards.
- Anki records an offline grade with the time of the sync, not the time of the review.
- When you copy files to the device, CircuitPython restarts the program and releases IO3. The device then turns off once, and you must turn it on again.

## Troubleshooting

| Message on the screen | Cause and fix |
|---|---|
| `Anki on <host>:<port>: HTTP/1.0 501 ...` | Another program uses that port. Set `ANKI_PORT` to the AnkiConnect port. |
| `Offline, no saved cards.` | The device cannot reach Anki, and its cache is empty. Make sure that Anki is open on the laptop and that the device is on the same Wi-Fi network. |
| `No cards due.` | The decks in `ANKI_DECK` have no due or new cards. |

## License

This project uses the MIT License. See [LICENSE](LICENSE).
