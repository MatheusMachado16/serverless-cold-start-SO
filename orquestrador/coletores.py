"""Coletores: condições do host, cgroups v2, /proc, docker events e controle de caches.

Regra do projeto: métrica indisponível vira None (célula vazia no CSV), nunca 0.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import time
from pathlib import Path


def _ler(caminho: str) -> str | None:
    try:
        return Path(caminho).read_text().strip()
    except OSError:
        return None


def temperatura_cpu_c() -> float | None:
    for hw in glob.glob("/sys/class/hwmon/hwmon*"):
        if _ler(f"{hw}/name") in ("k10temp", "coretemp"):
            v = _ler(f"{hw}/temp1_input")
            if v:
                return int(v) / 1000
    return None


def frequencia_media_khz() -> float | None:
    vals = []
    for f in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"):
        v = _ler(f)
        if v and v.isdigit():
            vals.append(int(v))
    return sum(vals) / len(vals) if vals else None


def governador_cpu() -> str | None:
    return _ler("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")


def na_tomada() -> bool | None:
    achou = False
    for ps in glob.glob("/sys/class/power_supply/*"):
        if _ler(f"{ps}/type") == "Mains":
            achou = True
            if _ler(f"{ps}/online") == "1":
                return True
    return False if achou else None


def meminfo_kb() -> dict:
    out = {}
    txt = _ler("/proc/meminfo") or ""
    for linha in txt.splitlines():
        k, _, v = linha.partition(":")
        partes = v.split()
        if partes and partes[0].isdigit():
            out[k] = int(partes[0])
    return out


def condicoes_host() -> dict:
    m = meminfo_kb()
    swap_usado = None
    if "SwapTotal" in m and "SwapFree" in m:
        swap_usado = m["SwapTotal"] - m["SwapFree"]
    return {
        "temp_c": temperatura_cpu_c(),
        "freq_khz": frequencia_media_khz(),
        "mem_disponivel_kb": m.get("MemAvailable"),
        "swap_usado_kb": swap_usado,
        "na_tomada": na_tomada(),
        "governador": governador_cpu(),
    }


def cgroup_do_pid(pid: int) -> str | None:
    """Diretório cgroup v2 do processo, visto do host."""
    txt = _ler(f"/proc/{pid}/cgroup")
    if not txt:
        return None
    for linha in txt.splitlines():
        if linha.startswith("0::"):
            caminho = "/sys/fs/cgroup" + linha[3:]
            return caminho if os.path.isdir(caminho) else None
    return None


def _kv(caminho: str) -> dict:
    out = {}
    txt = _ler(caminho) or ""
    for linha in txt.splitlines():
        partes = linha.split()
        if len(partes) == 2 and partes[1].lstrip("-").isdigit():
            out[partes[0]] = int(partes[1])
    return out


def ler_cgroup(cg: str | None) -> dict:
    """Contadores cumulativos do cgroup. Chaves ausentes ficam None."""
    r = dict(cpu_usec=None, mem_atual_bytes=None, mem_pico_bytes=None, oom_kill=None,
             pgfault=None, pgmajfault=None, pgfault_minor=None,
             io_rbytes=None, io_wbytes=None, io_rios=None, io_wios=None)
    if not cg:
        return r
    r["cpu_usec"] = _kv(f"{cg}/cpu.stat").get("usage_usec")
    atual, pico = _ler(f"{cg}/memory.current"), _ler(f"{cg}/memory.peak")
    r["mem_atual_bytes"] = int(atual) if atual and atual.isdigit() else None
    r["mem_pico_bytes"] = int(pico) if pico and pico.isdigit() else None  # kernel >= 5.19
    r["oom_kill"] = _kv(f"{cg}/memory.events").get("oom_kill")
    ms = _kv(f"{cg}/memory.stat")
    r["pgfault"], r["pgmajfault"] = ms.get("pgfault"), ms.get("pgmajfault")
    if r["pgfault"] is not None and r["pgmajfault"] is not None:
        r["pgfault_minor"] = r["pgfault"] - r["pgmajfault"]
    io = {"rbytes": 0, "wbytes": 0, "rios": 0, "wios": 0}
    visto = False
    for linha in (_ler(f"{cg}/io.stat") or "").splitlines():
        for campo in linha.split()[1:]:
            k, _, v = campo.partition("=")
            if k in io and v.isdigit():
                io[k] += int(v)
                visto = True
    if visto:
        r.update(io_rbytes=io["rbytes"], io_wbytes=io["wbytes"], io_rios=io["rios"], io_wios=io["wios"])
    return r


def ler_proc(pid: int) -> dict:
    """Fallback sem cgroup: falhas de página, CPU e pico de RSS de um processo."""
    r = dict(cpu_usec=None, pgfault_minor=None, pgmajfault=None, mem_pico_bytes=None)
    st = _ler(f"/proc/{pid}/stat")
    if st:
        c = st[st.rfind(")") + 2:].split()
        hz = os.sysconf("SC_CLK_TCK")
        r["pgfault_minor"], r["pgmajfault"] = int(c[7]), int(c[9])
        r["cpu_usec"] = int((int(c[11]) + int(c[12])) * 1_000_000 / hz)
    for linha in (_ler(f"/proc/{pid}/status") or "").splitlines():
        if linha.startswith("VmHWM:"):
            r["mem_pico_bytes"] = int(linha.split()[1]) * 1024
    return r


def descartar_caches(nivel: int = 3) -> float:
    """sync + drop_caches. Retorna a duração (s) do procedimento. Exige root/sudo."""
    t = time.perf_counter()
    cmd = f"sync; echo {nivel} > /proc/sys/vm/drop_caches"
    pref = [] if os.geteuid() == 0 else ["sudo", "-n"]
    r = subprocess.run(pref + ["sh", "-c", cmd], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            "Não foi possível descartar caches (rode como root ou libere `sudo -n` "
            f"para este comando): {r.stderr.strip()}")
    return time.perf_counter() - t


class ColetorEventosDocker:
    """Captura create/start/die/oom do contêiner. Os carimbos são em relógio de
    parede; ficam em campo separado e só são relacionados a t0 pelo par
    (wall_ns, mono_ns) registrado no início, conforme o README, seção 7."""

    def __init__(self, nome_container: str, destino: Path):
        self.nome, self.destino = nome_container, destino
        self.proc = None
        self.wall_ns = self.mono_ns = None

    def iniciar(self):
        self.destino.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.destino, "w")
        self.proc = subprocess.Popen(
            ["docker", "events", "--filter", f"container={self.nome}", "--format", "{{json .}}"],
            stdout=self._f, stderr=subprocess.DEVNULL)
        time.sleep(0.15)  
        self.wall_ns, self.mono_ns = time.time_ns(), time.perf_counter_ns()

    def parar(self) -> dict:
        time.sleep(0.1)
        if self.proc:
            self.proc.terminate()
            self.proc.wait()
            self._f.close()
        marcos = {}
        try:
            for linha in self.destino.read_text().splitlines():
                ev = json.loads(linha)
                marcos.setdefault(ev.get("Action") or ev.get("status"), ev.get("timeNano"))
        except (OSError, ValueError):
            pass
        return marcos
