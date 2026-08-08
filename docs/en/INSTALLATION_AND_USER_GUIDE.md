
# Installation and User Guide

🇫🇷 [Version française](../GUIDE_INSTALLATION_UTILISATION.md)

## Before you start

The bridge does not modify LiveProfessor projects. Even so, back up the project and your Controller Map presets before testing it in an important session.

Two operating modes are available:

- **Companion**: recommended; provides dynamic names and values and supports up to 99 Rotary controls. Requires LiveProfessor 2023.0.8 or later.
- **Generic**: fallback solution; parameter values can be controlled, but display names must come from a JSON profile.

Use an official LiveProfessor licence, trial period or test licence supplied by Audioström.

## Installing the bridge

1. Copy the release folder wherever you want.
2. Run `EC4-LiveProfessor-Bridge.exe`. No installer or administrator privileges are required.
3. Connect the Faderfox EC4.
4. In the application, click **Refresh MIDI ports** and select the input and output containing `Faderfox EC4`.
5. Configure the LiveProfessor controller described below before clicking **Start**.

The normal configuration file is stored at:

```text
%LOCALAPPDATA%\EC4LiveProfessorBridge\config.json
```

For portable operation, copy `config.example.json` next to the executable and rename it `config.json`.

## Recommended mode — Companion

### Requirements

- LiveProfessor 2023.0.8 or later;
- no other application listening on UDP port `8011`;
- an EC4 setup/group that can be reserved for LiveProfessor.

### Define the LiveProfessor controller

The exact labels may vary slightly between LiveProfessor versions.

#### Recommended method — load the supplied `.ctrl2` file

A newly created **Companion Controller** exposes only four Rotary controls by default:

```text
Rotary1
Rotary2
Rotary3
Rotary4
```

The bridge uses 16 Rotary controls per bank and can address up to 99 controls. The simplest method is therefore to load/import the `.ctrl2` file supplied with the project or release package.

After importing it, check that the controller contains at least:

```text
Rotary1 → Rotary16
```

Add or keep `Rotary17` through `Rotary99` when you want to use the additional banks.

#### Manual method

1. Open **Hardware Controllers** in LiveProfessor.
2. Add a **Companion Controller**.
3. Keep the four Rotary controls created by default.
4. Add at least `Rotary5` through `Rotary16`.
5. Optionally add `Rotary17` through `Rotary99`.
6. Save the completed controller for later reuse.

Use these network settings:

```text
Address: 127.0.0.1
LiveProfessor input port: 8010
Feedback address: 127.0.0.1
Feedback port: 8011
```

If the Companion Controller type is not available, the installed LiveProfessor version is too old. Do not attempt to work around this by injecting code or automating the screen.

### Create one Controller Map per plugin type

This replaces repeated MIDI Learn operations with one reusable definition inside LiveProfessor:

1. Load a test instance of the plugin outside an important production session.
2. Open **Controller Maps** and create a new map.
3. Use **Quick Assign** or the map editor to assign `Rotary1`, `Rotary2`, and so on to the required parameters.
4. Enable **Only If Selected** so the same physical encoders follow the currently selected instance.
5. Keep the control range normalized from 0 to 1 and leave feedback enabled.
6. Save the map with **Save Map Preset. For later use with same plugin-type**.
7. Use **Apply Map Preset** on other instances of the same plugin type. When available, apply or copy the map to all instances of that type.

A map belongs to a specific **plugin type**. Do not assume that a VST2 map can be reused unchanged with the VST3 edition of the same product.

For push buttons, the bridge’s **Learn encoders + push** operation identifies the MIDI Notes sent by the EC4 group. In LiveProfessor, then use `GenericButton1` through `GenericButton15`, already provided by `Ec4.ctrl2`, directly in the **Controller Maps** editor. Enable the **Toggle** transformation for an on/off function. Quick Assign may fail for buttons; if the required parameter is absent from the Controller Map list, the plugin probably does not expose it to LiveProfessor.

### Configure and start the bridge

Recommended bridge settings:

- Mode: `companion`;
- LiveProfessor address: `127.0.0.1`;
- LP port: `8010`;
- feedback port: `8011`;
- dedicated EC4 area: choose a setup/group reserved for LiveProfessor;
- SysEx display: enabled;
- persistent selected-plugin parameter display: enabled;
- profile: empty, unless fallback labels are required.

Click **Save**, then **Start**. The status should change from `Searching for Faderfox EC4` to `Connected`. After the EC4 SysEx response is received, the status also shows the active setup and group.

To use the page currently displayed on the EC4:

1. select the desired setup and group on the EC4;
2. click **Use current setup/group**.

The choice is saved immediately. Outside that target area, the bridge ignores parameter commands and sends no feedback, leaving the other EC4 pages available for other uses.

### Learn any EC4 setup/group

You do not have to reproduce the default fallback CC and Note numbers.

1. Keep the bridge running and stay on the chosen setup/group.
2. Click **Learn encoders + push**.
3. Turn encoders 1 through 16 slightly, in that order.
4. When the second phase starts, press encoder push buttons 1 through 16, in that order.
5. Wait for the **Mapping learned and saved** confirmation.

The mapping is stored for that setup/group pair and reused at the next launch.

The encoders must be configured on the EC4 as **absolute CC controls from 0 to 127**, and the push buttons as **MIDI Notes**. Shift+push gestures use separate SysEx messages and are not part of the learning sequence.

### Displaying the selected plugin parameters

When **Always display parameters of the selected plugin** is enabled, the EC4 shows a 16-cell grid for the active bank. Turning or pressing an encoder temporarily displays the full parameter name and value, then the grid returns automatically.

In Companion mode, labels come from LiveProfessor `ControllerNames` feedback. They therefore follow the controls in the Controller Map of the selected plugin. The bridge sends `/init` and `/refresh` at startup and repeats the request until at least one name is received.

Without an active LiveProfessor instance, a correctly configured Companion Controller and an applicable Controller Map, the labels remain generic (`P001`, `P002`, and so on). The bridge cannot invent internal plugin parameter names.

## Fallback mode — Generic OSC

Generic mode is a fallback option and may require adjustments depending on the LiveProfessor version. Begin with a test project and a single parameter.

1. Open **Hardware Controllers**.
2. Add a generic **OSC** controller.
3. Set its input to `127.0.0.1:8010` and feedback to `127.0.0.1:8011`.
4. Declare normalized floating-point controls using `/EC4/Rotary1` through `/EC4/Rotary99`. Start with 1 through 16 for a minimal test.
5. Enable feedback on the same addresses.
6. Map the controls to plugin parameters and save one map preset per plugin type.
7. Select `generic` in the bridge.
8. Optionally choose a name profile such as `profiles\exemple-plugin.json`.

Without a profile, the EC4 displays `P001`, `P002`, and so on. This generic OSC route does not provide the dynamic names available through the modern Companion Controller.

## Daily controls

| EC4 action | Result |
|---|---|
| Turn encoders 1–16 | Change the 16 parameters of the active bank |
| Shift+push encoders 1/2 | Previous / next parameter bank |
| Shift+push encoders 3/4 | Previous / next View Set |
| Shift+push encoder 5 | Show / hide the selected plugin |
| Shift+push encoder 6 | Previous chain |
| Shift+push encoders 7/8 | Previous / next plugin |
| Shift+push encoder 9 | Enable / disable processing on the selected plugin |
| Shift+push encoder 10 | Next chain |
| Shift+push encoders 11/12 | Previous / next plugin |
| Shift+push encoders 13/14 | Previous / next Cue |
| Shift+push encoders 15/16 | Previous / next global snapshot |
| Simple push on encoders 1–15 | Send `GenericButton1` through `GenericButton15` to Companion |
| Simple push on encoder 16 | Tap Tempo |
| Push an encoder | Temporarily display its name, value, bank and encoder number |
| **Test EC4 display** button | Display a diagnostic screen without touching the audio path |

## JSON profiles

A profile is only a fallback source for display labels. It does not replace a LiveProfessor Controller Map.

```json
{
  "plugin_label": "Test compressor",
  "manufacturer": "Manufacturer",
  "plugin_format": "VST3",
  "plugin_id": "class-id-if-known",
  "parameters": [
    {"name": "Threshold", "short": "Thrs", "unit": "dB", "stable_id": "id-1"},
    {"name": "Ratio", "short": "Rati", "stable_id": "id-2"}
  ]
}
```

The identifier fields are preserved for a possible future API, but they are not currently used for automatic plugin recognition because the studied LiveProfessor protocol does not transmit a stable plugin identity.

## Diagnostics and logging

- **Diagnostic** checks OSC/SysEx encoding locally and lists the available MIDI ports.
- Log file: `%LOCALAPPDATA%\EC4LiveProfessorBridge\bridge.log`.
- Up to four files are kept: the current log and three 2 MB rotations.
- If the EC4 is disconnected, the bridge closes the missing ports and attempts to reconnect every two seconds.

## Troubleshooting

### The status remains `EC4 disconnected`

- Close any other application that may have opened the EC4 MIDI ports exclusively.
- Reconnect the EC4, click **Refresh MIDI ports**, then check both MIDI selectors.
- Read the log to confirm the exact port name detected by Windows.

### Error on feedback port 8011

Another application is probably already using the port, often Bitfocus Companion. Close the other receiver or choose another matching pair of ports in LiveProfessor and the bridge.

### Parameters move but the EC4 display does not change

- Check that SysEx display is enabled.
- Check that the current EC4 setup/group exactly matches the **dedicated EC4 area** selected in the bridge.
- Use **Use current setup/group** to save the page currently shown by the EC4.

### Names remain P001, P002…

- In Companion mode, verify UDP feedback on port 8011 and the Companion Controller definition.
- Check that a Controller Map is applied to the plugin and that its Rotary controls have names.
- Check that the relevant plugin is the one selected in LiveProfessor.
- In Generic mode, select a JSON profile; dynamic names are not expected in this mode.

### A reinserted plugin is no longer controlled

Apply its Controller Map preset again in LiveProfessor. The bridge does not write directly into LiveProfessor projects and cannot force this operation without an official API.
