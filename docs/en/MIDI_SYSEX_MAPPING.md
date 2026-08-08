# MIDI and SysEx Mapping for the Faderfox EC4

🇫🇷 [Version française](../CARTOGRAPHIE_MIDI_SYSEX.md)

The channel numbers below are the values shown to the user on the EC4. The Python code uses zero-based numbering: user channel 13 is `12`, and user channel 14 is `13`.

## Parameter control — default fallback mapping

| Function | User channel | Message | Range | Control mode |
|---|---:|---|---:|---|
| Parameters 1–8 | 13 | CC | 48–55 | Absolute, value feedback, takeover disabled |
| Parameters 9–16 | 14 | CC | 73–80 | Absolute, value feedback, takeover disabled |
| Show details for parameters 1–16 | 13 | Notes | 40–55 | Momentary press |
| Previous bank | 14 | Note | 112 | Momentary press |
| Next bank | 14 | Note | 113 | Momentary press |

This is the fallback mapping used when no custom mapping has been learned for the selected setup/group. From version 0.3.0 onward, the interface can learn the 16 encoder CC messages and 16 push Notes from any setup/group.

The encoders remain in absolute mode. OSC feedback received from LiveProfessor is converted to CC values from 0 to 127 and sent back to the corresponding learned encoder. This is the anti-jump strategy. A 100 ms guard blocks an identical feedback message from being interpreted as a new user movement.

## Plugin and chain navigation

| LiveProfessor action | Channel | Note |
|---|---:|---:|
| Show/hide the selected plugin | 13 | 112 |
| Enable/disable processing on the selected plugin | 13 | 113 |
| Previous plugin | 13 | 114 |
| Next plugin | 13 | 115 |
| Show/hide the selected plugin | 13 | 116 |
| Plugin lock | 13 | 117 — no matching public OSC command found |
| Previous chain | 13 | 118 |
| Next chain | 13 | 119 |

## Shift+push SysEx gestures

The EC4 provides 16 SysEx button messages for encoder pushes used together with Shift.

| Internal index | Encoder | Bridge action |
|---:|---:|---|
| 0 | 1 | Unavailable: no matching public command found |
| 1 | 2 | Previous global snapshot |
| 2 | 3 | Next global snapshot |
| 3 | 4 | Unavailable |
| 4 | 5 | Unavailable |
| 5 | 6 | Previous plugin |
| 6 | 7 | Next plugin |
| 7 | 8 | Unavailable |
| 8 | 9 | First bank |
| 9 | 10 | Previous bank |
| 10 | 11 | Next bank |
| 11 | 12 | Last bank |
| 12 | 13 | Enable/disable processing on the selected plugin |
| 13 | 14 | Previous bank |
| 14 | 15 | Next bank |
| 15 | 16 | Show/hide the selected plugin |

A **simple push on encoder 16** triggers Tap Tempo. Simple pushes on encoders 1–15 display the corresponding parameter details. Bank and snapshot actions in the table above require Shift+push.

## Additional controls present in the legacy EC4 preset but not forwarded by the bridge

The following controls are documented for reference. The current bridge intentionally does not redirect them to LiveProfessor.

### Sixteen channel strips

Channels 1–8 use user MIDI channel 13, while channels 9–16 use user MIDI channel 14. For the second group, controller numbers 0–7 are reused on the other MIDI channel.

| Function per channel strip | Type | Base for strip 1/9 | Range on each MIDI channel |
|---|---|---:|---:|
| Select | Note | 56 | 56–63 |
| Volume | CC | 40 | 40–47 |
| Pan | CC | 32 | 32–39 |
| Send 1 | CC | 0 | 0–7 |
| Send 2 | CC | 8 | 8–15 |
| Send 3 | CC | 16 | 16–23 |
| Send 4 | CC | 24 | 24–31 |
| Launch clip/action | Note | 64 | 64–71 |
| Stop clip/action | Note | 72 | 72–79 |
| Arm | Note | 80 | 80–87 |
| Monitor | Note | 88 | 88–95 |
| Solo | Note | 96 | 96–103 |
| Mute | Note | 104 | 104–111 |

### Selected channel controls

These controls use user MIDI channel 14.

| Function | Message |
|---|---|
| Sends 1–3 | CC 56–58 |
| Sends 4–12 | CC 64–72 |
| Pan | CC 62 |
| Volume | CC 63 |
| Channel view | Note 120 |
| Secondary view | Note 121 |
| Stop action | Note 122 |
| Launch action | Note 123 |
| Arm | Note 124 |
| Monitor | Note 125 |
| Solo | Note 126 |
| Mute | Note 127 |

The scene and channel selectors are duplicated on user channels 13 and 14 as CC 59 and CC 60. They use the `relative_smooth_two_compliment` mode in the legacy preset.

### Transport and master controls

User MIDI channel 13:

| Function | Message | Notable mode |
|---|---|---|
| Coarse tempo | CC 56 | Smoothed relative, two's complement |
| Fine tempo | CC 57 | Smoothed relative, two's complement |
| Quantization | CC 58 | Absolute |
| Scene selection | CC 59 | Smoothed relative |
| Channel selection | CC 60 | Smoothed relative |
| Cue volume | CC 61 | Absolute |
| Master pan | CC 62 | Absolute |
| Master volume | CC 63 | Absolute |
| Nudge down/up | Notes 120/121 | Buttons |
| Stop/launch scene | Notes 122/123 | Buttons |
| Play/stop/record | Notes 124/125/126 | Buttons |
| Arrangement view | Note 127 | Button |
| Tempo display | Pitch bend | Feedback to the EC4 |

User MIDI channel 14 also contains a crossfader on CC 48 and crossfader assignment on CC 61.

## EC4 SysEx protocol

### Prefixes

- Request for the active setup and group: `F0 00 00 00 4E 20 10 F7`.
- EC4 response prefix: `F0 00 00 00 4E 2C 1B`.
- Button message prefix: `F0 00 00 00 4E 2C 1B 4E`.

### Setup/group response

Exact 14-byte format:

```text
F0 00 00 00 4E 2C 1B 4E 28 Ss 4E 24 Gg F7
```

The internal setup value is `Ss & 0F`, and the internal group value is `Gg & 0F`.

The bridge requests this state on every connection. The dedicated setup and group are selected explicitly in the interface. CC/Note commands, feedback and display updates are ignored outside that target area. From version 0.3.0 onward, a learned MIDI mapping can be stored for each setup/group pair.

The original fallback configuration uses displayed setup 13 and group 3, but the current target selection can use any valid setup/group pair.

### Shift, User and Shift+push

After the button prefix:

- Shift: `26 11 4E 2E`;
- User 1–4: `26 12 4E 2E` through `26 15 4E 2E`;
- Shift+push for encoder `i`: `2A (10+i) 4E 2E`, where `i` is from 0 to 15.

A state byte follows the identifier: `11` means pressed; another value means released. The message ends with `F7`.

Example: Shift+push on encoder 10, pressed:

```text
F0 00 00 00 4E 2C 1B 4E 2A 19 4E 2E 11 F7
```

### Main display — 16 cells of 4 characters

```text
F0 00 00 00 4E 2C 1B 4E 22 10 4A 20 10
[64 encoded characters]
F7
```

Each 8-bit character `c` becomes three bytes:

```text
4D (20 | c>>4) (10 | c&0F)
```

The complete message is 206 bytes long. Each of the 16 labels is truncated or padded to four characters.

### Full temporary display — 4 lines of 20 characters

```text
F0 00 00 00 4E 2C 1B 4E 22 13 4A (20|offset_hi) (10|offset_lo)
[encoded text]
4E 22 14 F7
```

A complete 80-character screen is 257 bytes long. To clear and hide the overlay, the final block `4E 22 14` is replaced with `4E 22 15` after 80 spaces have been sent.

Version 0.4.0 also reuses this full-screen area as a persistent 4 × 4 grid. Each cell contains a short parameter name. After a temporary value overlay, the active bank grid is restored instead of returning to the labels stored in the EC4 group.

The character table supports common ASCII characters plus `Ä`, `Ö`, `Ü`, `ä`, `ö`, `ü`, `à`, `²`, `³`, `§`, square brackets, backslash and comparison signs. An unsupported character is replaced with code `1F`.

## What the bridge actually listens to

To minimize conflicts, the bridge intercepts only:

- the 16 learned parameter CC messages, or the built-in fallback mapping;
- the 16 learned push Notes, or the built-in fallback mapping;
- the two bank Notes;
- plugin and chain navigation Notes;
- the useful Shift+push gestures;
- setup/group SysEx responses;
- OSC feedback required for values and display updates.

The additional channel-strip, transport, clip/action and send controls remain documented but are not redirected to LiveProfessor.
