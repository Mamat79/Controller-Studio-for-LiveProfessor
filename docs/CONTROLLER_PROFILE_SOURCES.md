# Sources et modes des profils de contrôleurs

Controller Studio V.2026.4 fournit 33 profils déclaratifs. Un profil `community`
est utilisable pour l'export `.ctrl2`, AutoMap et l'apprentissage MIDI, mais son
plan complet n'a pas encore été validé sur un exemplaire physique par le projet.
Les profils programmables utilisent un plan SiLeMIO simple et reproductible à
saisir dans l'éditeur officiel du fabricant.

## Contrôleurs à plan fixe ou documenté

| Profil | Mode requis | Référence |
| --- | --- | --- |
| Akai LPD8 MK2 | Program 1, pads Note 36–43 et potentiomètres CC 36–43, canal 1 | [Guide officiel Akai](https://support.inmusicstore.com/en/support/solutions/articles/69000867977-lpd8-mkii-how-to-use-16-pads-and-knobs-in-mpc-beats) |
| Akai MIDImix | Plan d'usine : 24 potentiomètres, 9 faders, Mute et Rec Arm | [Guide officiel MIDImix](https://cdn.inmusicbrands.com/akai/attachments/MIDIMIX/MIDImix-UserGuide-v1.0.pdf) |
| Akai APC Mini MK2 | Port 0 : faders CC 48–56, boutons Track 100–107, Scene 112–119 et grille 0–63 | [Protocole officiel APC Mini MK2](https://cdn.inmusicbrands.com/akai/attachments/APC%20mini%20mk2%20-%20Communication%20Protocol%20-%20v1.0.pdf) |
| Arturia MiniLab 3 | User Program : encodeur principal CC 114/115, huit potentiomètres, quatre faders et huit pads | [MIDI Implementation officiel](https://support.arturia.com/hc/en-us/articles/6189475866396-MiniLab-3-General-Questions) |
| Arturia BeatStep | User Preset SiLeMIO : 16 encodeurs CC 20–35 et 16 pads Note 36–51, canal 1 | [Manuel officiel BeatStep](https://dl.arturia.net/products/beatstep/manual/BeatStep_Manual_1_0_1_EN.pdf) |
| Behringer X-Touch Compact | Standard, Layer A, canal 1 | [Quick Start Guide et MIDI Map](https://mediadl.musictribe.com/media/PLM/data/docs/P0B3L/QSG_BE_0808-AAE_X-TOUCH%20COMPACT_WW.pdf) |
| Behringer X-Touch Mini | Standard, Preset A, canal 11 | [Quick Start Guide et MIDI Map](https://mediadl.musictribe.com/media/PLM/data/docs/P0B3M/QSG_BE_0808-AAF_X-TOUCH-MINI_WW.pdf) |
| Behringer X-Touch One | MIDI mode, canal 1 | [MIDI Mode Implementation](https://mediadl.musictribe.com/download/software/behringer/X-TOUCH/Document_BE_X-TOUCH-ONE-MIDI-Mode-Implementation.pdf) |
| Korg nanoKONTROL2 | Mode CC, canal global 1 | [Parameter Guide et MIDI Implementation](https://www.korg.com/tmp/support/download/index.php/product/0/159/?country=us&page=product&prodid=159&prodtype=0) |
| Novation Launch Control XL MK2 | User Template SiLeMIO : faders CC 5–12, potentiomètres CC 13–36, boutons CC 37–52, canal 1 | [Guide officiel Components](https://support.novationmusic.com/hc/en-gb/articles/360009860380-Launch-Control-XL-Components-guide) |
| Novation Launch Control XL 3 | Default Mode 16, canal 16 | [Paramètres officiels du Mode 16](https://userguides.novationmusic.com/hc/en-gb/articles/26260540230162-Launch-Control-XL-3-appendix) |
| Faderfox EC4, PC4, UC4 et PC12 | Setups d'usine indiqués dans le nom du profil | [Manuels officiels Faderfox](https://faderfox.de/downloads.html) |
| DJ TechTools MIDI Fighter Twister | Factory Banks 1–4 | [Guide officiel MIDI Fighter Twister](https://www.midifighter.com/#Twister) |

## Contrôleurs configurables

| Famille | Plan du profil Controller Studio | Configuration officielle |
| --- | --- | --- |
| Akai MPK Mini MK3, MPK Mini IV et MPK Mini Plus | huit potentiomètres CC 70–77 canal 1, huit pads Note 36–43 canal 10 | [MPK Mini MK3](https://support.akaipro.com/en/support/solutions/articles/69000798861-akai-pro-mpk-mini-mk3-frequently-asked-questions), [MPK Mini IV](https://support.akaipro.com/en/support/solutions/articles/69000872348-mpk-mini-iv-frequently-asked-questions), [MPK Mini Plus](https://cdn.inmusicbrands.com/akai/attachments/mpkminiplus/MPK%20mini%20Plus%20-%20User%20Guide%20-%20v1.2.pdf) |
| Novation Launchkey Mini MK3/MK4 | huit potentiomètres CC 21–28 et seize pads Note 36–51 ; quatre pages Custom | [Components MK3](https://support.novationmusic.com/hc/en-gb/articles/360014619639-Launchkey-MK3-Components-Guide), [Components MK4](https://support.novationmusic.com/hc/en-gb/articles/20229018847506-Launchkey-MK4-Components-Guide) |
| Novation Launchkey 49/61/88 MK3/MK4 | huit potentiomètres CC 21–28, neuf faders CC 41–49 et neuf boutons CC 51–59 ; quatre pages Custom | [Components MK3](https://support.novationmusic.com/hc/en-gb/articles/360014619639-Launchkey-MK3-Components-Guide), [Components MK4](https://support.novationmusic.com/hc/en-gb/articles/20229018847506-Launchkey-MK4-Components-Guide) |
| Arturia KeyLab Essential MK3 | User Program SiLeMIO : neuf potentiomètres CC 74–82, neuf faders CC 83–91 et huit pads Note 36–43 | [Guide officiel Arturia](https://support.arturia.com/hc/en-us/articles/8841900354076-KeyLab-Essential-mk3-General-Questions) |
| Novation Launchpad X et Launchpad Mini MK3 | Custom Mode SiLeMIO : huit faders CC 21–28 et huit interrupteurs Note 36–43 | [Launchpad X](https://support.novationmusic.com/hc/en-gb/articles/360010307540-Note-Mode-Settings-on-the-Launchpad-X), [Launchpad Mini MK3](https://userguides.novationmusic.com/hc/en-gb/articles/23731330721682-Launchpad-Mini-s-Settings-menu) |

## Surfaces MCU / HUI

Les profils suivants utilisent le sous-ensemble standard Mackie Control :
faders en Pitch Bend, V-Pots relatifs CC 16–23, appuis Note 32–39 et touchers
Note 104–111. Sélectionnez le mode **MCU**, **MC** ou **Mackie Control** sur le
matériel. Le FaderPort 16 est représenté par deux pages de huit voies, comme une
surface MCU principale accompagnée de son extender.

| Profil | Source officielle |
| --- | --- |
| Behringer X-Touch | [Documentation officielle X-Touch](https://www.behringer.com/product.html?modelCode=0808-AAB) |
| PreSonus FaderPort V2, 8 et 16 | [Modes MCU/HUI/MIDI officiels](https://support.presonus.com/hc/en-us/articles/217070166-Faderport-Family-Native-Mode-HUI-Mode-MCU-Modes-and-MIDI-Mode) |
| Solid State Logic UF1 | [Support officiel UF1 / Mackie Control](https://support.solidstatelogic.com/hc/en-gb/articles/12592482788509-UF1-and-Logic-how-do-I-control-any-plug-in-parameter-on-UF1-s-fader) |
| Solid State Logic UF8 | [Guide utilisateur officiel UF8](https://www.solidstatelogic.com/assets/uploads/downloads/UF8/SSL%20UF8%20User%20Guide.pdf) |

## Validation matérielle

Le profil Faderfox EC4 est la référence déjà testée avec le moteur temps réel.
Les autres profils restent marqués `community` jusqu'à une capture réelle de
toutes les commandes et, lorsque le matériel le permet, une vérification des
LED, moteurs, couleurs et retours. L'éditeur intégré permet de corriger un CC,
un canal ou un appui sans modifier les profils distribués.
