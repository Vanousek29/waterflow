"""
fyzika.py - simulace vody pomocí částic

Používá metodu "Double Density Relaxation" (Clavet a kol., 2005):
  1. na každou částici působí gravitace
  2. odhadneme novou polohu (x + v)
  3. podle hustoty okolních částic je od sebe odtlačíme / přitáhneme
     (tlak = voda se nedá stlačit, "blízký tlak" = částice se nepřekrývají)
  4. vyřešíme kolize se stěnami (úsečkami)
  5. rychlost = (nová poloha - stará poloha)

Výsledkem je voda, která teče, šplouchá, tvoří kapky a hladinu.
Všechny výpočty jsou vektorizované v numpy, aby to bylo rychlé.
"""
import numpy as np


class Voda:
    def __init__(self, pozice):
        self.x = np.array(pozice, dtype=np.float32).reshape(-1, 2)
        self.v = np.zeros_like(self.x)

        # --- parametry vody (vyladěné pro jednotky = pixely, krok = 1) ---
        self.h = 16.0          # dosah interakce mezi částicemi
        self.rho0 = 4.5        # klidová hustota
        self.k = 0.25          # tuhost (jak moc voda odolává stlačení)
        self.k_near = 0.9      # blízká tuhost (zabraňuje shlukování)
        self.gravitace = 0.12  # px / krok^2
        self.sigma = 0.08      # lineární viskozita
        self.beta = 0.04       # kvadratická viskozita
        self.vmax = 4.5        # max. posun za krok (aby voda neprolétla zdí)
        self.polomer = 3.5     # poloměr částice pro kolize
        self.treni = 0.015     # tření o stěny a trubky

    @property
    def pocet(self):
        return len(self.x)

    # ------------------------------------------------------------------
    def _pary(self):
        """Najde všechny dvojice částic blíž než h (hrubou silou, N je malé)."""
        x = self.x
        dx = np.subtract.outer(x[:, 0], x[:, 0])
        dy = np.subtract.outer(x[:, 1], x[:, 1])
        d2 = dx * dx + dy * dy
        i, j = np.nonzero(d2 < self.h * self.h)
        m = i < j
        return i[m], j[m]

    def krok(self, A, B, R):
        """Jeden krok simulace. A, B = konce úseček stěn (M,2), R = poloměr kolize (M,)."""
        n = self.pocet
        if n == 0:
            return
        x, v = self.x, self.v

        # 1) gravitace
        v[:, 1] += self.gravitace

        # 2) predikce polohy
        stara = x.copy()
        x += v

        i, j = self._pary()
        if len(i):
            # 3a) viskozita - částice letící proti sobě se trochu zpomalí
            rij = x[j] - x[i]
            r = np.sqrt((rij * rij).sum(1))
            r = np.maximum(r, 1e-4)
            smer = rij / r[:, None]
            q = 1.0 - r / self.h
            u = ((v[i] - v[j]) * smer).sum(1)
            u = np.where(u > 0, u, 0.0)
            imp = (q * (self.sigma * u + self.beta * u * u))[:, None] * smer * 0.5
            self._pricti(i, j, -imp, imp)

            # 3b) relaxace hustoty (tlak)
            rij = x[j] - x[i]
            r = np.sqrt((rij * rij).sum(1))
            r = np.maximum(r, 1e-4)
            smer = rij / r[:, None]
            q = np.clip(1.0 - r / self.h, 0.0, 1.0)
            q2 = q * q
            rho = np.bincount(i, q2, n) + np.bincount(j, q2, n)
            rho_n = np.bincount(i, q2 * q, n) + np.bincount(j, q2 * q, n)
            P = self.k * (rho - self.rho0)
            Pn = self.k_near * rho_n
            D = ((P[i] + P[j]) * q + (Pn[i] + Pn[j]) * q2) * 0.25
            posun = D[:, None] * smer
            self._pricti(i, j, -posun, posun)

        # omezení rychlosti (proti "tunelování" skrz stěny)
        d = x - stara
        delka = np.sqrt((d * d).sum(1))
        prilis = delka > self.vmax
        if prilis.any():
            d[prilis] *= (self.vmax / delka[prilis])[:, None]
            x[:] = stara + d

        # 4) kolize se stěnami
        if len(A):
            self._kolize(A, B, R, stara)
            self._kolize(A, B, R, None)

        # 5) nová rychlost
        self.v = (x - stara).astype(np.float32)

    def _pricti(self, i, j, di, dj):
        n = self.pocet
        self.x[:, 0] += np.bincount(i, di[:, 0], n) + np.bincount(j, dj[:, 0], n)
        self.x[:, 1] += np.bincount(i, di[:, 1], n) + np.bincount(j, dj[:, 1], n)

    def _kolize(self, A, B, R, stara):
        x = self.x
        AB = B - A                                   # (M,2)
        L2 = (AB * AB).sum(1) + 1e-6                 # (M,)
        AP = x[:, None, :] - A[None, :, :]           # (N,M,2)
        t = np.clip((AP * AB[None]).sum(2) / L2, 0.0, 1.0)
        C = A[None] + t[..., None] * AB[None]        # nejbližší bod na úsečce
        d = x[:, None, :] - C
        dist = np.sqrt((d * d).sum(2))
        pen = R[None, :] - dist                      # o kolik je částice "ve zdi"
        k = np.argmax(pen, axis=1)
        idx = np.arange(len(x))
        p = pen[idx, k]
        hit = p > 0
        if not hit.any():
            return
        dv = d[idx, k][hit]
        dd = np.maximum(dist[idx, k][hit], 1e-6)
        normala = dv / dd[:, None]
        x[hit] += normala * p[hit][:, None]
        if stara is not None and self.treni > 0:
            # tření o stěnu: zpomalí pohyb podél stěny
            pohyb = x[hit] - stara[hit]
            vn = (pohyb * normala).sum(1)[:, None] * normala
            x[hit] -= (pohyb - vn) * self.treni

    # ------------------------------------------------------------------
    def odeber(self, maska_ponechat):
        self.x = self.x[maska_ponechat]
        self.v = self.v[maska_ponechat]

    def rychlost(self):
        return np.sqrt((self.v * self.v).sum(1))