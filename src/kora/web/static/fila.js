document.getElementById("processar")?.addEventListener("click", async (e) => {
  const botao = e.currentTarget;
  botao.setAttribute("aria-busy", "true");
  try {
    const { resultado } = await api("/api/lote");
    avisar({ iniciado: "Lote iniciado.", andamento: "Já há um lote rodando.",
             indisponivel: "O serviço de lotes não está instalado. Rode deploy/install.sh." }[resultado] || resultado,
           resultado === "indisponivel");
    if (resultado !== "indisponivel") setTimeout(() => location.reload(), 1500);
  } catch (err) {
    avisar(err.message, true);
  } finally {
    botao.removeAttribute("aria-busy");
  }
});
