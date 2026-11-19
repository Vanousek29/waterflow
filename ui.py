"""
ui.py - prvky uživatelského rozhraní (tlačítka, ukazatele, panely)
"""

import pygame

import vzhled as V


def plynule(aktualni, cil, dt, rychlost=14.0):
    """Exponenciální přiblížení k cíli (pro plynulé animace)."""
    return aktualni + (cil - aktualni) * min(1.0, dt * rychlost)


def pruzne(t):
    """Easing s lehkým překmitem (0 -> 1)."""
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    c = 1.70158 * 1.3
    t -= 1
    return 1 + (c + 1) * t * t * t + c * t * t


def klavesa(povrch, text, pravy_stred, alfa=255):
    """Malá "klávesa" se zkratkou, např. [Mezerník]."""
    f = V.font("tucne", 11)
    w = max(20, f.size(text)[0] + 12)
    r = pygame.Rect(0, 0, w, 20)
    r.midright = pravy_stred
    V.zaobleny_obdelnik(povrch, (0, 0, 0, int(70 * alfa / 255)), r, 5, 1,
                        (255, 255, 255, int(40 * alfa / 255)))
    V.text(povrch, f, text, r.center, V.TEXT_TLUMENY, "center", alfa=alfa)
    return r


STYLY = {
    #              výplň              výplň při najetí        text            okraj
    "primarni": (V.AKCENT, (122, 216, 255), (8, 28, 44), None),
    "uspech": (V.ZELENA, (130, 236, 178), (8, 36, 22), None),
    "sekundarni": (V.PANEL_SVETLY, (34, 48, 68), V.TEXT, V.PANEL_OKRAJ),
    "duch": (None, (30, 44, 62), V.TEXT_TLUMENY, None),
}


class Tlacitko:
    def __init__(self, rect, text="", ikona=None, styl="sekundarni", zkratka=None,
                 velikost_pisma=16):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.ikona = ikona
        self.styl = styl
        self.zkratka = zkratka
        self.velikost_pisma = velikost_pisma
        self.aktivni = True
        self.viditelne = True
        self.zapnuto = False        # pro přepínací tlačítka
        self._najeti = 0.0
        self._stisk = False
        self._nad = False

    def aktualizuj(self, mys, dt):
        self._nad = self.viditelne and self.aktivni and self.rect.collidepoint(mys)
        self._najeti = plynule(self._najeti, 1.0 if self._nad else 0.0, dt, 18)

    @property
    def nad(self):
        return self._nad

    def udalost(self, e):
        """Vrátí True, když bylo tlačítko stisknuto (kliknutí)."""
        if not (self.viditelne and self.aktivni):
            self._stisk = False
            return False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            self._stisk = True
            return False
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            bylo = self._stisk
            self._stisk = False
            return bylo and self.rect.collidepoint(e.pos)
        return False

    def kresli(self, povrch):
        if not self.viditelne:
            return
        vypln, vypln_nad, barva_textu, okraj = STYLY[self.styl]
        if self.zapnuto:
            vypln, okraj = (38, 62, 92), V.AKCENT
        r = self.rect.move(0, 1 if self._stisk and self._nad else 0)
        alfa = 255 if self.aktivni else 90
        t = self._najeti
        if vypln is not None or t > 0.01:
            if vypln is None:
                barva = (*vypln_nad, int(255 * t))
            else:
                barva = (*V.mix(vypln, vypln_nad, t), alfa)
            if self.styl in ("primarni", "uspech") and self.aktivni:
                # měkký stín pod hlavním tlačítkem
                V.zaobleny_obdelnik(povrch, (0, 0, 0, 60), r.move(0, 3), 12)
            V.zaobleny_obdelnik(povrch, barva, r, 12, 1 if okraj else 0,
                                (*okraj, alfa) if okraj else None)
            if self.styl in ("primarni", "uspech"):
                # jemný odlesk nahoře
                lesk = pygame.Rect(r.x + 2, r.y + 2, r.w - 4, r.h // 2 - 2)
                V.zaobleny_obdelnik(povrch, (255, 255, 255, 34), lesk, 10)

        f = V.font("tucne", self.velikost_pisma)
        tw = f.size(self.text)[0] if self.text else 0
        iv = int(self.velikost_pisma * 1.15)
        mezera = 9 if self.text and self.ikona else 0
        zkr_w = 0
        if self.zkratka and r.w >= 150:
            zkr_w = max(20, V.font("tucne", 11).size(self.zkratka)[0] + 12) + 8
        celkem = (iv if self.ikona else 0) + mezera + tw
        x = r.centerx - celkem / 2 - zkr_w / 2
        cy = r.centery
        if self.ikona:
            ik = V.ikona(self.ikona, iv, barva_textu)
            if alfa < 255:
                ik = ik.copy()
                ik.set_alpha(alfa)
            povrch.blit(ik, (int(x), cy - iv // 2))
            x += iv + mezera
        if self.text:
            V.text(povrch, f, self.text, (x, cy), barva_textu, "midleft", alfa=alfa)
        if zkr_w:
            if self.styl in ("primarni", "uspech"):
                fz = V.font("tucne", 11)
                w = max(20, fz.size(self.zkratka)[0] + 12)
                kr = pygame.Rect(0, 0, w, 20)
                kr.midright = (r.right - 10, cy)
                V.zaobleny_obdelnik(povrch, (0, 0, 0, 40), kr, 5)
                V.text(povrch, fz, self.zkratka, kr.center, barva_textu, "center", alfa=200)
            else:
                klavesa(povrch, self.zkratka, (r.right - 10, cy), alfa)


def ukazatel(povrch, rect, podil, barva, pozadi=(8, 13, 21), nahled=None, barva_nahledu=None):
    """Vodorovný ukazatel (progress bar) se zaoblenými konci."""
    rect = pygame.Rect(rect)
    r = rect.h // 2
    pygame.draw.rect(povrch, pozadi, rect, border_radius=r)
    pygame.draw.rect(povrch, (36, 50, 70), rect, 1, border_radius=r)
    if nahled is not None and nahled > podil:
        w = int(rect.w * max(0.0, min(1.0, nahled)))
        if w > 2:
            pygame.draw.rect(povrch, barva_nahledu, (rect.x, rect.y, w, rect.h), border_radius=r)
    w = int(rect.w * max(0.0, min(1.0, podil)))
    if w > 2:
        pygame.draw.rect(povrch, barva, (rect.x, rect.y, w, rect.h), border_radius=r)
        lesk = pygame.Surface((w, max(1, rect.h // 2 - 1)), pygame.SRCALPHA)
        lesk.fill((255, 255, 255, 40))
        povrch.blit(lesk, (rect.x, rect.y + 1))


def karta(povrch, rect, barva=V.PANEL, alfa=240, okraj=V.PANEL_OKRAJ, r=16, stin=True):
    rect = pygame.Rect(rect)
    if stin:
        for k, a in ((10, 26), (6, 34), (3, 40)):
            V.zaobleny_obdelnik(povrch, (0, 0, 0, a), rect.inflate(k, k).move(0, k // 2 + 2), r + k // 2)
    V.zaobleny_obdelnik(povrch, (*barva, alfa), rect, r, 1, (*okraj, 255))


class Zprava:
    """Krátké oznámení (toast), které se objeví a zmizí."""

    def __init__(self):
        self.text = ""
        self.ikona = None
        self.zbyva = 0.0
        self.delka = 1.0
        self.barva = V.TEXT

    def ukaz(self, text, sekundy=2.4, ikona=None, barva=V.TEXT):
        self.text, self.ikona, self.barva = text, ikona, barva
        self.zbyva = self.delka = sekundy

    def skryj(self):
        self.zbyva = min(self.zbyva, 0.2)

    def aktualizuj(self, dt):
        self.zbyva = max(0.0, self.zbyva - dt)

    def kresli(self, povrch, stred_x, y):
        if self.zbyva <= 0:
            return
        uplynulo = self.delka - self.zbyva
        alfa = min(1.0, uplynulo / 0.15, self.zbyva / 0.3)
        posun = (1 - min(1.0, uplynulo / 0.2)) * -10
        f = V.font("tucne", 16)
        tw = f.size(self.text)[0]
        iw = 22 if self.ikona else 0
        rect = pygame.Rect(0, 0, tw + iw + 40, 40)
        rect.midtop = (stred_x, y + posun)
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        V.zaobleny_obdelnik(s, (*V.PANEL, 235), s.get_rect(), 20, 1, (*V.PANEL_OKRAJ, 255))
        x = 20
        if self.ikona:
            s.blit(V.ikona(self.ikona, 18, self.barva), (x, 11))
            x += iw
        V.text(s, f, self.text, (x, 20), self.barva, "midleft")
        s.set_alpha(int(255 * alfa))
        povrch.blit(s, rect)
