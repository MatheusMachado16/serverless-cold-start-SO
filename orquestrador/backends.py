"""Backends de execução.

- BackendDocker: o experimento real (contêiner novo a cada amostra fria).
- BackendProcesso: SOMENTE para validar o pipeline em máquinas sem Docker.
  Sobe o mesmo server.py do SeBS como processo comum. Os números NÃO representam
  cold start de contêiner e a coluna `backend` do CSV deixa isso explícito.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import coletores


class FalhaInicializacao(RuntimeError):
    def __init__(self, motivo: str, detalhe: str = ""):
        super().__init__(f"{motivo}: {detalhe}")
        self.motivo, self.detalhe = motivo, detalhe


@dataclass
class Handle:
    nome: str
    porta: int
    container_id: str | None = None
    pid: int | None = None
    proc: subprocess.Popen | None = None
    tmp: str | None = None
    extra: dict = field(default_factory=dict)


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


class BackendDocker:
    nome = "docker"

    def __init__(self, amb: dict, raiz: Path):
        self.amb, self.raiz = amb, raiz

    def _pacote(self, cfg) -> Path:
        return (self.raiz / self.amb["dir_pacotes"] / cfg["workload"] / cfg["runtime"] / cfg["pacote"]).resolve()

    def criar(self, cfg: dict, porta: int, env_extra: dict, nome: str | None = None) -> Handle:
        """`docker create` (não inicia o processo). Faz parte de t0 -> t_created."""
        nome = nome or f"cs-{uuid.uuid4().hex[:10]}"
        mem = int(cfg["mem_mib"]) * 1024 * 1024
        env = {
            "CONTAINER_UID": str(os.getuid()),
            "CONTAINER_GID": str(os.getgid()),
            "CONTAINER_USER": "docker_user",
            **env_extra,
        }
        cmd = ["docker", "create", "--name", nome,
               "--memory", str(mem), "--memory-swap", str(mem),     # sem swap no contêiner (constante)
               "--cpus", str(self.amb.get("cpus", 1)),               # CPU constante em todas as configs
               "--network", cfg["rede"],
               "--privileged", "--security-opt", "seccomp=unconfined",  # igual ao sebs/local/local.py
               "-v", f"{self._pacote(cfg)}:/function:ro"]
        if cfg["rede"] == "bridge":
            cmd += ["-p", f"127.0.0.1:{porta}:{porta}"]
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
        cmd += [self.amb["imagens"][cfg["runtime"]], "/bin/bash", "/sebs/run_server.sh", str(porta)]
        r = _run(cmd)
        if r.returncode != 0:
            raise FalhaInicializacao("docker_create", r.stderr.strip())
        return Handle(nome=nome, porta=porta, container_id=r.stdout.strip())

    def iniciar(self, h: Handle):
        r = _run(["docker", "start", h.nome])
        if r.returncode != 0:
            raise FalhaInicializacao("docker_start", r.stderr.strip())

    def vivo(self, h: Handle) -> tuple[bool, str]:
        r = _run(["docker", "inspect", "-f", "{{.State.Running}}|{{.State.OOMKilled}}|{{.State.ExitCode}}", h.nome])
        if r.returncode != 0:
            return False, "inspect_falhou"
        rodando, oom, cod = r.stdout.strip().split("|")
        if rodando == "true":
            return True, ""
        self._salvar_log_falha(h)
        return False, "oom" if oom == "true" else f"saiu_cod_{cod}"

    def _salvar_log_falha(self, h: Handle):
        """Guarda as últimas linhas do contêiner que caiu, antes de o remover() apagá-lo."""
        r = _run(["docker", "logs", "--tail", "40", h.nome])
        txt = (r.stdout + r.stderr).strip()
        h.extra["log_falha"] = txt
        d = self.raiz / "resultados" / "falhas"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{h.nome}.log").write_text(txt + "\n", encoding="utf-8")

    def pos_resposta(self, h: Handle) -> dict:
        """Lido depois de t_resp (fora da janela cronometrada)."""
        r = _run(["docker", "inspect", "-f",
                  "{{.State.Pid}}|{{.State.OOMKilled}}|{{.HostConfig.Memory}}|{{.HostConfig.NetworkMode}}|"
                  "{{.HostConfig.MemorySwap}}|{{.HostConfig.NanoCpus}}", h.nome])
        info = {}
        if r.returncode == 0:
            pid, oom, mem, rede, swap, nano = r.stdout.strip().split("|")
            h.pid = int(pid) or None
            info = {"oom_flag": oom == "true", "mem_efetiva_bytes": int(mem), "rede_efetiva": rede,
                    "swap_efetivo_bytes": int(swap), "nano_cpus": int(nano)}
        cg = coletores.cgroup_do_pid(h.pid) if h.pid else None
        h.extra["cgroup"] = cg
        m = coletores.ler_cgroup(cg)
        if m["cpu_usec"] is None and h.pid:  # sem cgroup legível: cai para /proc (só o PID principal)
            m.update({k: v for k, v in coletores.ler_proc(h.pid).items() if m.get(k) is None})
        m.update(info)
        return m

    def remover(self, h: Handle):
        self.vivo(h)   # se o contêiner já caiu, guarda o log antes de apagá-lo
        _run(["docker", "rm", "-f", h.nome])


class BackendProcesso:
    """Mesmo server.py do SeBS (com CODE_LOCATION trocado), sem contêiner."""
    nome = "processo"

    def __init__(self, amb: dict, raiz: Path):
        self.amb, self.raiz = amb, raiz

    def criar(self, cfg: dict, porta: int, env_extra: dict, nome: str | None = None) -> Handle:
        sebs = Path(self.amb["sebs_dir"]).expanduser()
        pkg = (self.raiz / self.amb["dir_pacotes"] / cfg["workload"] / cfg["runtime"] / cfg["pacote"]).resolve()
        if cfg["runtime"] != "python":
            raise FalhaInicializacao("backend_processo", "só Python é suportado neste backend de validação")
        base = (sebs / "dockerfiles/local/python/server.py").read_text()
        patched = base.replace("CODE_LOCATION='/function'", f"CODE_LOCATION={str(pkg)!r}")
        tmp = tempfile.mkdtemp(prefix="cs-proc-")
        (Path(tmp) / "server.py").write_text(patched)
        return Handle(nome=f"proc-{uuid.uuid4().hex[:8]}", porta=porta, tmp=tmp,
                      extra={"env": {**os.environ, **env_extra}})

    def iniciar(self, h: Handle):
        h.proc = subprocess.Popen([sys.executable, "-u", str(Path(h.tmp) / "server.py"), str(h.porta)],
                                  env=h.extra["env"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        h.pid = h.proc.pid
        h.container_id = f"pid:{h.pid}"

    def vivo(self, h: Handle) -> tuple[bool, str]:
        cod = h.proc.poll()
        return (True, "") if cod is None else (False, f"saiu_cod_{cod}")

    def pos_resposta(self, h: Handle) -> dict:
        m = coletores.ler_proc(h.pid)
        m.update(oom_kill=None, pgfault=None, mem_atual_bytes=None, io_rbytes=None, io_wbytes=None,
                 io_rios=None, io_wios=None, oom_flag=False, mem_efetiva_bytes=None, rede_efetiva="host(processo)",
                 swap_efetivo_bytes=None, nano_cpus=None)
        return m

    def remover(self, h: Handle):
        if h.proc and h.proc.poll() is None:
            h.proc.kill()
            h.proc.wait()
        if h.tmp:
            for f in Path(h.tmp).glob("*"):
                f.unlink(missing_ok=True)
            Path(h.tmp).rmdir()


BACKENDS = {"docker": BackendDocker, "processo": BackendProcesso}
