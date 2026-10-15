import math

A = 6378137
F = 1 / 298.257222101
E2 = F * (2 - F)
E = math.sqrt(E2)
E4 = E2 * E2
E6 = E4 * E2
DEG = math.pi / 180
LON0 = -96 * DEG
LAT0 = 23 * DEG
LAT1 = 29.5 * DEG
LAT2 = 45.5 * DEG


def _q(phi: float) -> float:
    sine = math.sin(phi)
    return (1 - E2) * (sine / (1 - E2 * sine * sine) - math.log((1 - E * sine) / (1 + E * sine)) / (2 * E))


def _m(phi: float) -> float:
    sine = math.sin(phi)
    return math.cos(phi) / math.sqrt(1 - E2 * sine * sine)


Q1 = _q(LAT1)
Q2 = _q(LAT2)
QP = _q(math.pi / 2)
M1 = _m(LAT1)
M2 = _m(LAT2)
N = (M1 * M1 - M2 * M2) / (Q2 - Q1)
C = M1 * M1 + N * Q1
RHO0 = (A * math.sqrt(C - N * _q(LAT0))) / N


def _geodetic_from_authalic(beta: float) -> float:
    return (
        beta
        + (E2 / 3 + (31 * E4) / 180 + (517 * E6) / 5040) * math.sin(2 * beta)
        + ((23 * E4) / 360 + (251 * E6) / 3780) * math.sin(4 * beta)
        + ((761 * E6) / 45360) * math.sin(6 * beta)
    )


def albers5070_to_lon_lat(x: float, y: float) -> list[float]:
    rho = math.hypot(x, RHO0 - y)
    theta = math.atan2(x, RHO0 - y)
    sine = (C - (rho / A) ** 2 * N * N) / (N * QP)
    beta = math.asin(max(-1, min(1, sine)))
    lon = round(((LON0 + theta / N) / DEG) * 1e5) / 1e5
    lat = round((_geodetic_from_authalic(beta) / DEG) * 1e5) / 1e5
    return [lon, lat]
