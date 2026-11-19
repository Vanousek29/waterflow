"""
svet.py - vykreslování herního světa (voda, nádrže, trubky, stroje, zóny)

Statické věci se kreslí jen jednou do dvou vrstev (pod vodou a nad vodou),
trubky hráče do další vrstvy, která se překreslí, jen když se trubky změní.
Každý snímek se pak kreslí jen voda a to, co se hýbe.
"""
import math
import random

import numpy as np
import pygame

import vzhled as V
from logika import SIRKA, VYSKA, TL_STENY, TL_TRUBKY, TL_SKLA, R_PORTALU

ZMENSENI = 2          # voda se počítá v polovičním rozlišení (rychlejší)
PODLAHA_Y = 686


# =====================================================================
# Pozadí
# =====================================================================
def vytvor_pozadi(sirka=SIRKA, vyska=VYSKA):
    pov = V.gradient_svisly(sirka, vyska, V.POZADI_HORE, V.POZADI_DOLE)
    mrizka = pygame.Surface((sirka, vyska), pygame.SRCALPHA)
    for i, x in enumerate(range(0, sirka, 20)):
        a = 22 if i % 5 == 0 else 9
        pygame.draw.line(mrizka, (*V.MRIZKA, a), (x, 0), (x, vyska))
    for i, y in enumerate(range(0, vyska, 20)):
        a = 22 if i % 5 == 0 else 9
        pygame.draw.line(mrizka, (*V.MRIZKA, a), (0, y), (sirka, y))
    pov.blit(mrizka, (0, 0))
    # vinětace - tmavší okraje
    vin = pygame.Surface((sirka // 8, vyska // 8), pygame.SRCALPHA)
    cx, cy = vin.get_width() / 2, vin.get_height() / 2
    for y in range(vin.get_height()):
        for x in range(vin.get_width()):
            d = math.hypot((x - cx) / cx, (y - cy) / cy * 0.9)
            vin.set_at((x, y), (0, 0, 0, int(min(1, max(0, d - 0.55) / 0.8) * 150)))
    pov.blit(pygame.transform.smoothscale(vin, (sirka, vyska)), (0, 0))
    return pov


def kresli_podlahu(povrch, x0=0, x1=SIRKA):
    """Podlaha s mřížkou kanálu (voda, která sem spadne, je pryč)."""
    pygame.draw.rect(povrch, (9, 14, 22), (x0, PODLAHA_Y, x1 - x0, VYSKA - PODLAHA_Y))
    pygame.draw.line(povrch, (52, 72, 98), (x0, PODLAHA_Y), (x1, PODLAHA_Y), 2)
    for x in range(x0 + 8, x1, 18):
        pygame.draw.rect(povrch, (4, 7, 12), (x, PODLAHA_Y + 5, 10, 6), border_radius=2)


# =====================================================================
# Voda (metaballs)
# =====================================================================
class KreslicVody:
    """
    Každá částice se nakreslí jako rozmazaná skvrna, skvrny se sčítají
    a pak se podle prahu určí, kde je voda. Tím se jednotlivé kuličky
    slijí do souvislé hladiny. Barva závisí na "hloubce" (hustotě skvrn).
    """

    def __init__(self):
        self.w, self.h = SIRKA // ZMENSENI, VYSKA // ZMENSENI
        self.pole = pygame.Surface((self.w, self.h))
        self.r = 7
        self.skvrna = pygame.Surface((self.r * 2, self.r * 2))
        for yy in range(self.r * 2):
            for xx in range(self.r * 2):
                d = math.hypot(xx - self.r + 0.5, yy - self.r + 0.5) / self.r
                v = max(0.0, 1 - d * d) ** 2
                c = int(135 * v)
                self.skvrna.set_at((xx, yy), (c, c, c))
        self.vystup = pygame.Surface((self.w, self.h), pygame.SRCALPHA)

        # tabulka: "množství vody" v pixelu (0-255) -> barva a průhlednost
        a = np.arange(256, dtype=np.float32)
        prah = 60
        self.lut_alfa = np.clip((a - prah) * 9, 0, 222).astype(np.uint8)
        t = np.clip((a - prah) / 170.0, 0, 1)[:, None]
        hladina = np.array([210, 247, 255], np.float32)     # světlý okraj / hladina
        stred = np.array([74, 194, 255], np.float32)
        hluboko = np.array([30, 118, 222], np.float32)      # tmavší hloubka
        t1 = np.clip(t / 0.14, 0, 1)
        t2 = np.clip((t - 0.14) / 0.86, 0, 1) ** 0.75
        barva = hladina + (stred - hladina) * t1
        barva = barva + (hluboko - barva) * t2
        self.lut_rgb = barva.astype(np.uint8)

    def kresli(self, povrch, voda, ox=0, oy=0):
        if voda.pocet == 0:
            return
        r = self.r
        pos = (voda.x / ZMENSENI).astype(int) - r
        x0 = max(0, int(pos[:, 0].min()))
        y0 = max(0, int(pos[:, 1].min()))
        x1 = min(self.w, int(pos[:, 0].max()) + 2 * r)
        y1 = min(self.h, int(pos[:, 1].max()) + 2 * r)
        if x1 <= x0 or y1 <= y0:
            return
        vyrez = pygame.Rect(x0, y0, x1 - x0, y1 - y0)
        pole = self.pole.subsurface(vyrez)
        pole.fill((0, 0, 0))
        pole.blits([(self.skvrna, (int(p[0]) - x0, int(p[1]) - y0), None, pygame.BLEND_RGB_ADD)
                    for p in pos], doreturn=False)

        a = pygame.surfarray.pixels_red(pole)
        vystup = self.vystup.subsurface(vyrez)
        pygame.surfarray.pixels3d(vystup)[:] = self.lut_rgb[a]
        pygame.surfarray.pixels_alpha(vystup)[:] = self.lut_alfa[a]
        del a
        velky = pygame.transform.smoothscale(vystup, (vyrez.w * ZMENSENI, vyrez.h * ZMENSENI))
        povrch.blit(velky, (x0 * ZMENSENI + ox, y0 * ZMENSENI + oy))

        # pěna / odlesky na rychlých částicích
        rych = voda.rychlost()
        for p in voda.x[rych > 3.9][::3]:
            povrch.fill((225, 245, 255), (int(p[0]) + ox, int(p[1]) + oy, 2, 2))


# =====================================================================
# Efekty (částice na ozdobu, nemají vliv na hru)
# =====================================================================
class Efekty:
    def __init__(self):
        self.castice = []   # [x, y, vx, vy, zivot, max_zivot, barva, velikost, gravitace]

    def odtok(self, body):
        for p in body[::2]:
            for _ in range(2):
                a = random.uniform(0, math.tau)
                s = random.uniform(0.3, 1.4)
                self.castice.append([p[0], p[1], math.cos(a) * s, math.sin(a) * s - 0.4,
                                     0.0, random.uniform(0.25, 0.5), V.ODTOK, 2, 0.0])

    def konfety(self, x, y, pocet=90):
        barvy = [V.ZLATA, V.AKCENT, V.ZELENA, V.MED_SVETLA, V.PORTAL_VSTUP, (255, 255, 255)]
        for _ in range(pocet):
            a = random.uniform(-math.pi * 0.95, -math.pi * 0.05)
            s = random.uniform(3, 9)
            self.castice.append([x, y, math.cos(a) * s, math.sin(a) * s, 0.0,
                                 random.uniform(1.2, 2.2), random.choice(barvy),
                                 random.choice((3, 4, 5)), 0.18])

    def aktualizuj(self, dt):
        nove = []
        for c in self.castice:
            c[4] += dt
            if c[4] < c[5]:
                c[0] += c[2]
                c[1] += c[3]
                c[3] += c[8]
                c[2] *= 0.985
                nove.append(c)
        self.castice = nove

    def kresli(self, povrch):
        for x, y, _, _, z, mz, barva, vel, g in self.castice:
            t = 1 - z / mz
            if g:   # konfeta - otáčející se obdélníček
                w = max(1, int(vel * abs(math.sin(z * 9 + x))))
                pygame.draw.rect(povrch, barva, (int(x), int(y), w, vel))
            else:
                r = max(1, int(vel * t + 0.5))
                pygame.draw.circle(povrch, V.mix(barva, (255, 255, 255), 0.3), (int(x), int(y)), r)


# =====================================================================
# Kreslení objektů
# =====================================================================
def kresli_trubku(povrch, body, styl="normal"):
    """Měděná trubka podél lomené čáry."""
    if styl == "chyba":
        okraj, telo, svetlo = (90, 20, 28), V.CERVENA, (255, 170, 170)
    elif styl == "nahled":
        okraj, telo, svetlo = V.MED_TMAVA, V.mix(V.MED, (255, 255, 255), 0.15), V.MED_SVETLA
    elif styl == "smazat":
        okraj, telo, svetlo = (90, 20, 28), V.mix(V.MED, V.CERVENA, 0.6), (255, 200, 190)
    else:
        okraj, telo, svetlo = V.MED_TMAVA, V.MED, V.MED_SVETLA
    V.aa_lomenka(povrch, okraj, body, TL_TRUBKY + 3)
    V.aa_lomenka(povrch, telo, body, TL_TRUBKY)
    for a, b in zip(body, body[1:]):
        a2, b2 = V.svetla_strana(a, b, 1.6)
        V.aa_kapsle(povrch, svetlo, a2, b2, 2)
    # koncovky (příruby)
    for p in (body[0], body[-1]):
        V.aa_kruh(povrch, okraj, p, TL_TRUBKY / 2 + 2.5)
        V.aa_kruh(povrch, V.mix(telo, (0, 0, 0), 0.12), p, TL_TRUBKY / 2 + 1)
        V.aa_kruh(povrch, svetlo, (p[0] - 1, p[1] - 1), 1.5)


def kresli_stenu(povrch, a, b, barva=V.OCEL, svetla=V.OCEL_SVETLA, tmava=V.OCEL_TMAVA, tl=TL_STENY):
    V.aa_kapsle(povrch, tmava, a, b, tl + 3)
    V.aa_kapsle(povrch, barva, a, b, tl)
    a2, b2 = V.svetla_strana(a, b, tl * 0.22)
    V.aa_kapsle(povrch, svetla, a2, b2, max(2, tl * 0.28))


def kresli_stin(povrch, a, b, tl, alfa=70):
    dx, dy = V.STIN_POSUN
    V.aa_kapsle(povrch, (0, 0, 0, alfa), (a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy), tl + 2)


def sraf(povrch, rect, barva, krok=14, alfa=36):
    """Šrafovaná oblast (zákaz kreslení)."""
    x, y, w, h = map(int, rect)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((*barva, 14))
    for k in range(-h, w, krok):
        pygame.draw.line(s, (*barva, alfa), (k, h), (k + h, 0), 3)
    V.carkovany_obdelnik(s, (*barva, 150), (1, 1, w - 2, h - 2), 9, 6, 2)
    povrch.blit(s, (x, y))
    if w >= 46 and h >= 46:
        # ikonka "zákaz tužky"
        ik = V.ikona("tuzka", 18, (*barva, 190))
        povrch.blit(ik, (x + 10, y + 10))
        pygame.draw.circle(povrch, V.mix(barva, (0, 0, 0), 0.1), (x + 19, y + 19), 13, 2)
        pygame.draw.line(povrch, V.mix(barva, (0, 0, 0), 0.1), (x + 10, y + 28), (x + 28, y + 10), 2)


class KreslicSveta:
    def __init__(self):
        self.pozadi = vytvor_pozadi()
        self.voda = KreslicVody()
        self.efekty = Efekty()
        self._staticke_klic = None
        self._spodni = None
        self._horni = None
        self._trubky_klic = None
        self._trubky = None
        self._zare_cache = {}
        rng = random.Random(7)
        self._vitr_seminka = [(rng.random(), rng.random(), rng.uniform(0.6, 1.4)) for _ in range(60)]

    # ------------------------------------------------------------ statické vrstvy
    def _priprav_staticke(self, L):
        if self._staticke_klic is L:
            return
        self._staticke_klic = L
        d = L.d
        spodni = self.pozadi.copy()
        horni = pygame.Surface((SIRKA, VYSKA), pygame.SRCALPHA)

        kresli_podlahu(spodni)

        for r in d["zakaz"]:
            sraf(spodni, r, V.ZAKAZ)
        for r in d["odtoky"]:
            x, y, w, h = map(int, r)
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            for yy in range(h):
                t = yy / max(1, h - 1)
                pygame.draw.line(s, (*V.mix((70, 10, 30), (24, 4, 12), t), 200), (0, yy), (w, yy))
            maska = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(maska, (255, 255, 255, 255), maska.get_rect(), border_radius=8)
            s.blit(maska, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            pygame.draw.rect(s, (*V.ODTOK, 210), s.get_rect(), 2, border_radius=8)
            spodni.blit(s, (x, y))
        for (x, y, w, h, fx, fy) in d["vetraky"]:
            s = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
            s.fill((*V.VITR, 12))
            V.carkovany_obdelnik(s, (*V.VITR, 60), (1, 1, w - 2, h - 2), 4, 6, 2)
            spodni.blit(s, (x, y))

        # stíny všeho pevného
        stiny = pygame.Surface((SIRKA, VYSKA), pygame.SRCALPHA)
        for a in d["steny"]:
            kresli_stin(stiny, a[:2], a[2:], TL_STENY, 255)
        for a in L.usecky_nadrzi():
            kresli_stin(stiny, a[:2], a[2:], TL_STENY, 255)
        for g in d["sklenice"]:
            if not g[4]:
                gx, gy, gw, gh = g[:4]
                for a in [(gx, gy - gh, gx, gy), (gx, gy, gx + gw, gy), (gx + gw, gy, gx + gw, gy - gh)]:
                    kresli_stin(stiny, a[:2], a[2:], TL_SKLA, 255)
        stiny.set_alpha(60)
        spodni.blit(stiny, (0, 0))

        # vnitřek nádrží
        for (x, y, w, h) in d["nadrze"]:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            for yy in range(h):
                pygame.draw.line(s, (*V.mix((40, 58, 82), (22, 33, 48), yy / h), 230), (0, yy), (w, yy))
            spodni.blit(s, (x, y))

        # koleje posuvných desek
        for (x1, y1, x2, y2, osa, amp, _) in d["desky"]:
            if osa == "x":
                a, b = (min(x1, x2) - amp, (y1 + y2) / 2), (max(x1, x2) + amp, (y1 + y2) / 2)
            else:
                a, b = ((x1 + x2) / 2, min(y1, y2) - amp), ((x1 + x2) / 2, max(y1, y2) + amp)
            V.carkovana_cara(spodni, V.mix(V.DESKA, V.POZADI_DOLE, 0.55), a, b, 6, 6, 2)
            for p in (a, b):
                pygame.draw.circle(spodni, V.mix(V.DESKA, V.POZADI_DOLE, 0.4), p, 4, 2)
        # dráha mlýnků
        for (cx, cy, Ld, _) in d["mlynky"]:
            pocet = int(Ld * math.pi / 14)
            for k in range(pocet):
                a = k / pocet * math.tau
                pygame.draw.circle(spodni, V.mix(V.STROJ, V.POZADI_DOLE, 0.65),
                                   (cx + math.cos(a) * Ld / 2, cy + math.sin(a) * Ld / 2), 1.5)

        # ---- horní vrstva (nad vodou)
        for a in d["steny"]:
            kresli_stenu(horni, a[:2], a[2:])
        for (x, y, w, h) in d["nadrze"]:
            cx, o = x + w / 2, d["otvor"] / 2
            for a in [(x, y, x, y + h), (x + w, y, x + w, y + h),
                      (x, y + h, cx - o, y + h), (cx + o, y + h, x + w, y + h)]:
                kresli_stenu(horni, a[:2], a[2:], V.NADRZ, (190, 206, 224), V.OCEL_TMAVA)
            # nýty
            for yy in range(y + 14, y + h - 6, 22):
                for xx in (x, x + w):
                    pygame.draw.circle(horni, (70, 84, 104), (xx, yy), 2)
            # příruby nahoře
            for xx in (x, x + w):
                V.aa_kapsle(horni, V.OCEL_TMAVA, (xx - 7, y), (xx + 7, y), 7)
                V.aa_kapsle(horni, (190, 206, 224), (xx - 6, y), (xx + 6, y), 4)

        self._spodni = spodni
        self._horni = horni

    def _priprav_trubky(self, L):
        klic = (L, L.verze_tahu)
        if self._trubky_klic is not None and self._trubky_klic[0] is L and self._trubky_klic[1] == L.verze_tahu:
            return
        self._trubky_klic = klic
        s = pygame.Surface((SIRKA, VYSKA), pygame.SRCALPHA)
        stin = pygame.Surface((SIRKA, VYSKA), pygame.SRCALPHA)
        for t in L.tahy:
            for a, b in zip(t, t[1:]):
                kresli_stin(stin, a, b, TL_TRUBKY, 255)
        stin.set_alpha(70)
        s.blit(stin, (0, 0))
        for t in L.tahy:
            kresli_trubku(s, t)
        self._trubky = s

    # ------------------------------------------------------------ jednotlivé části
    def _kresli_odtoky(self, o, L, t):
        for (x, y, w, h) in L.d["odtoky"]:
            # šipky "sání" dolů
            krok = 26
            posun = (t * 22) % krok
            clip = o.get_clip()
            o.set_clip(pygame.Rect(x + 2, y + 2, w - 4, h - 4).clip(clip))
            for cx in range(int(x) + 22, int(x + w) - 10, 44):
                for k in range(-1, int(h / krok) + 2):
                    yy = y + k * krok + posun
                    pygame.draw.lines(o, V.mix(V.ODTOK, (40, 6, 16), 0.5), False,
                                      [(cx - 7, yy - 4), (cx, yy + 3), (cx + 7, yy - 4)], 2)
            o.set_clip(clip)
            if w >= 70 and h >= 26:
                V.text(o, V.font("tucne", 12), "ODTOK", (x + w / 2, y + h / 2),
                       V.mix(V.ODTOK, (255, 255, 255), 0.35), "center", alfa=200)

    def _kresli_vitr(self, o, L, t):
        for (x, y, w, h, fx, fy) in L.d["vetraky"]:
            sila = math.hypot(fx, fy) or 1
            ux, uy = fx / sila, fy / sila
            s = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
            delka = 26
            for (rx, ry, rr) in self._vitr_seminka[: max(8, int(w * h / 900))]:
                # pozice podél směru proudu se posouvá v čase
                if abs(ux) > abs(uy):
                    px = (rx * w + t * 160 * ux * rr) % (w + delka) - delka / 2
                    py = ry * h
                else:
                    px = rx * w
                    py = (ry * h + t * 160 * uy * rr) % (h + delka) - delka / 2
                pygame.draw.line(s, (*V.VITR, 70), (px - ux * delka / 2, py - uy * delka / 2),
                                 (px + ux * delka / 2, py + uy * delka / 2), 2)
            # šipky uprostřed
            cx, cy = w / 2, h / 2
            for k in (-1, 0, 1):
                bx, by = cx + ux * k * 18, cy + uy * k * 18
                faze = (math.sin(t * 5 - k * 1.2) + 1) / 2
                nx, ny = -uy, ux
                body = [(bx - ux * 7 + nx * 9, by - uy * 7 + ny * 9), (bx + ux * 3, by + uy * 3),
                        (bx - ux * 7 - nx * 9, by - uy * 7 - ny * 9)]
                pygame.draw.lines(s, (*V.VITR, int(60 + 120 * faze)), False, body, 3)
            o.blit(s, (x, y))

    def _zare(self, barva):
        if barva not in self._zare_cache:
            self._zare_cache[barva] = V.zare(R_PORTALU * 2, barva, 1.0)
        return self._zare_cache[barva]

    def _kresli_portaly(self, o, L, t, vrstva):
        """Vstup a výstup jednoho páru mají stejnou barvu; vstup vtahuje, výstup chrlí."""
        for i, (ax, ay, bx, by) in enumerate(L.d["portaly"]):
            c = V.PORTAL_BARVY[i % len(V.PORTAL_BARVY)]
            svetla = V.mix(c, (255, 255, 255), 0.45)
            if vrstva == 0:
                # spojnice - tečky putují od vstupu k výstupu
                n = max(2, int(math.dist((ax, ay), (bx, by)) / 16))
                for k in range(1, n):
                    f = k / n
                    jas = 0.18 + 0.32 * max(0.0, math.sin(t * 5 - f * 10))
                    pygame.draw.circle(o, V.mix(V.POZADI_DOLE, c, jas),
                                       (ax + (bx - ax) * f, ay + (by - ay) * f), 2)
                for (px, py), sila in (((ax, ay), 0.6), ((bx, by), 1.0)):
                    z = self._zare(c)
                    z.set_alpha(int(255 * sila))
                    o.blit(z, (px - z.get_width() / 2, py - z.get_height() / 2))
                V.aa_kruh(o, V.mix(c, (0, 0, 0), 0.82), (ax, ay), R_PORTALU - 2)
                V.aa_kruh(o, V.mix(c, (0, 0, 0), 0.55), (bx, by), R_PORTALU - 2)
                V.aa_kruh(o, V.mix(c, (255, 255, 255), 0.2), (bx, by), 7)
            else:
                for (px, py), smer in (((ax, ay), 1), ((bx, by), -1)):
                    r = R_PORTALU - 1
                    for k in range(3):
                        a0 = t * 3 * smer + k * math.tau / 3
                        pygame.draw.arc(o, c, (px - r, py - r, 2 * r, 2 * r), a0, a0 + 1.5, 3)
                    # spirála teček: dovnitř u vstupu, ven u výstupu
                    for k in range(7):
                        faze = (t * 0.9 + k / 7) % 1.0
                        rr = (1 - faze if smer == 1 else faze) * (R_PORTALU - 6)
                        a = k * math.tau / 7 + faze * 2.4 * smer
                        jas = 1 - faze if smer == -1 else faze
                        pygame.draw.circle(o, V.mix(c, svetla, jas),
                                           (px + math.cos(a) * rr, py + math.sin(a) * rr), 2)
                    if smer == 1:
                        V.aa_kruh(o, (10, 6, 18), (px, py), 5)

    def _kresli_sklenici_zadni(self, o, L):
        for (gx, gy, gw, gh), puvodni in zip(L.sklenice(), L.d["sklenice"]):
            s = pygame.Surface((int(gw), int(gh)), pygame.SRCALPHA)
            s.fill((170, 215, 250, 22))
            o.blit(s, (gx, gy - gh))
            if puvodni[4]:
                # pohyblivá sklenice nemá stín ve statické vrstvě
                for a in [(gx, gy - gh, gx, gy), (gx, gy, gx + gw, gy), (gx + gw, gy, gx + gw, gy - gh)]:
                    kresli_stin(o, a[:2], a[2:], TL_SKLA, 50)

    def _kresli_sklenici_predni(self, o, L, t, s_popisky=True):
        f_velke = V.font("tucne", 15)
        f_male = V.font("tucne", 11)
        for i, (gx, gy, gw, gh) in enumerate(L.sklenice()):
            obrys = [(gx, gy - gh), (gx, gy), (gx + gw, gy), (gx + gw, gy - gh)]
            V.aa_lomenka(o, (52, 78, 104), obrys, TL_SKLA + 3)
            V.aa_lomenka(o, V.SKLO, obrys, TL_SKLA - 1)
            # okraj (hrdlo)
            for xx, k in ((gx, -1), (gx + gw, 1)):
                V.aa_kapsle(o, (52, 78, 104), (xx, gy - gh), (xx + k * 5, gy - gh - 2), 6)
                V.aa_kapsle(o, V.SKLO, (xx, gy - gh), (xx + k * 5, gy - gh - 2), 3)
            # odlesk
            lesk = pygame.Surface((4, max(1, int(gh - 26))), pygame.SRCALPHA)
            lesk.fill((255, 255, 255, 70))
            o.blit(lesk, (gx + 7, gy - gh + 12))
            lesk2 = pygame.Surface((3, max(1, int(gh * 0.18))), pygame.SRCALPHA)
            lesk2.fill((255, 255, 255, 50))
            o.blit(lesk2, (gx + 14, gy - gh + 16))
            # stupnice
            for k in range(1, 5):
                yy = gy - gh * k / 5
                pygame.draw.line(o, (150, 185, 215), (gx + gw - 12, yy), (gx + gw - 4, yy), 2)

            if not s_popisky:
                continue
            # štítek s procenty nad sklenicí
            p = L.pocty[i] / L.celkem if L.celkem else 0
            cil = L.cil_sklenice / L.celkem if L.celkem else 0
            hotovo = L.pocty[i] >= L.cil_sklenice
            t1 = f"{int(p * 100)} %"
            t2 = f" / {int(round(cil * 100))} %"
            w1, w2 = f_velke.size(t1)[0], f_male.size(t2)[0]
            sirka = w1 + w2 + 22
            rect = pygame.Rect(0, 0, sirka, 26)
            rect.midbottom = (gx + gw / 2, gy - gh - 12)
            barva_okraje = V.ZELENA if hotovo else V.PANEL_OKRAJ
            V.zaobleny_obdelnik(o, (*V.PANEL, 225), rect, 13, 2, (*barva_okraje, 255))
            V.text(o, f_velke, t1, (rect.x + 11, rect.centery), V.ZELENA if hotovo else V.TEXT, "midleft")
            V.text(o, f_male, t2, (rect.x + 11 + w1, rect.centery + 1), V.TEXT_TLUMENY, "midleft")
            pygame.draw.polygon(o, barva_okraje, [(rect.centerx - 6, rect.bottom - 1),
                                                  (rect.centerx + 6, rect.bottom - 1),
                                                  (rect.centerx, rect.bottom + 6)])

    def _kresli_zaklopky(self, o, L, t):
        d = L.d
        for (x, y, w, h) in d["nadrze"]:
            cx, o2 = x + w / 2, d["otvor"] / 2
            if not L.pusteno:
                a, b = (cx - o2 + 2, y + h), (cx + o2 - 2, y + h)
                V.aa_kapsle(o, (90, 20, 28), a, b, TL_STENY + 1)
                V.aa_kapsle(o, V.CERVENA, a, b, TL_STENY - 3)
                V.aa_kapsle(o, (255, 160, 160), (a[0], a[1] - 2), (b[0], b[1] - 2), 2)
                # kolečko ventilu
                V.aa_kruh(o, (90, 20, 28), (cx, y + h + 11), 6)
                V.aa_kruh(o, V.CERVENA, (cx, y + h + 11), 4)
            else:
                for xx in (cx - o2 - 2, cx + o2 + 2):
                    V.aa_kruh(o, V.mix(V.CERVENA, (0, 0, 0), 0.3), (xx, y + h), 4)

    def _kresli_stroje(self, o, L):
        d = L.d
        for i, (cx, cy, Ld, _) in enumerate(d["mlynky"]):
            useky = L.mlynek(i)
            for a in useky:
                kresli_stin(o, a[:2], a[2:], TL_STENY, 50)
            for a in useky:
                kresli_stenu(o, a[:2], a[2:], V.STROJ, V.mix(V.STROJ, (255, 255, 255), 0.45), V.STROJ_TMAVY)
            V.aa_kruh(o, V.STROJ_TMAVY, (cx, cy), 11)
            V.aa_kruh(o, V.mix(V.STROJ, (255, 255, 255), 0.25), (cx, cy), 8)
            V.aa_kruh(o, V.STROJ_TMAVY, (cx, cy), 3)
        for a in L.usecky_desek():
            kresli_stin(o, a[:2], a[2:], TL_STENY, 50)
            kresli_stenu(o, a[:2], a[2:], V.DESKA, V.mix(V.DESKA, (255, 255, 255), 0.45), V.DESKA_TMAVA)

    # ------------------------------------------------------------ hlavní kreslení
    def kresli(self, o, L, t, kresleny=None, kresleny_ok=True, zvyrazneny=None, mys=None,
               popisky=True, efekty=True):
        """
        o        : povrch (aspoň 1000x700), svět se kreslí od (0, 0)
        L        : Level
        t        : čas pro animace (s)
        kresleny : právě kreslená trubka (seznam bodů) nebo None
        zvyrazneny : index trubky pod kurzorem (smazání pravým tlačítkem)
        mys      : pozice myši pro kurzor kreslení
        """
        self._priprav_staticke(L)
        self._priprav_trubky(L)
        o.blit(self._spodni, (0, 0))
        self._kresli_odtoky(o, L, t)
        self._kresli_vitr(o, L, t)
        self._kresli_portaly(o, L, t, 0)
        self._kresli_sklenici_zadni(o, L)

        self.voda.kresli(o, L.voda)

        o.blit(self._horni, (0, 0))
        self._kresli_zaklopky(o, L, t)
        self._kresli_stroje(o, L)
        o.blit(self._trubky, (0, 0))
        if zvyrazneny is not None and zvyrazneny < len(L.tahy):
            kresli_trubku(o, L.tahy[zvyrazneny], "smazat")
        if kresleny and len(kresleny) >= 2:
            kresli_trubku(o, kresleny, "nahled" if kresleny_ok else "chyba")
        self._kresli_portaly(o, L, t, 1)
        self._kresli_sklenici_predni(o, L, t, popisky)

        if efekty:
            if len(L.odtecene):
                self.efekty.odtok(L.odtecene)
            self.efekty.aktualizuj(1 / 60)
            self.efekty.kresli(o)

        if mys is not None and L.stav == "kresleni" and 0 <= mys[0] < SIRKA:
            ok = L.bod_povolen(mys)
            if ok:
                pygame.draw.circle(o, (255, 255, 255), mys, 5, 1)
                pygame.draw.circle(o, V.MED_SVETLA, mys, 2)
            else:
                pygame.draw.circle(o, V.CERVENA, mys, 9, 2)
                pygame.draw.line(o, V.CERVENA, (mys[0] - 6, mys[1] + 6), (mys[0] + 6, mys[1] - 6), 2)

    def nahled(self, L, sirka, vyska):
        """Zmenšený obrázek levelu pro výběr levelu."""
        s = pygame.Surface((SIRKA, VYSKA))
        self.kresli(s, L, 0.0, popisky=False, efekty=False)
        self._staticke_klic = None     # nenechávat v cache cizí level
        self._trubky_klic = None
        return pygame.transform.smoothscale(s, (sirka, vyska))
