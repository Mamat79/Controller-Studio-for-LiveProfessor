"""Build the bilingual EC4 LiveProfessor Bridge PDF user guides."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026.1"
FR_OUTPUT = ROOT / "docs" / "NOTICE_EC4_BRIDGE_FR.pdf"
EN_OUTPUT = ROOT / "docs" / "en" / "EC4_BRIDGE_USER_GUIDE_EN.pdf"

INK = colors.HexColor("#10222D")
MUTED = colors.HexColor("#546A76")
CYAN = colors.HexColor("#13BFEF")
CYAN_DARK = colors.HexColor("#087D9D")
MAGENTA = colors.HexColor("#EA3E8E")
PALE = colors.HexColor("#EAF8FC")
PALE_GREY = colors.HexColor("#F4F7F8")
WHITE = colors.white


@dataclass(frozen=True)
class Locale:
    code: str
    title: str
    subtitle: str
    footer: str
    contents: str
    sections: tuple[tuple[str, list[object]], ...]


def _register_fonts() -> tuple[str, str]:
    candidates = [
        (
            Path(r"C:\Windows\Fonts\segoeui.ttf"),
            Path(r"C:\Windows\Fonts\seguisb.ttf"),
        ),
        (
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ),
    ]
    for regular, bold in candidates:
        if regular.is_file() and bold.is_file():
            pdfmetrics.registerFont(TTFont("GuideSans", str(regular)))
            pdfmetrics.registerFont(TTFont("GuideSans-Bold", str(bold)))
            addMapping("GuideSans", 0, 0, "GuideSans")
            addMapping("GuideSans", 1, 0, "GuideSans-Bold")
            return "GuideSans", "GuideSans-Bold"
    return "Helvetica", "Helvetica-Bold"


REGULAR_FONT, BOLD_FONT = _register_fonts()


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "GuideTitle",
            parent=base["Title"],
            fontName=BOLD_FONT,
            fontSize=27,
            leading=31,
            textColor=INK,
            alignment=TA_CENTER,
            spaceAfter=8 * mm,
        ),
        "subtitle": ParagraphStyle(
            "GuideSubtitle",
            parent=base["Normal"],
            fontName=REGULAR_FONT,
            fontSize=12,
            leading=17,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "GuideH1",
            parent=base["Heading1"],
            fontName=BOLD_FONT,
            fontSize=20,
            leading=24,
            textColor=INK,
            spaceBefore=2 * mm,
            spaceAfter=5 * mm,
        ),
        "h2": ParagraphStyle(
            "GuideH2",
            parent=base["Heading2"],
            fontName=BOLD_FONT,
            fontSize=13,
            leading=17,
            textColor=CYAN_DARK,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "GuideBody",
            parent=base["BodyText"],
            fontName=REGULAR_FONT,
            fontSize=9.5,
            leading=13.2,
            textColor=INK,
            spaceAfter=2.3 * mm,
        ),
        "small": ParagraphStyle(
            "GuideSmall",
            parent=base["BodyText"],
            fontName=REGULAR_FONT,
            fontSize=8,
            leading=10.5,
            textColor=MUTED,
        ),
        "bullet": ParagraphStyle(
            "GuideBullet",
            parent=base["BodyText"],
            fontName=REGULAR_FONT,
            fontSize=9.3,
            leading=12.8,
            textColor=INK,
            leftIndent=5 * mm,
            firstLineIndent=-3 * mm,
            bulletIndent=1 * mm,
            spaceAfter=1.3 * mm,
        ),
        "callout": ParagraphStyle(
            "GuideCallout",
            parent=base["BodyText"],
            fontName=REGULAR_FONT,
            fontSize=9.3,
            leading=13,
            textColor=INK,
        ),
        "toc": ParagraphStyle(
            "GuideToc",
            parent=base["BodyText"],
            fontName=REGULAR_FONT,
            fontSize=10,
            leading=15,
            textColor=INK,
            leftIndent=4 * mm,
        ),
        "table_header": ParagraphStyle(
            "GuideTableHeader",
            parent=base["BodyText"],
            fontName=BOLD_FONT,
            fontSize=8.4,
            leading=10.5,
            textColor=WHITE,
        ),
        "table": ParagraphStyle(
            "GuideTable",
            parent=base["BodyText"],
            fontName=REGULAR_FONT,
            fontSize=8.1,
            leading=10.2,
            textColor=INK,
        ),
    }


STYLES = _styles()


class GuideDocument(BaseDocTemplate):
    def __init__(self, path: Path, locale: Locale):
        super().__init__(
            str(path),
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=17 * mm,
            title=locale.title,
            author="SiLeMI/O - By Mamat",
            subject="Faderfox EC4 and LiveProfessor bridge user guide",
        )
        self.locale = locale
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="guide",
        )
        self.addPageTemplates(PageTemplate(id="guide", frames=[frame], onPage=self._decorate))

    def _decorate(self, canvas, doc):
        canvas.saveState()
        width, height = A4
        if doc.page > 1:
            canvas.setStrokeColor(colors.HexColor("#CCEAF3"))
            canvas.setLineWidth(0.7)
            canvas.line(18 * mm, height - 12 * mm, width - 18 * mm, height - 12 * mm)
            canvas.setFont(REGULAR_FONT, 7.5)
            canvas.setFillColor(MUTED)
            canvas.drawString(18 * mm, height - 9 * mm, f"EC4 LiveProfessor Bridge {VERSION}")
            canvas.drawRightString(width - 18 * mm, height - 9 * mm, "SiLeMI/O - By Mamat")
            canvas.line(18 * mm, 11 * mm, width - 18 * mm, 11 * mm)
            canvas.drawString(18 * mm, 7 * mm, self.locale.footer)
            canvas.drawRightString(width - 18 * mm, 7 * mm, str(doc.page))
        canvas.restoreState()


def _p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLES[style])


def _bullets(items: list[str]) -> list[Paragraph]:
    return [Paragraph(f"- {item}", STYLES["bullet"]) for item in items]


def _callout(title: str, text: str, color=CYAN) -> Table:
    content = _p(f"<b>{title}</b><br/>{text}", "callout")
    table = Table([[content]], colWidths=[168 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), 0.8, color),
                ("LINEBEFORE", (0, 0), (0, -1), 4, color),
                ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]
        )
    )
    return table


def _table(headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    data = [[_p(item, "table_header") for item in headers]]
    data += [[_p(item, "table") for item in row] for row in rows]
    table = Table(data, colWidths=[w * mm for w in widths], repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B9CBD3")),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
    ]
    for row in range(1, len(data)):
        if row % 2 == 0:
            style.append(("BACKGROUND", (0, row), (-1, row), PALE_GREY))
    table.setStyle(TableStyle(style))
    return table


def _architecture(labels: tuple[str, str, str, str]) -> Drawing:
    ec4, bridge, lp, feedback = labels
    d = Drawing(168 * mm, 45 * mm)
    y = 12 * mm
    boxes = [
        (2 * mm, 42 * mm, ec4, MAGENTA),
        (63 * mm, 43 * mm, bridge, CYAN),
        (126 * mm, 40 * mm, lp, colors.HexColor("#74CC49")),
    ]
    for x, w, label, color in boxes:
        d.add(Rect(x, y, w, 18 * mm, rx=3 * mm, ry=3 * mm, fillColor=PALE_GREY, strokeColor=color, strokeWidth=2))
        d.add(String(x + w / 2, y + 10.5 * mm, label, textAnchor="middle", fontName=BOLD_FONT, fontSize=9, fillColor=INK))
    d.add(Line(44 * mm, y + 12 * mm, 62 * mm, y + 12 * mm, strokeColor=INK, strokeWidth=1.6))
    d.add(Line(106 * mm, y + 12 * mm, 125 * mm, y + 12 * mm, strokeColor=INK, strokeWidth=1.6))
    d.add(String(53 * mm, y + 14 * mm, "MIDI + SysEx", textAnchor="middle", fontName=REGULAR_FONT, fontSize=7, fillColor=MUTED))
    d.add(String(116 * mm, y + 14 * mm, "OSC", textAnchor="middle", fontName=REGULAR_FONT, fontSize=7, fillColor=MUTED))
    d.add(Line(125 * mm, y + 4 * mm, 44 * mm, y + 4 * mm, strokeColor=CYAN_DARK, strokeWidth=1.2))
    d.add(String(85 * mm, y + 0.5 * mm, feedback, textAnchor="middle", fontName=REGULAR_FONT, fontSize=7.5, fillColor=CYAN_DARK))
    return d


def _cover(locale: Locale) -> list[object]:
    grid = Drawing(168 * mm, 53 * mm)
    for row in range(4):
        for col in range(4):
            x = 34 * mm + col * 26 * mm
            y = 5 * mm + (3 - row) * 12 * mm
            grid.add(Rect(x, y, 21 * mm, 8.5 * mm, rx=1.8 * mm, ry=1.8 * mm, fillColor=PALE_GREY, strokeColor=CYAN if (row + col) % 2 else MAGENTA, strokeWidth=1.1))
            grid.add(String(x + 10.5 * mm, y + 3.2 * mm, str(row * 4 + col + 1), textAnchor="middle", fontName=BOLD_FONT, fontSize=7.5, fillColor=INK))
    return [
        Spacer(1, 28 * mm),
        _p("SiLeMI/O", "title"),
        _p(locale.title, "title"),
        _p(locale.subtitle, "subtitle"),
        Spacer(1, 15 * mm),
        grid,
        Spacer(1, 15 * mm),
        _callout(
            f"Version {VERSION}",
            "Faderfox EC4 - LiveProfessor - Auto-mapping - UniBank / FullBank",
            MAGENTA,
        ),
        Spacer(1, 18 * mm),
        _p("By Mamat<br/>-----[]---", "subtitle"),
        PageBreak(),
    ]


def _fr_locale() -> Locale:
    shortcuts = [
        ["Tourner 1-16", "Modifier les paramètres de la banque active"],
        ["Shift + push 1 / 2", "Banque précédente / suivante"],
        ["Shift + push 3 / 4", "View Set précédent / suivant"],
        ["Shift + push 5", "Afficher / masquer le plugin sélectionné"],
        ["Shift + push 6 / 10", "Chaîne précédente / suivante"],
        ["Shift + push 7 / 8", "Plugin précédent / suivant"],
        ["Shift + push 9", "Activer / désactiver le plugin sélectionné"],
        ["Shift + push 11 / 12", "Plugin précédent / suivant (raccourci doublé)"],
        ["Shift + push 13 / 14", "Cue précédente / suivante"],
        ["Shift + push 15 / 16", "Snapshot global précédent / suivant"],
        ["Push 1-15 sans Shift", "GenericButton1 à GenericButton15"],
        ["Push 16 sans Shift", "Tap Tempo"],
    ]
    sections: tuple[tuple[str, list[object]], ...] = (
        (
            "1. Comprendre le bridge",
            [
                _p("Le bridge relie les 16 encodeurs du Faderfox EC4 aux paramètres du plugin sélectionné dans LiveProfessor. Il transmet les gestes en OSC et renvoie vers l'EC4 les noms, les valeurs et les écrans de navigation."),
                _architecture(("Faderfox EC4", "EC4 Bridge", "LiveProfessor", "Noms + valeurs + état")),
                _p("Le mode <b>Companion</b> est recommandé. Le mode <b>Generic</b> reste disponible comme solution de repli lorsque les noms dynamiques ne sont pas nécessaires."),
                _callout("Principe de sécurité", "L'auto-mapping ne remplace jamais le projet choisi. Il crée une copie .rack2 distincte. Enregistrez malgré tout votre session avant de l'ouvrir dans LiveProfessor."),
            ],
        ),
        (
            "2. Installation et premier démarrage",
            [
                _p("Prérequis : Windows 10 ou 11 x64, LiveProfessor avec Companion Controller, un Faderfox EC4 et ses ports MIDI disponibles."),
                *_bullets([
                    "Lancez l'installateur EC4-LiveProfessor-Bridge-Setup-v2026.1.exe.",
                    "Branchez l'EC4 avant d'ouvrir les réglages de connexion.",
                    "Dans Outils > Connexions, choisissez l'entrée et la sortie MIDI Faderfox EC4.",
                    "Conservez 127.0.0.1, le port LiveProfessor 8010 et le retour 8011.",
                    "Choisissez un setup/groupe EC4 dédié, puis enregistrez et démarrez le bridge.",
                ]),
                _callout("Résultat attendu", "L'état passe à Connecté et l'EC4 affiche brièvement Connexion OK, SiLeMI/O et la signature By Mamat."),
            ],
        ),
        (
            "3. Installer le contrôleur LiveProfessor",
            [
                _p("Le bridge fournit deux fichiers neutres. <b>UniBank</b> est recommandé dans la majorité des projets ; <b>FullBank</b> sert aux plugins qui nécessitent plus de 16 paramètres."),
                _table(
                    ["Fichier", "Contenu", "Usage"],
                    [
                        ["Ec4-UniBank.ctrl2", "16 Rotary + 16 boutons", "Une banque simple, lisible et rapide"],
                        ["Ec4-FullBank.ctrl2", "99 Rotary + 16 boutons", "Plusieurs banques pour les plugins très fournis"],
                    ],
                    [45, 50, 73],
                ),
                Spacer(1, 3 * mm),
                *_bullets([
                    "Dans le bridge, choisissez Outils > CTRL2 UniBank ou CTRL2 FullBank et copiez le fichier dans un dossier facile à retrouver.",
                    "Dans LiveProfessor, ouvrez Controllers > Hardware Controllers Setup.",
                    "Utilisez Load from file, puis sélectionnez le fichier .ctrl2 copié.",
                    "Vérifiez 127.0.0.1, l'entrée 8010 et le retour 8011.",
                ]),
            ],
        ),
        (
            "4. Auto-mapping automatique",
            [
                _p("La fonction phare de la version 2026.1 crée une Controller Map dynamique pour un plugin ou pour tous les plugins du projet. Chaque rotatif agit uniquement sur l'instance sélectionnée."),
                *_bullets([
                    "Enregistrez le projet ouvert dans LiveProfessor.",
                    "Cliquez sur le bouton Auto-mapping ou ouvrez Outils > Auto-mapping.",
                    "Choisissez le projet .rack2 puis cliquez sur Analyser le projet.",
                    "Sélectionnez un plugin précis ou Tous les plugins détectés.",
                    "Conservez UniBank - 16 paramètres, sauf besoin réel de FullBank - 99 paramètres.",
                    "Créez la copie auto-mappée sous un nouveau nom.",
                    "Acceptez l'ouverture proposée uniquement après avoir enregistré le projet LiveProfessor courant.",
                ]),
                _callout("Aucun CTRL2 dans le projet source ?", "Le bridge ajoute automatiquement son modèle EC4 intégré à la copie. Il ne modifie jamais le fichier source."),
                _p("AutoMap réutilise d'abord les affectations actives et les presets manuels. L'ordre personnalisé est conservé instance par instance, puis réutilisé comme profil du type de plugin. Un poussoir appris est aussi conservé et, si le rotatif correspondant est libre, le même paramètre lui est affecté pour afficher son label."),
                _callout("Plugin totalement inconnu", "Le fichier .rack2 contient les numéros et valeurs, mais pas les noms de paramètres. Sans profil existant, AutoMap garde donc l'ordre technique. Un Output déjà placé sur le rotatif 16 y reste ; il n'est pas deviné sans nom fiable."),
                _p("Si des mappings se remplacent après des Learn manuels, analysez le projet puis cliquez sur <b>Réparer les mappings</b>. Le bridge crée une nouvelle copie, garde toujours les affectations actives en priorité, récupère seulement les affectations absentes et synchronise les presets partagés. Les plugins, réglages, snapshots et routages ne sont pas modifiés."),
            ],
        ),
        (
            "5. Commandes quotidiennes",
            [
                _p("Maintenez Shift pour afficher la légende des raccourcis sur l'EC4 avant d'appuyer sur un encodeur."),
                _table(["Action EC4", "Résultat"], shortcuts, [62, 106]),
            ],
        ),
        (
            "6. Banques, affichage et précision",
            [
                *_bullets([
                    "Une banque contient 16 paramètres, alignés sur les 16 encodeurs.",
                    "Les encodeurs non mappés restent sans libellé pour conserver un écran lisible.",
                    "Un mouvement affiche temporairement le nom complet et la valeur réelle reçue de LiveProfessor.",
                    "Le retour de valeur protège contre les sauts lorsque l'état du plugin et celui du contrôleur diffèrent.",
                    "Les réglages de réactivité se trouvent dans Outils > Connexions et rafraîchissement.",
                ]),
                _callout("Réglage conseillé", "Commencez avec les valeurs par défaut. Diminuez les délais seulement si le réseau local et LiveProfessor restent stables ; une valeur trop basse peut multiplier les rafraîchissements inutiles."),
            ],
        ),
        (
            "7. Apprendre n'importe quel setup/groupe",
            [
                _p("Il n'est pas nécessaire de conserver les CC du setup d'origine. L'apprentissage enregistre les 16 rotatifs et leurs 16 push pour le setup/groupe actuellement affiché."),
                *_bullets([
                    "Placez l'EC4 sur la page désirée et cliquez sur Utiliser le setup/groupe actuel.",
                    "Cliquez sur Apprendre rotatifs + push.",
                    "Tournez légèrement les rotatifs 1 à 16 dans l'ordre.",
                    "Appuyez ensuite sur les push 1 à 16 dans le même ordre.",
                    "Attendez la confirmation Mapping appris et enregistré.",
                ]),
                _p("Les rotatifs doivent envoyer des CC absolus de 0 à 127 et les push des Notes MIDI. Les gestes Shift+push utilisent un canal SysEx distinct et ne font pas partie de cet apprentissage."),
            ],
        ),
        (
            "8. Réduction, journal et mises à jour",
            [
                *_bullets([
                    "Réduire place l'application dans la zone de notification Windows lorsqu'elle est disponible.",
                    "Un clic ouvre la fenêtre ; un clic droit affiche les commandes Démarrer, Arrêter, Redémarrer et Quitter.",
                    "Quitter ferme réellement le bridge et libère les ports MIDI et OSC.",
                    "Le journal est accessible depuis Affichage > Journal.",
                    "La recherche de mise à jour peut être lancée manuellement ou au démarrage.",
                ]),
                _p("Journal sur Windows : <font name='Courier'>%LOCALAPPDATA%\\EC4LiveProfessorBridge\\bridge.log</font>."),
            ],
        ),
        (
            "9. Dépannage",
            [
                _table(
                    ["Symptôme", "Vérifications"],
                    [
                        ["EC4 déconnecté", "Fermer les autres applications MIDI, rebrancher l'EC4, actualiser et resélectionner les deux ports."],
                        ["Port 8011 indisponible", "Fermer l'autre récepteur OSC ou choisir la même nouvelle paire de ports dans LiveProfessor et le bridge."],
                        ["P001 / P002 au lieu des noms", "Vérifier Companion, la Controller Map du plugin sélectionné et le feedback UDP."],
                        ["Le plugin ne bouge pas", "Vérifier que le plugin est sélectionné et que sa map utilise Only If Selected ; recréer la copie après tout ajout de plugin."],
                        ["Valeurs lentes", "Contrôler le réseau local, puis ajuster progressivement les délais de rafraîchissement."],
                        ["Push non assignable", "Vérifier GenericButton1 à 15 dans le CTRL2 et l'exposition du paramètre par le plugin."],
                    ],
                    [52, 116],
                ),
            ],
        ),
        (
            "10. Limites, sauvegarde et assistance",
            [
                *_bullets([
                    "Sauvegardez les projets et les presets Controller Map avant un changement important.",
                    "L'auto-mapping travaille sur une copie et crée une sauvegarde horodatée si la destination existe.",
                    "Un plugin ajouté après l'auto-mapping nécessite une nouvelle génération.",
                    "Utilisez une licence, une période d'essai ou une licence de test LiveProfessor fournie officiellement.",
                    "Le bridge n'est ni affilié ni certifié par Faderfox ou Audioström.",
                ]),
                _callout("Projet et téléchargements", "https://github.com/Mamat79/EC4-LiveProfessor-Bridge", MAGENTA),
                _p("Rapporter un bug : https://github.com/Mamat79/EC4-LiveProfessor-Bridge/issues<br/>Releases : https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases"),
                _p("EC4 LiveProfessor Bridge - SiLeMI/O - By Mamat - -----[]---", "small"),
            ],
        ),
    )
    return Locale("fr", "Notice EC4 LiveProfessor Bridge", "Installation, auto-mapping et utilisation quotidienne", "Notice française", "Sommaire", sections)


def _en_locale() -> Locale:
    shortcuts = [
        ["Turn 1-16", "Change parameters in the active bank"],
        ["Shift + push 1 / 2", "Previous / next bank"],
        ["Shift + push 3 / 4", "Previous / next View Set"],
        ["Shift + push 5", "Show / hide selected plugin"],
        ["Shift + push 6 / 10", "Previous / next chain"],
        ["Shift + push 7 / 8", "Previous / next plugin"],
        ["Shift + push 9", "Enable / disable selected plugin"],
        ["Shift + push 11 / 12", "Previous / next plugin (duplicate shortcut)"],
        ["Shift + push 13 / 14", "Previous / next Cue"],
        ["Shift + push 15 / 16", "Previous / next global snapshot"],
        ["Push 1-15 without Shift", "GenericButton1 through GenericButton15"],
        ["Push 16 without Shift", "Tap Tempo"],
    ]
    sections: tuple[tuple[str, list[object]], ...] = (
        ("1. Understanding the bridge", [_p("The bridge connects the 16 Faderfox EC4 encoders to parameters of the selected LiveProfessor plugin. It sends gestures over OSC and returns names, values and navigation displays to the EC4."), _architecture(("Faderfox EC4", "EC4 Bridge", "LiveProfessor", "Names + values + state")), _p("<b>Companion</b> mode is recommended. <b>Generic</b> mode remains available as a fallback when dynamic labels are not required."), _callout("Safety principle", "Auto-mapping never replaces the selected project. It creates a separate .rack2 copy. Save the current LiveProfessor session before opening that copy.")]),
        ("2. Installation and first start", [_p("Requirements: Windows 10 or 11 x64, LiveProfessor with Companion Controller, a Faderfox EC4 and available MIDI ports."), *_bullets(["Run EC4-LiveProfessor-Bridge-Setup-v2026.1.exe.", "Connect the EC4 before opening connection settings.", "In Tools > Connections, select the Faderfox EC4 MIDI input and output.", "Keep 127.0.0.1, LiveProfessor port 8010 and feedback port 8011.", "Choose a dedicated EC4 setup/group, save, then start the bridge."]), _callout("Expected result", "Status changes to Connected and the EC4 briefly displays Connection OK, SiLeMI/O and the By Mamat signature.")]),
        ("3. Installing the LiveProfessor controller", [_p("The bridge supplies two neutral files. <b>UniBank</b> is recommended for most projects; <b>FullBank</b> is intended for plugins that genuinely need more than 16 parameters."), _table(["File", "Contents", "Use"], [["Ec4-UniBank.ctrl2", "16 Rotary + 16 buttons", "One fast, readable bank"], ["Ec4-FullBank.ctrl2", "99 Rotary + 16 buttons", "Several banks for large plugins"]], [45, 50, 73]), Spacer(1, 3 * mm), *_bullets(["In the bridge, choose Tools > UniBank CTRL2 or FullBank CTRL2 and save the file somewhere easy to find.", "In LiveProfessor, open Controllers > Hardware Controllers Setup.", "Use Load from file and select the copied .ctrl2 file.", "Verify 127.0.0.1, input 8010 and feedback 8011."])]),
        ("4. Automatic mapping", [_p("The main 2026.1 feature creates a dynamic Controller Map for one plugin or every plugin in the project. Each rotary controls only the selected instance."), *_bullets(["Save the current LiveProfessor project.", "Click Auto-mapping or open Tools > Auto-mapping.", "Choose the .rack2 project, then click Analyze project.", "Select one plugin or All detected plugins.", "Keep UniBank - 16 parameters unless FullBank - 99 parameters is genuinely needed.", "Create the auto-mapped copy under a new name.", "Accept the open-project prompt only after saving the current LiveProfessor project."]), _callout("No CTRL2 in the source project?", "The bridge automatically adds its embedded EC4 template to the copy. The source file is never modified."), _p("AutoMap first reuses active assignments and manual presets. Custom order is preserved per instance and then reused as the plugin-type profile. Learned pushes are preserved too; when the matching rotary is free, it receives the same parameter so the EC4 can display its label."), _callout("Completely unknown plugin", "The .rack2 file stores parameter numbers and values, not parameter names. Without an existing profile, AutoMap keeps technical order. An Output already placed on rotary 16 stays there; it is not guessed without a reliable name."), _p("If mappings replace one another after manual Learn operations, analyze the project and click <b>Repair mappings</b>. The bridge creates a new copy, always keeps active assignments authoritative, restores only missing assignments and synchronizes shared presets. Plugins, settings, snapshots and routing are not changed.")]),
        ("5. Daily controls", [_p("Hold Shift to display the shortcut guide on the EC4 before pressing an encoder."), _table(["EC4 action", "Result"], shortcuts, [62, 106])]),
        ("6. Banks, display and precision", [*_bullets(["A bank contains 16 parameters aligned with the 16 encoders.", "Unmapped encoders remain blank for a clearer display.", "A movement temporarily displays the full name and real value returned by LiveProfessor.", "Value feedback prevents jumps when plugin and controller states differ.", "Responsiveness settings are available under Tools > Connections and refresh."]), _callout("Recommended setting", "Start with the defaults. Reduce delays only while the local network and LiveProfessor remain stable; excessively low values may create unnecessary refresh traffic.")]),
        ("7. Learning any EC4 setup/group", [_p("You do not need to keep the original setup CC numbers. Learning stores the 16 rotaries and 16 pushes for the currently displayed setup/group."), *_bullets(["Open the desired EC4 page and click Use current setup/group.", "Click Learn rotaries + push.", "Turn rotaries 1 through 16 slightly, in order.", "Then press pushes 1 through 16 in the same order.", "Wait for the Mapping learned and saved confirmation."]), _p("Rotaries must send absolute CC values from 0 to 127 and pushes must send MIDI Notes. Shift+push gestures use a separate SysEx channel and are not part of this learning process.")]),
        ("8. Tray, log and updates", [*_bullets(["Minimize places the application in the Windows notification area when available.", "A click opens the window; right-click shows Start, Stop, Restart and Quit.", "Quit really closes the bridge and releases MIDI and OSC ports.", "The log is available under View > Log.", "Update checks can run manually or at startup."]), _p("Windows log: <font name='Courier'>%LOCALAPPDATA%\\EC4LiveProfessorBridge\\bridge.log</font>.")]),
        ("9. Troubleshooting", [_table(["Symptom", "Checks"], [["EC4 disconnected", "Close other MIDI applications, reconnect the EC4, refresh and select both ports again."], ["Port 8011 unavailable", "Close the other OSC receiver or choose the same new port pair in LiveProfessor and the bridge."], ["P001 / P002 instead of names", "Check Companion, the selected plugin Controller Map and UDP feedback."], ["Plugin does not move", "Check selection and Only If Selected; regenerate the copy after adding a plugin."], ["Slow values", "Check the local network, then adjust refresh delays gradually."], ["Push cannot be assigned", "Check GenericButton1 through 15 in the CTRL2 and whether the plugin exposes the parameter."]], [52, 116])]),
        ("10. Limits, backup and support", [*_bullets(["Back up projects and Controller Map presets before significant changes.", "Auto-mapping works on a copy and creates a timestamped backup when the destination exists.", "A plugin added after auto-mapping requires a new generation.", "Use an official LiveProfessor licence, trial or test licence.", "The bridge is not affiliated with or certified by Faderfox or Audiostrom."]), _callout("Project and downloads", "https://github.com/Mamat79/EC4-LiveProfessor-Bridge", MAGENTA), _p("Report a bug: https://github.com/Mamat79/EC4-LiveProfessor-Bridge/issues<br/>Releases: https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases"), _p("EC4 LiveProfessor Bridge - SiLeMI/O - By Mamat - -----[]---", "small")]),
    )
    return Locale("en", "EC4 LiveProfessor Bridge User Guide", "Installation, auto-mapping and daily operation", "English user guide", "Contents", sections)


def build(locale: Locale, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    story: list[object] = _cover(locale)
    story.append(_p(locale.contents, "h1"))
    for title, _ in locale.sections:
        story.append(_p(title, "toc"))
    story.append(PageBreak())
    for index, (title, content) in enumerate(locale.sections):
        story.append(_p(title, "h1"))
        story.extend(content)
        if index != len(locale.sections) - 1:
            story.append(PageBreak())
    GuideDocument(output, locale).build(story)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", choices=("fr", "en", "all"), default="all")
    args = parser.parse_args()
    if args.language in ("fr", "all"):
        build(_fr_locale(), FR_OUTPUT)
        print(FR_OUTPUT)
    if args.language in ("en", "all"):
        build(_en_locale(), EN_OUTPUT)
        print(EN_OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
