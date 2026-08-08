
# EC4 Configuration Example

🇫🇷 [Version française](../CONFIGURATION_EC4.md)

The bridge can use its built-in fallback mapping or learn the MIDI messages from any suitable EC4 setup/group without reprogramming the whole device.

## Default fallback mapping

The following mapping is the initial fallback used when no learned mapping exists for the selected setup/group.

| Encoders | EC4 channel shown to the user | CC numbers | Values |
|---|---:|---:|---:|
| 1–8 | 13 | 48–55 | Absolute 0–127 |
| 9–16 | 14 | 73–80 | Absolute 0–127 |

| Buttons | Channel | Notes |
|---|---:|---:|
| Parameter pushes 1–16 | 13 | 40–55 |
| Previous/next bank | 14 | 112/113 |
| Plugin and chain navigation | 13 | 112–119 |

The EC4 must accept CC feedback on the same channels and controller numbers. This feedback aligns the encoder's internal value with the current plugin value and prevents abrupt jumps.

## Dedicated setup and group

The current bridge can reserve any setup/group pair from 1 to 16.

When the EC4 is on another page, parameter commands, feedback and display updates are suspended. This prevents the bridge from interfering with other EC4 uses.

Recommended procedure:

1. select the EC4 page you want to reserve for LiveProfessor;
2. start the bridge;
3. click **Use current setup/group**;
4. check that the Setup and Group fields match the values shown in the status area.

## Learning a custom mapping

The selected page does not have to use the fallback CC and Note numbers.

1. Keep the EC4 on the target setup/group.
2. Click **Learn encoders + push**.
3. Turn encoders 1 through 16 in order.
4. Press their 16 push buttons in order.
5. Wait for the confirmation that the mapping has been learned and saved.

The bridge stores the MIDI addresses for that setup/group pair.

The encoders must remain configured as **absolute CC controls from 0 to 127** so value feedback can prevent jumps. Encoder pushes must send **MIDI Notes**. Shift+push gestures are transmitted as separate SysEx messages and are not included in the learning phase.

## Bridge configuration file

The example file [config.example.json](../../config.example.json) includes settings for:

- up to 99 controls;
- banks of 16;
- OSC output to `127.0.0.1:8010` and feedback on `127.0.0.1:8011`;
- a 100 ms echo guard;
- MIDI reconnection every two seconds;
- display protection outside the selected setup/group;
- the persistent parameter grid (`persistent_parameter_display`);
- the dedicated setup and group (`target_setup`, `target_group`);
- restriction of bridge commands to that area (`restrict_to_target`);
- learned mappings per setup/group (`encoder_mappings`).

For a first test, select an unused EC4 group, click **Use current setup/group**, then run **Learn encoders + push**.
