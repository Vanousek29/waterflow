"""
vzhled.py - barvy, fonty a vyhlazené (anti-aliased) kreslicí primitivy

Všechno, co se týká vzhledu a nezávisí na konkrétní scéně, je tady,
aby se dal styl hry upravovat na jednom místě.
"""
import math
import os

import pygame
from pygame import gfxdraw

# =====================================================================
# Paleta
# =====================================================================
POZADI_HORE = (13, 20, 31)
POZADI_DOLE = (21, 35, 52)
MRIZKA = (130, 180, 255)

PANEL = (14, 21, 32)
PANEL_SVETLY = (22, 32, 47)
PANEL_OKRAJ = (42, 60, 84)

TEXT = (234, 241, 249)
TEXT_TLUMENY = (146, 163, 186)
TEXT_SLABY = (92, 108, 130)

AKCENT = (70, 196, 255)          # voda / hlavní akce
AKCENT_TMAVY = (28, 116, 178)
ZLATA = (255, 204, 77)
ZELENA = (82, 222, 146)
CERVENA = (240, 86, 96)
ORANZOVA = (255, 158, 72)

MED = (206, 122, 62)             # trubky hráče
MED_SVETLA = (255, 196, 140)
MED_TMAVA = (96, 48, 24)

OCEL = (82, 98, 122)             # stěny
OCEL_SVETLA = (138, 158, 184)
OCEL_TMAVA = (24, 32, 44)

NADRZ = (120, 138, 162)
SKLO = (205, 228, 246)
STROJ = (66, 178, 158)           # mlýnky
STROJ_TMAVY = (20, 64, 58)
DESKA = (150, 122, 230)          # posuvné desky
DESKA_TMAVA = (48, 34, 92)
VITR = (176, 226, 255)
PORTAL_VSTUP = (196, 110, 255)
PORTAL_VYSTUP = (72, 232, 186)
PORTAL_BARVY = [(196, 110, 255), (255, 176, 64), (72, 232, 186)]   # barva podle páru
ZAKAZ = (255, 160, 80)
ODTOK = (232, 64, 92)

STIN = (0, 0, 0)
STIN_POSUN = (4, 6)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def s_alfou(barva, alfa):
    return (*barva[:3], int(alfa))


# =====================================================================
# Fonty
# =====================================================================
_SLOZKA_FONTU = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
_FONTY = {
    # soubor ve Windows, záložní rodiny pro jiné systémy
    "nadpis": (["bahnschrift.ttf"], ["bahnschrift", "dejavusanscondensed", "dejavusans"]),
    "tucne": (["seguisb.ttf", "segoeuib.ttf"], ["dejavusans", "liberationsans", "freesans"]),
    "text": (["segoeui.ttf"], ["dejavusans", "liberationsans", "freesans"]),
    "cerne": (["seguibl.ttf", "segoeuib.ttf"], ["dejavusans", "liberationsans", "freesans"]),
}
_cache_fontu = {}


def font(druh, velikost):
    klic = (druh, velikost)
    if klic in _cache_fontu:
        return _cache_fontu[klic]
    soubory, rodiny = _FONTY[druh]
    f = None
    for s in soubory:
        cesta = os.path.join(_SLOZKA_FONTU, s)
        if os.path.exists(cesta):
            f = pygame.font.Font(cesta, velikost)
            break
    if f is None:
        for r in rodiny:
            cesta = pygame.font.match_font(r, bold=druh in ("tucne", "cerne"))
            if cesta:
                f = pygame.font.Font(cesta, velikost)
                break
    if f is None:
        f = pygame.font.Font(None, int(velikost * 1.3))
        f.set_bold(druh in ("tucne", "cerne"))
    _cache_fontu[klic] = f
    return f


def text(povrch, f, retezec, pozice, barva=TEXT, zarovnani="topleft", alfa=255, stin=False):
    """Vykreslí text; zarovnani je jméno atributu pygame.Rect (topleft, center, midright...)."""
    obr = f.render(retezec, True, barva)
    rect = obr.get_rect(**{zarovnani: (int(pozice[0]), int(pozice[1]))})
    if stin:
        s = f.render(retezec, True, (0, 0, 0))
        s.set_alpha(int(alfa * 0.55))
        povrch.blit(s, rect.move(0, 2))
    if alfa < 255:
        obr.set_alpha(int(alfa))
    povrch.blit(obr, rect)
    return rect


def zalom(f, retezec, sirka):
    """Rozdělí text na řádky, které se vejdou do dané šířky."""
    radky = []
    for odstavec in retezec.split("\n"):
        slova, radek = odstavec.split(" "), ""
        for s in slova:
            zkus = (radek + " " + s).strip()
            if f.size(zkus)[0] <= sirka or not radek:
                radek = zkus
            else:
                radky.append(radek)
                radek = s
        radky.append(radek)
    return radky


# =====================================================================
# Vyhlazené tvary
# =====================================================================
def aa_kruh(povrch, barva, stred, r):
    x, y, r = int(round(stred[0])), int(round(stred[1])), int(round(r))
    if r < 1:
        return
    gfxdraw.aacircle(povrch, x, y, r, barva)
    gfxdraw.filled_circle(povrch, x, y, r, barva)


def aa_kapsle(povrch, barva, a, b, tloustka):
    """Úsečka se zakulacenými konci, vyhlazená."""
    r = tloustka / 2
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L > 0.5:
        nx, ny = -dy / L * r, dx / L * r
        body = [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny),
                (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]
        gfxdraw.aapolygon(povrch, body, barva)
        gfxdraw.filled_polygon(povrch, body, barva)
    aa_kruh(povrch, barva, a, r - 0.5)
    aa_kruh(povrch, barva, b, r - 0.5)


def aa_lomenka(povrch, barva, body, tloustka):
    for a, b in zip(body, body[1:]):
        aa_kapsle(povrch, barva, a, b, tloustka)


def svetla_strana(a, b, posun):
    """Posune úsečku k "osvětlené" straně (světlo zleva shora)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    if nx + ny * 1.6 > 0:
        nx, ny = -nx, -ny
    return (a[0] + nx * posun, a[1] + ny * posun), (b[0] + nx * posun, b[1] + ny * posun)


def zaobleny_obdelnik(povrch, barva, rect, r, okraj=0, barva_okraje=None):
    """Zaoblený obdélník; podporuje průhlednou barvu (RGBA)."""
    rect = pygame.Rect(rect)
    if rect.w <= 0 or rect.h <= 0:
        return
    if len(barva) == 4 and barva[3] < 255:
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, barva, s.get_rect(), border_radius=r)
        if okraj and barva_okraje:
            pygame.draw.rect(s, barva_okraje, s.get_rect(), okraj, border_radius=r)
        povrch.blit(s, rect)
    else:
        pygame.draw.rect(povrch, barva, rect, border_radius=r)
        if okraj and barva_okraje:
            if len(barva_okraje) == 4:
                s = pygame.Surface(rect.size, pygame.SRCALPHA)
                pygame.draw.rect(s, barva_okraje, s.get_rect(), okraj, border_radius=r)
                povrch.blit(s, rect)
            else:
                pygame.draw.rect(povrch, barva_okraje, rect, okraj, border_radius=r)


def carkovany_obdelnik(povrch, barva, rect, delka=8, mezera=6, tloustka=2, posun=0.0):
    x, y, w, h = rect
    obvod = [((x, y), (x + w, y)), ((x + w, y), (x + w, y + h)),
             ((x + w, y + h), (x, y + h)), ((x, y + h), (x, y))]
    for a, b in obvod:
        carkovana_cara(povrch, barva, a, b, delka, mezera, tloustka, posun)


def carkovana_cara(povrch, barva, a, b, delka=8, mezera=6, tloustka=2, posun=0.0):
    L = math.dist(a, b)
    if L < 1:
        return
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    krok = delka + mezera
    s = -(posun % krok)
    while s < L:
        s0, s1 = max(0.0, s), min(L, s + delka)
        if s1 > s0:
            pygame.draw.line(povrch, barva, (a[0] + ux * s0, a[1] + uy * s0),
                             (a[0] + ux * s1, a[1] + uy * s1), tloustka)
        s += krok


def gradient_svisly(sirka, vyska, hore, dole):
    pov = pygame.Surface((sirka, vyska))
    for y in range(vyska):
        pygame.draw.line(pov, mix(hore, dole, y / max(1, vyska - 1)), (0, y), (sirka, y))
    return pov


def zare(polomer, barva, sila=1.0):
    """Měkká kruhová záře (pro portály, hvězdy...)."""
    s = pygame.Surface((polomer * 2, polomer * 2), pygame.SRCALPHA)
    for r in range(polomer, 0, -2):
        t = 1 - r / polomer
        pygame.draw.circle(s, (*barva[:3], int(255 * sila * t * t * 0.35)), (polomer, polomer), r)
    return s


# =====================================================================
# Ikony a hvězdy (kreslené ve 4x rozlišení a zmenšené = hladké hrany)
# =====================================================================
_cache_ikon = {}
SS = 4  # supersampling


def _hvezda_body(cx, cy, r, vnitrni=0.46, natoceni=-math.pi / 2):
    body = []
    for j in range(10):
        a = natoceni + j * math.pi / 5
        rr = r if j % 2 == 0 else r * vnitrni
        body.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    return body


def hvezda(velikost, plna=True, barva=ZLATA, prazdna_barva=(60, 74, 96)):
    klic = ("hvezda", velikost, plna, barva, prazdna_barva)
    if klic in _cache_ikon:
        return _cache_ikon[klic]
    V = velikost * SS
    s = pygame.Surface((V, V), pygame.SRCALPHA)
    c = V / 2
    body = _hvezda_body(c, c * 1.06, c * 0.96)
    if plna:
        pygame.draw.polygon(s, mix(barva, (120, 70, 0), 0.45), body)
        vnitrek = _hvezda_body(c, c * 1.06, c * 0.96 - SS * max(1, velikost / 14))
        pygame.draw.polygon(s, barva, vnitrek)
        # odlesk
        odl = _hvezda_body(c, c * 0.98, c * 0.5)
        pygame.draw.polygon(s, (*mix(barva, (255, 255, 255), 0.45), 120), odl[8:] + odl[:3])
    else:
        pygame.draw.polygon(s, prazdna_barva, body)
        vnitrek = _hvezda_body(c, c * 1.06, c * 0.96 - SS * max(1.5, velikost / 10))
        pygame.draw.polygon(s, mix(prazdna_barva, (0, 0, 0), 0.45), vnitrek)
    s = pygame.transform.smoothscale(s, (velikost, velikost))
    _cache_ikon[klic] = s
    return s


def ikona(jmeno, velikost, barva=TEXT):
    klic = (jmeno, velikost, barva)
    if klic in _cache_ikon:
        return _cache_ikon[klic]
    V = velikost * SS
    s = pygame.Surface((V, V), pygame.SRCALPHA)
    c = V / 2
    w = max(2, int(V * 0.11))      # tloušťka čáry
    col = barva

    def oblouk(stred, r, a0, a1, tl):
        # oblouk složený z kruhů (hladší než pygame.draw.arc)
        n = max(8, int(abs(a1 - a0) * r / (tl * 0.4)))
        for k in range(n + 1):
            a = a0 + (a1 - a0) * k / n
            pygame.draw.circle(s, col, (stred[0] + math.cos(a) * r, stred[1] + math.sin(a) * r), tl / 2)

    def cara(a, b, tl=w):
        pygame.draw.line(s, col, a, b, int(tl))
        pygame.draw.circle(s, col, a, tl / 2)
        pygame.draw.circle(s, col, b, tl / 2)

    if jmeno == "play":
        pygame.draw.polygon(s, col, [(V * 0.3, V * 0.18), (V * 0.82, V * 0.5), (V * 0.3, V * 0.82)])
    elif jmeno == "rychle":
        pygame.draw.polygon(s, col, [(V * 0.12, V * 0.22), (V * 0.5, V * 0.5), (V * 0.12, V * 0.78)])
        pygame.draw.polygon(s, col, [(V * 0.5, V * 0.22), (V * 0.88, V * 0.5), (V * 0.5, V * 0.78)])
    elif jmeno == "restart":
        oblouk((c, c), V * 0.32, -math.pi * 0.35, math.pi * 1.45, w)
        a = -math.pi * 0.35
        hx, hy = c + math.cos(a) * V * 0.32, c + math.sin(a) * V * 0.32
        pygame.draw.polygon(s, col, [(hx - V * 0.17, hy - V * 0.05), (hx + V * 0.06, hy - V * 0.2),
                                     (hx + V * 0.08, hy + V * 0.1)])
    elif jmeno == "zpet":
        oblouk((c + V * 0.04, c + V * 0.06), V * 0.27, -math.pi * 0.5, math.pi * 0.5, w)
        cara((c + V * 0.04, c - V * 0.21), (V * 0.3, c - V * 0.21))
        cara((c + V * 0.04, c + V * 0.33), (V * 0.36, c + V * 0.33))
        pygame.draw.polygon(s, col, [(V * 0.12, c - V * 0.21), (V * 0.34, c - V * 0.4),
                                     (V * 0.34, c - V * 0.02)])
    elif jmeno == "kos":
        cara((V * 0.2, V * 0.27), (V * 0.8, V * 0.27))
        cara((V * 0.4, V * 0.17), (V * 0.6, V * 0.17))
        pygame.draw.polygon(s, col, [(V * 0.26, V * 0.34), (V * 0.74, V * 0.34),
                                     (V * 0.68, V * 0.86), (V * 0.32, V * 0.86)])
        for xx in (0.42, 0.58):
            pygame.draw.line(s, (0, 0, 0, 0), (V * xx, V * 0.44), (V * xx, V * 0.76), max(2, w // 2))
    elif jmeno == "mrizka":
        for i in range(2):
            for j in range(2):
                pygame.draw.rect(s, col, (V * (0.17 + i * 0.36), V * (0.17 + j * 0.36), V * 0.3, V * 0.3),
                                 border_radius=int(V * 0.07))
    elif jmeno == "zamek":
        oblouk((c, V * 0.4), V * 0.18, math.pi, math.pi * 2, w)
        cara((c - V * 0.18, V * 0.4), (c - V * 0.18, V * 0.5))
        cara((c + V * 0.18, V * 0.4), (c + V * 0.18, V * 0.5))
        pygame.draw.rect(s, col, (V * 0.22, V * 0.46, V * 0.56, V * 0.4), border_radius=int(V * 0.08))
        pygame.draw.circle(s, (0, 0, 0, 0), (c, V * 0.63), V * 0.06)
    elif jmeno in ("vlevo", "vpravo"):
        k = -1 if jmeno == "vlevo" else 1
        cara((c - k * V * 0.12, V * 0.22), (c + k * V * 0.14, c), w * 1.2)
        cara((c + k * V * 0.14, c), (c - k * V * 0.12, V * 0.78), w * 1.2)
    elif jmeno == "fajfka":
        cara((V * 0.2, V * 0.52), (V * 0.42, V * 0.74), w * 1.3)
        cara((V * 0.42, V * 0.74), (V * 0.8, V * 0.28), w * 1.3)
    elif jmeno == "krizek":
        cara((V * 0.26, V * 0.26), (V * 0.74, V * 0.74), w * 1.2)
        cara((V * 0.74, V * 0.26), (V * 0.26, V * 0.74), w * 1.2)
    elif jmeno == "vypnout":
        oblouk((c, c + V * 0.04), V * 0.3, -math.pi * 0.28, math.pi * 1.28, w)
        cara((c, V * 0.12), (c, V * 0.48))
    elif jmeno == "zarovka":
        pygame.draw.circle(s, col, (c, V * 0.4), V * 0.25)
        pygame.draw.rect(s, col, (V * 0.38, V * 0.52, V * 0.24, V * 0.2))
        cara((V * 0.4, V * 0.8), (V * 0.6, V * 0.8), w)
    elif jmeno == "tuzka":
        pygame.draw.polygon(s, col, [(V * 0.66, V * 0.14), (V * 0.86, V * 0.34), (V * 0.36, V * 0.84),
                                     (V * 0.16, V * 0.64)])
        pygame.draw.polygon(s, col, [(V * 0.16, V * 0.64), (V * 0.36, V * 0.84), (V * 0.1, V * 0.9)])
    elif jmeno == "kapka":
        pygame.draw.circle(s, col, (c, V * 0.6), V * 0.26)
        pygame.draw.polygon(s, col, [(c, V * 0.1), (c - V * 0.245, V * 0.52), (c + V * 0.245, V * 0.52)])
    elif jmeno == "pauza":
        pygame.draw.rect(s, col, (V * 0.24, V * 0.18, V * 0.17, V * 0.64), border_radius=int(V * 0.05))
        pygame.draw.rect(s, col, (V * 0.59, V * 0.18, V * 0.17, V * 0.64), border_radius=int(V * 0.05))
    elif jmeno == "hodiny":
        oblouk((c, c), V * 0.34, 0, math.pi * 2, w)
        cara((c, c), (c, V * 0.3))
        cara((c, c), (V * 0.66, V * 0.6))
    s = pygame.transform.smoothscale(s, (velikost, velikost))
    _cache_ikon[klic] = s
    return s
