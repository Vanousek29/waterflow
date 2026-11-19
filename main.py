"""
Vodní inženýr - hra se simulací vody
=====================================
Dostaň vodu z nádrže do sklenice pomocí trubek, které nakreslíš myší.
30 levelů v 5 kapitolách: základy, odtoky, stroje, vítr a portály.

Ovládání:
  Levé tlačítko + tažení   kreslení trubky (volnou rukou)
  Shift + tažení           rovná trubka
  Pravé tlačítko           smazání trubky
  MEZERNÍK                 pustit vodu
  R                        vrátit vodu zpět (trubky zůstanou)
  F                        zrychlit (když voda teče)
  Z  (Ctrl+Z)              zpět poslední trubku
  C                        smazat všechny trubky
  ESC                      výběr levelu / menu

Spuštění:  pip install pygame numpy   a pak   python main.py
Vývoj:     python overeni.py   ověří, že všechny levely jdou vyřešit
"""
import json
import math
import os
import sys

import pygame

import ui
import vzhled as V
from levely import KAPITOLY, VSECHNY_LEVELY
from logika import Level, SIRKA, VYSKA, MIN_DELKA_USECKY
from svet import KreslicSveta, kresli_podlahu, vytvor_pozadi

SOUBOR_POSTUPU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "postup.json")

PANEL_W = 260
OKNO_W, OKNO_H = SIRKA + PANEL_W, VYSKA


# =====================================================================
# Uložený postup
# =====================================================================
class Postup:
    """Hvězdy za jednotlivé levely (podle id). Level je odemčený, když před ním
    zůstal nejvýš jeden nevyřešený - jeden těžký level se tedy dá přeskočit."""

    def __init__(self, cesta):
        self.cesta = cesta
        self.mapa = {}
        try:
            with open(cesta, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("verze") == 2:
                self.mapa = {k: int(v) for k, v in data.get("hvezdy", {}).items()}
        except (OSError, ValueError, AttributeError):
            pass

    def uloz(self):
        try:
            with open(self.cesta, "w", encoding="utf-8") as f:
                json.dump({"verze": 2, "hvezdy": self.mapa}, f, indent=1)
        except OSError:
            pass

    def hvezdy(self, lid):
        return self.mapa.get(lid, 0)

    def zapis(self, lid, n):
        if n > self.hvezdy(lid):
            self.mapa[lid] = n
            self.uloz()
            return True
        return False

    def vyreseno(self, i):
        return self.hvezdy(VSECHNY_LEVELY[i]["id"]) > 0

    def odemceno(self, i):
        return sum(1 for j in range(i) if not self.vyreseno(j)) <= 1

    def dalsi(self):
        for i in range(len(VSECHNY_LEVELY)):
            if self.odemceno(i) and not self.vyreseno(i):
                return i
        return None

    def celkem(self):
        return sum(self.hvezdy(l["id"]) for l in VSECHNY_LEVELY)

    def vyreseno_celkem(self):
        return sum(1 for i in range(len(VSECHNY_LEVELY)) if self.vyreseno(i))


def kod_levelu(index):
    d = VSECHNY_LEVELY[index]
    k = d["kapitola"]
    c = KAPITOLY[k]["levely"].index(d) + 1
    return f"{k + 1}–{c}"


# =====================================================================
# Menu
# =====================================================================
DEMO = dict(
    nazev="demo", napoveda="",
    nadrze=[(560, 70, 150, 100)], otvor=40,
    sklenice=[(640, 680, 150, 130)],
    steny=[], inkoust=10000, cil=0.99, limit=1e9,
)
DEMO_TAHY = [
    [(520, 205), (860, 300)],
    [(960, 300), (930, 380), (700, 470)],
    [(600, 450), (640, 520)],
]


class ScenaMenu:
    def __init__(self, hra):
        self.hra = hra
        self.demo_svet = KreslicSveta()
        self.demo_svet.pozadi = hra.pozadi.subsurface((PANEL_W, 0, SIRKA, VYSKA)).copy()
        self._novy_demo()
        x, y = 84, 420
        self.b_hrat = ui.Tlacitko((x, y, 330, 58), "Hrát", "play", "primarni", "Enter", 19)
        self.b_levely = ui.Tlacitko((x, y + 72, 330, 50), "Výběr levelu", "mrizka", "sekundarni", "L")
        self.b_konec = ui.Tlacitko((x, y + 134, 330, 46), "Konec", "vypnout", "duch", "Esc")
        self.tlacitka = [self.b_hrat, self.b_levely, self.b_konec]
        # přechod z pozadí do ukázky, aby byl nadpis čitelný
        self.zavoj = pygame.Surface((760, OKNO_H), pygame.SRCALPHA)
        for x in range(760):
            t = x / 760
            a = int(235 * (1 - t) ** 1.6)
            pygame.draw.line(self.zavoj, (*V.POZADI_HORE, a), (x, 0), (x, OKNO_H))
        self.t = 0.0

    def _novy_demo(self):
        self.demo = Level(DEMO)
        for t in DEMO_TAHY:
            self.demo.pridej_tah(t)
        self.demo_cekani = 0.9
        self.demo_konec = None

    def udalost(self, e):
        if self.b_hrat.udalost(e):
            self.hrat()
        elif self.b_levely.udalost(e):
            self.hra.prejdi(lambda: ScenaVyber(self.hra))
        elif self.b_konec.udalost(e):
            self.hra.konec()
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.hrat()
            elif e.key == pygame.K_l:
                self.hra.prejdi(lambda: ScenaVyber(self.hra))
            elif e.key == pygame.K_ESCAPE:
                self.hra.konec()

    def hrat(self):
        i = self.hra.postup.dalsi()
        if i is None:
            self.hra.prejdi(lambda: ScenaVyber(self.hra))
        else:
            self.hra.prejdi(lambda: ScenaHra(self.hra, i))

    def aktualizuj(self, dt):
        self.t += dt
        mys = pygame.mouse.get_pos()
        for b in self.tlacitka:
            b.aktualizuj(mys, dt)
        self.hra.kurzor("ruka" if any(b.nad for b in self.tlacitka) else "sipka")
        L = self.demo
        L.snimek()
        if not L.pusteno:
            self.demo_cekani -= dt
            if self.demo_cekani <= 0:
                L.pustit()
        elif self.demo_konec is None and (L.cas_od_pusteni > 9 or L.voda.pocet < L.celkem * 0.3):
            self.demo_konec = 1.6
        if self.demo_konec is not None:
            self.demo_konec -= dt
            if self.demo_konec <= 0:
                self._novy_demo()

    def kresli(self, o):
        o.blit(self.hra.pozadi, (0, 0))
        kresli_podlahu(o, 0, PANEL_W + 8)
        svet = o.subsurface((PANEL_W, 0, SIRKA, VYSKA))
        self.demo_svet.kresli(svet, self.demo, self.t, popisky=False)
        o.blit(self.zavoj, (0, 0))

        x = 80
        f_male = V.font("tucne", 13)
        V.text(o, f_male, "H R A   S E   S I M U L A C Í   V O D Y", (x + 4, 150), V.AKCENT)
        f_titul = V.font("nadpis", 96)
        V.text(o, f_titul, "VODNÍ", (x - 2, 168), V.TEXT, stin=True)
        V.text(o, f_titul, "INŽENÝR", (x - 2, 258), V.mix(V.AKCENT, (255, 255, 255), 0.25), stin=True)
        V.text(o, V.font("text", 19), "Nakresli trubky a dostaň vodu do sklenice.", (x + 2, 372),
               V.TEXT_TLUMENY)
        for b in self.tlacitka:
            b.kresli(o)

        p = self.hra.postup
        y = OKNO_H - 46
        o.blit(V.hvezda(18), (x + 4, y))
        V.text(o, V.font("tucne", 15), f"{p.celkem()} / {3 * len(VSECHNY_LEVELY)}", (x + 28, y + 9),
               V.TEXT, "midleft")
        V.text(o, V.font("text", 15), f"·   {p.vyreseno_celkem()} / {len(VSECHNY_LEVELY)} levelů",
               (x + 100, y + 9), V.TEXT_TLUMENY, "midleft")


# =====================================================================
# Výběr levelu
# =====================================================================
KARTA_W, KARTA_H = 354, 248
MRIZKA_X, MRIZKA_Y, MEZERA = (OKNO_W - 3 * KARTA_W - 2 * 18) // 2, 172, 18


class ScenaVyber:
    def __init__(self, hra, kapitola=None, zprava=None):
        self.hra = hra
        p = hra.postup
        if kapitola is None:
            i = p.dalsi()
            kapitola = VSECHNY_LEVELY[i]["kapitola"] if i is not None else 0
        self.kapitola = kapitola
        self.b_zpet = ui.Tlacitko((MRIZKA_X, 30, 46, 46), "", "vlevo", "sekundarni")
        sirka_tabu = (3 * KARTA_W + 2 * MEZERA - 4 * 12) // 5
        self.taby = [pygame.Rect(MRIZKA_X + k * (sirka_tabu + 12), 94, sirka_tabu, 60)
                     for k in range(len(KAPITOLY))]
        self.najeti_tab = [0.0] * len(KAPITOLY)
        self.najeti_karet = [0.0] * 6
        self.zprava = ui.Zprava()
        if zprava:
            self.zprava.ukaz(zprava, 4.0, "fajfka", V.ZELENA)
        self.t = 0.0

    def indexy(self):
        k = KAPITOLY[self.kapitola]
        return [VSECHNY_LEVELY.index(l) for l in k["levely"]]

    def rect_karty(self, n):
        sl, rad = n % 3, n // 3
        return pygame.Rect(MRIZKA_X + sl * (KARTA_W + MEZERA), MRIZKA_Y + rad * (KARTA_H + MEZERA),
                           KARTA_W, KARTA_H)

    def kapitola_odemcena(self, k):
        prvni = VSECHNY_LEVELY.index(KAPITOLY[k]["levely"][0])
        return self.hra.postup.odemceno(prvni)

    def udalost(self, e):
        if self.b_zpet.udalost(e):
            self.hra.prejdi(lambda: ScenaMenu(self.hra))
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for k, r in enumerate(self.taby):
                if r.collidepoint(e.pos):
                    if self.kapitola_odemcena(k):
                        self.kapitola = k
                    else:
                        self.zamceno()
            for n, i in enumerate(self.indexy()):
                if self.rect_karty(n).collidepoint(e.pos):
                    if self.hra.postup.odemceno(i):
                        self.hra.prejdi(lambda i=i: ScenaHra(self.hra, i))
                    else:
                        self.zamceno()
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.hra.prejdi(lambda: ScenaMenu(self.hra))
            elif e.key in (pygame.K_RIGHT, pygame.K_TAB):
                k = min(len(KAPITOLY) - 1, self.kapitola + 1)
                if self.kapitola_odemcena(k):
                    self.kapitola = k
                elif k != self.kapitola:
                    self.zamceno()
            elif e.key == pygame.K_LEFT:
                self.kapitola = max(0, self.kapitola - 1)

    def zamceno(self):
        self.zprava.ukaz("Nejdřív vyřeš předchozí levely.", 2.2, "zamek", V.TEXT_TLUMENY)

    def aktualizuj(self, dt):
        self.t += dt
        mys = pygame.mouse.get_pos()
        self.b_zpet.aktualizuj(mys, dt)
        self.zprava.aktualizuj(dt)
        ruka = self.b_zpet.nad
        for k, r in enumerate(self.taby):
            nad = r.collidepoint(mys) and self.kapitola_odemcena(k)
            ruka |= nad and k != self.kapitola
            self.najeti_tab[k] = ui.plynule(self.najeti_tab[k], 1.0 if nad else 0.0, dt, 16)
        for n, i in enumerate(self.indexy()):
            nad = self.rect_karty(n).collidepoint(mys) and self.hra.postup.odemceno(i)
            ruka |= nad
            self.najeti_karet[n] = ui.plynule(self.najeti_karet[n], 1.0 if nad else 0.0, dt, 16)
        self.hra.kurzor("ruka" if ruka else "sipka")

    def kresli(self, o):
        p = self.hra.postup
        o.blit(self.hra.pozadi, (0, 0))
        self.b_zpet.kresli(o)
        V.text(o, V.font("nadpis", 38), "Výběr levelu", (MRIZKA_X + 64, 29), V.TEXT)

        # celkem hvězd
        f = V.font("tucne", 17)
        txt = f"{p.celkem()} / {3 * len(VSECHNY_LEVELY)}"
        w = f.size(txt)[0] + 58
        r = pygame.Rect(0, 0, w, 40)
        r.topright = (OKNO_W - MRIZKA_X, 33)
        V.zaobleny_obdelnik(o, (*V.PANEL, 230), r, 20, 1, (*V.PANEL_OKRAJ, 255))
        o.blit(V.hvezda(22), (r.x + 14, r.y + 9))
        V.text(o, f, txt, (r.x + 44, r.centery), V.TEXT, "midleft")

        # záložky kapitol
        for k, rt in enumerate(self.taby):
            kap = KAPITOLY[k]
            odem = self.kapitola_odemcena(k)
            vybrana = k == self.kapitola
            t = self.najeti_tab[k]
            barva = V.PANEL_SVETLY if vybrana else V.mix(V.PANEL, V.PANEL_SVETLY, t)
            V.zaobleny_obdelnik(o, (*barva, 235), rt, 12, 1,
                                (*(kap["barva"] if vybrana else V.PANEL_OKRAJ), 255))
            if vybrana:
                pygame.draw.rect(o, kap["barva"], (rt.x + 14, rt.bottom - 4, rt.w - 28, 3), border_radius=2)
            alfa = 255 if odem else 110
            c = pygame.Rect(rt.x + 12, rt.y + 12, 22, 22)
            pygame.draw.rect(o, V.mix(kap["barva"], V.PANEL, 0.2 if odem else 0.7), c, border_radius=6)
            if odem:
                V.text(o, V.font("tucne", 13), str(k + 1), c.center, V.PANEL, "center")
            else:
                o.blit(V.ikona("zamek", 14, V.PANEL), (c.x + 4, c.y + 4))
            V.text(o, V.font("tucne", 16), kap["nazev"], (c.right + 9, c.centery), V.TEXT, "midleft",
                   alfa=alfa)
            hv = sum(p.hvezdy(l["id"]) for l in kap["levely"])
            ft = V.font("tucne", 12)
            V.text(o, ft, f"{hv}/{3 * len(kap['levely'])}", (rt.right - 30, c.centery), V.TEXT_TLUMENY,
                   "midright", alfa=alfa)
            o.blit(V.hvezda(14, hv > 0), (rt.right - 26, c.centery - 7))
            V.text(o, V.font("text", 12), kap["popis"], (rt.x + 12, rt.y + 40), V.TEXT_SLABY, "midleft",
                   alfa=alfa)

        # karty levelů
        vygenerovano = False
        for n, i in enumerate(self.indexy()):
            d = VSECHNY_LEVELY[i]
            rc = self.rect_karty(n)
            t = self.najeti_karet[n]
            rc = rc.move(0, -int(4 * t))
            odem = p.odemceno(i)
            nahled = self.hra.nahledy.get(d["id"])
            if nahled is None and not vygenerovano:
                nahled = self.hra.nahled(d)
                vygenerovano = True
            ui.karta(o, rc, V.PANEL, 255, V.PANEL_OKRAJ, 14, stin=True)
            if nahled is not None:
                o.blit(nahled, rc)
            # spodní pruh s názvem
            o.blit(self.hra.prouzek, (rc.x, rc.bottom - self.hra.prouzek.get_height()))
            if not odem:
                o.blit(self.hra.zamceno, rc)
                o.blit(V.ikona("zamek", 34, V.TEXT_TLUMENY), (rc.centerx - 17, rc.centery - 34))
                V.text(o, V.font("tucne", 14), "Zamčeno", (rc.centerx, rc.centery + 14), V.TEXT_TLUMENY,
                       "center")
            barva_kap = KAPITOLY[self.kapitola]["barva"]
            barva_okraje = barva_kap if t > 0.05 else V.PANEL_OKRAJ
            V.zaobleny_obdelnik(o, (0, 0, 0, 0), rc, 14, 2 if t > 0.05 else 1, (*barva_okraje, 255))
            # štítek s číslem levelu
            fk = V.font("tucne", 13)
            kod = kod_levelu(i)
            st = pygame.Rect(rc.x + 12, rc.y + 12, fk.size(kod)[0] + 18, 24)
            V.zaobleny_obdelnik(o, (*V.PANEL, 225), st, 12, 1, (*V.mix(barva_kap, V.PANEL, 0.4), 255))
            V.text(o, fk, kod, st.center, barva_kap, "center", alfa=255 if odem else 140)
            V.text(o, V.font("tucne", 19), d["nazev"], (rc.x + 16, rc.bottom - 22), V.TEXT, "midleft",
                   alfa=255 if odem else 130)
            if odem:
                h = p.hvezdy(d["id"])
                for s in range(3):
                    o.blit(V.hvezda(20, s < h), (rc.right - 82 + s * 23, rc.bottom - 32))
        self.zprava.kresli(o, OKNO_W // 2, OKNO_H - 70)


# =====================================================================
# Hra
# =====================================================================
class ScenaHra:
    def __init__(self, hra, index):
        self.hra = hra
        self.index = index
        self.data = VSECHNY_LEVELY[index]
        self.kap = KAPITOLY[self.data["kapitola"]]
        self.L = Level(self.data, index + 1)
        self.kresleny = None
        self.rovne = False
        self.blokovano = False
        self.rychle = False
        self.zprava = ui.Zprava()
        self.uvod_t = 0.0
        self.konec_t = 0.0
        self.ulozene_hvezdy = 0
        self.puvodni_hvezdy = hra.postup.hvezdy(self.data["id"])
        hra.svet.efekty.castice.clear()

        px, pw = SIRKA + 22, PANEL_W - 44
        polovina = (pw - 10) // 2
        self.b_pustit = ui.Tlacitko((px, 506, pw, 56), "Pustit vodu", "play", "primarni", "Mezerník", 17)
        self.b_znovu = ui.Tlacitko((px, 506, pw, 56), "Zkusit znovu", "restart", "sekundarni", "R", 17)
        self.b_zpet = ui.Tlacitko((px, 574, polovina, 44), "Zpět", "zpet", "sekundarni", None, 15)
        self.b_smazat = ui.Tlacitko((px + polovina + 10, 574, polovina, 44), "Smazat", "kos",
                                    "sekundarni", None, 15)
        self.b_rychle = ui.Tlacitko((px, 574, pw, 44), "Zrychlit", "rychle", "sekundarni", "F", 15)
        self.b_levely = ui.Tlacitko((px, 630, pw, 44), "Výběr levelu", "mrizka", "duch", "Esc", 15)
        self.panelova = [self.b_pustit, self.b_znovu, self.b_zpet, self.b_smazat, self.b_rychle,
                         self.b_levely]

        # tlačítka v okně konce levelu
        cx, cy = SIRKA // 2, VYSKA // 2
        self.o_znovu = ui.Tlacitko((cx - 200, cy + 104, 150, 50), "Znovu", "restart", "sekundarni", "R", 16)
        self.o_dalsi = ui.Tlacitko((cx - 38, cy + 104, 238, 50), "Další level", "vpravo", "uspech", "Enter", 17)
        self.o_levely = ui.Tlacitko((cx - 200, cy + 104, 150, 50), "Levely", "mrizka", "sekundarni", "Esc", 16)
        self.o_upravit = ui.Tlacitko((cx - 38, cy + 104, 238, 50), "Upravit trubky", "tuzka", "primarni",
                                     "R", 17)
        self.okenni = [self.o_znovu, self.o_dalsi, self.o_levely, self.o_upravit]

        f = V.font("text", 14)
        self.radky_napovedy = V.zalom(f, self.data["napoveda"], pw - 46)
        self.radky_nazvu = V.zalom(V.font("tucne", 22), self.data["nazev"], pw)
        self.posledni = index == len(VSECHNY_LEVELY) - 1
        if self.posledni:
            self.o_dalsi.text = "Dokončit"

    # ---------------------------------------------------------- ovládání
    def pustit(self):
        L = self.L
        if L.stav != "kresleni":
            return
        if not L.tahy:
            self.zprava.ukaz("Nejdřív nakresli aspoň jednu trubku.", 2.4, "tuzka", V.ZLATA)
            return
        L.pustit()
        self.kresleny = None
        self.zprava.skryj()

    def znovu(self):
        self.L.reset_vody()
        self.kresleny = None
        self.konec_t = 0.0
        self.rychle = False
        self.ulozene_hvezdy = 0
        self.hra.svet.efekty.castice.clear()

    def dalsi(self):
        if self.posledni:
            self.hra.prejdi(lambda: ScenaVyber(self.hra, self.data["kapitola"],
                                               "Všechny levely dokončené. Skvělá práce, inženýre!"))
        else:
            self.hra.prejdi(lambda: ScenaHra(self.hra, self.index + 1))

    def levely(self):
        self.hra.prejdi(lambda: ScenaVyber(self.hra, self.data["kapitola"]))

    def udalost(self, e):
        L = self.L
        konec = L.stav in ("vyhra", "prohra") and self.konec_t > 0.35
        if konec:
            if L.stav == "vyhra":
                if self.o_dalsi.udalost(e):
                    return self.dalsi()
                if self.o_znovu.udalost(e):
                    return self.znovu()
            else:
                if self.o_upravit.udalost(e):
                    return self.znovu()
                if self.o_levely.udalost(e):
                    return self.levely()
        if self.b_pustit.udalost(e):
            return self.pustit()
        if self.b_znovu.udalost(e):
            return self.znovu()
        if self.b_zpet.udalost(e):
            return L.zpet()
        if self.b_smazat.udalost(e):
            return L.smaz_vse()
        if self.b_rychle.udalost(e):
            self.rychle = not self.rychle
            return
        if self.b_levely.udalost(e):
            return self.levely()

        if e.type == pygame.KEYDOWN:
            ctrl = e.mod & pygame.KMOD_CTRL
            if e.key == pygame.K_ESCAPE:
                self.levely()
            elif e.key == pygame.K_SPACE:
                self.pustit()
            elif e.key == pygame.K_r:
                self.znovu()
            elif e.key == pygame.K_f and L.stav == "tece":
                self.rychle = not self.rychle
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and L.stav == "vyhra":
                self.dalsi()
            elif L.stav == "kresleni" and e.key == pygame.K_c and not ctrl:
                L.smaz_vse()
            elif L.stav == "kresleni" and e.key == pygame.K_z:
                L.zpet()

        if L.stav != "kresleni":
            self.kresleny = None
            return

        if e.type == pygame.MOUSEBUTTONDOWN and e.pos[0] < SIRKA:
            if e.button == 1:
                if L.bod_povolen(e.pos):
                    self.kresleny = [e.pos]
                    self.rovne = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    self.blokovano = False
                    self.uvod_t = max(self.uvod_t, 1.75)
                else:
                    self.zprava.ukaz("Sem se kreslit nesmí!", 1.8, "krizek", V.CERVENA)
            elif e.button == 3:
                L.smaz_tah_u(e.pos)

        elif e.type == pygame.MOUSEMOTION and self.kresleny and not self.rovne:
            posl = self.kresleny[-1]
            if math.dist(posl, e.pos) >= MIN_DELKA_USECKY and not self.blokovano:
                delka = L.inkoust_pouzit() + L.inkoust_pouzit([self.kresleny + [e.pos]])
                if delka > L.d["inkoust"]:
                    self.blokovano = True
                    self.zprava.ukaz("Došel inkoust!", 1.8, "tuzka", V.ORANZOVA)
                elif not L.usecka_povolena(posl, e.pos):
                    self.blokovano = True
                    self.zprava.ukaz("Sem se kreslit nesmí!", 1.8, "krizek", V.CERVENA)
                else:
                    self.kresleny.append(e.pos)

        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.kresleny:
            if self.rovne:
                tah = [self.kresleny[0], (min(e.pos[0], SIRKA), e.pos[1])]
                if math.dist(*tah) < 8:
                    pass
                elif L.inkoust_pouzit() + math.dist(*tah) > L.d["inkoust"]:
                    self.zprava.ukaz("Na tak dlouhou trubku nemáš inkoust!", 2.0, "tuzka", V.ORANZOVA)
                elif not L.usecka_povolena(*tah):
                    self.zprava.ukaz("Trubka vede přes zakázané místo!", 2.0, "krizek", V.CERVENA)
                else:
                    L.pridej_tah(tah)
            else:
                L.pridej_tah(self.kresleny)
            self.kresleny = None

    def nahled_tahu(self):
        """Body právě kreslené trubky a jestli je v pořádku."""
        if not self.kresleny:
            return None, True
        if not self.rovne:
            return self.kresleny, True
        mys = pygame.mouse.get_pos()
        body = [self.kresleny[0], (min(mys[0], SIRKA), mys[1])]
        L = self.L
        ok = L.usecka_povolena(*body) and L.inkoust_pouzit() + math.dist(*body) <= L.d["inkoust"]
        return body, ok

    # ---------------------------------------------------------- aktualizace
    def aktualizuj(self, dt):
        L = self.L
        L.snimek()
        if self.rychle and L.stav == "tece":
            L.snimek()
        if L.stav != "tece":
            self.rychle = False
        self.uvod_t += dt
        self.zprava.aktualizuj(dt)

        if L.stav in ("vyhra", "prohra"):
            if self.konec_t == 0.0 and L.stav == "vyhra":
                for gx, gy, gw, gh in L.sklenice():
                    self.hra.svet.efekty.konfety(gx + gw / 2, gy - gh, 70)
            self.konec_t += dt
        if L.stav == "vyhra":
            h = L.hvezdy()
            if h > self.ulozene_hvezdy:
                self.ulozene_hvezdy = h
                self.hra.postup.zapis(self.data["id"], h)

        kresleni = L.stav == "kresleni"
        tece = L.stav == "tece"
        self.b_pustit.viditelne = kresleni
        self.b_znovu.viditelne = not kresleni
        self.b_zpet.viditelne = self.b_smazat.viditelne = kresleni
        self.b_zpet.aktivni = self.b_smazat.aktivni = bool(L.tahy)
        self.b_rychle.viditelne = tece
        self.b_rychle.zapnuto = self.rychle
        konec = L.stav in ("vyhra", "prohra") and self.konec_t > 0.35
        self.o_znovu.viditelne = self.o_dalsi.viditelne = konec and L.stav == "vyhra"
        self.o_upravit.viditelne = self.o_levely.viditelne = konec and L.stav == "prohra"

        mys = pygame.mouse.get_pos()
        for b in self.panelova + self.okenni:
            b.aktualizuj(mys, dt)
        if any(b.nad for b in self.panelova + self.okenni):
            self.hra.kurzor("ruka")
        elif kresleni and mys[0] < SIRKA:
            self.hra.kurzor("krizek")
        else:
            self.hra.kurzor("sipka")

    # ---------------------------------------------------------- kreslení
    def kresli(self, o):
        L = self.L
        svet = o.subsurface((0, 0, SIRKA, VYSKA))
        mys = pygame.mouse.get_pos()
        v_svete = mys[0] < SIRKA
        body, ok = self.nahled_tahu()
        zvyrazneny = None
        if L.stav == "kresleni" and not self.kresleny and v_svete:
            zvyrazneny = L.tah_u(mys)
        self.hra.svet.kresli(svet, L, self.hra.cas, kresleny=body, kresleny_ok=ok,
                             zvyrazneny=zvyrazneny, mys=mys if v_svete else None)
        self.kresli_uvod(svet)
        self.zprava.kresli(svet, SIRKA // 2, 70)
        if L.stav in ("vyhra", "prohra"):
            self.kresli_konec(svet)
        self.kresli_panel(o)

    def kresli_uvod(self, o):
        t = self.uvod_t
        if t > 2.2 or self.L.stav != "kresleni":
            return
        alfa = min(1.0, t / 0.25, (2.2 - t) / 0.45)
        f1, f2 = V.font("tucne", 14), V.font("nadpis", 40)
        kod = f"LEVEL {kod_levelu(self.index)}"
        w = max(f1.size(kod)[0], f2.size(self.data["nazev"])[0]) + 80
        r = pygame.Rect(0, 0, w, 100)
        r.center = (SIRKA // 2, int(VYSKA * 0.45 + (1 - min(1.0, t / 0.3)) * 14))
        s = pygame.Surface(r.size, pygame.SRCALPHA)
        V.zaobleny_obdelnik(s, (*V.PANEL, 215), s.get_rect(), 20, 1, (*V.PANEL_OKRAJ, 255))
        pygame.draw.rect(s, self.kap["barva"], (w // 2 - 22, 0, 44, 3), border_radius=2)
        V.text(s, f1, kod, (w // 2, 28), self.kap["barva"], "center")
        V.text(s, f2, self.data["nazev"], (w // 2, 62), V.TEXT, "center")
        s.set_alpha(int(255 * alfa))
        o.blit(s, r)

    def kresli_panel(self, o):
        L, d = self.L, self.L.d
        x0 = SIRKA
        o.blit(self.hra.panel_pozadi, (x0, 0))
        px, pw = x0 + 22, PANEL_W - 44
        y = 24
        V.text(o, V.font("tucne", 12), f"KAPITOLA {self.data['kapitola'] + 1}  ·  {self.kap['nazev'].upper()}",
               (px, y), self.kap["barva"])
        y += 18
        V.text(o, V.font("nadpis", 46), kod_levelu(self.index), (px - 2, y), V.TEXT)
        y += 54
        for radek in self.radky_nazvu:
            V.text(o, V.font("tucne", 22), radek, (px, y), V.TEXT)
            y += 28
        y += 10

        # nápověda
        h = len(self.radky_napovedy) * 19 + 22
        V.zaobleny_obdelnik(o, V.PANEL_SVETLY, (px, y, pw, h), 12, 1, V.PANEL_OKRAJ)
        o.blit(V.ikona("zarovka", 18, V.ZLATA), (px + 12, y + 11))
        for i, radek in enumerate(self.radky_napovedy):
            V.text(o, V.font("text", 14), radek, (px + 38, y + 10 + i * 19), V.TEXT_TLUMENY)
        y += h + 22

        f_popis, f_hodnota = V.font("tucne", 13), V.font("tucne", 15)
        # inkoust
        limit = d["inkoust"]
        pouzito = L.inkoust_pouzit()
        body, _ = self.nahled_tahu()
        navic = L.inkoust_pouzit([body]) if body and len(body) >= 2 else 0.0
        zbyva = max(0.0, limit - pouzito - navic)
        podil = zbyva / limit
        V.text(o, f_popis, "Inkoust", (px, y), V.TEXT_TLUMENY)
        V.text(o, f_hodnota, f"{int(round(podil * 100))} %", (px + pw, y - 1),
               V.CERVENA if podil < 0.1 else V.TEXT, "topright")
        ui.ukazatel(o, (px, y + 22, pw, 10), podil, V.MED, nahled=max(0.0, limit - pouzito) / limit,
                    barva_nahledu=(120, 80, 52))
        y += 48

        # voda ve sklenici
        p = L.ve_sklenici / L.celkem if L.celkem else 0.0
        prahy = L.prahy_hvezd()
        hotovo = all(n >= L.cil_sklenice for n in L.pocty) and L.ve_sklenici >= L.cil_pocet
        V.text(o, f_popis, "Voda ve sklenici" if len(L.pocty) == 1 else "Voda ve sklenicích",
               (px, y), V.TEXT_TLUMENY)
        V.text(o, f_hodnota, f"{int(p * 100)} %", (px + pw, y - 1), V.ZELENA if hotovo else V.TEXT,
               "topright")
        bar = pygame.Rect(px, y + 22, pw, 10)
        ui.ukazatel(o, bar, p, V.ZELENA if hotovo else V.AKCENT)
        # značky cíle a hvězd
        for k, prah in enumerate(prahy):
            xx = bar.x + int(bar.w * prah)
            if k == 0:
                pygame.draw.line(o, V.TEXT, (xx, bar.y - 4), (xx, bar.bottom + 3), 2)
            else:
                pygame.draw.line(o, (60, 78, 102), (xx, bar.y + 2), (xx, bar.bottom - 2), 1)
            o.blit(V.hvezda(13, p >= prah - 1e-9), (xx - 6, bar.bottom + 5))
        y += 60
        if len(L.pocty) > 1:
            V.text(o, V.font("text", 13), f"Každá sklenice aspoň {int(round(d['cil'] / len(L.pocty) * 100))} %",
                   (px, y - 6), V.TEXT_SLABY)
            y += 16

        # čas
        if L.stav == "tece":
            zbyva_s = max(0.0, d["limit"] - L.cas_od_pusteni)
            V.text(o, f_popis, "Čas", (px, y), V.TEXT_TLUMENY)
            V.text(o, f_hodnota, f"{zbyva_s:.1f} s".replace(".", ","), (px + pw, y - 1),
                   V.CERVENA if zbyva_s < 5 else V.TEXT, "topright")
            ui.ukazatel(o, (px, y + 22, pw, 6), zbyva_s / d["limit"], V.TEXT_SLABY)
            y += 40
        elif L.stav == "kresleni" and y < 384:
            f = V.font("text", 13)
            V.text(o, V.font("tucne", 12), "OVLÁDÁNÍ", (px, 386), V.TEXT_SLABY)
            for i, (kl, popis) in enumerate((("Tažení myší", "nová trubka"), ("Shift + tažení", "rovná trubka"),
                                             ("Pravé tlačítko", "smazat trubku"),
                                             ("Z  /  C", "zpět  /  smazat vše"))):
                yy = 406 + i * 23
                V.text(o, V.font("tucne", 13), kl, (px, yy), V.TEXT_TLUMENY)
                V.text(o, f, popis, (px + pw, yy), V.TEXT_SLABY, "topright")

        for b in self.panelova:
            b.kresli(o)

    def kresli_konec(self, o):
        L = self.L
        t = self.konec_t
        vyhra = L.stav == "vyhra"
        ztmaveni = pygame.Surface((SIRKA, VYSKA), pygame.SRCALPHA)
        ztmaveni.fill((4, 8, 14, int(150 * min(1.0, t / 0.4))))
        o.blit(ztmaveni, (0, 0))
        if t < 0.15:
            return
        k = ui.pruzne(min(1.0, (t - 0.15) / 0.45))
        cx, cy = SIRKA // 2, VYSKA // 2
        karta = pygame.Rect(0, 0, 460, 344)
        karta.center = (cx, cy + int((1 - k) * 40))
        s = pygame.Surface((karta.w + 40, karta.h + 40), pygame.SRCALPHA)
        ui.karta(s, pygame.Rect(20, 20, karta.w, karta.h), V.PANEL, 245,
                 V.ZELENA if vyhra else V.mix(V.CERVENA, V.PANEL_OKRAJ, 0.4), 22)
        s.set_alpha(int(255 * min(1.0, (t - 0.15) / 0.25)))
        o.blit(s, karta.move(-20, -20))
        if k < 0.3:
            return
        a = int(255 * min(1.0, (t - 0.25) / 0.25))
        if vyhra:
            V.text(o, V.font("nadpis", 40), "Level splněn!", (cx, karta.y + 50), V.ZELENA, "center", alfa=a)
            h = L.hvezdy()
            for i in range(3):
                start = 0.45 + i * 0.28
                sx = cx + (i - 1) * 92
                sy = karta.y + 132 + (0 if i == 1 else 10)
                vel = 78 if i == 1 else 66
                prazdna = V.hvezda(vel, False)
                o.blit(prazdna, (sx - vel // 2, sy - vel // 2))
                if i < h and t > start:
                    m = ui.pruzne(min(1.0, (t - start) / 0.35))
                    v2 = max(1, int(vel * m))
                    hv = pygame.transform.smoothscale(V.hvezda(vel), (v2, v2))
                    o.blit(hv, (sx - v2 // 2, sy - v2 // 2))
            V.text(o, V.font("tucne", 18), f"Ve sklenici je {int(L.vysledek * 100)} % vody",
                   (cx, karta.y + 200), V.TEXT, "center", alfa=a)
            if h > self.puvodni_hvezdy and self.puvodni_hvezdy > 0:
                pozn, barva = "Nový rekord!", V.ZLATA
            elif h < 3:
                pozn, barva = f"Na další hvězdu potřebuješ {int(math.ceil(L.prahy_hvezd()[h] * 100))} %", \
                    V.TEXT_TLUMENY
            else:
                pozn, barva = "Perfektní!", V.ZLATA
            V.text(o, V.font("text", 15), pozn, (cx, karta.y + 226), barva, "center", alfa=a)
            self.o_znovu.kresli(o)
            self.o_dalsi.kresli(o)
        else:
            V.text(o, V.font("nadpis", 40), "Nepovedlo se", (cx, karta.y + 56), V.CERVENA, "center", alfa=a)
            o.blit(V.ikona("kapka", 44, V.mix(V.CERVENA, V.PANEL, 0.3)), (cx - 22, karta.y + 92))
            V.text(o, V.font("tucne", 18), L.duvod, (cx, karta.y + 170), V.TEXT, "center", alfa=a)
            V.text(o, V.font("text", 15), "Trubky ti zůstanou – stačí je upravit.", (cx, karta.y + 198),
                   V.TEXT_TLUMENY, "center", alfa=a)
            self.o_levely.kresli(o)
            self.o_upravit.kresli(o)


# =====================================================================
# Hlavní třída
# =====================================================================
KURZORY = {"sipka": pygame.SYSTEM_CURSOR_ARROW, "ruka": pygame.SYSTEM_CURSOR_HAND,
           "krizek": pygame.SYSTEM_CURSOR_CROSSHAIR}


class Hra:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Vodní inženýr")
        self.okno = pygame.display.set_mode((OKNO_W, OKNO_H))
        try:
            pygame.display.set_icon(V.ikona("kapka", 32, V.AKCENT))
        except pygame.error:
            pass
        self.hodiny = pygame.time.Clock()
        self.pozadi = vytvor_pozadi(OKNO_W, OKNO_H)
        self.panel_pozadi = V.gradient_svisly(PANEL_W, OKNO_H, (17, 25, 38), (11, 17, 26))
        pygame.draw.line(self.panel_pozadi, V.PANEL_OKRAJ, (0, 0), (0, OKNO_H))
        self.svet = KreslicSveta()
        self._kreslic_nahledu = KreslicSveta()
        self.nahledy = {}
        self.prouzek = pygame.Surface((KARTA_W, 64), pygame.SRCALPHA)
        for yy in range(64):
            pygame.draw.line(self.prouzek, (*V.PANEL, int(228 * min(1, yy / 38) ** 1.4)),
                             (0, yy), (KARTA_W, yy))
        self.zamceno = pygame.Surface((KARTA_W, KARTA_H), pygame.SRCALPHA)
        self.zamceno.fill((8, 12, 20, 175))
        self.postup = Postup(SOUBOR_POSTUPU)
        self.cas = 0.0
        self.scena = ScenaMenu(self)
        self._dalsi = None
        self._faze = None
        self._prechod = 0.0
        self._kurzor = None

    def nahled(self, data):
        L = Level(data)
        s = self._kreslic_nahledu.nahled(L, KARTA_W, KARTA_H)
        # zaoblené rohy
        maska = pygame.Surface((KARTA_W, KARTA_H), pygame.SRCALPHA)
        pygame.draw.rect(maska, (255, 255, 255, 255), maska.get_rect(), border_radius=14)
        vysl = pygame.Surface((KARTA_W, KARTA_H), pygame.SRCALPHA)
        vysl.blit(s, (0, 0))
        vysl.blit(maska, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        self.nahledy[data["id"]] = vysl
        return vysl

    def kurzor(self, typ):
        if typ != self._kurzor:
            self._kurzor = typ
            try:
                pygame.mouse.set_cursor(KURZORY[typ])
            except (pygame.error, TypeError):
                pass

    def prejdi(self, vytvor_scenu):
        if self._faze is None:
            self._dalsi = vytvor_scenu
            self._faze = "ven"
            self._prechod = 0.0

    def konec(self):
        pygame.quit()
        sys.exit()

    def krok(self, dt):
        """Jeden snímek hry: události, aktualizace, kreslení."""
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.konec()
            if self._faze is None:
                self.scena.udalost(e)
        self.cas += dt
        if self._faze == "ven":
            self._prechod = min(1.0, self._prechod + dt / 0.16)
            if self._prechod >= 1.0:
                self.scena = self._dalsi()
                self._faze = "dovnitr"
        elif self._faze == "dovnitr":
            self._prechod = max(0.0, self._prechod - dt / 0.22)
            if self._prechod <= 0.0:
                self._faze = None
        self.scena.aktualizuj(dt)
        self.scena.kresli(self.okno)
        if self._prechod > 0:
            z = pygame.Surface((OKNO_W, OKNO_H))
            z.fill((5, 9, 15))
            z.set_alpha(int(255 * (self._prechod ** 0.8)))
            self.okno.blit(z, (0, 0))

    def spust(self):
        while True:
            dt = self.hodiny.tick(60) / 1000.0
            self.krok(min(dt, 1 / 20))
            pygame.display.flip()


if __name__ == "__main__":
    Hra().spust()
