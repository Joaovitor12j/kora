// Galeria: busca ao digitar, gaveta de detalhes, mover de categoria.
(() => {
  const miolo = () => document.getElementById("miolo");
  const form = document.getElementById("busca");
  const campo = form.querySelector("input[type=search]");
  const gaveta = document.getElementById("gaveta");
  const fundo = document.getElementById("fundo-gaveta");
  const corpo = document.getElementById("gaveta-corpo");
  let origem = null; // quem abriu a gaveta, para devolver o foco

  // --- atalho e busca ao digitar ---
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) {
      e.preventDefault();
      campo.focus();
      campo.select();
    }
    if (e.key === "Escape" && !gaveta.hidden) fecharGaveta();
  });

  async function atualizar(url, empurrar = false) {
    try {
      const html = await (await fetch(url)).text();
      const novo = new DOMParser().parseFromString(html, "text/html").getElementById("miolo");
      if (!novo) return;
      miolo().replaceWith(novo);
      (empurrar ? history.pushState : history.replaceState).call(history, null, "", url);
    } catch {
      location.href = url;
    }
  }

  let espera;
  campo.addEventListener("input", () => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      const params = new URLSearchParams(new FormData(form));
      for (const [chave, valor] of [...params]) if (!valor) params.delete(chave);
      atualizar(params.size ? `/?${params}` : "/");
    }, 220);
  });
  form.addEventListener("submit", (e) => { e.preventDefault(); clearTimeout(espera); campo.dispatchEvent(new Event("input")); });

  // Filtros do rail: troca só o miolo, sem recarregar a página.
  document.addEventListener("click", (e) => {
    const a = e.target.closest(".filtros a, .limpar, .mais, .vazio a.botao");
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || a.target) return;
    e.preventDefault();
    const url = new URL(a.href);
    if (campo.value && !url.searchParams.has("q") && a.matches(".filtros a")) url.searchParams.set("q", campo.value);
    atualizar(url.pathname + url.search, true);
  });
  window.addEventListener("popstate", () => atualizar(location.pathname + location.search));

  // --- gaveta ---
  async function abrirGaveta(rel, gatilho) {
    origem = gatilho || origem;
    try {
      const r = await fetch(`/nota?p=${encodeURIComponent(rel)}`, { headers: { "X-Fragmento": "1" } });
      if (!r.ok) throw new Error();
      corpo.innerHTML = await r.text();
    } catch {
      avisar("Não consegui abrir essa nota. Ela pode ter sido movida no Obsidian.", true);
      return;
    }
    gaveta.hidden = fundo.hidden = false;
    requestAnimationFrame(() => { gaveta.classList.add("aberta"); fundo.classList.add("aberta"); });
    document.body.style.overflow = "hidden";
    document.getElementById("fechar-gaveta").focus();
    history.replaceState(null, "", `#${encodeURIComponent(rel)}`);
  }

  function fecharGaveta() {
    gaveta.classList.remove("aberta");
    fundo.classList.remove("aberta");
    document.body.style.overflow = "";
    history.replaceState(null, "", location.pathname + location.search);
    setTimeout(() => { gaveta.hidden = fundo.hidden = true; corpo.innerHTML = ""; }, 240);
    if (origem && document.contains(origem)) origem.focus();
  }

  document.addEventListener("click", (e) => {
    const linha = e.target.closest("a.linha");
    if (linha && !e.metaKey && !e.ctrlKey && !e.shiftKey) {
      e.preventDefault();
      abrirGaveta(linha.dataset.nota, linha);
    }
  });
  document.getElementById("fechar-gaveta").addEventListener("click", fecharGaveta);
  fundo.addEventListener("click", fecharGaveta);

  // Prende o Tab dentro da gaveta enquanto ela está aberta.
  gaveta.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    const foco = [...gaveta.querySelectorAll("a[href], button, select, summary, input")].filter((x) => !x.disabled);
    if (!foco.length) return;
    const [primeiro, ultimo] = [foco[0], foco[foco.length - 1]];
    if (e.shiftKey && document.activeElement === primeiro) { e.preventDefault(); ultimo.focus(); }
    else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primeiro.focus(); }
  });

  // --- mover de categoria ---
  gaveta.addEventListener("change", async (e) => {
    const sel = e.target.closest("select[data-mover]");
    if (!sel) return;
    sel.disabled = true;
    try {
      const r = await api("/api/categoria", { p: sel.dataset.mover, categoria: sel.value });
      avisar(`Movido para ${r.categoria}`);
      await atualizar(location.pathname + location.search);
      await abrirGaveta(r.p);
    } catch (err) {
      avisar(err.message, true);
      sel.disabled = false;
    }
  });

  // Link direto para uma nota (#caminho).
  if (location.hash.length > 1) abrirGaveta(decodeURIComponent(location.hash.slice(1)));
})();
