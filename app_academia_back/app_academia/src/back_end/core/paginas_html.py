"""
Páginas HTML mostradas quando o usuário clica nos links enviados por e-mail.

Este módulo só cuida da apresentação. Os endpoints continuam com a mesma
lógica de hoje e apenas devolvem uma destas páginas no lugar do JSON.
"""
import json
from html import escape
from string import Template

from fastapi import HTTPException
from fastapi.responses import HTMLResponse

NOME_APP = "TreinoPro"

# Traço interno de cada ícone (o círculo em volta é o mesmo para todos).
_ICONES = {
    "sucesso": '<path pathLength="1" d="M15.5 25 21.5 31 33.5 18.5"/>',
    "erro": '<path pathLength="1" d="M18 18 31 31M31 18 18 31"/>',
    "aviso": '<path pathLength="1" d="M24.5 14.5v12.5M24.5 33v1"/>',
    "app": '<path pathLength="1" d="M18.5 30.5 30.5 18.5M21.5 18.5h9v9"/>',
}

_TEMPLATE = Template("""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="referrer" content="no-referrer">
<meta name="robots" content="noindex">
<title>$titulo | $nome_app</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,100..900&display=swap">
<style>
:root {
  color-scheme: light dark;
  /* Mesmas cores do e-mail (verde-limão #B9F227 e texto #121815) */
  --fundo: #F2F4F1;
  --texto: #121815;
  --texto-suave: #5A645F;
  --nome-app: #121815;
  --marca: #B9F227;
  --marca-texto: #121815;
  --verde: #4C8A0E;
  --vermelho: #C23A2E;
  --ambar: #A86A00;
  --fonte: "Archivo", system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fundo: #121815;
    --texto: #EEF2EF;
    --texto-suave: #A3ADA7;
    --nome-app: #B9F227;
    --verde: #B9F227;
    --vermelho: #FF7B6F;
    --ambar: #F0B04A;
  }
}
.sucesso { --status: var(--verde); }
.erro    { --status: var(--vermelho); }
.aviso   { --status: var(--ambar); }
.app     { --status: var(--verde); }

* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
body {
  display: flex;
  flex-direction: column;
  background: var(--fundo);
  color: var(--texto);
  font-family: var(--fonte);
  -webkit-font-smoothing: antialiased;
  padding:
    max(1.5rem, env(safe-area-inset-top))
    max(1.5rem, env(safe-area-inset-right))
    max(1.5rem, env(safe-area-inset-bottom))
    max(1.5rem, env(safe-area-inset-left));
}
.marca {
  margin: 0;
  font-weight: 800;
  font-stretch: 125%;
  font-size: 1.125rem;
  letter-spacing: -0.01em;
  color: var(--nome-app);
}
main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2.5rem 0;
}
.bloco {
  width: 100%;
  max-width: 30rem;
  border-left: 4px solid var(--status);
  padding: 0.25rem 0 0.25rem 1.5rem;
}
.icone {
  display: block;
  width: 3.5rem;
  height: 3.5rem;
  margin-bottom: 1.5rem;
  fill: none;
  stroke: var(--status);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.icone * {
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
  animation: tracar 0.5s cubic-bezier(0.3, 0.7, 0.4, 1) forwards;
}
.icone path { animation-delay: 0.35s; }
@keyframes tracar { to { stroke-dashoffset: 0; } }
@media (prefers-reduced-motion: reduce) {
  .icone * { animation: none; stroke-dashoffset: 0; }
}
h1 {
  margin: 0 0 1rem;
  font-weight: 800;
  font-stretch: 112%;
  font-size: clamp(2rem, 7.5vw, 2.75rem);
  line-height: 1.05;
  letter-spacing: -0.015em;
  text-wrap: balance;
}
.texto {
  margin: 0;
  max-width: 34ch;
  font-size: 1.0625rem;
  line-height: 1.55;
  color: var(--texto-suave);
}
.nota {
  margin: 1rem 0 0;
  max-width: 34ch;
  font-size: 0.9375rem;
  line-height: 1.5;
  color: var(--texto-suave);
}
.botao {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 3rem;
  margin-top: 2rem;
  padding: 0.75rem 1.5rem;
  border-radius: 0.5rem;
  background: var(--marca);
  color: var(--marca-texto);
  font-family: inherit;
  font-weight: 700;
  font-size: 1rem;
  text-decoration: none;
}
.botao:hover { filter: brightness(1.08); }
.botao:focus-visible { outline: 3px solid var(--texto); outline-offset: 3px; }
@media (max-width: 30rem) {
  .botao { width: 100%; }
}
</style>
</head>
<body class="$tipo">
<p class="marca">$nome_app</p>
<main>
  <section class="bloco">
    <svg class="icone" viewBox="0 0 49 49" aria-hidden="true">
      <circle pathLength="1" cx="24.5" cy="24.5" r="22"/>
      $icone
    </svg>
    <h1>$titulo</h1>
    <p class="texto">$mensagem</p>
    $nota
    $botao
  </section>
</main>
$script
</body>
</html>
""")


def renderizar_pagina(
    titulo: str,
    mensagem: str,
    tipo: str = "sucesso",
    nota: str | None = None,
    texto_botao: str | None = None,
    link_botao: str | None = None,
    redirecionar_para: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """
    Monta a página HTML.

    tipo: "sucesso", "erro", "aviso" ou "app" (define a cor e o ícone).
    redirecionar_para: se informado, a página tenta abrir esse link sozinha
    assim que carrega (usado para abrir o app pelo deep link).
    """
    if tipo not in _ICONES:
        raise ValueError(f"Tipo de página desconhecido: {tipo}")

    html_nota = f'<p class="nota">{escape(nota)}</p>' if nota else ""

    html_botao = ""
    if texto_botao and link_botao:
        html_botao = (
            f'<a class="botao" href="{escape(link_botao, quote=True)}">'
            f"{escape(texto_botao)}</a>"
        )

    html_script = ""
    if redirecionar_para:
        destino = json.dumps(redirecionar_para).replace("<", "\\u003c")
        html_script = f"<script>window.location.href = {destino};</script>"

    html = _TEMPLATE.substitute(
        titulo=escape(titulo),
        mensagem=escape(mensagem),
        nome_app=escape(NOME_APP),
        tipo=tipo,
        icone=_ICONES[tipo],
        nota=html_nota,
        botao=html_botao,
        script=html_script,
    )

    # no-store: a URL tem o token, então o navegador não deve guardar a página.
    return HTMLResponse(
        content=html,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


# ==============================================
#   PÁGINAS PRONTAS PARA CADA LINK DO E-MAIL
# ==============================================

def pagina_email_confirmado() -> HTMLResponse:
    """Mostrada depois que o link de /confirmar-email dá certo."""
    return renderizar_pagina(
        titulo="E-mail confirmado",
        mensagem=f"Sua conta no {NOME_APP} está ativa. Volte ao app e entre com seu e-mail e senha.",
    )


def pagina_conta_excluida() -> HTMLResponse:
    """Mostrada depois que o link de /confirmar-exclusao-conta dá certo."""
    return renderizar_pagina(
        titulo="Conta excluída",
        mensagem=f"Sua conta no {NOME_APP} foi excluída. Você não precisa fazer mais nada.",
    )


def pagina_abrir_app(deep_link: str) -> HTMLResponse:
    """
    Página do link /abrir-app/redefinir-senha: tenta abrir o app sozinha
    e deixa um botão caso o navegador do e-mail bloqueie o redirecionamento.
    """
    return renderizar_pagina(
        titulo=f"Abrindo o {NOME_APP}",
        mensagem="Se o app não abrir sozinho, toque no botão abaixo.",
        nota=f"Abra este link no celular em que o {NOME_APP} está instalado.",
        tipo="app",
        texto_botao=f"Abrir o {NOME_APP}",
        link_botao=deep_link,
        redirecionar_para=deep_link,
    )


def pagina_link_invalido(status_code: int = 400) -> HTMLResponse:
    """Para quando o token estiver expirado, adulterado ou já tiver sido usado."""
    return renderizar_pagina(
        titulo="Link inválido ou expirado",
        mensagem="Este link já foi usado ou passou do prazo de validade.",
        nota=f"Peça um novo e-mail pelo app do {NOME_APP}.",
        tipo="erro",
        status_code=status_code,
    )


def pagina_erro(erro: HTTPException) -> HTMLResponse:
    """
    Transforma o HTTPException que o endpoint já lança hoje em uma página,
    mantendo o mesmo status code e a mesma mensagem (detail).
    """
    if erro.status_code >= 500:
        return renderizar_pagina(
            titulo="Serviço indisponível",
            mensagem="Não foi possível concluir agora. Abra o link de novo daqui a alguns minutos.",
            tipo="aviso",
            status_code=erro.status_code,
        )

    detalhe = erro.detail if isinstance(erro.detail, str) else None
    return renderizar_pagina(
        titulo="Não foi possível concluir",
        mensagem=detalhe or "Este link já foi usado ou passou do prazo de validade.",
        nota=f"Se precisar, peça um novo e-mail pelo app do {NOME_APP}.",
        tipo="erro",
        status_code=erro.status_code,
    )
