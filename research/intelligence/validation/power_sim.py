"""Power and confound simulation for Intelligence validation designs. Stdlib only, seeded, SYNTHETIC.

Not evidence about fish. It sizes a study: how many paired observations are needed to distinguish a ranking that
really finds more fish from one that does not, and how badly raw catch counts mislead when effort varies.
Run:  python3 -I power_sim.py
"""
import math, random

random.seed(20261013)


def nb(mu, k):
    """Negative binomial draw via gamma-Poisson (var = mu + mu^2/k)."""
    if mu <= 0:
        return 0
    lam = random.gammavariate(k, mu / k)
    # Poisson by inversion (small lam) / normal approx for large
    if lam > 60:
        return max(0, int(round(random.gauss(lam, math.sqrt(lam)))))
    L, p, n = math.exp(-lam), 1.0, 0
    while True:
        p *= random.random()
        if p <= L:
            return n
        n += 1


def sign_test_p(wins, losses):
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(wins, n + 1)) / 2 ** n      # one-sided: top-ranked > lower-ranked


def power_paired(n_pairs, base, lift, k, night_sd=0.6, trials=1500):
    """Observer fishes the top-ranked and a lower-ranked zone the same night, same effort, random order.
    A shared lognormal 'night effect' multiplies both zones (this is what pairing cancels)."""
    hits = 0
    for _ in range(trials):
        w = l = 0
        for _ in range(n_pairs):
            night = math.exp(random.gauss(-night_sd ** 2 / 2, night_sd))
            a, b = nb(base * lift * night, k), nb(base * night, k)
            w += a > b
            l += a < b
        hits += sign_test_p(w, l) < 0.05
    return hits / trials


def power_unpaired(n_trips, base, lift, k, night_sd=0.6, trials=600):
    """Same counts, but different nights for top vs lower zones (what an uncontrolled app log gives). Welch-style z on log(1+x)."""
    hits = 0
    for _ in range(trials):
        A, B = [], []
        for _ in range(n_trips):
            A.append(math.log1p(nb(base * lift * math.exp(random.gauss(-night_sd ** 2 / 2, night_sd)), k)))
            B.append(math.log1p(nb(base * math.exp(random.gauss(-night_sd ** 2 / 2, night_sd)), k)))
        ma, mb = sum(A) / n_trips, sum(B) / n_trips
        va = sum((x - ma) ** 2 for x in A) / (n_trips - 1); vb = sum((x - mb) ** 2 for x in B) / (n_trips - 1)
        z = (ma - mb) / math.sqrt(va / n_trips + vb / n_trips + 1e-12)
        hits += z > 1.645
    return hits / trials


def n_for_power(fn, target=0.8, grid=(10, 15, 20, 30, 40, 60, 80, 120, 160, 240, 400), **kw):
    for n in grid:
        if fn(n, **kw) >= target:
            return n
    return None


def effort_confound(trips=4000):
    """Raw catch per TRIP vs ranking, when hunters spend more hours on zones they like. The ranking has ZERO real effect (lift=1)."""
    rows = []
    for _ in range(trips):
        top = random.random() < 0.5                    # followed the top recommendation?
        hours = random.gauss(3.5 if top else 2.5, 0.8)  # recommendation followers stay out longer (an effort confound)
        hours = max(0.5, hours)
        catch = sum(nb(2.0, 1.0) for _ in range(int(round(hours * 2))))      # 2 sightings/half-hour, no real lift
        rows.append((top, hours, catch))
    a = [c for t, h, c in rows if t]; b = [c for t, h, c in rows if not t]
    ra = [c / h for t, h, c in rows if t]; rb = [c / h for t, h, c in rows if not t]
    return sum(a) / len(a), sum(b) / len(b), sum(ra) / len(ra), sum(rb) / len(rb)


if __name__ == "__main__":
    print("## P1  paired blind-area design: pairs needed for 80% power (one-sided sign test, alpha 0.05)")
    print("base_sightings_per_visit,lift,dispersion_k,pairs_needed")
    for base in (2, 5, 10):
        for lift in (1.25, 1.5, 2.0, 3.0):
            for k in (1.0, 4.0):
                print(base, lift, k, n_for_power(power_paired, base=base, lift=lift, k=k, trials=600))
    print("## P2  paired vs unpaired (uncontrolled app log), base=5, k=1, night_sd 0.6: units needed for 80% power")
    print("lift,paired_pairs,unpaired_trips_per_arm")
    for lift in (1.5, 2.0, 3.0):
        print(lift, n_for_power(power_paired, base=5, lift=lift, k=1.0, trials=600),
              n_for_power(power_unpaired, base=5, lift=lift, k=1.0, grid=(20, 40, 80, 160, 320, 640, 1280)))
    print("## P3  effort confound: ranking has NO real effect (lift = 1.0)")
    ca, cb, ra, rb = effort_confound()
    print(f"raw catch per trip   followed-top={ca:.2f}  other={cb:.2f}  apparent lift={ca/cb:.2f}")
    print(f"catch per effort-hr  followed-top={ra:.2f}  other={rb:.2f}  apparent lift={ra/rb:.2f}")
