<p align="center">
  <img src="src/silemio_control_hub/assets/controller-studio.png" alt="Controller Studio for LiveProfessor" width="132">
</p>

<h1 align="center">Controller Studio for LiveProfessor</h1>

<p align="center">
  <strong>SiLeMI/O — By Mamat</strong><br>
  MIDI controllers, Plugin Studio and AutoMap in one Windows application.
</p>

<p align="center">
  <a href="https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/tag/v2026.4"><img alt="Version V.2026.4" src="https://img.shields.io/badge/version-V.2026.4-0b9fc6"></a>
  <img alt="Windows 10 and 11 x64" src="https://img.shields.io/badge/Windows-10%20%7C%2011%20x64-1674d1">
  <img alt="French and English" src="https://img.shields.io/badge/interface-FR%20%7C%20EN-445064">
</p>

## Latest version (quick access)

**Stable release: [Controller Studio V.2026.4](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/tag/v2026.4)**<br>
Direct downloads:

- [Controller Studio installer for Windows x64 (.exe)](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/download/v2026.4/Controller-Studio-for-LiveProfessor-Setup-v2026.4.exe)
- [Portable Windows x64 version (.exe)](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/download/v2026.4/Controller-Studio-for-LiveProfessor.exe)
- [Full English manual (.pdf)](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/download/v2026.4/Controller-Studio-for-LiveProfessor-Manual-EN.pdf)
- [Notice complète en français (.pdf)](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/download/v2026.4/Controller-Studio-for-LiveProfessor-Notice-FR.pdf)
- [SHA-256 checksums](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/download/v2026.4/SHA256SUMS.txt)

[Lire cette présentation en français](README.md)

> **Public V.2026.4 Windows release.** Controller Studio always works on a new AutoMap copy and keeps the source `.rack2` project untouched.

## What does Controller Studio do?

Controller Studio turns a MIDI controller into an organized control surface for LiveProfessor plug-ins. In one application, you can select or build a controller, create its LiveProfessor file, analyze project plug-ins and produce an AutoMap copy ready for testing.

| Live control | Controller bank | Plugin Studio | AutoMap |
|---|---|---|---|
| Real-time EC4 driver, banks, push, Shift, labels, values and reconnection | Ready-to-export profiles and a controller editor | Real names read from installed plug-ins, batch retrieval, priorities and individual checkboxes | Plug-in and instance selection, UniBank or FullBank, validated `.rack2` copy |

The interface is available in French and English, minimizes to the notification area and keeps the real-time log in a separate window.

## Three-step workflow

1. In **Controller bank**, select your hardware or create its profile, then export the `.ctrl2` file.
2. Add that controller to LiveProfessor and analyze your `.rack2` project with **Plugin Studio**.
3. Click the blue **AutoMap** button, choose the useful plug-ins and parameters, then open the new copy.

Controller Studio reloads the generated copy before presenting it. Existing manual assignments remain authoritative.

## Plugin Studio

A `.rack2` file stores parameter order and identifiers, but not always their human-readable labels. Plugin Studio retrieves that data directly from installed VST3 plug-ins, each in an isolated process. A result is accepted only when its parameter count exactly matches the LiveProfessor project.

After project analysis, **Retrieve all real names** processes every plug-in type in one operation, creates or updates local profiles, and automatically backs up previous versions.

For one plug-in:

1. open the plug-in profile and click **Automatically retrieve real names**;
2. use **Select all**, **Select none** or the individual checkboxes;
3. adjust the short label, kind, technical role or priority if needed, then save the local profile.

If an older format or a particular plug-in does not provide a directly compatible inventory, Controller Studio automatically offers LiveProfessor Companion/OSC feedback as a second method.

The link between each Controller Map slot and the internal parameter identifier is preserved, preventing a correct control from receiving another parameter’s label.

VST is a registered trademark of Steinberg Media Technologies GmbH. Third-party notices are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Built-in controller bank

V.2026.4 includes 33 declarative profiles ready to export and can build more directly in the application:

- Akai Professional LPD8 MK2, MIDImix, APC Mini MK2, MPK Mini MK3, MPK Mini IV, and MPK Mini Plus;
- Arturia MiniLab 3, KeyLab Essential MK3, and BeatStep;
- Faderfox EC4, PC4, UC4 and PC12;
- Behringer X-Touch, X-Touch Compact, X-Touch Mini, and X-Touch One;
- Korg nanoKONTROL2 (CC mode, factory knob and fader assignments);
- Novation Launch Control XL MK2/XL 3, Launchkey MK3/MK4, and Launchpad X/Mini MK3;
- PreSonus FaderPort V2, 8, and 16;
- Solid State Logic UF1 and UF8;
- DJ TechTools MIDI Fighter Twister;
- generic 16-control MIDI controller.

Hardware modes and manufacturer references are collected in the [controller profile documentation](docs/CONTROLLER_PROFILE_SOURCES.md). The bank can be updated from the application and then remains available offline.

## Build and share a controller

Click **Create a controller…** to start with eight encoders, then add, remove, or reorder absolute or relative encoders, faders, and buttons. Every control accepts CC, Note, NRPN, or Pitch Bend, its channel, and its number. **Learn movement** and **Learn push** capture messages directly from the chosen MIDI input. You can also **Edit / duplicate…** an existing model or **Import a profile…**.

**Save to my bank** validates the profile and makes it available offline. **Save + create .ctrl2** immediately produces the LiveProfessor file. Replacing a personal profile keeps a backup of the previous version. The Live page also provides **Configure / MIDI Learn…** for the active controller; the setup/group section shown with the EC4 remains hardware-specific.

The Live page **Settings** window restores EC4 Bridge’s advanced controls: Overlay update rate and duration, Companion and label refresh delays, LiveProfessor feedback timeout, and persistent display. These timings are available to every compatible controller; setup/group and SysEx tools remain EC4-only.

To submit a controller to the shared library:

1. create or select its profile in **Controller bank**;
2. click **Submit to the library…**;
3. Controller Studio validates the profile and automatically inserts all its content into the form;
4. GitHub opens to identify the author and request final confirmation;
5. add manufacturer documentation or hardware test results when possible, then submit.

That final confirmation deliberately stays with GitHub: Controller Studio never asks for or stores a password or access token.

The public library lives in this repository under [`library/`](library/). It contains declarative JSON profiles only—never downloaded executable code.

## Main features

- create, import, export and validate controller profiles;
- generate LiveProfessor Companion/OSC `.ctrl2` controllers;
- complete EC4 engine inherited from EC4 Bridge;
- remembered controller selection and MIDI/OSC reconnection;
- display labels and values, banks, push and shortcuts;
- read-only plug-in and Controller Map analysis;
- select all plug-ins, one instance or any precise subset;
- per-parameter selection and priority in Plugin Studio;
- UniBank and FullBank AutoMap in a new copy;
- preserve manual mappings and existing learned assignments;
- verified application and controller-library updates;
- FR/EN interface, notification-area mode and separate log window;
- built-in PDF manual and optional PayPal support.

## Documentation

- [Full English manual](src/silemio_control_hub/manuals/Controller-Studio-for-LiveProfessor-Manual-EN.pdf)
- [Notice complète en français](src/silemio_control_hub/manuals/Controller-Studio-for-LiveProfessor-Notice-FR.pdf)
- [README en français](README.md)
- [Controller profile sources](docs/CONTROLLER_PROFILE_SOURCES.md)
- [Release history](CHANGELOG.md)

The manual matching the interface language is also available from **Help > Open PDF manual**.

## Installation and updates

The installer places Controller Studio in the user’s Windows profile and creates Desktop and Start menu shortcuts. It can then be removed from Windows Apps.

**Help > Check for updates** queries the latest Release in this repository, verifies the download and starts the installer. The controller library is updated separately from the **Library** menu.

## Development and verification

```powershell
python -m pip install -e .
python -m pytest -q
python -m silemio_control_hub profiles
python -m silemio_control_hub validate-profile "path\profile.json"
python -m silemio_control_hub export-liveprofessor-controller faderfox.ec4 ".\Faderfox-EC4.ctrl2"
python -m silemio_control_hub library-update
```

## Support the project

Controller Studio is independently developed and maintained. Every feature remains available free of charge.

- [Support SiLeMI/O through PayPal](https://www.paypal.com/paypalme/MamatLeroy)
- the same link and QR code are available from the **Help** menu.

## Thanks

Thank you to everyone who tests controllers, documents MIDI layouts and expands the public library.

LiveProfessor, Faderfox, Behringer, Novation, DJ TechTools and all other cited names remain trademarks of their respective owners. Controller Studio is an independent tool and is not affiliated with those publishers or manufacturers.

---

**SiLeMI/O**<br>
**By Mamat**<br>
`-------[]--`
