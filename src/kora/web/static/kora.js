// Utilidades comuns: aviso e chamadas à API.
(() => {
  let timer;
  window.avisar = (texto, erro = false) => {
    const el = document.getElementById("aviso");
    el.textContent = texto;
    el.classList.toggle("erro", erro);
    el.classList.add("visivel");
    clearTimeout(timer);
    timer = setTimeout(() => el.classList.remove("visivel"), erro ? 6000 : 3200);
  };

  window.api = async (url, corpo, metodo = "POST") => {
    const r = await fetch(url, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
    const dados = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(dados.erro || `Erro ${r.status}`);
    return dados;
  };
})();
