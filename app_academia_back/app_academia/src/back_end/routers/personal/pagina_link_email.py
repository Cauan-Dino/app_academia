"""Páginas HTML abertas pelos links dos e-mails (confirmar conta, excluir conta, nova senha).

Os links são abertos no navegador, então as respostas são páginas formatadas em
vez de JSON, inclusive quando o link expirou ou não vale mais.
"""

from dataclasses import dataclass, field
from html import escape
from typing import Literal

from fastapi.responses import HTMLResponse

# Igual ao "scheme" do front_end/app.json.
ESQUEMA_APP = "treinopro"
LINK_ABRIR_APP = f"{ESQUEMA_APP}://"

# As páginas podem conter o token do link: sem cache e sem vazar pelo Referer.
CABECALHOS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}

Tipo = Literal["sucesso", "info", "aviso", "erro"]


@dataclass(frozen=True)
class Acao:
    """Botão da página: um link (href) ou um formulário POST (form_action)."""
    texto: str
    href: str | None = None
    form_action: str | None = None
    campos: dict[str, str] = field(default_factory=dict)
    estilo: Literal["primario", "perigo"] = "primario"


ICONES = {
    "sucesso": '<path d="M7 12.5l3.2 3.2L17 9" />',
    "info": '<path d="M12 11v6" /><path d="M12 7.5v.01" />',
    "aviso": '<path d="M12 7v6" /><path d="M12 16.5v.01" />',
    "erro": '<path d="M8 8l8 8" /><path d="M16 8l-8 8" />',
}

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#F4F6F2;color:#121815;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.pagina{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px 16px}
.cartao{width:100%;max-width:440px;background:#FFFFFF;border:1px solid #DDE3DF;border-radius:22px;padding:32px 26px 28px;text-align:center}
.logo{display:block;margin:0 auto 26px}
.icone{width:64px;height:64px;border-radius:50%;margin:0 auto 18px;display:flex;align-items:center;justify-content:center}
.icone svg{width:30px;height:30px;fill:none;stroke:currentColor;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}
.sucesso .icone{background:#E9F8EF;color:#237A51}
.info .icone{background:#EEF5DC;color:#58780B}
.aviso .icone{background:#FFF6DB;color:#8A5A00}
.erro .icone{background:#FFF0F0;color:#C84444}
h1{font-size:24px;line-height:1.25;margin:0 0 10px;font-weight:800;letter-spacing:-0.3px}
p{margin:0;color:#68726D;font-size:16px;line-height:1.55}
form{margin:0}
.botao{display:block;width:100%;margin-top:24px;padding:15px 18px;border:0;border-radius:14px;font:inherit;font-size:16px;font-weight:800;text-decoration:none;cursor:pointer}
.primario{background:#B9F227;color:#121815}
.perigo{background:#C84444;color:#FFFFFF}
.nota{margin-top:18px;font-size:13px;line-height:1.5}
.marca{margin-top:26px;font-size:12px;font-weight:800;letter-spacing:1.2px;color:#8FC500}
"""

LOGO = (
    '<svg class="logo" width="48" height="48" viewBox="0 0 100 100" aria-hidden="true">'
    '<rect width="100" height="100" rx="22" fill="#121815"/>'
    '<polygon points="28,25 82,25 77,39 23,39" fill="#B9F227"/>'
    '<polygon points="47,39 61,39 52,76 38,76" fill="#B9F227"/>'
    "</svg>"
)


def _botao(acao: Acao) -> str:
    classes = f"botao {acao.estilo}"
    texto = escape(acao.texto)
    if acao.form_action:
        campos = "".join(
            f'<input type="hidden" name="{escape(nome)}" value="{escape(valor)}">'
            for nome, valor in acao.campos.items()
        )
        return (
            f'<form method="post" action="{escape(acao.form_action)}">{campos}'
            f'<button type="submit" class="{classes}">{texto}</button></form>'
        )
    return f'<a class="{classes}" href="{escape(acao.href or "")}">{texto}</a>'


def pagina(
    *,
    tipo: Tipo,
    titulo: str,
    mensagem: str,
    acao: Acao | None = None,
    nota: str | None = None,
    redirecionar_para: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Monta a página. Todo texto passa por escape: o token vem da URL."""
    refresh = (
        f'<meta http-equiv="refresh" content="0; url={escape(redirecionar_para)}">'
        if redirecionar_para else ""
    )
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
{refresh}
<title>{escape(titulo)} · TreinoPro</title>
<style>{CSS}</style>
</head>
<body>
<main class="pagina">
<section class="cartao {tipo}">
{LOGO}
<div class="icone"><svg viewBox="0 0 24 24" aria-hidden="true">{ICONES[tipo]}</svg></div>
<h1>{escape(titulo)}</h1>
<p>{escape(mensagem)}</p>
{_botao(acao) if acao else ""}
{f'<p class="nota">{escape(nota)}</p>' if nota else ""}
<div class="marca">TREINOPRO</div>
</section>
</main>
</body>
</html>"""
    return HTMLResponse(html, status_code=status_code, headers=CABECALHOS)


ABRIR_APP = Acao(texto="Abrir o TreinoPro", href=LINK_ABRIR_APP)
NOTA_CELULAR = "O botão funciona no celular em que o TreinoPro está instalado."


def _erro_generico(acao_do_link: str, status_code: int) -> HTMLResponse:
    return pagina(
        tipo="erro",
        titulo="Algo deu errado",
        mensagem=f"Não foi possível {acao_do_link} agora. Tente abrir o link de novo em alguns minutos.",
        status_code=status_code,
    )


# ---------------------------------------------------------------------------
# Confirmar conta
# ---------------------------------------------------------------------------


def pagina_email_confirmado(ja_confirmado: bool) -> HTMLResponse:
    if ja_confirmado:
        return pagina(
            tipo="info",
            titulo="Este e-mail já foi confirmado",
            mensagem="Sua conta já está ativa. Entre no app com seu e-mail e senha.",
            acao=ABRIR_APP,
            nota=NOTA_CELULAR,
        )
    return pagina(
        tipo="sucesso",
        titulo="E-mail confirmado",
        mensagem="Sua conta no TreinoPro está ativa. Abra o app e entre com seu e-mail e senha.",
        acao=ABRIR_APP,
        nota=NOTA_CELULAR,
    )


def pagina_erro_confirmar_email(status_code: int) -> HTMLResponse:
    if status_code == 400:
        return pagina(
            tipo="aviso",
            titulo="Link expirado",
            mensagem=(
                "Este link de confirmação expirou ou foi trocado por um mais novo. "
                "Faça o cadastro de novo no app com o mesmo e-mail para receber outro link."
            ),
            nota="Os links valem por 30 minutos. Use sempre o e-mail mais recente.",
            status_code=400,
        )
    if status_code == 404:
        return pagina(
            tipo="erro",
            titulo="Conta não encontrada",
            mensagem="Não encontramos uma conta para este link. Faça o cadastro de novo no app.",
            status_code=404,
        )
    return _erro_generico("confirmar seu e-mail", status_code)


# ---------------------------------------------------------------------------
# Excluir conta
# ---------------------------------------------------------------------------


def pagina_confirmar_exclusao(token: str, form_action: str) -> HTMLResponse:
    # A exclusão só acontece no POST do botão: leitores de link de alguns
    # provedores de e-mail abrem os links sozinhos (GET) para checar segurança.
    return pagina(
        tipo="aviso",
        titulo="Excluir sua conta?",
        mensagem=(
            "Você perde o acesso ao TreinoPro, aos seus alunos e às suas aulas. "
            "Essa ação não pode ser desfeita pelo app."
        ),
        acao=Acao(
            texto="Excluir minha conta",
            form_action=form_action,
            campos={"token": token},
            estilo="perigo",
        ),
        nota="Se você não pediu a exclusão, feche esta página. Sua conta continua ativa.",
    )


def pagina_conta_excluida(ja_excluida: bool) -> HTMLResponse:
    if ja_excluida:
        return pagina(
            tipo="info",
            titulo="Esta conta já foi excluída",
            mensagem="Não há mais nada a fazer. Se quiser voltar, crie uma conta nova no app.",
        )
    return pagina(
        tipo="sucesso",
        titulo="Conta excluída",
        mensagem="Sua conta foi excluída. Obrigado por usar o TreinoPro.",
    )


def pagina_erro_exclusao(status_code: int) -> HTMLResponse:
    if status_code == 400:
        return pagina(
            tipo="aviso",
            titulo="Link expirado",
            mensagem=(
                "Este link de exclusão expirou. Se ainda quiser excluir a conta, "
                "peça um novo no app, em Dados e segurança."
            ),
            nota="Os links valem por 30 minutos.",
            status_code=400,
        )
    if status_code == 404:
        return pagina(
            tipo="info",
            titulo="Conta não encontrada",
            mensagem="Esta conta não existe mais ou já foi excluída.",
            status_code=404,
        )
    return _erro_generico("excluir sua conta", status_code)


# ---------------------------------------------------------------------------
# Nova senha
# ---------------------------------------------------------------------------


def pagina_abrir_app_nova_senha(link_app: str) -> HTMLResponse:
    # O Gmail não aceita links treinopro:// no e-mail: a página abre o app sozinha
    # (meta refresh) e mantém o botão para quando o navegador bloquear o redirecionamento.
    return pagina(
        tipo="info",
        titulo="Criar nova senha",
        mensagem="Abrindo o TreinoPro na tela de nova senha. Se nada acontecer, toque no botão.",
        acao=Acao(texto="Abrir o app", href=link_app),
        nota=NOTA_CELULAR,
        redirecionar_para=link_app,
    )


def pagina_link_senha_expirado() -> HTMLResponse:
    return pagina(
        tipo="aviso",
        titulo="Link expirado",
        mensagem=(
            "Este link para criar uma nova senha expirou. Peça outro no app: "
            "\"Esqueci minha senha\" no login, ou Dados e segurança se você estiver logado."
        ),
        nota="Os links valem por 30 minutos.",
        status_code=400,
    )
