"use strict";

const SEM_COR = "#DC2626";
const $ = (id) => document.getElementById(id);

const estado = {
  ativo: null,
  colaboradores: [],
  ultimoEvento: 0,
  periodo: "dia",
  pessoaSelecionada: undefined,
  audio: null,
};

// Utilidades

async function api(metodo, url, corpo) {
  const opcoes = { method: metodo, headers: {} };
  if (metodo !== "GET") {
    // O servidor exige JSON em toda alteração (proteção contra CSRF).
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo ?? {});
  }
  const resp = await fetch(url, opcoes);
  if (resp.status === 204) return null;
  const dados = await resp.json();
  if (!resp.ok) throw new Error(dados.erro || "Erro " + resp.status);
  return dados;
}

function el(tag, attrs = {}, ...filhos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "style") n.style.cssText = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const f of filhos) if (f !== null && f !== undefined) n.append(f);
  return n;
}

function formatarHora(iso) {
  const [data, hora] = iso.split("T");
  const [, mes, dia] = data.split("-");
  return `${dia}/${mes} ${hora.slice(0, 5)}`;
}

function formatarTaxa(taxa) {
  return (taxa * 100).toFixed(1).replace(".", ",") + "%";
}

// Som

function tocar(freq, vezes = 1) {
  const ctx = estado.audio;
  if (!ctx) return;
  for (let i = 0; i < vezes; i++) {
    const inicio = ctx.currentTime + i * 0.22;
    const osc = ctx.createOscillator();
    const ganho = ctx.createGain();
    osc.frequency.value = freq;
    osc.type = "square";
    ganho.gain.setValueAtTime(0.15, inicio);
    ganho.gain.setValueAtTime(0, inicio + 0.15);
    osc.connect(ganho).connect(ctx.destination);
    osc.start(inicio);
    osc.stop(inicio + 0.16);
  }
}

function somDoEvento(ev) {
  if (ev.tipo === "repetido") return tocar(220, 2);
  if (ev.tipo === "sem_colaborador") return tocar(150, 2);
  const c = estado.colaboradores.find((x) => x.id === ev.registro.colaborador_id);
  tocar(c ? c.som_hz : 440);
}

$("ativar-som").addEventListener("click", () => {
  estado.audio = new AudioContext();
  $("ativar-som").hidden = true;
  tocar(660);
});

// Abas

function mostrarAba(nome) {
  for (const b of document.querySelectorAll(".abas button")) {
    b.setAttribute("aria-selected", String(b.dataset.aba === nome));
  }
  for (const s of document.querySelectorAll(".aba")) s.hidden = s.id !== "aba-" + nome;
  if (nome === "pesquisar") $("busca").focus();
  if (nome === "relatorios") carregarRelatorio();
  if (nome === "colaboradores") carregarColaboradores();
}

for (const b of document.querySelectorAll(".abas button")) {
  b.addEventListener("click", () => mostrarAba(b.dataset.aba));
}

// Linha de registro (usada nas listas de bips, pesquisa e relatório)

function linhaRegistro(r, aoMudar) {
  const sem = r.colaborador_id === null;
  const cor = sem ? SEM_COR : r.colaborador_cor;
  const mover = el("select", { "aria-label": "Mover para" },
    el("option", { value: "" }, "Mover para…"),
    el("option", { value: "sem" }, "Sem colaborador"),
    ...estado.colaboradores
      .filter((c) => c.id !== r.colaborador_id)
      .map((c) => el("option", { value: String(c.id) }, c.nome)));
  mover.addEventListener("change", async () => {
    if (!mover.value) return;
    await api("PATCH", `/api/registros/${r.id}`, { colaborador_id: mover.value === "sem" ? null : Number(mover.value) });
    aoMudar();
  });

  const erro = r.erro
    ? el("button", { type: "button", onclick: async () => { await api("DELETE", `/api/registros/${r.id}/erro`); aoMudar(); } }, "Desfazer erro")
    : el("button", { type: "button", class: "perigo", onclick: async () => {
        const obs = prompt("Peça errada. Observação (opcional):", "");
        if (obs === null) return;
        await api("POST", `/api/registros/${r.id}/erro`, { obs });
        aoMudar();
      } }, "Peça errada");

  const excluir = el("button", { type: "button", class: "perigo", onclick: async () => {
    if (!confirm(`Excluir o registro ${r.rastreio}?`)) return;
    await api("DELETE", `/api/registros/${r.id}`);
    aoMudar();
  } }, "Excluir");

  return el("li", {},
    el("span", { class: "rastreio" }, r.rastreio),
    el("span", { class: "hora" }, formatarHora(r.bipado_em)),
    el("span", { class: "quem" + (sem ? " sem" : ""), style: `--cor:${cor}` }, sem ? "Sem colaborador" : r.colaborador_nome),
    r.erro ? el("span", { class: "marca-erro" }, "Peça errada" + (r.erro_obs ? `: ${r.erro_obs}` : "")) : null,
    el("div", { class: "acoes" }, erro, mover, excluir));
}

// Bipar

function desenharPainel() {
  const a = estado.ativo;
  $("painel").style.setProperty("--cor", a ? a.cor : SEM_COR);
  $("painel-nome").textContent = a ? a.nome : "Sem colaborador";
  const botoes = estado.colaboradores.map((c) => el("button", {
    type: "button", style: `--cor:${c.cor}`, "aria-pressed": String(a !== null && a.id === c.id),
    onclick: () => definirAtivo(c.id),
  }, c.nome));
  botoes.push(el("button", {
    type: "button", style: `--cor:${SEM_COR}`, "aria-pressed": String(a === null),
    onclick: () => definirAtivo(null),
  }, "Sem colaborador"));
  $("botoes-colab").replaceChildren(...botoes);
}

async function definirAtivo(id) {
  const resp = await api("POST", "/api/ativo", { colaborador_id: id });
  estado.ativo = resp.ativo;
  desenharPainel();
  if (estado.audio && resp.ativo) tocar(resp.ativo.som_hz);
}

async function carregarUltimos() {
  const lista = await api("GET", "/api/registros/ultimos");
  $("ultimos").replaceChildren(...lista.map((r) => linhaRegistro(r, carregarUltimos)));
}

// Aviso

let avisoTimer = null;
function mostrarAviso(ev) {
  const a = $("aviso");
  a.dataset.tipo = ev.tipo;
  a.textContent = ev.tipo === "novo" ? `${ev.rastreio} · ${ev.mensagem}` : ev.mensagem;
  a.hidden = false;
  clearTimeout(avisoTimer);
  avisoTimer = setTimeout(() => { a.hidden = true; }, 3000);
}

// Pesquisar

let buscaTimer = null;
async function pesquisar() {
  const q = $("busca").value.trim();
  $("busca-vazia").hidden = q.length >= 3;
  if (q.length < 3) { $("resultados").replaceChildren(); return; }
  const lista = await api("GET", "/api/busca?q=" + encodeURIComponent(q));
  if (lista.length === 0) {
    $("resultados").replaceChildren(el("li", {}, el("span", {}, `Nenhum pacote com "${q}".`)));
    return;
  }
  $("resultados").replaceChildren(...lista.map((r) => linhaRegistro(r, pesquisar)));
}

$("busca").addEventListener("input", () => {
  clearTimeout(buscaTimer);
  buscaTimer = setTimeout(pesquisar, 300);
});

// Relatórios

for (const b of document.querySelectorAll(".periodos button")) {
  b.addEventListener("click", () => {
    estado.periodo = b.dataset.periodo;
    estado.pessoaSelecionada = undefined;
    for (const x of document.querySelectorAll(".periodos button")) x.setAttribute("aria-pressed", String(x === b));
    carregarRelatorio();
  });
}

async function carregarRelatorio() {
  const linhas = await api("GET", "/api/relatorio?periodo=" + estado.periodo);
  $("resumo-vazio").hidden = linhas.length > 0;
  $("resumo").replaceChildren(...linhas.map((l) => {
    const chave = l.colaborador_id === null ? "sem" : String(l.colaborador_id);
    return el("tr", {
      "aria-selected": String(estado.pessoaSelecionada === chave),
      onclick: () => { estado.pessoaSelecionada = chave; carregarRelatorio(); },
    },
      el("td", {}, el("span", { class: "quem" + (chave === "sem" ? " sem" : ""), style: `--cor:${l.cor}` }, l.nome)),
      el("td", {}, String(l.pacotes)),
      el("td", {}, String(l.erros)),
      el("td", {}, formatarTaxa(l.taxa)));
  }));
  await carregarListaPessoa(linhas);
}

async function carregarListaPessoa(linhas) {
  const chave = estado.pessoaSelecionada;
  const linha = linhas.find((l) => (l.colaborador_id === null ? "sem" : String(l.colaborador_id)) === chave);
  $("lista-titulo").hidden = !linha;
  if (!linha) { $("lista-pessoa").replaceChildren(); return; }
  $("lista-titulo").textContent = `Pacotes de ${linha.nome}`;
  const lista = await api("GET", `/api/relatorio/lista?periodo=${estado.periodo}&colaborador_id=${chave}`);
  $("lista-pessoa").replaceChildren(...lista.map((r) => linhaRegistro(r, carregarRelatorio)));
}

// Colaboradores

async function carregarColaboradores() {
  const inativos = $("mostrar-inativos").checked;
  const lista = await api("GET", "/api/colaboradores" + (inativos ? "?inativos=1" : ""));
  $("colaboradores").replaceChildren(...lista.map(linhaColaborador));
  $("limiar").textContent = "";
  const e = await api("GET", "/api/estado");
  $("limiar").textContent = `Leitor calibrado: ${e.calibracao.limiar_ms} ms`;
}

function linhaColaborador(c) {
  const cor = el("input", { type: "color", value: c.cor, "aria-label": `Cor de ${c.nome}` });
  cor.addEventListener("change", () => salvarColaborador(c.id, { cor: cor.value }));
  const renomear = el("button", { type: "button", onclick: () => {
    const nome = prompt("Novo nome:", c.nome);
    if (nome && nome.trim() !== c.nome) salvarColaborador(c.id, { nome });
  } }, "Renomear");
  const ativar = c.ativo
    ? el("button", { type: "button", class: "perigo", onclick: () => salvarColaborador(c.id, { ativo: false }) }, "Desativar")
    : el("button", { type: "button", onclick: () => salvarColaborador(c.id, { ativo: true }) }, "Reativar");
  return el("li", { class: "colab-linha" + (c.ativo ? "" : " inativo") },
    el("span", { class: "quem", style: `--cor:${c.cor}` }, c.nome),
    cor,
    el("div", { class: "acoes" }, renomear, ativar));
}

async function salvarColaborador(id, dados) {
  $("colab-erro").hidden = true;
  try {
    await api("PATCH", `/api/colaboradores/${id}`, dados);
  } catch (e) {
    $("colab-erro").textContent = e.message;
    $("colab-erro").hidden = false;
  }
  await atualizarTudo();
  await carregarColaboradores();
}

$("form-colab").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  $("colab-erro").hidden = true;
  try {
    await api("POST", "/api/colaboradores", { nome: $("novo-nome").value });
    $("novo-nome").value = "";
  } catch (e) {
    $("colab-erro").textContent = e.message;
    $("colab-erro").hidden = false;
  }
  await atualizarTudo();
  await carregarColaboradores();
});

$("mostrar-inativos").addEventListener("change", carregarColaboradores);

$("recalibrar").addEventListener("click", async () => {
  if (!confirm("Recalibrar o leitor? Depois bipe 3 pacotes no UpSeller.")) return;
  await api("POST", "/api/calibracao");
  await atualizarEstado();
});

// Estado e polling

function desenharCalibracao(c) {
  $("calibracao").hidden = !c.calibrando;
  $("calibracao-progresso").textContent = `${c.amostras}/${c.total}`;
}

async function atualizarEstado() {
  const e = await api("GET", "/api/estado");
  estado.ativo = e.ativo;
  desenharCalibracao(e.calibracao);
  desenharPainel();
  return e;
}

async function atualizarTudo() {
  estado.colaboradores = await api("GET", "/api/colaboradores");
  await atualizarEstado();
  await carregarUltimos();
}

async function verificarEventos() {
  try {
    const eventos = await api("GET", "/api/eventos?desde=" + estado.ultimoEvento);
    if (eventos.length > 0) {
      estado.ultimoEvento = eventos[eventos.length - 1].id;
      const ultimo = eventos[eventos.length - 1];
      $("painel-ultimo").textContent = ultimo.rastreio;
      mostrarAviso(ultimo);
      somDoEvento(ultimo);
      await atualizarEstado();
      await carregarUltimos();
    }
  } catch (e) {
    // Servidor reiniciando: tenta de novo no próximo ciclo.
  }
  setTimeout(verificarEventos, 500);
}

async function iniciar() {
  const e = await api("GET", "/api/estado");
  estado.ultimoEvento = e.ultimo_evento_id;
  await atualizarTudo();
  verificarEventos();
  setInterval(() => atualizarEstado().catch(() => {}), 2000);
}

iniciar();
