"""
logika.py - pravidla hry (bez kreslení, dá se testovat i bez okna)

Formát levelu (souřadnice v pixelech herního světa 1000 x 700):
  nadrze   : [(x, y, sirka, vyska)]          nádrže s vodou, otvor je uprostřed dna
  otvor    : šířka otvoru v nádrži
  sklenice : [(x, y_dno, sirka, vyska)]      nebo (x, y_dno, w, h, amplituda, rychlost)
             pro sklenici, která jezdí sem a tam (rychlost v rad/s)
  steny    : pevné překážky [(x1, y1, x2, y2)]
  zakaz    : oblasti, kam se nesmí kreslit [(x, y, w, h)]
  odtoky   : oblasti, kde voda zmizí [(x, y, w, h)]
  mlynky   : rotující lopatky [(stred_x, stred_y, delka, rychlost_rad_za_s)]
  desky    : posuvné desky [(x1, y1, x2, y2, osa 'x'/'y', amplituda, rychlost)]
  vetraky  : proudy vzduchu [(x, y, w, h, sila_x, sila_y)]  (px / krok^2, gravitace = 0.12)
  portaly  : [(vstup_x, vstup_y, vystup_x, vystup_y)]  voda vleze do vstupu a vyleze z výstupu
  inkoust  : kolik pixelů trubek smíš nakreslit
  cil      : kolik % vody musí být ve sklenicích (u více sklenic se dělí rovným dílem)
"""
import math
import numpy as np
from fyzika import Voda

SIRKA, VYSKA = 1000, 700
KROKY_ZA_SNIMEK = 3            # kolik fyzikálních kroků na jeden snímek (60 FPS)
DT = 1.0 / (60 * KROKY_ZA_SNIMEK)

TL_STENY = 10                  # tloušťky (px) pro kreslení i kolize
TL_TRUBKY = 8
TL_SKLA = 6
ROZESTUP = 6.0                 # rozestup částic při vytvoření vody
LIMIT_CASU = 25.0              # s po puštění vody, pak prohra
MIN_DELKA_USECKY = 12          # při kreslení volnou rukou
R_PORTALU = 24                 # poloměr portálu

VYCHOZI = dict(
    nazev="", napoveda="", otvor=40,
    steny=(), zakaz=(), odtoky=(), mlynky=(), desky=(), vetraky=(), portaly=(),
    inkoust=1000, cil=0.5, limit=LIMIT_CASU,
)


def priprav_level(data):
    """Doplní výchozí hodnoty a sjednotí formát sklenic."""
    d = dict(VYCHOZI)
    d.update(data)
    for k in ("steny", "zakaz", "odtoky", "mlynky", "desky", "vetraky", "portaly", "nadrze"):
        d[k] = [tuple(v) for v in d.get(k, ())]
    skl = d["sklenice"]
    if skl and isinstance(skl[0], (int, float)):
        skl = [skl]
    d["sklenice"] = [tuple(s) + (0, 0) if len(s) == 4 else tuple(s) for s in skl]
    return d


def _bod_v_obdelniku(px, py, r, okraj=0):
    x, y, w, h = r[:4]
    return x - okraj <= px <= x + w + okraj and y - okraj <= py <= y + h + okraj


def _v_obdelniku(x, r):
    rx, ry, rw, rh = r[:4]
    return (x[:, 0] > rx) & (x[:, 0] < rx + rw) & (x[:, 1] > ry) & (x[:, 1] < ry + rh)


class Level:
    def __init__(self, data, cislo=0):
        self.d = priprav_level(data)
        self.cislo = cislo
        self.tahy = []                 # nakreslené trubky = seznamy bodů
        self.verze_tahu = 0            # zvýší se při každé změně trubek
        self._cache_klic = None
        self._cache = None
        self.reset_vody()

    # ------------------------------------------------------------ voda
    def reset_vody(self):
        self.cas = 0.0
        self.pusteno = False
        self.cas_od_pusteni = 0.0
        self.stav = "kresleni"         # kresleni / tece / vyhra / prohra
        self.duvod = ""
        self.dosazeno = False
        self.cas_dosazeni = 0.0
        self.cas_posledni_zmeny = 0.0
        self.max_ve_sklenici = 0
        self.ve_sklenici = 0
        self.pocty = [0] * len(self.d["sklenice"])
        self.vysledek = 0.0
        self.odtecene = np.zeros((0, 2), np.float32)   # kde voda právě zmizela (pro efekty)

        body = []
        okraj = TL_STENY / 2 + 4
        for n, (x, y, w, h) in enumerate(self.d["nadrze"]):
            x0, x1 = x + okraj, x + w - okraj
            y_dno = y + h - okraj
            radku = int((h - 2 * okraj) * 0.8 / ROZESTUP)
            sloupcu = int((x1 - x0) / ROZESTUP)
            rng = np.random.default_rng(1 + n)
            for r in range(radku):
                for s in range(sloupcu):
                    body.append((x0 + 2 + s * ROZESTUP + rng.uniform(-0.5, 0.5),
                                 y_dno - 2 - r * ROZESTUP))
        self.voda = Voda(body)
        self.celkem = len(body)
        self.cil_pocet = math.ceil(self.d["cil"] * self.celkem)
        n_skl = max(1, len(self.d["sklenice"]))
        self.cil_sklenice = math.ceil(self.d["cil"] * self.celkem / n_skl)

    def pustit(self):
        if self.stav == "kresleni":
            self.pusteno = True
            self.stav = "tece"

    # ------------------------------------------------------------ trubky
    def pridej_tah(self, body):
        if len(body) >= 2 and self.stav == "kresleni":
            self.tahy.append([tuple(map(float, p)) for p in body])
            self.verze_tahu += 1

    def zpet(self):
        if self.tahy and self.stav == "kresleni":
            self.tahy.pop()
            self.verze_tahu += 1

    def smaz_vse(self):
        if self.tahy and self.stav == "kresleni":
            self.tahy.clear()
            self.verze_tahu += 1

    def smaz_tah_u(self, p, dosah=14):
        best, bi = dosah, None
        for i, t in enumerate(self.tahy):
            for a, b in zip(t, t[1:]):
                d = _vzdalenost_k_usecce(p, a, b)
                if d < best:
                    best, bi = d, i
        if bi is not None and self.stav == "kresleni":
            self.tahy.pop(bi)
            self.verze_tahu += 1
            return True
        return False

    def tah_u(self, p, dosah=14):
        """Index trubky pod kurzorem (pro zvýraznění před smazáním)."""
        best, bi = dosah, None
        for i, t in enumerate(self.tahy):
            for a, b in zip(t, t[1:]):
                d = _vzdalenost_k_usecce(p, a, b)
                if d < best:
                    best, bi = d, i
        return bi

    # ------------------------------------------------------------ sklenice
    def sklenice(self):
        """Aktuální polohy sklenic [(x, y_dno, w, h)]."""
        out = []
        for (gx, gy, gw, gh, amp, rych) in self.d["sklenice"]:
            if amp:
                gx = gx + amp * math.sin(self.cas * rych)
            out.append((gx, gy, gw, gh))
        return out

    # ------------------------------------------------------------ úsečky
    def usecky_nadrzi(self):
        u = []
        for (x, y, w, h) in self.d["nadrze"]:
            cx = x + w / 2
            o = self.d["otvor"] / 2
            u += [(x, y, x, y + h), (x + w, y, x + w, y + h),
                  (x, y + h, cx - o, y + h), (cx + o, y + h, x + w, y + h)]
        return u

    def usecky_zaklopek(self):
        u = []
        for (x, y, w, h) in self.d["nadrze"]:
            cx = x + w / 2
            o = self.d["otvor"] / 2
            u.append((cx - o, y + h, cx + o, y + h))
        return u

    def usecky_sklenice(self):
        u = []
        for gx, gy, gw, gh in self.sklenice():
            u += [(gx, gy - gh, gx, gy), (gx, gy, gx + gw, gy), (gx + gw, gy, gx + gw, gy - gh)]
        return u

    def mlynek(self, i):
        cx, cy, L, rych = self.d["mlynky"][i]
        a = self.cas * rych
        dx, dy = math.cos(a) * L / 2, math.sin(a) * L / 2
        return [(cx - dx, cy - dy, cx + dx, cy + dy), (cx + dy, cy - dx, cx - dy, cy + dx)]

    def usecky_mlynku(self):
        u = []
        for i in range(len(self.d["mlynky"])):
            u += self.mlynek(i)
        return u

    def usecky_desek(self):
        u = []
        for (x1, y1, x2, y2, osa, amp, rych) in self.d["desky"]:
            o = amp * math.sin(self.cas * rych)
            if osa == "x":
                u.append((x1 + o, y1, x2 + o, y2))
            else:
                u.append((x1, y1 + o, x2, y2 + o))
        return u

    def usecky_tahu(self):
        u = []
        for t in self.tahy:
            for a, b in zip(t, t[1:]):
                u.append((a[0], a[1], b[0], b[1]))
        return u

    def _staticke_usecky(self):
        """Úsečky, které se během pouštění nehýbou (cache podle verze trubek)."""
        klic = (self.verze_tahu, self.pusteno)
        if self._cache_klic == klic:
            return self._cache
        segs, R = [], []
        rp = self.voda.polomer

        def pridej(seznam, tl):
            segs.extend(seznam)
            R.extend([tl / 2 + rp] * len(seznam))

        pridej(self.usecky_nadrzi(), TL_STENY)
        if not self.pusteno:
            pridej(self.usecky_zaklopek(), TL_STENY)
        pridej(self.d["steny"], TL_STENY)
        staticke_skl = [s for s in self.d["sklenice"] if not s[4]]
        for gx, gy, gw, gh, _, _ in staticke_skl:
            pridej([(gx, gy - gh, gx, gy), (gx, gy, gx + gw, gy), (gx + gw, gy, gx + gw, gy - gh)],
                   TL_SKLA)
        pridej(self.usecky_tahu(), TL_TRUBKY)
        self._cache_klic = klic
        self._cache = (segs, R)
        return self._cache

    def vsechny_usecky(self):
        segs, R = self._staticke_usecky()
        segs, R = list(segs), list(R)
        rp = self.voda.polomer
        for (gx, gy, gw, gh, amp, rych) in self.d["sklenice"]:
            if amp:
                gx = gx + amp * math.sin(self.cas * rych)
                segs += [(gx, gy - gh, gx, gy), (gx, gy, gx + gw, gy), (gx + gw, gy, gx + gw, gy - gh)]
                R += [TL_SKLA / 2 + rp] * 3
        dyn = self.usecky_mlynku() + self.usecky_desek()
        segs += dyn
        R += [TL_STENY / 2 + rp] * len(dyn)
        if not segs:
            z = np.zeros((0, 2), np.float32)
            return z, z, np.zeros(0, np.float32)
        s = np.array(segs, np.float32)
        return s[:, :2], s[:, 2:], np.array(R, np.float32)

    # ------------------------------------------------------------ kreslení
    def inkoust_pouzit(self, tahy=None):
        tahy = self.tahy if tahy is None else tahy
        c = 0.0
        for t in tahy:
            for a, b in zip(t, t[1:]):
                c += math.dist(a, b)
        return c

    def inkoust_zbyva(self):
        return self.d["inkoust"] - self.inkoust_pouzit()

    def bod_povolen(self, p):
        okraj = TL_TRUBKY / 2
        if not (0 <= p[0] <= SIRKA and 0 <= p[1] <= VYSKA):
            return False
        for r in self.d["zakaz"] + self.d["odtoky"]:
            if _bod_v_obdelniku(p[0], p[1], r, okraj):
                return False
        for (x, y, w, h) in self.d["nadrze"]:
            if _bod_v_obdelniku(p[0], p[1], (x + 8, y - 30, w - 16, h + 30 - 8)):
                return False
        for (ax, ay, bx, by) in self.d["portaly"]:
            if math.dist(p, (ax, ay)) < R_PORTALU + okraj or math.dist(p, (bx, by)) < R_PORTALU + okraj:
                return False
        return True

    def usecka_povolena(self, a, b):
        n = max(2, int(math.dist(a, b) / 3))
        for k in range(n + 1):
            t = k / n
            if not self.bod_povolen((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)):
                return False
        return True

    # ------------------------------------------------------------ simulace
    def snimek(self):
        """Posune hru o jeden snímek (1/60 s)."""
        odtecene = []
        for _ in range(KROKY_ZA_SNIMEK):
            self.cas += DT
            if self.pusteno:
                self.cas_od_pusteni += DT
            self._vitr()
            A, B, R = self.vsechny_usecky()
            self.voda.krok(A, B, R)
            self._portaly()
            z = self._odeber_ztracenou_vodu()
            if len(z):
                odtecene.append(z)
        self.odtecene = np.concatenate(odtecene) if odtecene else np.zeros((0, 2), np.float32)
        self._vyhodnot()

    def _vitr(self):
        if not self.d["vetraky"] or self.voda.pocet == 0:
            return
        x, v = self.voda.x, self.voda.v
        for (rx, ry, rw, rh, fx, fy) in self.d["vetraky"]:
            m = _v_obdelniku(x, (rx, ry, rw, rh))
            if m.any():
                v[m, 0] += fx
                v[m, 1] += fy

    def _portaly(self):
        if not self.d["portaly"] or self.voda.pocet == 0:
            return
        x = self.voda.x
        for (ax, ay, bx, by) in self.d["portaly"]:
            d = x - np.array((ax, ay), np.float32)
            m = (d * d).sum(1) < R_PORTALU * R_PORTALU
            if m.any():
                x[m] += np.array((bx - ax, by - ay), np.float32)

    def _odeber_ztracenou_vodu(self):
        x = self.voda.x
        if len(x) == 0:
            return np.zeros((0, 2), np.float32)
        ok = (x[:, 1] < VYSKA + 30) & (x[:, 0] > -30) & (x[:, 0] < SIRKA + 30)
        ve_skle = np.zeros(len(x), bool)
        for g in self.sklenice():
            gx, gy, gw, gh = g
            ve_skle |= _v_obdelniku(x, (gx, gy - gh, gw, gh))
        v_odtoku = np.zeros(len(x), bool)
        for r in self.d["odtoky"]:
            v_odtoku |= _v_obdelniku(x, r)
        v_odtoku &= ~ve_skle
        ok &= ~v_odtoku
        if not ok.all():
            ztracene = x[v_odtoku].copy()
            self.voda.odeber(ok)
            return ztracene
        return np.zeros((0, 2), np.float32)

    def pocty_ve_sklenicich(self):
        x = self.voda.x
        if len(x) == 0:
            return [0] * len(self.d["sklenice"])
        return [int(_v_obdelniku(x, (gx, gy - gh, gw, gh)).sum())
                for gx, gy, gw, gh in self.sklenice()]

    def pocet_ve_sklenici(self):
        return sum(self.pocty_ve_sklenicich())

    def _vyhodnot(self):
        self.pocty = self.pocty_ve_sklenicich()
        n = sum(self.pocty)
        if n > self.max_ve_sklenici:
            self.max_ve_sklenici = n
            self.cas_posledni_zmeny = self.cas_od_pusteni
        self.ve_sklenici = n
        if self.stav != "tece":
            if self.stav == "vyhra":
                self.vysledek = max(self.vysledek, n / self.celkem)
            return

        splneno = all(p >= self.cil_sklenice for p in self.pocty) and n >= self.cil_pocet
        if splneno:
            if not self.dosazeno:
                self.dosazeno = True
                self.cas_dosazeni = self.cas_od_pusteni
            # čekáme, až se voda uklidní, a pak vyhodnotíme
            if (self.cas_od_pusteni - self.cas_posledni_zmeny > 1.5
                    or self.cas_od_pusteni - self.cas_dosazeni > 8):
                self.stav = "vyhra"
                self.vysledek = n / self.celkem
        elif self.dosazeno:
            # voda vytekla ven (např. pohyblivá sklenice)
            self.dosazeno = False
        if self.stav == "tece":
            if self.voda.pocet < self.cil_pocet:
                self.stav, self.duvod = "prohra", "Uteklo příliš mnoho vody."
            elif self.cas_od_pusteni > self.d["limit"]:
                self.stav, self.duvod = "prohra", "Došel čas – voda se zasekla."

    def prahy_hvezd(self):
        """Podíl vody pro 1, 2 a 3 hvězdy."""
        c = self.d["cil"]
        if "hvezdy" in self.d:
            return (c,) + tuple(self.d["hvezdy"])
        return c, c + (1 - c) * 0.35, c + (1 - c) * 0.7

    def hvezdy(self):
        if self.stav != "vyhra":
            return 0
        _, h2, h3 = self.prahy_hvezd()
        p = self.vysledek
        return 3 if p >= h3 - 1e-9 else 2 if p >= h2 - 1e-9 else 1


def _vzdalenost_k_usecce(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy + 1e-9
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)
