"use strict";

const SEM_COR = "#DC2626";
const SEM_CONEXAO = "Sem conexão com o Bip";
const LIMITE_ACAO_MS = 15000;
// Consulta periódica que demora mais que isso conta como falha (programa travado).
const LIMITE_CONSULTA_MS = 3000;
// Consultas falhando sem parar por mais que isso: o Bip caiu.
const QUEDA_MS = 2000;
const $ = (id) => document.getElementById(id);

const estado = {
  ativo: null,
  colaboradores: [],
  ultimoEvento: 0,
  // Id do programa em execução. Muda quando ele reinicia (e os ids de evento recomeçam do 1).
  sessao: null,
  // Conta reinícios: resposta de /api/eventos pedida na sessão anterior é descartada.
  geracao: 0,
  // Listas precisam ser recarregadas do servidor no próximo ciclo.
  recarregar: false,
  periodo: "dia",
  pessoaSelecionada: undefined,
  audio: null,
};

// Utilidades

async function api(metodo, url, corpo, limiteMs = LIMITE_ACAO_MS) {
  const controle = new AbortController();
  const timer = setTimeout(() => controle.abort(), limiteMs);
  const opcoes = { method: metodo, headers: {}, signal: controle.signal };
  if (metodo !== "GET") {
    // O servidor exige JSON em toda alteração (proteção contra CSRF).
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo ?? {});
  }
  try {
    let resp;
    try {
      resp = await fetch(url, opcoes);
    } catch {
      throw new Error(SEM_CONEXAO);
    }
    if (resp.status === 204) return null;
    let dados;
    try {
      dados = await resp.json();
    } catch {
      // Corpo que não é JSON (página de erro, resposta cortada): nunca mostrar "Unexpected token".
      throw new Error(controle.signal.aborted ? SEM_CONEXAO : "Erro " + resp.status);
    }
    if (!resp.ok) throw new Error((dados && typeof dados.erro === "string" && dados.erro) || "Erro " + resp.status);
    return dados;
  } finally {
    clearTimeout(timer);
  }
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

function tocar(freq, vezes = 1, duracao = 0.15) {
  const ctx = estado.audio;
  if (!ctx) return;
  for (let i = 0; i < vezes; i++) {
    const inicio = ctx.currentTime + i * (duracao + 0.07);
    const osc = ctx.createOscillator();
    const ganho = ctx.createGain();
    osc.frequency.value = freq;
    osc.type = "square";
    ganho.gain.setValueAtTime(0.15, inicio);
    ganho.gain.setValueAtTime(0, inicio + duracao);
    osc.connect(ganho).connect(ctx.destination);
    osc.start(inicio);
    osc.stop(inicio + duracao + 0.01);
  }
}

function tocarAlarme() {
  tocar(110, 3, 0.35);
}

function somDoEvento(ev) {
  if (ev.tipo === "repetido") return tocar(220, 2);
  if (ev.tipo === "sem_colaborador") return tocar(150, 2);
  const c = estado.colaboradores.find((x) => x.id === ev.registro?.colaborador_id);
  tocar(c ? c.som_hz : 440);
}

// O navegador só libera som depois de um clique: o primeiro clique em qualquer
// lugar (normalmente no botão do colaborador) já ativa.
function ativarSom() {
  if (estado.audio) return;
  estado.audio = new AudioContext();
  $("ativar-som").hidden = true;
}

document.addEventListener("pointerdown", ativarSom, { capture: true });
$("ativar-som").addEventListener("click", () => tocar(660));

// Mensagens

// Os avisos ficam na camada do topo (popover), por cima da calibração e do diálogo.
// Mostrar de novo põe a camada na frente do que abriu depois dela.
function avisosNaFrente() {
  const avisos = $("avisos");
  if (!avisos.showPopover) return;
  if (avisos.matches(":popover-open")) avisos.hidePopover();
  avisos.showPopover();
}

new ResizeObserver(() => {
  document.documentElement.style.setProperty("--altura-topo", $("topo").offsetHeight + "px");
}).observe($("topo"));
avisosNaFrente();

// Aviso do bip: some sozinho em 3 s.
let avisoTimer = null;
function mostrarAviso(ev, outros = 0) {
  const a = $("aviso");
  a.dataset.tipo = ev.tipo;
  const texto = ev.tipo === "novo" ? `${ev.rastreio} · ${ev.mensagem}` : ev.mensagem;
  a.textContent = outros > 0 ? `${texto} (+${outros} ${outros === 1 ? "bip" : "bips"})` : texto;
  a.hidden = false;
  clearTimeout(avisoTimer);
  avisoTimer = setTimeout(() => { a.hidden = true; }, 3000);
}

$("aviso").addEventListener("click", () => { $("aviso").hidden = true; });

// Mensagens que não são bip: erro (vermelho), alerta (amarelo) e info. Clique fecha.
function mostrarMensagem(texto, tipo, ms) {
  const caixa = $("mensagens");
  for (const m of [...caixa.children]) if (m.textContent === texto) m.remove();
  const m = el("div", {
    class: "mensagem", "data-tipo": tipo, role: tipo === "info" ? "status" : "alert", title: "Clique para fechar",
  }, texto);
  const timer = setTimeout(() => m.remove(), ms);
  m.addEventListener("click", () => { clearTimeout(timer); m.remove(); });
  caixa.append(m);
  while (caixa.children.length > 3) caixa.firstElementChild.remove();
}

// Toda ação do usuário passa por aqui: se falhar, avisa em vermelho e redesenha a
// parte afetada a partir do servidor, para a tela nunca mostrar algo que não aconteceu.
async function acao(descricao, fn, recarregar) {
  try {
    await fn();
    return true;
  } catch (e) {
    mostrarMensagem(`Não foi possível ${descricao}: ${e.message}`, "erro", 7000);
    if (recarregar) {
      try { await recarregar(); } catch { /* sem conexão: a faixa vermelha avisa */ }
    }
    return false;
  }
}

// Botão que fica com foco seria disparado de novo por um Enter perdido (bip na janela errada).
function soltarFoco() {
  if (document.activeElement instanceof HTMLButtonElement) document.activeElement.blur();
}

document.addEventListener("click", (ev) => {
  const b = ev.target instanceof Element ? ev.target.closest("button") : null;
  if (b) b.blur();
});

// Diálogo na própria página (no lugar de prompt/confirm, que travam a página e o som).
// Com `campo` devolve o texto digitado ou null; sem, devolve true/false.
function abrirDialogo({ titulo, texto = "", campo = null, confirmar = "OK", perigo = false }) {
  const d = $("dialogo");
  const entrada = $("dialogo-campo");
  if (d.open) return Promise.resolve(campo === null ? false : null);
  $("dialogo-titulo").textContent = titulo;
  $("dialogo-texto").textContent = texto;
  $("dialogo-texto").hidden = !texto;
  entrada.hidden = campo === null;
  entrada.value = campo ?? "";
  $("dialogo-ok").textContent = confirmar;
  $("dialogo-ok").classList.toggle("perigo", perigo);
  d.returnValue = "";
  d.showModal();
  avisosNaFrente();
  if (campo === null) {
    $("dialogo-cancelar").focus();
  } else {
    entrada.focus();
    entrada.select();
  }
  return new Promise((resolve) => {
    d.addEventListener("close", () => {
      soltarFoco();
      const confirmou = d.returnValue === "ok";
      resolve(campo === null ? confirmou : confirmou ? entrada.value : null);
    }, { once: true });
  });
}

$("dialogo-cancelar").addEventListener("click", () => $("dialogo").close(""));

// Bip na janela do Bip: se esta janela está com o foco, o UpSeller não recebe o bip
// (o Bip registra assim mesmo, pela escuta global). Leitor = 10+ teclas com menos de
// 50 ms entre elas, seguidas de Enter.
const RAJADA_MIN_TECLAS = 10;
const RAJADA_INTERVALO_MS = 50;
const RAJADA_VAZIA = { teclas: 0, ultimo: 0, alvo: null, valor: null, selecao: null };
let rajada = RAJADA_VAZIA;

function campoDeTexto(n) {
  return n instanceof HTMLTextAreaElement || (n instanceof HTMLInputElement && (n.type === "text" || n.type === "search"));
}

window.addEventListener("keydown", (ev) => {
  // O leitor aperta Shift para letra maiúscula: não quebra a sequência.
  if (ev.key === "Shift" || ev.key === "CapsLock") return;
  const alfanumerico = ev.key.length === 1 && /^[0-9a-z]$/i.test(ev.key)
    && !ev.ctrlKey && !ev.altKey && !ev.metaKey && !ev.repeat;
  const emSequencia = rajada.teclas > 0 && ev.timeStamp - rajada.ultimo < RAJADA_INTERVALO_MS;
  if (alfanumerico) {
    if (!emSequencia) {
      const alvo = document.activeElement;
      const texto = campoDeTexto(alvo);
      rajada = {
        teclas: 0, ultimo: 0, alvo,
        valor: texto ? alvo.value : null,
        selecao: texto ? [alvo.selectionStart, alvo.selectionEnd] : null,
      };
    }
    rajada.teclas++;
    rajada.ultimo = ev.timeStamp;
    // Num <select> com foco, digitar escolhe a opção pelo nome: um bip poderia mover um registro.
    if (document.activeElement instanceof HTMLSelectElement) ev.preventDefault();
    return;
  }
  const r = rajada;
  rajada = RAJADA_VAZIA;
  if (ev.key !== "Enter" || !emSequencia || r.teclas < RAJADA_MIN_TECLAS) return;
  ev.preventDefault();
  ev.stopImmediatePropagation();
  if (r.valor !== null && r.alvo.isConnected) {
    r.alvo.value = r.valor;
    try { r.alvo.setSelectionRange(...r.selecao); } catch { /* campo sem seleção */ }
    r.alvo.dispatchEvent(new Event("input", { bubbles: true }));
  }
  mostrarMensagem("Esse bip foi para a janela do Bip, não para o UpSeller. Clique no UpSeller e bipe de novo. Aqui vai aparecer \"Já registrado\", é normal.", "alerta", 8000);
}, { capture: true });

// Abas

function abaVisivel(nome) {
  return !$("aba-" + nome).hidden;
}

function mostrarAba(nome) {
  for (const b of document.querySelectorAll(".abas button")) {
    b.setAttribute("aria-selected", String(b.dataset.aba === nome));
  }
  for (const s of document.querySelectorAll(".aba")) s.hidden = s.id !== "aba-" + nome;
  if (nome === "pesquisar") $("busca").focus();
  if (nome === "relatorios") acao("carregar o relatório", carregarRelatorio, recarregarRelatorio);
  if (nome === "colaboradores") acao("carregar os colaboradores", carregarColaboradores, limparColaboradores);
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
  mover.addEventListener("change", () => {
    const destino = mover.value;
    // Volta para "Mover para…" na hora: se falhar, o select não fica mostrando a escolha.
    mover.value = "";
    mover.blur();
    if (!destino) return;
    acao("mover", async () => {
      await api("PATCH", `/api/registros/${r.id}`, { colaborador_id: destino === "sem" ? null : Number(destino) });
      await aoMudar();
    }, aoMudar);
  });

  const erro = r.erro
    ? el("button", { type: "button", onclick: () => acao("desfazer o erro", async () => {
        await api("DELETE", `/api/registros/${r.id}/erro`);
        await aoMudar();
      }, aoMudar) }, "Desfazer erro")
    : el("button", { type: "button", class: "perigo", onclick: async () => {
        const obs = await abrirDialogo({
          titulo: "Peça errada", texto: `Pacote ${r.rastreio}. Observação (opcional):`,
          campo: "", confirmar: "Marcar peça errada", perigo: true,
        });
        if (obs === null) return;
        await acao("marcar peça errada", async () => {
          await api("POST", `/api/registros/${r.id}/erro`, { obs });
          await aoMudar();
        }, aoMudar);
      } }, "Peça errada");

  const excluir = el("button", { type: "button", class: "perigo", onclick: async () => {
    const ok = await abrirDialogo({
      titulo: "Excluir registro", texto: `Excluir o registro ${r.rastreio}?`, confirmar: "Excluir", perigo: true,
    });
    if (!ok) return;
    await acao("excluir", async () => {
      await api("DELETE", `/api/registros/${r.id}`);
      await aoMudar();
    }, aoMudar);
  } }, "Excluir");

  return el("li", {},
    el("span", { class: "rastreio" }, r.rastreio),
    el("span", { class: "hora" }, formatarHora(r.bipado_em)),
    el("span", { class: "quem" + (sem ? " sem" : ""), style: `--cor:${cor}` }, sem ? "Sem colaborador" : r.colaborador_nome),
    r.erro ? el("span", { class: "marca-erro" }, "Peça errada" + (r.erro_obs ? `: ${r.erro_obs}` : "")) : null,
    el("div", { class: "acoes" }, erro, mover, excluir));
}

// Bipar

// Botões só são recriados quando a lista de colaboradores muda. Recriar a cada
// atualização engole cliques (mousedown num botão, mouseup no substituto).
let chaveBotoes = "";

function desenharPainel() {
  const a = estado.ativo;
  $("painel").style.setProperty("--cor", a ? a.cor : SEM_COR);
  $("painel-nome").textContent = a ? a.nome : "Sem colaborador";
  const chave = JSON.stringify(estado.colaboradores.map((c) => [c.id, c.nome, c.cor]));
  if (chave !== chaveBotoes) {
    chaveBotoes = chave;
    const botoes = estado.colaboradores.map((c) => el("button", {
      type: "button", style: `--cor:${c.cor}`, "data-id": String(c.id), onclick: () => definirAtivo(c.id),
    }, c.nome));
    botoes.push(el("button", {
      type: "button", style: `--cor:${SEM_COR}`, "data-id": "", onclick: () => definirAtivo(null),
    }, "Sem colaborador"));
    $("botoes-colab").replaceChildren(...botoes);
  }
  const idAtivo = a ? String(a.id) : "";
  for (const b of $("botoes-colab").children) b.setAttribute("aria-pressed", String(b.dataset.id === idAtivo));
}

// Conta trocas de colaborador: resposta de /api/estado que saiu antes de uma troca
// chega atrasada com o colaborador antigo e não pode desfazer a troca na tela.
// Conta no início e no fim da troca: vale também para a consulta feita durante ela.
let trocas = 0;

function definirAtivo(id) {
  return acao("trocar o colaborador", async () => {
    trocas++;
    let resp;
    try {
      resp = await api("POST", "/api/ativo", { colaborador_id: id });
    } finally {
      trocas++;
    }
    estado.ativo = resp.ativo;
    desenharPainel();
    if (estado.audio && resp.ativo) tocar(resp.ativo.som_hz);
  }, atualizarTudo);
}

async function carregarUltimos() {
  const lista = await api("GET", "/api/registros/ultimos");
  $("ultimos").replaceChildren(...lista.map((r) => linhaRegistro(r, carregarUltimos)));
}

// Pesquisar

function buscaAtual() {
  return $("busca").value.trim();
}

let buscaTimer = null;
async function pesquisar() {
  const q = buscaAtual();
  $("busca-vazia").hidden = q.length >= 3;
  if (q.length < 3) { $("resultados").replaceChildren(); return; }
  let lista;
  try {
    lista = await api("GET", "/api/busca?q=" + encodeURIComponent(q));
  } catch (e) {
    if (buscaAtual() !== q) return; // falha de uma busca que já foi trocada por outra
    $("resultados").replaceChildren();
    throw e;
  }
  // Resposta fora de ordem: o campo já tem outra busca.
  if (buscaAtual() !== q) return;
  if (lista.length === 0) {
    $("resultados").replaceChildren(el("li", {}, el("span", {}, `Nenhum pacote com "${q}".`)));
    return;
  }
  $("resultados").replaceChildren(...lista.map((r) => linhaRegistro(r, pesquisar)));
}

$("busca").addEventListener("input", () => {
  clearTimeout(buscaTimer);
  buscaTimer = setTimeout(() => acao("pesquisar", pesquisar), 300);
});

// Relatórios

function marcarPeriodo() {
  for (const x of document.querySelectorAll(".periodos button")) {
    x.setAttribute("aria-pressed", String(x.dataset.periodo === estado.periodo));
  }
}

for (const b of document.querySelectorAll(".periodos button")) {
  b.addEventListener("click", () => {
    estado.periodo = b.dataset.periodo;
    estado.pessoaSelecionada = undefined;
    marcarPeriodo();
    acao("carregar o relatório", carregarRelatorio, recarregarRelatorio);
  });
}

// Depois de uma falha: nada do que estava na tela fica, e o resumo (sem pessoa
// escolhida) é pedido de novo. Se o servidor caiu, fica vazio.
async function recarregarRelatorio() {
  $("resumo").replaceChildren();
  $("resumo-vazio").hidden = true;
  $("lista-titulo").hidden = true;
  $("lista-pessoa").replaceChildren();
  estado.pessoaSelecionada = undefined;
  await carregarRelatorio();
}

async function carregarRelatorio() {
  const periodo = estado.periodo;
  const chave = estado.pessoaSelecionada;
  const mudou = () => periodo !== estado.periodo || chave !== estado.pessoaSelecionada;
  let linhas, lista;
  try {
    [linhas, lista] = await Promise.all([
      api("GET", "/api/relatorio?periodo=" + periodo),
      chave === undefined ? null : api("GET", `/api/relatorio/lista?periodo=${periodo}&colaborador_id=${chave}`),
    ]);
  } catch (e) {
    if (mudou()) return; // outro período ou pessoa já foi escolhido: essa falha não importa
    throw e;
  }
  if (mudou()) return;
  $("resumo-vazio").hidden = linhas.length > 0;
  $("resumo").replaceChildren(...linhas.map((l) => {
    const chaveLinha = l.colaborador_id === null ? "sem" : String(l.colaborador_id);
    return el("tr", {
      "aria-selected": String(chave === chaveLinha),
      onclick: () => {
        estado.pessoaSelecionada = chaveLinha;
        acao("carregar os pacotes", carregarRelatorio, recarregarRelatorio);
      },
    },
      el("td", {}, el("span", { class: "quem" + (chaveLinha === "sem" ? " sem" : ""), style: `--cor:${l.cor}` }, l.nome)),
      el("td", {}, String(l.pacotes)),
      el("td", {}, String(l.erros)),
      el("td", {}, formatarTaxa(l.taxa)));
  }));
  const linha = linhas.find((l) => (l.colaborador_id === null ? "sem" : String(l.colaborador_id)) === chave);
  $("lista-titulo").hidden = !linha;
  if (!linha) { $("lista-pessoa").replaceChildren(); return; }
  $("lista-titulo").textContent = `Pacotes de ${linha.nome}`;
  $("lista-pessoa").replaceChildren(...lista.map((r) => linhaRegistro(r, carregarRelatorio)));
}

// Colaboradores

function limparColaboradores() {
  $("colaboradores").replaceChildren();
  $("limiar").textContent = "";
}

async function carregarColaboradores() {
  const inativos = $("mostrar-inativos").checked;
  const [lista, e] = await Promise.all([
    api("GET", "/api/colaboradores" + (inativos ? "?inativos=1" : "")),
    api("GET", "/api/estado"),
  ]);
  $("colaboradores").replaceChildren(...lista.map(linhaColaborador));
  $("limiar").textContent = `Leitor calibrado: ${e.calibracao.limiar_ms} ms`;
}

async function recarregarColaboradores() {
  await atualizarTudo();
  await carregarColaboradores();
}

function linhaColaborador(c) {
  const cor = el("input", { type: "color", value: c.cor, "aria-label": `Cor de ${c.nome}` });
  cor.addEventListener("change", async () => {
    cor.blur();
    if (!(await salvarColaborador(c.id, { cor: cor.value }, "mudar a cor"))) cor.value = c.cor;
  });
  const renomear = el("button", { type: "button", onclick: async () => {
    const nome = await abrirDialogo({
      titulo: "Renomear colaborador", texto: `Novo nome para ${c.nome}:`, campo: c.nome, confirmar: "Salvar",
    });
    if (nome && nome.trim() !== c.nome) await salvarColaborador(c.id, { nome }, "renomear");
  } }, "Renomear");
  const ativar = c.ativo
    ? el("button", { type: "button", class: "perigo", onclick: () => salvarColaborador(c.id, { ativo: false }, "desativar") }, "Desativar")
    : el("button", { type: "button", onclick: () => salvarColaborador(c.id, { ativo: true }, "reativar") }, "Reativar");
  return el("li", { class: "colab-linha" + (c.ativo ? "" : " inativo") },
    el("span", { class: "quem", style: `--cor:${c.cor}` }, c.nome),
    cor,
    el("div", { class: "acoes" }, renomear, ativar));
}

function salvarColaborador(id, dados, descricao) {
  return acao(descricao, async () => {
    await api("PATCH", `/api/colaboradores/${id}`, dados);
    await recarregarColaboradores();
  }, recarregarColaboradores);
}

$("form-colab").addEventListener("submit", (ev) => {
  ev.preventDefault();
  acao("adicionar o colaborador", async () => {
    await api("POST", "/api/colaboradores", { nome: $("novo-nome").value });
    $("novo-nome").value = "";
    await recarregarColaboradores();
  }, recarregarColaboradores);
});

$("mostrar-inativos").addEventListener("change", () => {
  acao("carregar os colaboradores", carregarColaboradores, limparColaboradores);
});

$("recalibrar").addEventListener("click", async () => {
  const ok = await abrirDialogo({
    titulo: "Recalibrar o leitor?", texto: "Depois bipe 3 pacotes no UpSeller.", confirmar: "Recalibrar",
  });
  if (!ok) return;
  await acao("recalibrar", async () => {
    await api("POST", "/api/calibracao");
    await atualizarEstado();
  }, atualizarEstado);
});

$("cancelar-calibracao").addEventListener("click", () => {
  acao("cancelar a calibração", async () => {
    await api("POST", "/api/calibracao/cancelar");
    await atualizarEstado();
  }, atualizarEstado);
});

// Faixas de problema no topo

let desconectado = false;
let escutaAtiva = true;

function desenharFaixas() {
  $("faixa-desconectado").hidden = !desconectado;
  // Desconectado não dá para saber da escuta; a faixa de queda já basta.
  $("faixa-escuta").hidden = desconectado || escutaAtiva;
}

// Momento da primeira falha seguida das consultas (null = conectado).
let falhaDesde = null;

function conexaoVoltou() {
  falhaDesde = null;
  if (!desconectado) return;
  desconectado = false;
  desenharFaixas();
}

function conexaoFalhou() {
  if (falhaDesde === null) falhaDesde = performance.now();
  vigiarConexao();
}

function vigiarConexao() {
  if (desconectado || falhaDesde === null || performance.now() - falhaDesde < QUEDA_MS) return;
  desconectado = true;
  desenharFaixas();
  tocarAlarme();
}

// Estado e polling

function desenharCalibracao(c) {
  $("calibracao").hidden = !c.calibrando;
  $("calibracao-progresso").textContent = `${c.amostras}/${c.total}`;
}

async function atualizarEstado(limiteMs) {
  const trocasAntes = trocas;
  const e = await api("GET", "/api/estado", undefined, limiteMs);
  if (estado.sessao === null) {
    // Primeira resposta: bips de antes da tela abrir não viram aviso.
    estado.sessao = e.sessao;
    estado.ultimoEvento = e.ultimo_evento_id;
    estado.recarregar = true;
  } else if (e.sessao !== estado.sessao) {
    // O programa reiniciou: os ids de evento recomeçam do 1.
    estado.sessao = e.sessao;
    estado.ultimoEvento = 0;
    estado.geracao++;
    estado.recarregar = true;
    mostrarMensagem("O Bip foi reiniciado", "info", 3000);
  }
  if (trocas === trocasAntes) estado.ativo = e.ativo;
  const escuta = e.escuta_ativa !== false;
  if (escutaAtiva && !escuta) tocarAlarme();
  escutaAtiva = escuta;
  desenharFaixas();
  desenharCalibracao(e.calibracao);
  desenharPainel();
  return e;
}

async function atualizarTudo() {
  estado.colaboradores = await api("GET", "/api/colaboradores");
  await atualizarEstado();
  await carregarUltimos();
}

// Depois de início ou reinício do programa: tudo, inclusive a aba aberta.
async function recarregarTudo() {
  await atualizarTudo();
  if (abaVisivel("relatorios")) await carregarRelatorio();
  if (abaVisivel("colaboradores")) await carregarColaboradores();
  if (abaVisivel("pesquisar")) await pesquisar();
}

async function recarregarAposBips() {
  await atualizarEstado();
  await carregarUltimos();
  if (abaVisivel("relatorios")) await carregarRelatorio();
}

// Vários bips na mesma consulta: o aviso e o som são do mais grave (empate: o mais recente).
const GRAVIDADE = { novo: 0, sem_colaborador: 1, repetido: 2 };

function maisGrave(eventos) {
  let escolhido = eventos[0];
  for (const ev of eventos) {
    if ((GRAVIDADE[ev.tipo] ?? 0) >= (GRAVIDADE[escolhido.tipo] ?? 0)) escolhido = ev;
  }
  return escolhido;
}

function avisarEventos(eventos) {
  const ultimo = eventos[eventos.length - 1];
  estado.ultimoEvento = ultimo.id;
  $("painel-ultimo").textContent = ultimo.rastreio;
  const grave = maisGrave(eventos);
  mostrarAviso(grave, eventos.length - 1);
  somDoEvento(grave);
}

async function consultar() {
  let eventos, geracao;
  try {
    // /api/estado antes dos eventos: um reinício é percebido antes de usar o cursor velho.
    await atualizarEstado(LIMITE_CONSULTA_MS);
    geracao = estado.geracao;
    eventos = await api("GET", "/api/eventos?desde=" + estado.ultimoEvento, undefined, LIMITE_CONSULTA_MS);
  } catch {
    conexaoFalhou();
    return;
  }
  conexaoVoltou();
  const houveBips = geracao === estado.geracao && eventos.length > 0;
  if (houveBips) avisarEventos(eventos);
  if (!houveBips && !estado.recarregar) return;
  const tudo = estado.recarregar;
  estado.recarregar = false;
  try {
    await (tudo ? recarregarTudo() : recarregarAposBips());
  } catch {
    estado.recarregar = true; // tenta de novo no próximo ciclo
  }
}

async function ciclo() {
  try {
    await consultar();
  } catch (e) {
    console.error(e);
  }
  setTimeout(ciclo, 500);
}

setInterval(vigiarConexao, 250);
ciclo();
