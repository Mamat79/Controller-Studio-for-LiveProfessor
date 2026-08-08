# Sources and Evidence Level

🇫🇷 [Version française](../SOURCES.md)

Links checked on 7 August 2026.

## Official sources

- [Audioström — LiveProfessor](https://www.audiostrom.com/): public version 2026.1.0, VST/AU support, snapshots, cue lists, MIDI, OSC and LTC.
- [Hardware Controllers](https://intercom.help/audiostrom/en/articles/8318600-hardware-controllers): reusable virtual controller layer.
- [Defining a new controller](https://intercom.help/audiostrom/en/articles/8319060-defining-a-new-controller): MIDI, OSC and Companion controllers and feedback.
- [Controller Maps](https://intercom.help/audiostrom/en/articles/8318601-controller-maps): maps, Quick Assign and map changes through snapshots or cues.
- [Controller Transformations](https://intercom.help/audiostrom/en/articles/8320237-controller-transformations): relative controls, inversion, limits and curves.
- [List of OSC commands](https://intercom.help/audiostrom/en/articles/8319137-list-of-osc-commands): remote commands published by LiveProfessor.
- [Installing plugins / Plugin Manager](https://intercom.help/audiostrom/en/articles/8315264-installing-plugins-the-plugin-manager): plugin formats and management.
- [Audioström change log](https://www.audiostrom.com/change-log): version history.
- [Faderfox EC4](https://www.faderfox.de/ec4.html): 16 encoders, groups/setups, absolute and relative modes, feedback and OLED display.
- [Faderfox EC4 Manual V03](https://www.faderfox.de/PDF/EC4%20Manual%20V03.pdf): configuration, Shift/push operation and device protocol.

## Public technical source

- [Bitfocus Companion — Audioström LiveProfessor module](https://github.com/bitfocus/companion-module-audiostrom-liveprofessor): open-source implementation of the Companion controller protocol, ports 8010/8011, `/init`, `/refresh`, 99 Rotary controls, commands and feedback. Its help file requires LiveProfessor 2023.0.8 or later.

This source demonstrates a protocol used in practice, but it does not turn undocumented LiveProfessor functions into an official API.

## Unofficial field report

- [PA-Forum — LiveProfessor thread](https://paforum.de/forum/index.php?pageNo=17&thread%2F136765-liveprofessor-als-waves-alternative-wie-geht-das-m%C3%B6glichst-gut%2F=): user feedback concerning `Only If Selected` and applying a map to newly created plugin instances.

This source is used only as an indication of a practical limitation. The main design and protocol are based on official documentation, the EC4 manual and the public Companion module source code.
