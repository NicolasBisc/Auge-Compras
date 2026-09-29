"use strict";
/* =============================================================================
   Auge · Compras e conciliação — interface
   Uma página, várias telas (#painel, #projecao, #precos, #conciliacao,
   #aquisicoes, #cadastros, #regras). Os dados vêm da API; sem servidor, de
   js/dados-exemplo.js. Toda escrita passa pela API — no modo exemplo, só valida.
   ============================================================================= */

/* ---------------------------------------------------------------- utilidades */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = {
  brl: (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v ?? 0),
  num: (v, c = 1) => new Intl.NumberFormat("pt-BR", { maximumFractionDigits: c }).format(v ?? 0),
  pct: (v) => (v > 0 ? "+" : "") + new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1 }).format(v ?? 0),
  data: (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : ""),
  dia: (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : ""),
  dataLonga: (iso) => new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(new Date(iso + "T12:00:00Z")),
  cnpj: (d) => String(d || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5"),
  plural: (n, s, p) => `${fmt.num(n)} ${Math.abs(n) === 1 ? s : p}`,
};
const PLURAIS = { voucher: "vouchers", unidade: "unidades", "licença": "licenças", hora: "horas" };
const un = (nome, n) => (Math.abs(n) === 1 ? nome : PLURAIS[nome] || nome + "s");

const I = {
  seta: '<path d="M3 8h10M9 4l4 4-4 4"/>',
  chevron: '<path d="m4 6 4 4 4-4"/>',
  ok: '<path d="m3.5 8.5 3 3 6-7"/>',
  alerta: '<path d="M8 4.5v4.5M8 11.5v.5"/>',
  x: '<path d="M4 4l8 8M12 4l-8 8"/>',
  info: '<path d="M8 7.5v4M8 5v.5"/><circle cx="8" cy="8" r="6.5"/>',
  relogio: '<circle cx="8" cy="8" r="6.5"/><path d="M8 4.5V8l2.5 1.5"/>',
  raio: '<path d="M9 1.5 3.5 9H8l-1 5.5L12.5 7H8z"/>',
  upload: '<path d="M8 10.5V2.5M5 5.5l3-3 3 3"/><path d="M2.5 10.5v2A1.5 1.5 0 0 0 4 14h8a1.5 1.5 0 0 0 1.5-1.5v-2"/>',
  busca: '<circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3 3"/>',
  doc: '<path d="M4 1.5h5.5L12.5 4.5V14.5h-8.5z"/><path d="M9.5 1.5v3h3"/>',
};
const icone = (n, extra = "") => `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${extra}>${I[n]}</svg>`;

let avisoTimer;
function avisar(texto) {
  const a = $("#aviso"); a.textContent = texto; a.classList.add("visivel");
  $("#anuncio").textContent = texto;
  clearTimeout(avisoTimer); avisoTimer = setTimeout(() => a.classList.remove("visivel"), 3600);
}

/* ------------------------------------------------------------------ dados */
let DEMO = window.__DEMO__ || null;                      // arquivo único publicado
const EXEMPLO = window.__DADOS_EXEMPLO__ || null;       // Live Server / arquivo aberto direto
const modoExemplo = () => !!DEMO;

async function buscar(caminho) {
  const r = await fetch(caminho);
  if (!(r.headers.get("content-type") || "").includes("json")) throw new Error("Servidor da API não encontrado.");
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Erro ${r.status}`);
  return r.json();
}
async function obter(caminho) {
  if (!DEMO && EXEMPLO) {
    try { return await buscar(caminho); } catch { DEMO = EXEMPLO; }
  }
  if (DEMO) {
    if (caminho in DEMO) return structuredClone(DEMO[caminho]);
    throw new Error("Esta informação não está nos dados de exemplo.");
  }
  return buscar(caminho);
}
function obterSincrono(caminho) { return DEMO && caminho in DEMO ? structuredClone(DEMO[caminho]) : null; }
async function escrever(metodo, caminho, corpo) {
  if (modoExemplo()) throw new Error("No modo de demonstração nada é gravado. Rode o servidor para usar de verdade.");
  const opcoes = { method: metodo };
  if (corpo instanceof FormData) opcoes.body = corpo;
  else if (corpo !== undefined) { opcoes.headers = { "Content-Type": "application/json" }; opcoes.body = JSON.stringify(corpo); }
  const r = await fetch(caminho, opcoes);
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof dados.detail === "string" ? dados.detail : `Erro ${r.status}`);
  return dados;
}
let CATALOGO = null;
async function catalogos(recarregar = false) {
  if (!CATALOGO || recarregar) CATALOGO = await obter("/api/catalogos");
  return CATALOGO;
}

/* ------------------------------------------------------------------- menu */
const MENU = [
  { nome: "Painel", destino: "painel" },
  { nome: "Compras", itens: [
    { titulo: "Projeção de compra", texto: "O que e quanto comprar, com preço esperado", destino: "projecao" },
    { titulo: "Aquisições", texto: "Pedidos feitos e o que já chegou", destino: "aquisicoes" } ] },
  { nome: "Controle", itens: [
    { titulo: "Evolução de preço", texto: "Histórico por item, comparando fornecedores", destino: "precos" },
    { titulo: "Conciliação de notas", texto: "Conferir o XML da nota contra o pedido", destino: "conciliacao" } ] },
  { nome: "Cadastros", itens: [
    { titulo: "Itens e mínimos", texto: "Serviços revendidos e estoque mínimo", destino: "cadastros?aba=itens" },
    { titulo: "Fornecedores", texto: "CNPJ e prazo de entrega", destino: "cadastros?aba=fornecedores" },
    { titulo: "Clientes e entregas", texto: "Quem recebeu cada item", destino: "cadastros?aba=alocacoes" } ] },
];

function montarMenu() {
  $("#menu").innerHTML = MENU.map((g, i) => g.itens ? `
    <li><button class="menu-item" type="button" aria-expanded="false" aria-controls="sub-${i}" data-grupo="${i}">${g.nome}${icone("chevron")}</button>
      <div class="submenu" id="sub-${i}">${g.itens.map((o) => `<a class="opcao" href="#${o.destino}" data-rota="${o.destino.split("?")[0]}"><strong>${o.titulo}</strong><span>${o.texto}</span></a>`).join("")}</div></li>`
    : `<li><a class="menu-item" href="#${g.destino}" data-rota="${g.destino}">${g.nome}</a></li>`).join("");
  $("#menu-movel").innerHTML = MENU.map((g) => g.itens ? `
    <details><summary>${g.nome}${icone("chevron")}</summary>${g.itens.map((o) => `<a class="opcao" href="#${o.destino}"><strong>${o.titulo}</strong><span>${o.texto}</span></a>`).join("")}</details>`
    : `<a class="solto" href="#${g.destino}">${g.nome}</a>`).join("")
    + `<details><summary>Configurações${icone("chevron")}</summary><a class="opcao" href="#regras"><strong>Regras do sistema</strong><span>Os limiares que decidem, com o porquê</span></a>
      <button class="opcao" type="button" data-abre="dlg-a11y" style="width: 100%; border: 0; background: none; text-align: left; cursor: pointer"><strong>Acessibilidade</strong><span>Tema, tamanho do texto, contraste e movimento</span></button></details>`
    + `<div style="padding-top: 24px; display: grid; gap: 12px"><button class="botao botao-principal" type="button" data-acao="nova-aquisicao">Nova aquisição</button><span class="pilula-demo" style="display: inline-flex; justify-self: start">Dados fictícios</span></div>`;

  const fechar = (exceto) => $$(".menu-item[aria-expanded]").forEach((b) => {
    if (b !== exceto) { b.setAttribute("aria-expanded", "false"); $("#" + b.getAttribute("aria-controls")).classList.remove("aberto"); } });
  $$(".menu-item[aria-expanded]").forEach((b) => {
    const painel = $("#" + b.getAttribute("aria-controls"));
    b.addEventListener("click", (e) => {
      const abrir = b.getAttribute("aria-expanded") !== "true";
      fechar(b); b.setAttribute("aria-expanded", String(abrir)); painel.classList.toggle("aberto", abrir);
      if (abrir && e.detail === 0) setTimeout(() => painel.querySelector("a")?.focus({ preventScroll: true }), 30);
    });
    b.parentElement.addEventListener("focusout", (e) => { if (!b.parentElement.contains(e.relatedTarget)) fechar(); });
  });
  document.addEventListener("click", (e) => { if (!e.target.closest(".menu") || e.target.closest(".opcao")) fechar(); });
  // menu de Configurações (engrenagem)
  const cfg = $("#btn-config"), painelCfg = $("#sub-config");
  const fecharCfg = () => { cfg.setAttribute("aria-expanded", "false"); painelCfg.classList.remove("aberto"); };
  cfg.addEventListener("click", (e) => { const abrir = cfg.getAttribute("aria-expanded") !== "true"; cfg.setAttribute("aria-expanded", String(abrir)); painelCfg.classList.toggle("aberto", abrir);
    if (abrir && e.detail === 0) setTimeout(() => painelCfg.querySelector("a, button")?.focus(), 30); });
  document.addEventListener("click", (e) => { if (!e.target.closest(".config") || e.target.closest(".opcao")) fecharCfg(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && cfg.getAttribute("aria-expanded") === "true") { fecharCfg(); cfg.focus(); } });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { const a = $(".menu-item[aria-expanded='true']"); if (a) { fechar(); a.focus(); } } });
}
function marcarMenu(rota) {
  $("#btn-config")?.classList.toggle("ativo", rota === "regras");
  $$(".menu-item").forEach((m) => m.classList.remove("ativo"));
  $$(".opcao").forEach((o) => o.classList.toggle("ativo", o.dataset.rota === rota));
  MENU.forEach((g, i) => {
    const ativo = g.itens ? g.itens.some((o) => o.destino.split("?")[0] === rota) : g.destino === rota;
    if (!ativo) return;
    const el = g.itens ? $(`.menu-item[data-grupo="${i}"]`) : $(`.menu-item[data-rota="${g.destino}"]`);
    el?.classList.add("ativo");
  });
}

/* --------------------------------------------------------------- diálogos */
function iniciarDialogos() {
  document.addEventListener("click", (e) => {
    const abre = e.target.closest("[data-abre]");
    if (abre) { $$("dialog[open]").forEach((d) => d.close()); $("#" + abre.dataset.abre).showModal(); return; }
    if (e.target.closest("[data-fecha]")) { e.target.closest("dialog").close(); return; }
    const acao = e.target.closest("[data-acao]");
    if (acao) { $$("dialog[open]").forEach((d) => d.close()); ACOES[acao.dataset.acao]?.(acao.dataset); }
  });
  $$("dialog").forEach((d) => d.addEventListener("click", (e) => { if (e.target === d) d.close(); }));
  $("#dlg-menu").addEventListener("click", (e) => { if (e.target.closest("a[href^='#']")) $("#dlg-menu").close(); });
}

/* ---------------------------------------------------------- acessibilidade */
const PREF = "auge-acessibilidade";
function lerPref() { try { return JSON.parse(localStorage.getItem(PREF)) || {}; } catch { return {}; } }
function aplicarPref(p) {
  const r = document.documentElement.dataset;
  // atributo próprio (data-tema): a escolha do usuário não é sobrescrita pelo tema do visualizador (data-theme)
  (p.tema === "light" || p.tema === "dark") ? (r.tema = p.tema === "light" ? "claro" : "escuro") : delete r.tema;
  (p.texto && p.texto !== "padrao") ? (r.texto = p.texto) : delete r.texto;
  p.contraste ? (r.contraste = "alto") : delete r.contraste;
  p.movimento ? (r.movimento = "reduzido") : delete r.movimento;
  p.links ? (r.links = "sublinhados") : delete r.links;
}
function iniciarAcessibilidade() {
  const p = lerPref(); aplicarPref(p);
  const f = $("#form-a11y");
  f.tema.value = p.tema || "auto"; f.texto.value = p.texto || "padrao";
  f.contraste.checked = !!p.contraste; f.movimento.checked = !!p.movimento; f.links.checked = !!p.links;
  f.addEventListener("change", () => {
    const nova = { tema: f.tema.value, texto: f.texto.value, contraste: f.contraste.checked, movimento: f.movimento.checked, links: f.links.checked };
    aplicarPref(nova);
    try { localStorage.setItem(PREF, JSON.stringify(nova)); } catch { /* sem armazenamento: vale só nesta visita */ }
  });
}

/* --------------------------------------------------- movimento e cabeçalho */
let observador;
function revelar(raiz) {
  observador?.disconnect();
  observador = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("visivel"); observador.unobserve(e.target); } }),
    { rootMargin: "0px 0px -6% 0px", threshold: .06 });
  $$(".revela", raiz).forEach((el) => observador.observe(el));
}
function iniciarTopo() {
  const topo = $("#topo");
  const f = () => topo.classList.toggle("rolou", scrollY > 8);
  addEventListener("scroll", f, { passive: true }); f();
}

/* -------------------------------------------------- formulário genérico */
function abrirFormulario(cfg) {
  const dlg = $("#dlg-form"), f = $("#form-generico");
  $("#t-form").textContent = cfg.titulo;
  const campo = (c) => {
    const id = "g-" + c.nome, ajuda = c.dica ? `<span class="dica-campo" id="d-${c.nome}">${esc(c.dica)}</span>` : "";
    const desc = `aria-describedby="${c.dica ? "d-" + c.nome + " " : ""}e-${c.nome}"`;
    const entrada = c.tipo === "select"
      ? `<select id="${id}" name="${c.nome}" ${desc}><option value="">${esc(c.vazio || "Escolha")}</option>${c.opcoes.map((o) => `<option value="${esc(o.valor)}">${esc(o.texto)}</option>`).join("")}</select>`
      : `<input id="${id}" name="${c.nome}" type="${c.tipo || "text"}" ${c.min != null ? `min="${c.min}"` : ""} ${c.max != null ? `max="${c.max}"` : ""} ${c.step ? `step="${c.step}"` : ""} ${c.modo ? `inputmode="${c.modo}"` : ""} ${desc}>`;
    return `<div class="campo" ${c.largo ? "" : ""}><label for="${id}">${esc(c.rotulo)}</label>${entrada}${ajuda}<span class="erro" id="e-${c.nome}" aria-live="polite"></span></div>`;
  };
  const linhas = [];
  for (let i = 0; i < cfg.campos.length; i++) {
    const c = cfg.campos[i];
    if (c.par && cfg.campos[i + 1]) { linhas.push(`<div class="duas">${campo(c)}${campo(cfg.campos[i + 1])}</div>`); i++; }
    else linhas.push(campo(c));
  }
  f.innerHTML = (modoExemplo() ? `<p class="aviso-demo">Demonstração: o formulário valida os campos, mas não grava. Com o servidor rodando, grava de verdade.</p>` : "")
    + (cfg.introducao ? `<p class="nota-pequena" style="font-size: .9375rem">${esc(cfg.introducao)}</p>` : "")
    + linhas.join("") + `<div class="rodape-dlg"><button class="botao botao-contorno" type="button" data-fecha>Cancelar</button><button class="botao botao-principal" type="submit">${esc(cfg.botao || "Salvar")}</button></div>`;
  cfg.campos.forEach((c) => { if (c.valor != null) f.elements[c.nome].value = c.valor; });

  const validar = (c) => {
    const el = f.elements[c.nome], v = el.value.trim();
    let msg = !v && c.obrigatorio !== false ? (c.msgVazio || "Preencha este campo.") : "";
    if (!msg && v && c.validar) msg = c.validar(v) || "";
    const caixa = el.closest(".campo");
    caixa.classList.toggle("invalido", !!msg); caixa.classList.toggle("valido", !msg && !!v);
    el.setAttribute("aria-invalid", String(!!msg)); $("#e-" + c.nome).textContent = msg;
    return !msg;
  };
  cfg.campos.forEach((c) => {
    const el = f.elements[c.nome];
    el.addEventListener("blur", () => validar(c));
    el.addEventListener("input", () => { if (el.closest(".campo").classList.contains("invalido")) validar(c); });
  });
  f.onsubmit = async (e) => {
    e.preventDefault();
    const ruins = cfg.campos.filter((c) => !validar(c));
    if (ruins.length) { f.elements[ruins[0].nome].focus(); return; }
    if (modoExemplo()) { avisar("Campos válidos. Na demonstração, nada é gravado."); return; }
    const valores = Object.fromEntries(cfg.campos.map((c) => [c.nome, f.elements[c.nome].value.trim()]));
    const botao = f.querySelector("[type=submit]"); botao.disabled = true;
    try { const r = await cfg.enviar(valores); dlg.close(); cfg.depois?.(r); }
    catch (erro) { avisar(erro.message); }
    finally { botao.disabled = false; }
  };
  dlg.showModal();
  setTimeout(() => f.querySelector("input, select")?.focus(), 60);
}

const HOJE = () => (DEMO ? DEMO["/api/painel"].hoje : null);
async function hojeAtual() { return HOJE() || (await obter("/api/regras")).hoje; }

const ACOES = {
  async "nova-aquisicao"(d = {}) {
    const [cat, hoje] = await Promise.all([catalogos(), hojeAtual()]);
    const servico = cat.servicos.find((s) => String(s.id) === String(d.servico));
    abrirFormulario({
      titulo: "Nova aquisição", botao: "Registrar",
      introducao: d.servico ? "Preenchido com a sugestão da projeção. Ajuste se precisar." : "",
      campos: [
        { nome: "servico_id", rotulo: "Item", tipo: "select", vazio: "Escolha o item", msgVazio: "Escolha um item.", valor: d.servico, opcoes: cat.servicos.map((s) => ({ valor: s.id, texto: s.nome })) },
        { nome: "fornecedor_id", rotulo: "Fornecedor", tipo: "select", vazio: "Escolha o fornecedor", msgVazio: "Escolha um fornecedor.", valor: d.fornecedor, opcoes: cat.fornecedores.map((f) => ({ valor: f.id, texto: f.nome })) },
        { nome: "quantidade", rotulo: "Quantidade", tipo: "number", min: 1, step: 1, modo: "numeric", par: true, valor: d.quantidade, msgVazio: "Informe a quantidade.",
          validar: (v) => Number(v) < 1 ? "A quantidade precisa ser pelo menos 1." : (!Number.isInteger(Number(v)) && (servico?.tipo_quantidade ?? "discreta") === "discreta") ? "Este item é contado em unidades inteiras." : "" },
        { nome: "preco_unitario", rotulo: "Preço unitário (R$)", tipo: "number", min: 0.01, step: 0.01, modo: "decimal", valor: d.preco, msgVazio: "Informe o preço unitário.",
          validar: (v) => Number(v) <= 0 ? "O preço precisa ser maior que zero." : "" },
        { nome: "data_pedido", rotulo: "Data do pedido", tipo: "date", max: hoje, valor: hoje, dica: "Não pode ser uma data futura.", msgVazio: "Informe a data do pedido.",
          validar: (v) => v > hoje ? "A data do pedido não pode estar no futuro." : "" },
      ],
      enviar: (v) => escrever("POST", "/api/aquisicoes", { servico_id: +v.servico_id, fornecedor_id: +v.fornecedor_id, quantidade: +v.quantidade, preco_unitario: +v.preco_unitario, data_pedido: v.data_pedido }),
      depois: (r) => { avisar(`Aquisição ${r.codigo} registrada.` + (["nota", "alerta"].includes(r.avaliacao_preco?.nivel) ? ` Atenção ao preço: ${r.avaliacao_preco.motivo}` : "")); rota(); },
    });
  },
  async "nova-alocacao"() {
    const [cat, hoje] = await Promise.all([catalogos(), hojeAtual()]);
    abrirFormulario({
      titulo: "Registrar entrega a cliente", botao: "Registrar",
      campos: [
        { nome: "servico_id", rotulo: "Item", tipo: "select", vazio: "Escolha o item", msgVazio: "Escolha um item.", opcoes: cat.servicos.map((s) => ({ valor: s.id, texto: s.nome })) },
        { nome: "cliente_id", rotulo: "Cliente", tipo: "select", vazio: "Escolha o cliente", msgVazio: "Escolha um cliente.", opcoes: cat.clientes.map((c) => ({ valor: c.id, texto: c.nome })) },
        { nome: "quantidade", rotulo: "Quantidade", tipo: "number", min: 1, step: 1, par: true, msgVazio: "Informe a quantidade.", validar: (v) => Number(v) < 1 ? "Pelo menos 1." : "" },
        { nome: "data", rotulo: "Data", tipo: "date", max: hoje, valor: hoje, validar: (v) => v > hoje ? "Não pode ser uma data futura." : "" },
      ],
      enviar: (v) => escrever("POST", "/api/alocacoes", { servico_id: +v.servico_id, cliente_id: +v.cliente_id, quantidade: +v.quantidade, data: v.data }),
      depois: () => { avisar("Entrega registrada."); rota(); },
    });
  },
  "novo-fornecedor"() {
    abrirFormulario({
      titulo: "Novo fornecedor", botao: "Salvar",
      campos: [
        { nome: "nome", rotulo: "Nome", msgVazio: "Informe o nome." },
        { nome: "cnpj", rotulo: "CNPJ", modo: "numeric", par: true, msgVazio: "Informe o CNPJ.", validar: (v) => v.replace(/\D/g, "").length !== 14 ? "O CNPJ tem 14 dígitos." : "" },
        { nome: "lead_time_dias", rotulo: "Prazo de entrega (dias)", tipo: "number", min: 0, step: 1, msgVazio: "Informe o prazo.", validar: (v) => Number(v) < 0 ? "Não pode ser negativo." : "" },
      ],
      enviar: (v) => escrever("POST", "/api/fornecedores", { nome: v.nome, cnpj: v.cnpj, lead_time_dias: +v.lead_time_dias }),
      depois: async () => { await catalogos(true); avisar("Fornecedor cadastrado."); rota(); },
    });
  },
  "novo-cliente"() {
    abrirFormulario({
      titulo: "Novo cliente", botao: "Salvar",
      campos: [
        { nome: "nome", rotulo: "Nome", msgVazio: "Informe o nome." },
        { nome: "segmento", rotulo: "Segmento", tipo: "select", vazio: "Escolha o segmento", msgVazio: "Escolha o segmento.",
          opcoes: ["Saúde", "Construção civil", "Comércio", "Serviços", "Alimentação", "Outro"].map((s) => ({ valor: s, texto: s })) },
      ],
      enviar: (v) => escrever("POST", "/api/clientes", v),
      depois: async () => { await catalogos(true); avisar("Cliente cadastrado."); rota(); },
    });
  },
  "novo-item"() {
    abrirFormulario({
      titulo: "Novo item", botao: "Salvar",
      campos: [
        { nome: "nome", rotulo: "Nome", msgVazio: "Informe o nome." },
        { nome: "categoria", rotulo: "Categoria", par: true, msgVazio: "Informe a categoria." },
        { nome: "unidade", rotulo: "Unidade", tipo: "select", vazio: "Escolha", msgVazio: "Escolha a unidade.", opcoes: ["voucher", "unidade", "licença", "hora"].map((u) => ({ valor: u, texto: u })) },
        { nome: "validade_meses", rotulo: "Validade (meses)", tipo: "number", min: 1, step: 1, par: true, obrigatorio: false, dica: "Deixe vazio se não vence." },
        { nome: "estoque_minimo", rotulo: "Mínimo em estoque", tipo: "number", min: 0, step: 1, obrigatorio: false, dica: "Usado enquanto há pouco histórico." },
      ],
      enviar: (v) => escrever("POST", "/api/servicos", { nome: v.nome, categoria: v.categoria, unidade: v.unidade, tipo_quantidade: "discreta",
        validade_meses: v.validade_meses ? +v.validade_meses : null, estoque_minimo: v.estoque_minimo ? +v.estoque_minimo : null }),
      depois: async () => { await catalogos(true); avisar("Item cadastrado."); rota(); },
    });
  },
};

/* ------------------------------------------------------------ componentes */
function faixa({ rotulo, titulo, descricao, indicadores = [], grande = false }) {
  const ind = indicadores.map((i) => {
    const conteudo = `<span class="indicador-rotulo">${esc(i.rotulo)}${i.href || i.acao ? icone("seta") : ""}</span><strong>${esc(i.valor)}</strong>`;
    if (i.href) return `<li><a class="indicador" href="${i.href}">${conteudo}</a></li>`;
    if (i.acao) return `<li><button class="indicador" type="button" data-acao="${i.acao}">${conteudo}</button></li>`;
    return `<li><div class="indicador">${conteudo}</div></li>`;
  }).join("");
  return `<section class="faixa${grande ? " grande" : ""}" aria-labelledby="titulo-pagina">${MARCA_DAGUA}<div class="conteiner">
    <div><p class="rotulo">${esc(rotulo)}</p><h1 id="titulo-pagina">${esc(titulo)}</h1>${descricao ? `<p class="descricao">${esc(descricao)}</p>` : ""}</div>
    ${ind ? `<ul class="indicadores" aria-label="Resumo">${ind}</ul>` : ""}
  </div></section>`;
}
/* a seta do "A" da Auge, só em contorno, como marca d'água das faixas */
const MARCA_DAGUA = `<svg class="marca-dagua" viewBox="0 0 100 126" aria-hidden="true" focusable="false">
  <polygon points="50,2 98,56 68,56 68,124 32,124 32,56 2,56"/><polygon class="interna" points="50,15 85,54 60,54 60,112 40,112 40,54 15,54"/></svg>`;
const SELO_STATUS = { comprar_agora: ["selo-alta", "Comprar agora"], planejar: ["selo-atencao", "Planejar"], ok: ["selo-ok", "Coberto"], sem_regra: ["selo-info", "Sem regra"] };
const SELO_CONF = { alta: ["selo-neutro", "Confiança alta"], media: ["selo-neutro", "Confiança média"], baixa: ["selo-atencao", "Confiança baixa"], insuficiente: ["selo-info", "Aprendendo"] };
const SELO_SIT = { aguardando: ["selo-info", "A caminho"], parcial: ["selo-atencao", "Parcial"], recebida: ["selo-ok", "Recebida"], excedente: ["selo-alta", "Veio a mais"], atrasada: ["selo-alta", "Atrasada"], faltante: ["selo-alta", "Faltante"] };
const SELO_PRECO = { alerta: ["selo-alta", "Alta de preço"], nota: ["selo-atencao", "Reajuste"], queda: ["selo-ok", "Queda"], normal: ["selo-neutro", "Dentro da oscilação"], sem_base: ["selo-neutro", "Sem comparação"] };
const selo = ([cls, txt]) => `<span class="selo ${cls}">${esc(txt)}</span>`;

/* -----------------------------------------------------------------------------
   Números simples: "tem" é o disponível mais o que está a caminho no prazo.
   ----------------------------------------------------------------------------- */
function temDe(x) { return x.posicao ?? (x.capacidade + x.em_transito); }
let HOJE_ISO = null;
const somaDias = (iso, n) => { const d = new Date(iso + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d; };
function rotuloDia(n) { const d = somaDias(HOJE_ISO, Math.floor(n)); return `${String(d.getUTCDate()).padStart(2, "0")}/${String(d.getUTCMonth() + 1).padStart(2, "0")}`; }
const ficha = (rotulo, valor, sub = "", cls = "") => `<div class="ficha ${cls}"><span>${esc(rotulo)}</span><strong>${esc(valor)}</strong>${sub ? `<small>${esc(sub)}</small>` : ""}</div>`;
function quandoAcaba(x) {
  const lt = x.linha_tempo || {};
  if (x.modo === "cold_start") return "Poucos dados para prever quando acaba.";
  if (lt.acaba_em == null) return "Não acaba nos próximos 30 dias.";
  return lt.acaba_em < 1 ? "Sem comprar, acaba hoje." : `Sem comprar, acaba por volta de ${rotuloDia(lt.acaba_em)}.`;
}


/* =============================================================================
   Tela: Painel
   ============================================================================= */
const NUM_M = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove"];
const NUM_F = ["zero", "uma", "duas", "três", "quatro", "cinco", "seis", "sete", "oito", "nove"];
const DESCREVE = { compra: [NUM_F, "compra", "compras"], entrega: [NUM_M, "pedido atrasado", "pedidos atrasados"], preco: [NUM_F, "alta de preço", "altas de preço"],
  fornecedor: [NUM_M, "fornecedor mais caro", "fornecedores mais caros"], regra: [NUM_M, "item sem regra", "itens sem regra"] };
const TIPO = { compra: "Compra", entrega: "Entrega", preco: "Preço", fornecedor: "Fornecedor", regra: "Regra" };
function frase(itens) {
  const conta = {}; itens.forEach((f) => (conta[f.tipo] = (conta[f.tipo] || 0) + 1));
  const partes = Object.entries(conta).map(([t, n]) => { const [ns, s, p] = DESCREVE[t] || [NUM_M, "item", "itens"]; return `${n < 10 ? ns[n] : n} ${n === 1 ? s : p}`; });
  const t = partes.length > 1 ? partes.slice(0, -1).join(", ") + " e " + partes.at(-1) : partes[0] || "";
  return t.charAt(0).toUpperCase() + t.slice(1);
}
function linhaDecisao(f) {
  if (f.tipo === "compra") return `${esc(f.fornecedor)}, cerca de ${fmt.brl(f.valor)}`;
  if (f.tipo === "entrega") return `${esc(f.servico)} com ${esc(f.fornecedor)}`;
  if (f.tipo === "regra") return esc(f.servico);
  return `${esc(f.servico)}, ${esc(f.fornecedor)}`;
}
function acaoDecisao(f, grande = false) {
  const t = grande ? "" : " botao-pequeno";
  if (f.tipo === "compra") return `<button class="botao botao-principal${t}" type="button" data-acao="nova-aquisicao" data-servico="${f.servico_id}" data-fornecedor="${f.fornecedor_id}" data-quantidade="${f.quantidade}" data-preco="${f.preco}">Registrar compra</button>
    <a class="botao botao-contorno${t}" href="#projecao?item=${f.servico_id}">Ver detalhes</a>`;
  if (f.tipo === "entrega") return `<a class="botao botao-principal${t}" href="#aquisicoes?codigo=${encodeURIComponent(f.ref)}">Ver pedido</a>`;
  if (f.tipo === "regra") return `<a class="botao botao-principal${t}" href="#cadastros?aba=itens">Definir mínimo</a>`;
  return `<a class="botao botao-principal${t}" href="#precos?item=${f.ref}">${f.tipo === "fornecedor" ? "Comparar fornecedores" : "Ver preços"}</a>`;
}
function slideDecisao(f, i, total) {
  const s = f.prioridade === 1 ? ["selo-alta", "Agora"] : f.prioridade === 2 ? ["selo-atencao", "Esta semana"] : ["selo-neutro", "Pode esperar"];
  return `<article class="slide" aria-roledescription="slide" aria-label="${i + 1} de ${total}: ${esc(f.titulo)}" data-i="${i}">
    <div class="slide-topo">${selo(s)}<span class="slide-tipo">${TIPO[f.tipo] || ""}</span><span class="slide-pos">${i + 1} de ${total}</span></div>
    <h3>${esc(f.titulo)}</h3>
    <p class="slide-linha">${linhaDecisao(f)}</p>
    <div class="fichas">${(f.numeros || []).map((n) => ficha(n.rotulo, n.valor)).join("")}</div>
    <p class="slide-motivo">${esc(f.detalhe)}</p>
    <div class="slide-acoes">${acaoDecisao(f, true)}</div>
  </article>`;
}
function ligarCarrossel(raiz) {
  const trilho = $(".carrossel-trilho", raiz); if (!trilho) return;
  const slides = $$(".slide", trilho), pontos = $$(".pontos button", raiz);
  const centro = (el) => el.offsetLeft - (trilho.clientWidth - el.offsetWidth) / 2;
  let atual = 0, escolhido = null, espera;
  const marcar = (i) => { atual = i;
    slides.forEach((s, k) => { s.classList.toggle("ativo", k === i); s.classList.toggle("vizinho", Math.abs(k - i) === 1);
      s.setAttribute("aria-hidden", String(Math.abs(k - i) > 1)); $$("a, button", s).forEach((b) => (b.tabIndex = k === i ? 0 : -1)); });
    pontos.forEach((p, k) => p.setAttribute("aria-current", String(k === i)));
    $$("[data-dir]", raiz).forEach((b) => (b.disabled = (b.dataset.dir === "-1" && i === 0) || (b.dataset.dir === "1" && i === slides.length - 1))); };
  const ir = (i) => { i = Math.max(0, Math.min(slides.length - 1, i)); escolhido = i; marcar(i);
    trilho.scrollTo({ left: centro(slides[i]), behavior: movimentoReduzido() ? "auto" : "smooth" });
    clearTimeout(espera); espera = setTimeout(() => (escolhido = null), 700); };
  // o ativo é o cartão mais perto do centro da área visível
  trilho.addEventListener("scroll", () => requestAnimationFrame(() => {
    if (escolhido !== null) return;
    const meio = trilho.scrollLeft + trilho.clientWidth / 2;
    let melhor = 0; slides.forEach((s, k) => { if (Math.abs(s.offsetLeft + s.offsetWidth / 2 - meio) < Math.abs(slides[melhor].offsetLeft + slides[melhor].offsetWidth / 2 - meio)) melhor = k; });
    if (melhor !== atual) marcar(melhor);
  }), { passive: true });
  // clique num cartão que não é o do meio: leva até ele, sem disparar os botões dele
  trilho.addEventListener("click", (e) => {
    const s = e.target.closest(".slide"); if (!s || s.classList.contains("ativo")) return;
    e.preventDefault(); e.stopPropagation(); ir(Number(s.dataset.i));
  }, true);
  $$("[data-dir]", raiz).forEach((b) => b.addEventListener("click", () => ir(atual + Number(b.dataset.dir))));
  pontos.forEach((p, k) => p.addEventListener("click", () => ir(k)));
  trilho.addEventListener("keydown", (e) => { if (e.key === "ArrowRight") { e.preventDefault(); ir(atual + 1); } if (e.key === "ArrowLeft") { e.preventDefault(); ir(atual - 1); } });
  marcar(0); trilho.scrollLeft = centro(slides[0]);
}
const movimentoReduzido = () => document.documentElement.dataset.movimento === "reduzido" || matchMedia("(prefers-reduced-motion: reduce)").matches;

function cartaoItem(c, spans) {
  const tem = temDe(c), min = c.minimo_seguro, falta = min == null ? null : Math.max(0, min - tem);
  const largo = c.status === "comprar_agora";
  const linha = largo ? `Faltam ${fmt.num(falta)} para o mínimo. ${quandoAcaba(c)}`
    : c.status === "sem_regra" ? "Sem mínimo definido." : c.em_transito ? `${fmt.num(c.em_transito)} a caminho. ${quandoAcaba(c)}` : quandoAcaba(c);
  const fichas = ficha("Tem", fmt.num(tem), "", falta ? "ruim" : "") + ficha("Precisa ter", min == null ? "—" : fmt.num(min))
    + (largo ? ficha("Comprar", fmt.num(c.sugestao), "", "destaque") + ficha("Custo", fmt.brl(c.custo_estimado)) : "");
  return `<li class="${largo ? "largo" : ""}" style="--s4: ${spans[0]}; --s2: ${spans[1]}"><a class="item-cartao${largo ? " critico" : ""}" href="#projecao?item=${c.servico_id}">
    <span class="item-topo"><strong>${esc(c.servico)}</strong>${selo(SELO_STATUS[c.status] || SELO_STATUS.ok)}</span>
    <span class="fichas fichas-pequenas">${fichas}</span>
    <span class="item-linha">${esc(linha)}${largo && c.fornecedor_sugerido ? ` Sugerido: ${esc(c.fornecedor_sugerido)}.` : ""}</span></a></li>`;
}
/* distribui os itens numa grade de 4 (ou 2) colunas: os que pedem compra ocupam 2,
   e o último estica para a linha fechar sem espaço vazio */
function gradeItens(caps) {
  const ordem = [...caps.filter((c) => c.status === "comprar_agora"), ...caps.filter((c) => c.status !== "comprar_agora")];
  const base = ordem.map((c) => (c.status === "comprar_agora" ? 2 : 1));
  const fechar = (colunas) => { const sp = base.map((b) => Math.min(b, colunas)); const total = sp.reduce((a, b) => a + b, 0), resto = total % colunas;
    if (resto) sp[sp.length - 1] += colunas - resto; return sp; };
  const s4 = fechar(4), s2 = fechar(2);
  return ordem.map((c, i) => cartaoItem(c, [s4[i], s2[i]])).join("");
}
function telaPainel(el, _q, d) {
  const agora = d.fila.filter((f) => f.prioridade === 1), depois = d.fila.filter((f) => f.prioridade > 1);
  const criticos = d.capacidades.filter((c) => c.status === "comprar_agora");
  const cobertos = d.capacidades.length - criticos.length;
  const titulo = agora.length === 0 ? "Nada urgente hoje." : agora.length === 1 ? "Uma decisão para hoje." : `${(NUM_F[agora.length] ?? agora.length)} decisões para hoje.`.replace(/^./, (c) => c.toUpperCase());
  const fila = [...agora, ...depois];
  el.innerHTML = faixa({
    grande: true, rotulo: fmt.dataLonga(d.hoje), titulo,
    descricao: agora.length ? `${frase(agora)}. ${cobertos} dos ${d.capacidades.length} itens estão cobertos.` : `Os ${d.capacidades.length} itens estão cobertos.`,
    indicadores: [
      { rotulo: "Compra sugerida", valor: fmt.brl(d.resumo.compra_sugerida_total), href: "#projecao" },
      { rotulo: "Pedidos a caminho", valor: fmt.brl(d.resumo.valor_em_transito), href: "#aquisicoes?filtro=abertas" },
      { rotulo: "Itens cobertos", valor: `${cobertos} de ${d.capacidades.length}`, href: "#projecao" },
    ],
  }) + `
  <section class="bloco-carrossel" aria-labelledby="t-decisoes">
    <div class="conteiner cabeca-bloco revela"><div><p class="sobretitulo">Fila de decisões</p>
      <h2 class="titulo-secao" id="t-decisoes">${agora.length} para agora${depois.length ? `, ${depois.length} ${depois.length === 1 ? "pode" : "podem"} esperar` : ""}</h2></div>
      <div class="carrossel-controles"><button class="botao botao-contorno botao-icone" type="button" data-dir="-1" aria-label="Decisão anterior">${icone("seta", 'style="transform: rotate(180deg)"')}</button>
        <button class="botao botao-contorno botao-icone" type="button" data-dir="1" aria-label="Próxima decisão">${icone("seta")}</button></div></div>
    <div class="carrossel revela d1" aria-roledescription="carrossel" aria-label="Decisões">
      <div class="carrossel-trilho" tabindex="0" aria-label="Use as setas do teclado para navegar">${fila.map((f, i) => slideDecisao(f, i, fila.length)).join("") || `<div class="cartao vazio">Nada na fila. Tudo em dia.</div>`}</div>
    </div>
    <div class="conteiner"><div class="pontos" role="group" aria-label="Escolher decisão">${fila.map((f, i) => `<button type="button" aria-label="Ir para ${i + 1}: ${esc(f.titulo)}" class="${f.prioridade === 1 ? "urgente" : ""}"></button>`).join("")}</div></div>
  </section>
  <section class="conteiner pagina" aria-labelledby="t-itens" style="padding-top: 24px">
    <div class="cabeca-bloco revela"><div><p class="sobretitulo">Capacidade</p><h2 class="titulo-secao" id="t-itens">Situação dos itens</h2></div>
      <a class="botao botao-contorno" href="#projecao">Ver todos na Projeção</a></div>
    <ul class="grade-itens revela d1">${gradeItens(d.capacidades)}</ul>
    <div class="cabeca-bloco revela" style="margin-top: 56px"><div><p class="sobretitulo">As quatro funções</p><h2 class="titulo-secao">Acesso rápido</h2></div></div>
    <nav class="grade-atalhos revela d1" aria-label="Acesso rápido">
      <button type="button" class="atalho-cartao" data-acao="nova-aquisicao"><strong>Registrar compra</strong><small>Cadastrar uma aquisição com o fornecedor</small>${icone("seta")}</button>
      <a class="atalho-cartao" href="#projecao"><strong>Projeção de compra</strong><small>O que e quanto comprar, com preço esperado</small>${icone("seta")}</a>
      <a class="atalho-cartao" href="#precos"><strong>Evolução de preço</strong><small>Histórico por item, comparando fornecedores</small>${icone("seta")}</a>
      <a class="atalho-cartao" href="#conciliacao"><strong>Conferir nota fiscal</strong><small>XML da nota contra o pedido</small>${icone("seta")}</a>
    </nav>
  </section>`;
  ligarCarrossel(el);
}

/* =============================================================================
   Tela: Projeção de compra
   ============================================================================= */
function telaProjecao(el, q, dados) {
  const h = Number(q.get("h")) || 30;
  const selecionado = Number(q.get("item")) || dados[0]?.servico_id;
  const p = dados.find((x) => x.servico_id === selecionado) || dados[0];
  const comprar = dados.filter((x) => x.status === "comprar_agora");
  const custo = dados.filter((x) => ["comprar_agora", "planejar"].includes(x.status)).reduce((s, x) => s + (x.custo_estimado || 0), 0);
  const previstos = dados.filter((x) => x.status === "ok" && x.sugestao > 0).length;
  el.innerHTML = faixa({
    rotulo: "Compras", titulo: "Projeção de compra",
    descricao: `O que comprar para cobrir o prazo de entrega de cada fornecedor e os próximos ${h} dias, com o preço esperado.`,
    indicadores: [
      { rotulo: "Comprar agora", valor: fmt.plural(comprar.length, "item", "itens") },
      { rotulo: "Custo sugerido agora", valor: fmt.brl(custo) },
      { rotulo: "Compras previstas no período", valor: fmt.plural(previstos, "item", "itens") },
    ],
  }) + `<div class="conteiner pagina">
    <div class="barra-ferramentas revela"><div class="grupo"><span class="campo-inline" id="rot-h">Período da compra</span>
      <div class="segmentado" role="group" aria-labelledby="rot-h">${[15, 30, 60].map((x) => `<a href="#projecao?h=${x}&item=${p.servico_id}" aria-current="${x === h}">${x} dias</a>`).join("")}</div></div>
      <p class="nota-pequena">Tem = disponível + a caminho. Precisa ter = o mínimo seguro de cada item.</p></div>
    <div class="grade-lista-detalhe">
      <ul class="itens revela" aria-label="Itens">${dados.map((x) => { const tem = temDe(x), min = x.minimo_seguro, abaixo = min != null && tem < min;
        return `<li><button class="item-lista" type="button" aria-pressed="${x.servico_id === p.servico_id}" data-item="${x.servico_id}">
        <span class="nome">${esc(x.servico)}</span>
        <span class="qtd"><strong>${x.sugestao || "0"}</strong><small>${x.status === "comprar_agora" ? "comprar agora" : x.sugestao ? "no período" : "nada a comprar"}</small></span>
        <span class="sub">${selo(SELO_STATUS[x.status] || SELO_STATUS.ok)} <span class="${abaixo ? "ruim" : ""}">tem ${fmt.num(tem)}, precisa ${min != null ? fmt.num(min) : "de regra"}</span></span>
      </button></li>`; }).join("")}</ul>
      <article class="cartao fixo revela d1" aria-live="polite" id="detalhe-projecao">${detalheProjecao(p)}</article>
    </div></div>`;
  $$(".item-lista", el).forEach((b) => b.addEventListener("click", () => {
    history.replaceState(null, "", `#projecao?h=${h}&item=${b.dataset.item}`);
    $$(".item-lista", el).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    $("#detalhe-projecao", el).innerHTML = detalheProjecao(dados.find((x) => x.servico_id === Number(b.dataset.item)));
    if (matchMedia("(max-width: 1180px)").matches) $("#detalhe-projecao", el).scrollIntoView({ behavior: "smooth", block: "start" });
  }));
}
function detalheProjecao(p) {
  const conf = SELO_CONF[p.confianca] || SELO_CONF.baixa;
  const tem = temDe(p), min = p.minimo_seguro, falta = min == null ? null : Math.max(0, min - tem);
  const origem = p.origem_minimo === "definido" ? "definido por você" : p.origem_minimo === "renovacoes" ? "pelas renovações previstas" : min == null ? "sem regra" : "calculado";
  const avisos = [];
  p.pedidos_atrasados.forEach((a) => avisos.push(`<div class="aviso-bloco atencao">${icone("relogio")}<div><strong>Pedido ${esc(a.codigo)} atrasado, fora da conta</strong>
    <p>As ${fmt.num(a.falta)} ${un(p.unidade, a.falta)} desse pedido não entram no "tem". Cobre o fornecedor antes de comprar de novo.</p></div></div>`));
  if (p.alternativa_rapida) avisos.push(`<div class="aviso-bloco info">${icone("raio")}<div><strong>${esc(p.alternativa_rapida.fornecedor)} entrega em ${fmt.num(p.alternativa_rapida.lead_time)} dias, por ${fmt.pct(p.alternativa_rapida.diferenca)}</strong>
    <p>O disponível dura menos que o prazo de ${esc(p.fornecedor_sugerido)} (${fmt.num(p.lead_time)} dias). Decisão de negócio: prazo ou preço.</p></div></div>`);
  if (p.modo === "cold_start") avisos.push(`<div class="aviso-bloco info">${icone("info")}<div><strong>Ainda aprendendo este item</strong>
    <p>Com ${fmt.plural(p.eventos_janela, "entrega", "entregas")} em ${p.dias_acompanhamento} dias, o sistema não estima ritmo. Vale o mínimo definido por você.</p></div></div>`);
  const nada = !p.sugestao;
  return `<div class="detalhe-topo"><div class="selos">${selo(SELO_STATUS[p.status] || SELO_STATUS.ok)}${selo(conf)}</div>
      <h2>${esc(p.servico)}</h2><p>${esc(p.resumo)}</p></div>
    <div class="fichas fichas-detalhe">
      ${ficha("Tem", fmt.num(tem), `${fmt.num(p.capacidade)} ${p.capacidade === 1 ? "disponível" : "disponíveis"}${p.em_transito ? ` + ${fmt.num(p.em_transito)} a caminho` : ""}`, falta ? "ruim" : "")}
      ${ficha("Precisa ter pelo menos", min == null ? "—" : fmt.num(min), origem)}
      ${ficha("Comprar", nada ? "Nada" : fmt.plural(p.sugestao, p.unidade, PLURAIS[p.unidade] || p.unidade + "s"), p.status === "comprar_agora" ? "agora" : p.sugestao ? "até o fim do período" : "o que tem cobre o período", nada ? "" : "destaque")}
      ${ficha("Custo estimado", nada ? "—" : fmt.brl(p.custo_estimado), p.fornecedor_sugerido ? `${fmt.brl(p.preco_esperado)} por ${p.unidade}` : "")}
    </div>
    <ul class="fatos">
      ${falta ? `<li class="ruim">Faltam ${fmt.num(falta)} para chegar ao mínimo.</li>` : min != null ? `<li class="bom">Coberto, com folga de ${fmt.num(tem - min)}.</li>` : ""}
      <li>${esc(quandoAcaba(p))}</li>
      ${p.fornecedor_sugerido ? `<li>Fornecedor sugerido: ${esc(p.fornecedor_sugerido)}, entrega em ${fmt.num(p.lead_time)} dias.</li>` : ""}
    </ul>
    ${avisos.length ? `<div class="avisos">${avisos.join("")}</div>` : ""}
    <details class="calculo"><summary>Como chegamos neste número${icone("chevron")}</summary>
      <dl class="passos">${(p.passos || []).map((s) => `<div class="passo"><dt>${esc(s.rotulo)}</dt><dd class="v">${esc(s.valor)}</dd><dd>${esc(s.detalhe)}</dd></div>`).join("")}</dl></details>
    <div class="detalhe-rodape">
      ${p.status === "sem_regra" ? `<a class="botao botao-principal" href="#cadastros?aba=itens">Definir mínimo</a>` : ""}
      <a class="botao botao-contorno" href="#precos?item=${p.servico_id}">Ver preços do item</a>
      ${p.sugestao > 0 ? `<button class="botao botao-principal" type="button" data-acao="nova-aquisicao" data-servico="${p.servico_id}" data-fornecedor="${p.fornecedor_sugerido_id}" data-quantidade="${p.sugestao}" data-preco="${p.preco_esperado}">Registrar compra de ${p.sugestao}</button>` : ""}
    </div>`;
}

/* =============================================================================
   Tela: Evolução de preço
   ============================================================================= */
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
/* cores de fornecedor: seis tons bem diferentes entre si (também em claridade, não só em matiz),
   cada fornecedor com a sua cor fixa em todos os itens, e o usuário pode trocar */
const PALETA = ["Azul", "Laranja", "Verde-azulado", "Roxo", "Magenta", "Dourado"];
const FORMAS = ["círculo", "quadrado", "triângulo", "losango"];
const CHAVE_CORES = "auge-cores-fornecedor";
function coresSalvas() { try { return JSON.parse(localStorage.getItem(CHAVE_CORES)) || {}; } catch { return {}; } }
function corDe(fid) { const s = coresSalvas(); return fid in s ? Number(s[fid]) : (fid - 1) % PALETA.length; }
function salvarCor(fid, i) { const s = coresSalvas(); s[fid] = i; try { localStorage.setItem(CHAVE_CORES, JSON.stringify(s)); } catch { /* sem armazenamento */ } }
function forma(k, x, y, r, extra) {
  if (k === 1) return `<rect x="${(x - r).toFixed(1)}" y="${(y - r).toFixed(1)}" width="${2 * r}" height="${2 * r}" rx="1.5" ${extra}/>`;
  if (k === 2) return `<path d="M${x.toFixed(1)} ${(y - r * 1.2).toFixed(1)} L${(x + r * 1.15).toFixed(1)} ${(y + r * .85).toFixed(1)} L${(x - r * 1.15).toFixed(1)} ${(y + r * .85).toFixed(1)}Z" ${extra}/>`;
  if (k === 3) return `<path d="M${x.toFixed(1)} ${(y - r * 1.3).toFixed(1)} L${(x + r * 1.3).toFixed(1)} ${y.toFixed(1)} L${x.toFixed(1)} ${(y + r * 1.3).toFixed(1)} L${(x - r * 1.3).toFixed(1)} ${y.toFixed(1)}Z" ${extra}/>`;
  return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" ${extra}/>`;
}
const formaIcone = (k) => `<svg viewBox="0 0 16 16" aria-hidden="true" class="forma-icone">${forma(k, 8, 8, 4.5, 'fill="var(--c)"')}</svg>`;
function passoBonito(bruto) { const e = 10 ** Math.floor(Math.log10(bruto)); const f = bruto / e; return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * e; }
function grafico(ev) {
  const series = ev.series.filter((s) => s.pontos.length);
  if (!series.length) return `<div class="vazio">${icone("info")}<p>Nenhuma compra deste item no período.</p></div>`;
  const W = 820, H = 330, m = { l: 64, r: 24, t: 24, b: 36 };
  const t = (iso) => Date.parse(iso + "T12:00:00Z");
  const x0 = t(ev.inicio), x1 = t(ev.fim);
  const precos = series.flatMap((s) => s.pontos.map((p) => p.preco));
  let y0 = Math.min(...precos), y1 = Math.max(...precos);
  const folga = Math.max((y1 - y0) * .2, y1 * .03); y0 -= folga; y1 += folga;
  const X = (v) => m.l + ((v - x0) / (x1 - x0)) * (W - m.l - m.r);
  const Y = (v) => m.t + (1 - (v - y0) / (y1 - y0)) * (H - m.t - m.b);
  const passo = passoBonito((y1 - y0) / 4);
  const linhasY = []; for (let v = Math.ceil(y0 / passo) * passo; v <= y1; v += passo) linhasY.push(v);
  const meses = []; let d = new Date(x0); d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1));
  while (d.getTime() <= x1) { meses.push(d.getTime()); d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1)); }
  const pulo = meses.length > 7 ? 2 : 1;
  const grupos = series.map((s, k) => {
    const ci = corDe(s.fornecedor_id), fk = k % FORMAS.length;
    const ps = s.pontos.map((p) => [X(t(p.data)), Y(p.preco), p]);
    let dc = `M${ps[0][0].toFixed(1)} ${ps[0][1].toFixed(1)}`;
    for (let i = 1; i < ps.length; i++) dc += ` H${ps[i][0].toFixed(1)} V${ps[i][1].toFixed(1)}`;   // degraus
    const ult = ps.at(-1);
    const marcas = ps.map(([px, py, p]) => {
      const anel = p.nivel === "alerta" ? `<circle cx="${px}" cy="${py}" r="12" fill="none" stroke="var(--alta)" stroke-width="2"/>` :
        p.nivel === "nota" ? `<circle cx="${px}" cy="${py}" r="11" fill="none" stroke="var(--atencao)" stroke-width="2"/>` :
        p.rebaixado ? `<circle cx="${px}" cy="${py}" r="11" fill="none" stroke="var(--tinta-3)" stroke-width="1.5" stroke-dasharray="3 3"/>` : "";
      return anel + forma(fk, px, py, 5.5, `class="ponto" fill="var(--c)" stroke="var(--superficie)" stroke-width="2" tabindex="0"
        data-f="${esc(s.fornecedor)}" data-d="${p.data}" data-p="${p.preco}" data-q="${p.quantidade}" data-c="${esc(p.codigo)}" data-n="${p.nivel}" data-r="${p.rebaixado ? 1 : 0}" data-m="${esc(p.motivo)}"`);
    }).join("");
    return `<g class="serie cor-${ci}"><path d="${dc}" fill="none" stroke="var(--c)" stroke-width="2.75" stroke-linejoin="round"/>
      <path d="M${ult[0].toFixed(1)} ${ult[1].toFixed(1)} H${X(x1).toFixed(1)}" fill="none" stroke="var(--c)" stroke-width="2" stroke-dasharray="4 5" opacity=".7"/>${marcas}</g>`;
  }).join("");
  const usadas = series.map((s) => corDe(s.fornecedor_id));
  const legenda = series.map((s, k) => {
    const ci = corDe(s.fornecedor_id);
    return `<li class="cor-${ci}"><button class="troca-cor" type="button" aria-haspopup="true" aria-expanded="false" data-fornecedor="${s.fornecedor_id}">
        ${formaIcone(k % FORMAS.length)}<span class="linha-amostra"></span><span>${esc(s.fornecedor)}</span><small>trocar cor</small></button>
      <div class="paleta" role="group" aria-label="Cor de ${esc(s.fornecedor)}">${PALETA.map((nome, i) => `<button type="button" class="cor-${i}" data-cor="${i}" aria-label="${nome}${i === ci ? ", atual" : ""}" aria-pressed="${i === ci}"
        ${usadas.includes(i) && i !== ci ? `disabled title="Já usada por outro fornecedor neste gráfico"` : ""}></button>`).join("")}</div></li>`;
  }).join("");
  const descricao = series.map((s) => `${s.fornecedor}: de ${fmt.brl(s.resumo.primeiro)} para ${fmt.brl(s.resumo.ultimo)}`).join("; ");
  return `<ul class="legenda-series">${legenda}</ul>
    <div class="grafico"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Preço unitário por compra. ${esc(descricao)}.">
      <g class="grade">${linhasY.map((v) => `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}"/>`).join("")}</g>
      <g class="eixo">${linhasY.map((v) => `<text x="${m.l - 12}" y="${Y(v) + 4}" text-anchor="end">${fmt.brl(v).replace(",00", "")}</text>`).join("")}
        ${meses.map((v, k) => (k % pulo ? "" : `<text x="${X(v)}" y="${H - 10}" text-anchor="middle">${MESES[new Date(v).getUTCMonth()]}</text>`)).join("")}</g>
      ${grupos}</svg><div class="dica" role="tooltip"></div></div>
    <p class="nota-pequena" style="padding: 0 24px 20px">Cada fornecedor tem cor e forma próprias, as mesmas em todos os itens. Linha em degraus: o preço vale de uma compra até a próxima; o tracejado é o último preço, ainda vigente. Anel vermelho = alta de preço; anel âmbar = reajuste.</p>`;
}
function ligarGrafico(raiz, redesenhar) {
  const dica = $(".dica", raiz); if (!dica) return;
  const caixa = $(".grafico", raiz);
  const mostrar = (c) => {
    const n = c.dataset.n, extra = n === "alerta" ? "Alta de preço" : n === "nota" ? "Reajuste" : c.dataset.r === "1" ? "Dentro da oscilação" : n === "queda" ? "Queda" : "";
    dica.innerHTML = `<strong>${esc(c.dataset.f)}</strong>${fmt.data(c.dataset.d)}, pedido ${esc(c.dataset.c)}<br>${fmt.brl(+c.dataset.p)} cada, ${fmt.num(+c.dataset.q)} un.${extra ? `<br><b>${extra}:</b> ${esc(c.dataset.m)}` : ""}`;
    const r = c.getBoundingClientRect(), b = caixa.getBoundingClientRect();
    dica.style.left = Math.min(Math.max(8, r.left - b.left - 140), b.width - 290) + "px";
    dica.style.top = (r.top - b.top - dica.offsetHeight - 14) + "px";
    dica.classList.add("visivel");
  };
  $$(".ponto", raiz).forEach((c) => {
    c.addEventListener("mouseenter", () => mostrar(c)); c.addEventListener("focus", () => mostrar(c));
    c.addEventListener("mouseleave", () => dica.classList.remove("visivel")); c.addEventListener("blur", () => dica.classList.remove("visivel"));
  });
  $$(".troca-cor", raiz).forEach((b) => {
    const paleta = b.nextElementSibling;
    b.addEventListener("click", () => { const abrir = b.getAttribute("aria-expanded") !== "true";
      $$(".troca-cor[aria-expanded='true']", raiz).forEach((x) => { x.setAttribute("aria-expanded", "false"); x.nextElementSibling.classList.remove("aberta"); });
      b.setAttribute("aria-expanded", String(abrir)); paleta.classList.toggle("aberta", abrir); if (abrir) paleta.querySelector("button:not([disabled])")?.focus(); });
    paleta.addEventListener("keydown", (e) => { if (e.key === "Escape") { b.setAttribute("aria-expanded", "false"); paleta.classList.remove("aberta"); b.focus(); } });
    $$("[data-cor]", paleta).forEach((c) => c.addEventListener("click", () => { salvarCor(b.dataset.fornecedor, Number(c.dataset.cor)); avisar(`Cor de ${b.querySelector("span:not(.linha-amostra)").textContent} alterada.`); redesenhar(); }));
  });
}
async function telaPrecos(el, q) {
  const cat = await catalogos();
  const item = Number(q.get("item")) || cat.servicos[0].id, dias = Number(q.get("dias")) || 180;
  const [ev, fora] = await Promise.all([obter(`/api/precos/evolucao?servico_id=${item}&dias=${dias}`), obter("/api/precos/anomalias?dias=180")]);
  const alertas = fora.filter((a) => a.nivel === "alerta").length, notas = fora.filter((a) => a.nivel === "nota").length;
  const comp = ev.comparacao.linhas;
  el.innerHTML = faixa({
    rotulo: "Controle", titulo: "Evolução de preço",
    descricao: "Quanto cada fornecedor cobrou por item e quais compras fugiram do padrão. A comparação usa o preço habitual de cada um.",
    indicadores: [{ rotulo: "Altas de preço em 6 meses", valor: String(alertas) }, { rotulo: "Reajustes em 6 meses", valor: String(notas) },
      { rotulo: "Mais barato neste item", valor: ev.comparacao.melhor || "—" }],
  }) + `<div class="conteiner pagina">
    <div class="barra-ferramentas revela"><div class="grupo">
      <label class="campo-inline" for="sel-item">Item</label>
      <select class="entrada" id="sel-item" style="min-width: 280px">${cat.servicos.map((s) => `<option value="${s.id}" ${s.id === item ? "selected" : ""}>${esc(s.nome)}</option>`).join("")}</select>
      <span class="campo-inline" id="rot-p">Período</span>
      <div class="segmentado" role="group" aria-labelledby="rot-p">${[[90, "3 meses"], [180, "6 meses"], [365, "12 meses"]].map(([v, t]) => `<a href="#precos?item=${item}&dias=${v}" aria-current="${v === dias}">${t}</a>`).join("")}</div>
    </div></div>
    <div class="grade-2">
      <div class="pilha">
        <section class="cartao revela" aria-labelledby="t-graf"><div class="cartao-cabeca"><h2 id="t-graf">${esc(ev.servico)}: preço unitário por compra</h2></div><div data-grafico>${grafico(ev)}</div></section>
        <section class="cartao revela d1" aria-labelledby="t-comp"><div class="cartao-cabeca"><h2 id="t-comp">Fornecedores deste item</h2><span class="nota-pequena">últimos 6 meses</span></div>
          ${comp.length ? `<div class="tabela-rola"><table class="tabela compacta"><thead><tr><th scope="col">Fornecedor</th><th scope="col" class="num">Próxima compra deve custar</th><th scope="col" class="num">Preço habitual</th>
            <th scope="col" class="num">Compras</th><th scope="col" class="num">Prazo</th><th scope="col" class="num">Acima do mais barato</th><th scope="col" class="num">Pago a mais</th></tr></thead>
            <tbody>${comp.map((l) => `<tr class="cor-${corDe(l.fornecedor_id)}"><td class="forte"><span class="fornecedor-cor"><span class="linha-amostra"></span>${esc(l.fornecedor)}</span> ${l.e_o_melhor ? selo(["selo-ok", "Mais barato"]) : ""}${l.base === "fraca" ? " " + selo(["selo-neutro", "Poucas compras"]) : ""}</td>
              <td class="num forte">${fmt.brl(l.preco_esperado)}</td><td class="num fraco">${fmt.brl(l.mediana)}</td>
              <td class="num fraco">${l.n_compras}</td><td class="num fraco">${l.lead_time} dias</td>
              <td class="num">${l.e_o_melhor ? "—" : `<span style="color: ${l.acima_do_limiar ? "var(--alta)" : "inherit"}; font-weight: 700">${fmt.pct(l.diferenca_para_melhor)}</span>`}</td>
              <td class="num">${l.custo_extra_estimado ? fmt.brl(l.custo_extra_estimado) : "—"}</td></tr>`).join("")}</tbody></table></div>
            <p class="nota-pequena" style="padding: 16px 24px 20px"><strong>Preço habitual</strong> é a mediana das últimas 5 compras. <strong>Próxima compra deve custar</strong> é igual ao habitual, exceto quando a última compra foi uma alta de preço: aí vale o último preço cobrado, porque pode ser um novo patamar. <strong>Pago a mais</strong> compara as compras de 6 meses com o mais barato de hoje.</p>`
          : `<div class="vazio">${icone("info")}<p>Sem compras deste item em 6 meses.</p></div>`}</section>
      </div>
      <section class="cartao fixo revela d2" aria-labelledby="t-fora"><div class="cartao-cabeca"><h2 id="t-fora">Compras fora do padrão</h2><span class="nota-pequena">todos os itens</span></div>
        <ul class="fora">${fora.map((a) => `<li><button type="button" data-item="${a.servico_id}">
          <span class="linha1">${selo(a.rebaixado && a.nivel === "normal" ? SELO_PRECO.normal : SELO_PRECO[a.nivel])}<span class="data">${fmt.data(a.data)}</span></span>
          <strong>${esc(a.servico)}, ${esc(a.fornecedor)}: ${fmt.brl(a.preco)}</strong><p>${esc(a.motivo)}</p></button></li>`).join("") || `<li class="vazio">Nenhuma compra fora do padrão.</li>`}</ul>
        <p class="nota-pequena" style="padding: 16px 24px 20px; border-top: 1px solid var(--linha)">Até 5% é reajuste normal. De 5% a 15% vira reajuste a observar. A partir de 15%, alta de preço.</p></section>
    </div></div>`;
  $("#sel-item", el).addEventListener("change", (e) => (location.hash = `#precos?item=${e.target.value}&dias=${dias}`));
  $$(".fora button", el).forEach((b) => b.addEventListener("click", () => (location.hash = `#precos?item=${b.dataset.item}&dias=${dias}`)));
  ligarGrafico(el, () => rota(true));
}

/* =============================================================================
   Tela: Conciliação
   ============================================================================= */
const NOMES_EXEMPLO = { "01": "Conforme, com arredondamento", "02": "Preço acima do combinado", "03": "Entrega parcial", "04": "Quantidade a mais",
  "05": "Diferença pequena", "06": "Diferenças pequenas repetidas", "07": "Emitente diferente", "08": "Pedido inexistente", "09": "Nota enviada duas vezes" };
const VEREDITO = { ok: ["v-ok", "ok", "Conforme: pode aceitar"], atencao: ["v-atencao", "alerta", "Atenção: aceite com ressalva"],
  divergencia: ["v-divergencia", "alerta", "Divergência: conteste antes de pagar"], rejeitada: ["v-rejeitada", "x", "Rejeitada: nada foi gravado"] };
let NOTA = { resultado: null, arquivo: null, exemplo: null };

function resultadoNota(r) {
  if (!r) return `<div class="vazio" style="padding: 72px 24px">${icone("doc")}<p><strong>Nenhuma nota conferida ainda.</strong></p><p>Escolha uma nota de exemplo ou envie um XML.</p></div>`;
  const [cls, ic, txt] = VEREDITO[r.status] || VEREDITO.atencao;
  const meta = r.rejeitada ? esc(r.motivo) : `Nota ${esc(r.numero)} de ${esc(r.emitente_nome)}, emitida em ${fmt.data(r.emissao)}, total ${fmt.brl(r.valor_total)}.`;
  const itens = (r.itens || []).map((it) => {
    const preco = it.verificacoes.find((c) => c.tipo === "preco" && c.valores?.total_esperado != null);
    const v = preco?.valores;
    return `<div class="item-nota"><h3>${esc(it.servico || it.descricao)}</h3><p>${it.aquisicao ? `Pedido ${esc(it.aquisicao)}, ${esc(it.fornecedor)}` : `Pedido informado: ${esc(it.pedido || "nenhum")}`}</p>
      <ul class="checks">${it.verificacoes.map((c) => `<li><span class="bola c-${c.status}">${icone(c.status === "ok" ? "ok" : c.status === "atencao" ? "alerta" : "x")}</span>
        <div><strong>${esc(c.titulo)}</strong><p>${esc(c.detalhe)}</p></div></li>`).join("")}</ul>
      ${v ? `<div class="comparacao">
        <div><span>Combinado</span><strong>${fmt.brl(v.total_esperado)}</strong><small>${fmt.num(it.quantidade)} × ${fmt.brl(v.unit_combinado)}</small></div>
        <div><span>Na nota</span><strong>${fmt.brl(v.total_nota)}</strong><small>${fmt.num(it.quantidade)} × ${fmt.brl(v.unit_nota)}</small></div>
        <div class="${preco.status === "divergencia" ? "ruim" : ""}"><span>Diferença</span><strong>${fmt.brl(v.diferenca)}</strong><small>${v.acumulado_fornecedor != null ? `${fmt.brl(v.acumulado_fornecedor)} em 90 dias` : "nesta nota"}</small></div>
        <div><span>Tolerado</span><strong>${fmt.brl(v.limite_material ?? v.tolerancia)}</strong><small>${v.limite_material != null ? "maior entre R$ 10 e 1%" : "arredondamento"}</small></div>
      </div>` : ""}</div>`;
  }).join("");
  const podeImportar = !r.rejeitada && (r.itens || []).some((i) => i.importavel);
  return `<div class="veredito ${cls}"><span class="icone">${icone(ic)}</span><div><h2>${txt}</h2><p>${meta}</p></div></div>${itens}
    <div class="detalhe-rodape">${modoExemplo() ? `<p class="nota-pequena" style="margin-right: auto; align-self: center">Na demonstração a importação fica desativada.</p>` : ""}
      <button class="botao botao-contorno" type="button" data-limpar>Descartar</button>
      ${podeImportar ? `<button class="botao botao-principal" type="button" data-importar ${modoExemplo() ? "disabled" : ""}>${r.status === "ok" ? "Importar nota" : r.status === "divergencia" ? "Importar mesmo assim" : "Importar com ressalva"}</button>` : ""}</div>`;
}
async function telaConciliacao(el) {
  const [exemplos, notas] = await Promise.all([obter("/api/notas-exemplo"), obter("/api/notas")]);
  const divergentes = notas.filter((n) => n.status === "divergencia").length, atencao = notas.filter((n) => n.status === "atencao").length;
  el.innerHTML = faixa({
    rotulo: "Controle", titulo: "Conferir nota fiscal",
    descricao: "Envie o XML da nota. O sistema compara quantidade, preço e emitente com o pedido antes de gravar qualquer coisa.",
    indicadores: [{ rotulo: "Notas importadas", valor: String(notas.length) }, { rotulo: "Com ressalva", valor: String(atencao) }, { rotulo: "Com divergência", valor: String(divergentes) }],
  }) + `<div class="conteiner pagina">
    <ol class="etapas revela" aria-label="Etapas"><li class="${NOTA.resultado ? "feita" : "atual"}"><b>1</b>Enviar</li><li class="${NOTA.resultado ? "atual" : ""}"><b>2</b>Conferir</li><li><b>3</b>Importar</li></ol>
    <div class="grade-lista-detalhe">
      <div class="pilha">
        <section class="cartao revela" aria-labelledby="t-env"><div class="cartao-cabeca"><h2 id="t-env">Enviar XML</h2></div><div class="cartao-corpo">
          <label class="soltar" id="soltar">${icone("upload")}<span>Arraste o arquivo da nota aqui ou</span><span class="botao botao-contorno botao-pequeno">Escolher arquivo</span>
            <input type="file" accept=".xml,text/xml,application/xml" class="sr-only" id="arquivo-xml"></label>
          ${modoExemplo() ? `<p class="nota-pequena" style="margin-top: 12px">Na demonstração, use as notas de exemplo abaixo. Envio de arquivo funciona com o servidor rodando.</p>` : ""}
        </div></section>
        <section class="cartao revela d1" aria-labelledby="t-ex"><div class="cartao-cabeca"><h2 id="t-ex">Notas de exemplo</h2><span class="nota-pequena">cada uma testa uma regra</span></div>
          <ul class="exemplos">${exemplos.map((n) => `<li><button type="button" data-exemplo="${esc(n)}" aria-pressed="${NOTA.exemplo === n}"><span><span class="n">${n.slice(0, 2)}</span>${esc(NOMES_EXEMPLO[n.slice(0, 2)] || n)}</span>${icone("seta", 'style="width: 14px; height: 14px"')}</button></li>`).join("")}</ul></section>
      </div>
      <article class="cartao fixo revela d2" aria-live="polite" id="resultado-nota">${resultadoNota(NOTA.resultado)}</article>
    </div>
    <section class="cartao revela" aria-labelledby="t-hist" style="margin-top: 36px"><div class="cartao-cabeca"><h2 id="t-hist">Notas importadas</h2><span class="nota-pequena">mais recentes primeiro</span></div>
      <div class="tabela-rola"><table class="tabela"><thead><tr><th scope="col">Recebida em</th><th scope="col">Número</th><th scope="col">Emitente</th><th scope="col">Itens</th><th scope="col" class="num">Total</th><th scope="col">Resultado</th></tr></thead>
      <tbody>${notas.slice(0, 12).map((n) => `<tr><td>${fmt.data(n.data_recebimento)}</td><td class="forte">${esc(n.numero)}</td><td class="fraco">${esc(n.emitente)}</td>
        <td class="fraco">${n.itens.map((i) => esc(i.servico)).join(", ")}</td><td class="num">${fmt.brl(n.valor_total)}</td>
        <td>${selo(n.status === "ok" ? ["selo-ok", "Conforme"] : n.status === "atencao" ? ["selo-atencao", "Ressalva"] : ["selo-alta", "Divergência"])}</td></tr>`).join("")}</tbody></table></div></section>
  </div>`;

  const mostrar = (r) => { NOTA.resultado = r; $("#resultado-nota", el).innerHTML = resultadoNota(r); ligarResultado();
    const et = $$(".etapas li", el); et[0].className = r ? "feita" : "atual"; et[1].className = r ? "atual" : ""; et[2].className = "";
    if (r && matchMedia("(max-width: 1180px)").matches) $("#resultado-nota", el).scrollIntoView({ behavior: "smooth", block: "start" }); };
  const ligarResultado = () => {
    $("[data-limpar]", el)?.addEventListener("click", () => { NOTA = { resultado: null, arquivo: null, exemplo: null }; $$("[data-exemplo]", el).forEach((b) => b.setAttribute("aria-pressed", "false")); mostrar(null); });
    $("[data-importar]", el)?.addEventListener("click", async () => {
      try {
        let r;
        if (NOTA.arquivo) { const fd = new FormData(); fd.append("arquivo", NOTA.arquivo); r = await escrever("POST", "/api/conciliacao/importar", fd); }
        else r = await escrever("POST", `/api/notas-exemplo/${encodeURIComponent(NOTA.exemplo)}/importar`);
        avisar(`Nota ${r.numero} importada. O que chegou já conta na capacidade.`);
        NOTA = { resultado: null, arquivo: null, exemplo: null }; rota();
      } catch (e) { avisar(e.message); }
    });
  };
  ligarResultado();
  $$("[data-exemplo]", el).forEach((b) => b.addEventListener("click", async () => {
    $$("[data-exemplo]", el).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    NOTA.exemplo = b.dataset.exemplo; NOTA.arquivo = null;
    try { mostrar(await obter(`/api/notas-exemplo/${encodeURIComponent(b.dataset.exemplo)}/previa`)); } catch (e) { avisar(e.message); }
  }));
  const conferirArquivo = async (arq) => {
    if (!arq) return;
    if (modoExemplo()) { avisar("Envio de arquivo precisa do servidor rodando. Use as notas de exemplo."); return; }
    NOTA.arquivo = arq; NOTA.exemplo = null; $$("[data-exemplo]", el).forEach((x) => x.setAttribute("aria-pressed", "false"));
    const fd = new FormData(); fd.append("arquivo", arq);
    try { const r = await fetch("/api/conciliacao/previa", { method: "POST", body: fd }); mostrar(await r.json()); } catch (e) { avisar(e.message); }
  };
  $("#arquivo-xml", el).addEventListener("change", (e) => conferirArquivo(e.target.files[0]));
  const zona = $("#soltar", el);
  ["dragenter", "dragover"].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.add("sobre"); }));
  ["dragleave", "drop"].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.remove("sobre"); }));
  zona.addEventListener("drop", (e) => conferirArquivo(e.dataTransfer.files[0]));
}

/* =============================================================================
   Tela: Aquisições
   ============================================================================= */
async function telaAquisicoes(el, q) {
  const dados = await obter("/api/aquisicoes");
  const filtro = q.get("filtro") || "todas", codigo = q.get("codigo"), busca = (q.get("busca") || "").toLowerCase();
  const abertas = (a) => ["aguardando", "parcial"].includes(a.situacao), problema = (a) => ["atrasada", "faltante", "excedente"].includes(a.situacao);
  let lista = filtro === "abertas" ? dados.filter(abertas) : filtro === "problema" ? dados.filter(problema) : dados;
  if (busca) lista = lista.filter((a) => `${a.codigo} ${a.servico} ${a.fornecedor}`.toLowerCase().includes(busca));
  const valorAberto = dados.filter(abertas).reduce((s, a) => s + (a.quantidade - a.recebido) * a.preco_unitario, 0);
  el.innerHTML = faixa({
    rotulo: "Compras", titulo: "Aquisições",
    descricao: "Cada pedido feito a um fornecedor e o que já chegou nas notas. É aqui que o combinado encontra o recebido.",
    indicadores: [{ rotulo: "Pedidos a caminho", valor: String(dados.filter(abertas).length), href: "#aquisicoes?filtro=abertas" },
      { rotulo: "Valor a caminho", valor: fmt.brl(valorAberto) }, { rotulo: "Com problema", valor: String(dados.filter(problema).length), href: "#aquisicoes?filtro=problema" }],
  }) + `<div class="conteiner pagina">
    <div class="barra-ferramentas revela"><div class="grupo">
      <div class="segmentado" role="group" aria-label="Filtrar pedidos">${[["todas", "Todas"], ["abertas", "A caminho"], ["problema", "Com problema"]].map(([v, t]) => `<a href="#aquisicoes?filtro=${v}" aria-current="${v === filtro}">${t}</a>`).join("")}</div>
      <label class="busca"><span class="sr-only">Buscar pedido</span>${icone("busca")}<input class="entrada" type="search" id="busca-aq" placeholder="Buscar por código, item ou fornecedor" value="${esc(q.get("busca") || "")}"></label>
    </div><button class="botao botao-principal" type="button" data-acao="nova-aquisicao">Nova aquisição</button></div>
    <section class="cartao revela d1" aria-label="Lista de aquisições"><div class="tabela-rola"><table class="tabela">
      <thead><tr><th scope="col">Pedido</th><th scope="col">Data</th><th scope="col">Item</th><th scope="col">Fornecedor</th><th scope="col" class="num">Recebido</th>
        <th scope="col" class="num">Preço unitário</th><th scope="col" class="num">Total</th><th scope="col">Entrega</th><th scope="col">Preço</th><th scope="col"><span class="sr-only">Ações</span></th></tr></thead>
      <tbody>${lista.map((a) => `<tr id="aq-${esc(a.codigo)}" class="${a.codigo === codigo ? "destaque" : ""}">
        <td class="forte">${esc(a.codigo)}</td><td class="fraco">${fmt.data(a.data_pedido)}</td><td>${esc(a.servico)}</td><td class="fraco">${esc(a.fornecedor)}</td>
        <td class="num">${fmt.num(a.recebido)} de ${fmt.num(a.quantidade)}</td><td class="num">${fmt.brl(a.preco_unitario)}</td><td class="num fraco">${fmt.brl(a.total)}</td>
        <td>${selo(SELO_SIT[a.situacao] || ["selo-neutro", a.situacao])}</td>
        <td>${["alerta", "nota", "queda"].includes(a.nivel_preco) ? selo(SELO_PRECO[a.nivel_preco]) : `<span class="fraco">—</span>`}</td>
        <td class="num">${["parcial", "atrasada"].includes(a.situacao) ? `<button class="botao botao-fantasma botao-pequeno" type="button" data-encerrar="${esc(a.codigo)}" title="Declarar que o restante não virá">Encerrar</button>` : ""}</td></tr>`).join("")
        || `<tr><td colspan="10"><div class="vazio">Nenhum pedido neste filtro.</div></td></tr>`}</tbody></table></div></section>
    <p class="nota-pequena" style="margin-top: 16px">"Encerrar" declara que o restante de um pedido não virá: o que falta vira faltante e deixa de contar como a caminho.</p>
  </div>`;
  let t; $("#busca-aq", el).addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { FOCO = "busca-aq"; history.replaceState(null, "", `#aquisicoes?filtro=${filtro}&busca=${encodeURIComponent(e.target.value)}`); rota(true); }, 300); });
  $$("[data-encerrar]", el).forEach((b) => b.addEventListener("click", async () => {
    try { await escrever("POST", `/api/aquisicoes/${encodeURIComponent(b.dataset.encerrar)}/encerrar`); avisar(`Pedido ${b.dataset.encerrar} encerrado.`); rota(); } catch (e) { avisar(e.message); } }));
  if (codigo) setTimeout(() => $(`#aq-${CSS.escape(codigo)}`, el)?.scrollIntoView({ behavior: "smooth", block: "center" }), 150);
}

/* =============================================================================
   Tela: Cadastros
   ============================================================================= */
async function telaCadastros(el, q) {
  const aba = q.get("aba") || "itens";
  const [cat, alocs] = await Promise.all([catalogos(), aba === "alocacoes" ? obter("/api/alocacoes") : Promise.resolve([])]);
  const abas = [["itens", "Itens e mínimos"], ["fornecedores", "Fornecedores"], ["clientes", "Clientes"], ["alocacoes", "Entregas a clientes"]];
  const busca = (q.get("busca") || "").toLowerCase();
  let conteudo = "", botao = "";
  if (aba === "itens") {
    botao = `<button class="botao botao-principal" type="button" data-acao="novo-item">Novo item</button>`;
    conteudo = `<table class="tabela"><thead><tr><th scope="col">Item</th><th scope="col">Categoria</th><th scope="col">Unidade</th><th scope="col">Validade</th><th scope="col">Mínimo em estoque</th></tr></thead>
      <tbody>${cat.servicos.map((s) => `<tr><td class="forte">${esc(s.nome)}</td><td class="fraco">${esc(s.categoria)}</td><td class="fraco">${esc(s.unidade)}</td>
        <td class="fraco">${s.validade_meses ? `${s.validade_meses} meses` : "não vence"}</td>
        <td><span style="display: inline-flex; gap: 8px; align-items: center"><label class="sr-only" for="min-${s.id}">Mínimo de ${esc(s.nome)}</label>
          <input class="entrada" id="min-${s.id}" type="number" min="0" step="1" value="${s.estoque_minimo ?? ""}" placeholder="sem">
          <button class="botao botao-contorno botao-pequeno" type="button" data-minimo="${s.id}">Salvar</button></span></td></tr>`).join("")}</tbody></table>`;
  } else if (aba === "fornecedores") {
    botao = `<button class="botao botao-principal" type="button" data-acao="novo-fornecedor">Novo fornecedor</button>`;
    conteudo = `<table class="tabela"><thead><tr><th scope="col">Fornecedor</th><th scope="col">CNPJ</th><th scope="col" class="num">Prazo de entrega</th></tr></thead>
      <tbody>${cat.fornecedores.map((f) => `<tr><td class="forte">${esc(f.nome)}</td><td class="fraco">${fmt.cnpj(f.cnpj)}</td><td class="num">${f.lead_time_dias} dias</td></tr>`).join("")}</tbody></table>`;
  } else if (aba === "clientes") {
    botao = `<button class="botao botao-principal" type="button" data-acao="novo-cliente">Novo cliente</button>`;
    const lista = cat.clientes.filter((c) => !busca || `${c.nome} ${c.segmento}`.toLowerCase().includes(busca));
    conteudo = `<table class="tabela"><thead><tr><th scope="col">Cliente</th><th scope="col">Segmento</th></tr></thead>
      <tbody>${lista.slice(0, 80).map((c) => `<tr><td class="forte">${esc(c.nome)}</td><td class="fraco">${esc(c.segmento)}</td></tr>`).join("")}</tbody></table>
      <p class="nota-pequena" style="padding: 14px 16px">${lista.length > 80 ? `Mostrando 80 de ${lista.length}. Use a busca para encontrar os demais.` : `${lista.length} clientes.`}</p>`;
  } else {
    botao = `<button class="botao botao-principal" type="button" data-acao="nova-alocacao">Registrar entrega</button>`;
    conteudo = `<table class="tabela"><thead><tr><th scope="col">Data</th><th scope="col">Item</th><th scope="col">Cliente</th><th scope="col" class="num">Quantidade</th></tr></thead>
      <tbody>${alocs.map((a) => `<tr><td class="fraco">${fmt.data(a.data)}</td><td class="forte">${esc(a.servico)}</td><td>${esc(a.cliente)}</td><td class="num">${fmt.num(a.quantidade)}</td></tr>`).join("")}</tbody></table>`;
  }
  const descricoes = { itens: "Os serviços que a Auge compra e repassa. O mínimo em estoque é a regra usada enquanto há pouco histórico.",
    fornecedores: "Quem vende para a Auge. O prazo cadastrado é substituído pelo prazo real depois de três entregas.",
    clientes: "Quem recebe os itens. Os nomes são fictícios.", alocacoes: "Cada item entregue a um cliente. É o que desconta da capacidade e mede o ritmo de consumo." };
  el.innerHTML = faixa({ rotulo: "Cadastros", titulo: abas.find((a) => a[0] === aba)[1], descricao: descricoes[aba],
    indicadores: [{ rotulo: "Itens", valor: String(cat.servicos.length), href: "#cadastros?aba=itens" }, { rotulo: "Fornecedores", valor: String(cat.fornecedores.length), href: "#cadastros?aba=fornecedores" },
      { rotulo: "Clientes", valor: String(cat.clientes.length), href: "#cadastros?aba=clientes" }] })
  + `<div class="conteiner pagina">
    <div class="barra-ferramentas revela"><div class="grupo"><div class="segmentado" role="tablist" aria-label="Cadastros">${abas.map(([v, t]) => `<a role="tab" href="#cadastros?aba=${v}" aria-selected="${v === aba}">${t}</a>`).join("")}</div>
      ${aba === "clientes" ? `<label class="busca"><span class="sr-only">Buscar cliente</span>${icone("busca")}<input class="entrada" type="search" id="busca-cli" placeholder="Buscar cliente" value="${esc(q.get("busca") || "")}"></label>` : ""}</div>${botao}</div>
    <section class="cartao revela d1"><div class="tabela-rola">${conteudo}</div></section></div>`;
  $$("[data-minimo]", el).forEach((b) => b.addEventListener("click", async () => {
    const v = $(`#min-${b.dataset.minimo}`, el).value;
    if (v !== "" && (Number(v) < 0 || !Number.isInteger(Number(v)))) { avisar("O mínimo precisa ser um número inteiro, zero ou maior."); return; }
    try { await escrever("PUT", `/api/servicos/${b.dataset.minimo}/estoque-minimo`, { estoque_minimo: v === "" ? null : Number(v) }); await catalogos(true); avisar("Mínimo salvo. A projeção já usa o novo valor."); }
    catch (e) { avisar(e.message); } }));
  let t; $("#busca-cli", el)?.addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { FOCO = "busca-cli"; history.replaceState(null, "", `#cadastros?aba=clientes&busca=${encodeURIComponent(e.target.value)}`); rota(true); }, 300); });
}

/* =============================================================================
   Tela: Regras
   ============================================================================= */
const DESCRICAO_REGRA = {
  "Cold start": "O que o sistema faz quando ainda tem pouco histórico de um item: não estima nada, usa o mínimo que você definiu.",
  "Projeção": "Como o sistema decide quanto comprar e quando, a partir do ritmo de consumo e do prazo real de cada fornecedor.",
  "Preço": "Quando um preço é considerado fora do padrão do próprio fornecedor, e quando um fornecedor é caro perto dos outros.",
  "Conciliação": "Quanta diferença entre a nota fiscal e o pedido é aceitável, e quando ela vira divergência.",
};
/* colunas por grupo: até 3 lado a lado; o último cartão estica para não sobrar célula vazia */
const colunas = (n) => Math.min(3, n);
const sobra = (n) => { const c = colunas(n); return Math.ceil(n / c) * c - n; };
async function telaRegras(el) {
  const d = await obter("/api/regras");
  const grupos = {}; d.regras.forEach((r) => (grupos[r.decisao] ||= []).push(r));
  el.innerHTML = faixa({ rotulo: "Transparência", titulo: "Regras do sistema",
    descricao: "Todo número que decide alguma coisa, com o porquê ao lado. Eles moram num único arquivo (app/config.py) e podem ser recalibrados depois do primeiro mês de uso real.",
    indicadores: [{ rotulo: "Regras documentadas", valor: String(d.regras.length) }, { rotulo: "Grupos de decisão", valor: String(Object.keys(grupos).length) }, { rotulo: "Data de referência", valor: fmt.data(d.hoje) }] })
  + `<div class="conteiner pagina"><div class="regras-lista">${Object.entries(grupos).map(([g, rs], i) => `
    <section class="cartao regras-grupo revela" aria-labelledby="rg-${i}">
      <header class="regras-cabeca"><span class="regras-num" aria-hidden="true">${String(i + 1).padStart(2, "0")}</span>
        <h2 id="rg-${i}">${esc(g)}</h2><p>${esc(DESCRICAO_REGRA[g] || "")}</p><span class="nota-pequena">${rs.length} ${rs.length === 1 ? "regra" : "regras"}</span></header>
      <div class="regras-grade" style="--colunas: ${colunas(rs.length)}">${rs.map((r, k) => `<article class="regra-cartao" ${k === rs.length - 1 ? `style="grid-column: span ${sobra(rs.length) + 1}"` : ""}><span class="regra-valor">${esc(r.valor)}</span><strong>${esc(r.regra)}</strong><p>${esc(r.porque)}</p></article>`).join("")}</div>
    </section>`).join("")}</div></div>`;
}

/* =============================================================================
   Roteador
   ============================================================================= */
const TELAS = {
  painel: { titulo: "Painel", render: telaPainel, dados: "/api/painel" },
  projecao: { titulo: "Projeção de compra", render: telaProjecao, dados: (q) => `/api/projecao?horizonte=${Number(q.get("h")) || 30}` },
  precos: { titulo: "Evolução de preço", render: telaPrecos },
  conciliacao: { titulo: "Conciliação", render: telaConciliacao },
  aquisicoes: { titulo: "Aquisições", render: telaAquisicoes },
  cadastros: { titulo: "Cadastros", render: telaCadastros },
  regras: { titulo: "Regras", render: telaRegras },
};
let rotaAnterior = null;
let FOCO = null;   // campo de busca que deve continuar com o foco depois de redesenhar a lista
async function rota(mesmaTela = false) {
  const [nome, qs] = location.hash.slice(1).split("?");
  const id = TELAS[nome] ? nome : (nome === "hoje" || !nome ? "painel" : null);
  if (!id) { if (nome !== "conteudo") history.replaceState(null, "", "#painel"); return nome === "conteudo" ? null : rota(); }
  const tela = TELAS[id], q = new URLSearchParams(qs || ""), el = $("#conteudo");
  document.title = `${tela.titulo} · Auge`;
  marcarMenu(id);
  try {
    if (!HOJE_ISO) HOJE_ISO = await hojeAtual();
    let dados;
    if (tela.dados) {
      const caminho = typeof tela.dados === "function" ? tela.dados(q) : tela.dados;
      dados = obterSincrono(caminho) ?? await obter(caminho);   // com dados na página, desenha antes da primeira pintura
    }
    await tela.render(el, q, dados);
  } catch (e) {
    el.innerHTML = faixa({ rotulo: "Aviso", titulo: "Não foi possível carregar esta tela.", descricao: e.message.includes("Servidor")
      ? "Esta página precisa do servidor Python para ter dados. No terminal, na pasta do projeto: py -m uvicorn app.main:app --reload e abra http://127.0.0.1:8000" : e.message });
  }
  if (!mesmaTela && rotaAnterior !== id) { scrollTo({ top: 0, behavior: "instant" }); el.focus({ preventScroll: true }); }
  rotaAnterior = id;
  if (FOCO) { const campo = $("#" + FOCO, el); FOCO = null; if (campo) { campo.focus({ preventScroll: true }); campo.setSelectionRange(campo.value.length, campo.value.length); } }
  revelar(el);
}

/* ------------------------------------------------------------------ início */
iniciarAcessibilidade();
montarMenu();
iniciarDialogos();
iniciarTopo();
addEventListener("hashchange", () => rota());
rota();
