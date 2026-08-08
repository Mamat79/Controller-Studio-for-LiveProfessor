# Sources et niveau de preuve

🇬🇧 [English version](en/SOURCES.md)

Liens vérifiés le 7 août 2026.

## Sources officielles

- [Audioström — LiveProfessor](https://www.audiostrom.com/) : version publique 2026.1.0, VST/AU, snapshots, cue lists, MIDI/OSC/LTC.
- [Hardware Controllers](https://intercom.help/audiostrom/en/articles/8318600-hardware-controllers) : couche de contrôleur virtuelle et réutilisable.
- [Defining a new controller](https://intercom.help/audiostrom/en/articles/8319060-defining-a-new-controller) : contrôleurs MIDI, OSC, Companion et feedback.
- [Controller Maps](https://intercom.help/audiostrom/en/articles/8318601-controller-maps) : maps, Quick Assign et changement de maps par snapshots/cues.
- [Controller Transformations](https://intercom.help/audiostrom/en/articles/8320237-controller-transformations) : relatif, inversion, limites et courbes.
- [List of OSC commands](https://intercom.help/audiostrom/en/articles/8319137-list-of-osc-commands) : commandes distantes publiées par LiveProfessor.
- [Installing plugins / Plugin Manager](https://intercom.help/audiostrom/en/articles/8315264-installing-plugins-the-plugin-manager) : formats et gestion des plugins.
- [Audioström change log](https://www.audiostrom.com/change-log) : historique des versions.
- [Faderfox EC4](https://www.faderfox.de/ec4.html) : 16 encodeurs, groupes/setups, modes absolus/relatifs, feedback et OLED.
- [Faderfox EC4 Manual V03](https://www.faderfox.de/PDF/EC4%20Manual%20V03.pdf) : configuration, Shift/push et protocole de l’appareil.

## Source technique publique

- [Bitfocus Companion — module Audioström LiveProfessor](https://github.com/bitfocus/companion-module-audiostrom-liveprofessor) : implémentation open source du contrôleur Companion, ports 8010/8011, messages `/init`, `/refresh`, 99 rotatifs, commandes et feedback. Le fichier d’aide demande LiveProfessor 2023.0.8 ou supérieur.

Cette source démontre un protocole réellement utilisé, mais ne transforme pas en API officielle les fonctions que LiveProfessor ne publie pas.

## Témoignage de terrain non officiel

- [PA-Forum — fil LiveProfessor](https://paforum.de/forum/index.php?pageNo=17&thread%2F136765-liveprofessor-als-waves-alternative-wie-geht-das-m%C3%B6glichst-gut%2F=) : retour utilisateur sur `Only If Selected` et l’application d’une map aux nouvelles instances.

Cette source est utilisée uniquement comme signal de limite pratique. La conception principale et le protocole reposent sur la documentation officielle, le manuel EC4 et le code public du module Companion.
