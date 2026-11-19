"""
overeni.py - vývojářský nástroj: ověří, že každý level jde vyřešit

Pro každý level z levely.py vezme referenční řešení z reseni.py a:
  1. zkontroluje, že řešení nepřekročí inkoust a nekreslí do zakázaných míst,
  2. pustí simulaci a ověří, že se level vyhraje (vypíše % vody a hvězdy),
  3. pustí vodu bez trubek a ověří, že se level vyhrát NEDÁ.

Použití:
  python overeni.py               všechny levely
  python overeni.py z3 o1         jen vybrané levely (podle id)
  python overeni.py --obrazky     uloží i průběh do složky overeni_obrazky/
"""
import math
import os
import sys
from multiprocessing import Pool

from levely import VSECHNY_LEVELY
from logika import Level
from reseni import RESENI


def simuluj(data, tahy, obrazky=None):
    L = Level(data)
    for t in tahy:
        L.tahy.append([tuple(map(float, p)) for p in t])
    L.verze_tahu += 1
    L.pustit()
    snimky = []
    n = 0
    zachyt = {int(c * 60) for c in (0, 1.0, 2.5, 4.5)}
    while L.stav == "tece" and n < 60 * 40:
        if obrazky is not None and n in zachyt:
            snimky.append(_obrazek(L, n / 60))
        L.snimek()
        n += 1
    if obrazky is not None:
        snimky.append(_obrazek(L, n / 60))
        _uloz(snimky, obrazky)
    return L, n / 60


_kreslic = None


def _obrazek(L, t):
    global _kreslic
    import pygame
    from svet import KreslicSveta
    if _kreslic is None:
        _kreslic = KreslicSveta()
    s = pygame.Surface((1000, 700))
    _kreslic.kresli(s, L, t, efekty=False)
    return pygame.transform.smoothscale(s, (500, 350))


def _uloz(snimky, cesta):
    import pygame
    out = pygame.Surface((500 * len(snimky), 350))
    for i, s in enumerate(snimky):
        out.blit(s, (500 * i, 0))
    pygame.image.save(out, cesta)


def over(args):
    lid, obrazky = args
    if obrazky:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        import pygame
        pygame.init()
        pygame.display.set_mode((1, 1))
    data = next(d for d in VSECHNY_LEVELY if d["id"] == lid)
    tahy = RESENI.get(lid)
    zpravy = []
    if not tahy:
        return lid, data["nazev"], False, ["chybí řešení"], None

    L = Level(data)
    inkoust = sum(math.dist(a, b) for t in tahy for a, b in zip(t, t[1:]))
    if inkoust > L.d["inkoust"]:
        zpravy.append(f"řešení potřebuje {inkoust:.0f} inkoustu, level dává {L.d['inkoust']}")
    for t in tahy:
        for a, b in zip(t, t[1:]):
            if not L.usecka_povolena(a, b):
                zpravy.append(f"úsečka {a}-{b} vede přes zakázané místo")

    cesta = os.path.join("overeni_obrazky", f"{lid}.png") if obrazky else None
    L, cas = simuluj(data, tahy, cesta)
    ok = L.stav == "vyhra"
    if not ok:
        zpravy.append(f"řešení nevyhrálo ({L.stav}: {L.duvod}, {L.ve_sklenici / L.celkem:.0%})")

    prazdny, _ = simuluj(data, [])
    if prazdny.stav == "vyhra":
        zpravy.append("level jde vyhrát i bez trubek!")
        ok = False
    ok = ok and not zpravy
    info = dict(proc=L.vysledek, hvezdy=L.hvezdy(), cas=cas, inkoust=inkoust,
                limit=L.d["inkoust"], castic=L.celkem, prahy=L.prahy_hvezd(),
                bez=prazdny.ve_sklenici / prazdny.celkem)
    return lid, data["nazev"], ok, zpravy, info


def main():
    argv = sys.argv[1:]
    obrazky = "--obrazky" in argv
    vyber = [a for a in argv if not a.startswith("--")]
    ids = [d["id"] for d in VSECHNY_LEVELY if not vyber or d["id"] in vyber]
    if obrazky:
        os.makedirs("overeni_obrazky", exist_ok=True)
    with Pool(min(len(ids), os.cpu_count() or 2)) as pool:
        vysledky = pool.map(over, [(i, obrazky) for i in ids])
    spatne = 0
    for lid, nazev, ok, zpravy, info in vysledky:
        znak = "OK " if ok else "!! "
        if info:
            h = info["prahy"]
            print(f"{znak}{lid:5s} {nazev:24s} {info['proc']:5.0%}  {'*' * info['hvezdy']:3s} "
                  f"(prahy {h[0]:.0%}/{h[1]:.0%}/{h[2]:.0%})  {info['cas']:4.1f} s  "
                  f"inkoust {info['inkoust']:4.0f}/{info['limit']:4d}  částic {info['castic']}  "
                  f"bez trubek {info['bez']:.0%}")
        else:
            print(f"{znak}{lid:5s} {nazev}")
        for z in zpravy:
            print("      -", z)
        spatne += not ok
    print(f"\n{len(vysledky) - spatne}/{len(vysledky)} levelů v pořádku")
    sys.exit(1 if spatne else 0)


if __name__ == "__main__":
    main()
