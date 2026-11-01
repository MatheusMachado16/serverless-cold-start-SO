"""Uma medição a frio e as medições quentes (README, seções 4 e 9).

Todas as durações usam time.perf_counter_ns() do orquestrador (relógio monotônico).

  t0       imediatamente antes de `docker create`
  t_ready  primeira resposta HTTP 200 de /alive
  t_req    imediatamente antes de abrir a conexão da requisição de trabalho
  t_resp   corpo da resposta lido por completo
"""
from __future__ import annotations

import http.client
import importlib.util
import json
import socket
import time
import uuid
from pathlib import Path

import coletores
from backends import FalhaInicializacao

NS_MS = 1e6


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def carregar_validador(raiz: Path, benchmark: str):
    """Usa o validate_output do próprio SeBS (benchmarks/<bench>/input.py)."""
    caminho = raiz / "benchmarks" / benchmark / "input.py"
    spec = importlib.util.spec_from_file_location("sebs_input_" + benchmark.replace("/", "_"), caminho)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except ModuleNotFoundError:   # ex.: thumbnailer importa PIL, que pode não existir no host
        return None
    return mod.validate_output


def _http(porta, metodo, caminho, corpo, timeout):
    conn = http.client.HTTPConnection("127.0.0.1", porta, timeout=timeout)
    try:
        conn.request(metodo, caminho, body=corpo, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        dados = resp.read()
        return resp.status, dados
    finally:
        conn.close()


def esperar_pronto(backend, h, runtime, timeout_s, intervalo_ms):
    """Sonda /alive até HTTP 200. Não executa o handler de trabalho.
    Retorna (t_ready_ns, n_sondagens)."""
    metodo, corpo = ("POST", "{}") if runtime == "nodejs" else ("GET", None)  # SeBS: node usa POST /alive
    limite = time.perf_counter() + timeout_s
    n, prox_checagem = 0, time.perf_counter() + 1.0
    while True:
        n += 1
        try:
            status, _ = _http(h.porta, metodo, "/alive", corpo, timeout=1.0)
            if status == 200:
                return time.perf_counter_ns(), n
        except (OSError, http.client.HTTPException):
            pass
        agora = time.perf_counter()
        if agora >= prox_checagem:                 # contêiner/processo ainda existe?
            ok, motivo = backend.vivo(h)
            if not ok:
                raise FalhaInicializacao(motivo or "morreu_antes_de_ficar_pronto")
            prox_checagem = agora + 1.0
        if agora > limite:
            raise FalhaInicializacao("timeout_pronto", f"{timeout_s}s")
        time.sleep(intervalo_ms / 1000)


def invocar(porta, evento, timeout_s):
    """Retorna (t_envio_ns, t_resp_ns, status, corpo_json|None)."""
    corpo = json.dumps(evento)
    t_env = time.perf_counter_ns()
    status, dados = _http(porta, "POST", "/", corpo, timeout_s)
    t_resp = time.perf_counter_ns()
    try:
        j = json.loads(dados)
    except ValueError:
        j = None
    return t_env, t_resp, status, j


def validar(validador, evento, corpo, runtime, status):
    """Retorna '' se válido, ou o motivo da invalidação."""
    if status != 200:
        return f"http_{status}"
    if corpo is None:
        return "resposta_nao_json"
    try:
        saida = corpo["result"]["output"]
    except (KeyError, TypeError):
        return "formato_inesperado"
    if validador is None:
        return ""   # sem validador disponível no host; registrar na meta
    try:
        return validador(None, evento, saida, runtime, None) or ""
    except Exception as e:  # noqa: BLE001
        return f"validador_erro:{type(e).__name__}"


def _ms(a, b):
    return None if a is None or b is None else (b - a) / NS_MS


def preparar_cache(backend, cfg, env_extra, evento, validador, amb, opts):
    """Fora de t0. Aquecido: contêiner sacrificial idêntico. Descartado: drop_caches."""
    if cfg["cache"] == "descartado":
        return {"cache_prep_s": coletores.descartar_caches(opts.get("drop_nivel", 3)), "cache_nivel": opts.get("drop_nivel", 3)}
    t = time.perf_counter()
    h = None
    try:
        h = backend.criar(cfg, porta_livre(), env_extra)
        backend.iniciar(h)
        esperar_pronto(backend, h, cfg["runtime"], opts["timeout_pronto_s"], opts["intervalo_sondagem_ms"])
        invocar(h.porta, evento, opts["timeout_req_s"])
    finally:
        if h:
            backend.remover(h)
    return {"cache_prep_s": time.perf_counter() - t, "cache_nivel": None}


def medir(backend, cfg, evento, validador, env_extra, amb, opts, n_quente, id_base, dir_eventos=None):
    """Executa 1 amostra fria (+ n_quente invocações quentes no mesmo processo).
    Retorna lista de dicts (linha fria, depois linhas quentes). Nunca levanta por falha
    da amostra: a falha vira linha com `validacao` != 'ok'."""
    linhas = []
    try:
        prep = preparar_cache(backend, cfg, env_extra, evento, validador, amb, opts)
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ not in ("FalhaInicializacao", "RemoteDisconnected", "ConnectionResetError",
                                    "ConnectionRefusedError", "TimeoutError", "timeout"):
            raise   # ex.: falha de drop_caches: não pode contaminar a amostra em silêncio
        # o contêiner de aquecimento não subiu; a amostra fria abaixo falha pelo mesmo
        # motivo e vira uma linha `falha_inicio` no CSV, sem abortar o piloto
        prep = {"cache_prep_s": None, "cache_nivel": None}
    porta = porta_livre()
    host_antes = coletores.condicoes_host()
    h, ev = None, None
    fria = {"tipo": "frio", "amostra_id": f"{id_base}-f", **prep, **{f"host_{k}": v for k, v in host_antes.items()},
            "porta": porta, "intervalo_sondagem_ms": opts["intervalo_sondagem_ms"]}
    try:
        nome_pre = None
        if opts.get("eventos") and backend.nome == "docker" and dir_eventos:
            nome_pre = f"cs-{uuid.uuid4().hex[:10]}"
            ev = coletores.ColetorEventosDocker(nome_pre, Path(dir_eventos) / f"{id_base}.jsonl")
            ev.iniciar()                      # assinatura ativa antes de t0
        t0 = time.perf_counter_ns()
        t0_wall = time.time_ns()
        h = backend.criar(cfg, porta, env_extra, nome=nome_pre)
        t_created = time.perf_counter_ns()
        backend.iniciar(h)
        t_started = time.perf_counter_ns()
        t_ready, polls = esperar_pronto(backend, h, cfg["runtime"], opts["timeout_pronto_s"], opts["intervalo_sondagem_ms"])
        t_env, t_resp, status, corpo = invocar(porta, evento, opts["timeout_req_s"])

        fria.update(
            container_id=h.container_id, t0_wall_ns=t0_wall,
            t_created_ms=_ms(t0, t_created), t_started_ms=_ms(t0, t_started),
            t_ready_ms=_ms(t0, t_ready), gap_ready_req_ms=_ms(t_ready, t_env),
            t_req_cold_ms=_ms(t_env, t_resp), t_cold_total_ms=_ms(t0, t_resp),
            lat_req_ms=_ms(t_env, t_resp), sondagens=polls, http_status=status,
        )
        motivo = validar(validador, evento, corpo, cfg["runtime"], status)
        fria["validacao"] = "ok" if not motivo else "invalida"
        fria["motivo"] = motivo
        # tempo de import do módulo (Python importa a função na 1ª requisição) vindo do servidor
        if corpo and "begin" in corpo and "end" in corpo:
            try:
                fria["srv_import_ms"] = (float(corpo["end"]) - float(corpo["begin"])) * 1000
            except (TypeError, ValueError):
                pass
        fria.update(backend.pos_resposta(h))       # cgroup/proc: depois de t_resp
        if ev:
            for acao, tn in ev.parar().items():    # relógio de parede do daemon -> relativo a t0
                if acao in ("create", "start", "die", "oom") and tn:
                    rel = ev.mono_ns + (int(tn) - ev.wall_ns)
                    fria[f"ev_{acao}_ms"] = _ms(t0, rel)
            ev = None
        if fria.get("oom_flag") or (fria.get("oom_kill") or 0) > 0:
            fria["validacao"], fria["motivo"] = "oom", "oom_killed"
        linhas.append(fria)

        # invocações quentes: mesmo contêiner e processo, sem descartar caches
        if fria["validacao"] == "ok":
            for i in range(n_quente):
                te, tr, st, cj = invocar(porta, evento, opts["timeout_req_s"])
                mq = validar(validador, evento, cj, cfg["runtime"], st)
                linhas.append({"tipo": "quente", "amostra_id": f"{id_base}-q{i:03d}", "container_id": h.container_id,
                               "lat_req_ms": _ms(te, tr), "http_status": st,
                               "validacao": "ok" if not mq else "invalida", "motivo": mq})
    except FalhaInicializacao as e:
        fria.update(validacao="falha_inicio", motivo=e.motivo, detalhe=e.detalhe, container_id=getattr(h, "container_id", None))
        if e.motivo == "oom":
            fria["validacao"] = "oom"
        linhas.append(fria)
    except Exception as e:  # noqa: BLE001  (timeout HTTP, conexão recusada, etc.)
        fria.update(validacao="erro", motivo=type(e).__name__, detalhe=str(e)[:200],
                    container_id=getattr(h, "container_id", None))
        linhas.append(fria)
    finally:
        if ev:
            ev.parar()
        if h:
            backend.remover(h)
    return linhas
