// Ajustes: marca o que mudou, testa a IA, valida e aplica.
(() => {
  const form = document.getElementById("form-ajustes");
  const barra = document.getElementById("barra");
  const lista = document.getElementById("lista-categorias");
  const resultadoTeste = document.getElementById("resultado-teste");

  const provedor = () => form.querySelector("input[name=LLM_PROVIDER]:checked").value;
  const campos = () => [...form.querySelectorAll("input[name], select[name]")].filter((el) => el.type !== "radio" || el.checked);

  const categorias = () => [...lista.children].map((li) => ({
    nome: li.querySelector(".cat-nome").value.trim(),
    descricao: li.querySelector(".cat-desc").value.trim(),
  }));

  const instantaneo = () => JSON.stringify([campos().map((el) => [el.name, el.value]), categorias()]);
  let inicial = instantaneo();

  function mostrarProvedor() {
    const atual = provedor();
    form.querySelectorAll(".painel-provedor").forEach((p) => { p.hidden = p.dataset.provedor !== atual; });
    document.getElementById("testar").disabled = atual === "";
    if (atual === "ollama") carregarModelos();
  }

  function atualizarBarra() {
    const mudou = instantaneo() !== inicial;
    barra.hidden = !mudou;
  }

  async function carregarModelos() {
    const url = form.querySelector("[name=OLLAMA_BASE_URL]").value;
    try {
      const { modelos } = await api(`/api/ollama/modelos?url=${encodeURIComponent(url)}`, undefined, "GET");
      document.getElementById("modelos-ollama").innerHTML = modelos.map((m) => `<option value="${m.replace(/"/g, "&quot;")}">`).join("");
    } catch { /* sem sugestões; o campo continua livre */ }
  }

  function carga() {
    const env = {};
    const lotes = {};
    for (const el of campos()) {
      if (el.name.startsWith("lotes.")) lotes[el.name.slice(6)] = el.value;
      else env[el.name] = el.value;
    }
    return { env, lotes, categorias: categorias() };
  }

  form.addEventListener("input", () => { atualizarBarra(); resultadoTeste.textContent = ""; });
  form.addEventListener("change", (e) => { if (e.target.name === "LLM_PROVIDER") mostrarProvedor(); atualizarBarra(); });
  form.querySelector("[name=OLLAMA_BASE_URL]").addEventListener("change", carregarModelos);

  lista.addEventListener("click", (e) => {
    const botao = e.target.closest(".remover");
    if (botao) { botao.closest(".cat").remove(); atualizarBarra(); }
  });
  document.getElementById("nova-categoria").addEventListener("click", () => {
    const li = document.createElement("li");
    li.className = "cat";
    li.innerHTML = `<input type="text" class="cat-nome" aria-label="Nome da categoria" placeholder="nome" spellcheck="false">
      <input type="text" class="cat-desc" aria-label="O que entra nesta categoria" placeholder="o que entra aqui" spellcheck="false">
      <button type="button" class="remover" aria-label="Remover categoria"><svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 3 13 13M13 3 3 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></button>`;
    const fixa = lista.querySelector("[data-fixa]");
    lista.insertBefore(li, fixa);  // o fallback fica sempre por último
    li.querySelector(".cat-nome").focus();
    atualizarBarra();
  });

  document.getElementById("testar").addEventListener("click", async (e) => {
    const botao = e.currentTarget;
    botao.setAttribute("aria-busy", "true");
    resultadoTeste.className = "resultado";
    resultadoTeste.textContent = "Testando…";
    try {
      const r = await api("/api/ajustes/testar", { provedor: provedor(), env: carga().env });
      resultadoTeste.className = `resultado ${r.ok ? "ok" : "falha"}`;
      resultadoTeste.textContent = r.ok ? `${r.nome} respondeu.` : `${r.nome}: ${r.detalhe}`;
    } catch (err) {
      resultadoTeste.className = "resultado falha";
      resultadoTeste.textContent = err.message;
    } finally {
      botao.removeAttribute("aria-busy");
    }
  });

  document.getElementById("descartar").addEventListener("click", () => location.reload());

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const botao = document.getElementById("salvar");
    botao.setAttribute("aria-busy", "true");
    botao.disabled = true;
    try {
      const r = await api("/api/ajustes", carga(), "PUT");
      const falhas = r.passos.filter((p) => !p.ok);
      if (falhas.length) avisar(falhas.map((p) => `${p.nome}: ${p.detalhe}`).join(" "), true);
      else avisar("Salvo. " + r.passos.map((p) => p.nome).join(". ") + ".");
      document.querySelectorAll("[data-segredo]").forEach((el) => { el.value = ""; });
      inicial = instantaneo();
      atualizarBarra();
    } catch (err) {
      avisar(err.message, true);
    } finally {
      botao.removeAttribute("aria-busy");
      botao.disabled = false;
    }
  });

  mostrarProvedor();
})();
