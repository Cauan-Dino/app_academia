# Explicações de cada arquivo

---

> ## routers/cadastro_usuario.py

### **/cadastro**
- Responsável por cadastrar o usuário
    - Verifica se o usuário possui uma conta inativa
        - Se sim, substitui as informações dessa conta pelas informações que o usuário está inserindo agora
        - Se não, cadastra um novo usuário completamente do zero
    - Gera um refresh e um access token quando o usuário se cadastrar

### **/login**
- Responsável por logar o usuário caso a conta exista
- Gera um access e um refresh token

---

> ## auth_token.py

### **criar_refresh_token/criar_access_token**
- Cria um refresh token e um access token com um tempo definido no .env

### **verificar_refresh_token/verificar_access_token**
- Verifica se o access/refresh token ainda esta válido e se é do tipo certo

### **/refresh**
- Gera outro access token com base no access token

---
> ## criptografia_de_senhas.py

### **critografar_senha**
- criptografa a senha

### **bcrypt_context**
- Instância que permite verificar se a senha salva no banco de dados bate com a senha enviado no json

--- 
> ## database.py

### **Explicação do arquivo**
- Cria a conexão com o banco de dados no mysql

---
> ## main.py

### **Explicação do arquivo**
- Responsável por juntar todas as rotas do `routers`
- Responsável por iniciar todas as variaveis de ambiente

---
> ## models.py

### **Explicação do arquivo**
- Responsável por criar as tabelas do banco de dados

---

> ## scheme.py

### **Explicação do arquivo**
- Responsável por criar os schemes que serão usados no json

---

> ## verifica_se_numero_existe.py

### **gerar_codigo_pro_sms**
- Gera um código aleátorio de 6 dígitos

### **validar_codigo_usuario**
- Válida se o código SMS que o usuário está inserindo ainda esta válido (se não foi expirado)
- Verifica se o código SMS que o usuário está inserindo bate com o que está salvo no banco de dados
- Verifica se o usuário já errou muitas vezes o codigo
    - Se sim, bloqueia ele de pedir novos códigos e de tentar
    - Se não, ainda consegue tentar e pedir novos códigos
- Cada vez que o código erra é adicionando mais um no atributo tentativas_erradas se chegar a 3 tentativas falhas em uma linha ou 5 no total proibe do usuário pedir/tentar códigos SMS

### **contar_solicitacoes_na_ultima_hora**
- Conta quantas solicitações foram enviadas na última hora, se for mais de 10 bloqueia o usuário de pedir novas solicatações na próxima hora

### **contar_erros_na_ultima_hora**
- Contas quantas vezes o usuário inseriu o código errado, se for mais de 5 vezes no total na última hora bloqueia ele de pedir novos códigos na próxima hora

### **pode_solicitar_novo_sms**
- Impede o usuário de solicitar outro SMS no mesmo minuto

### **/enviar-sms**
- Verifica se o usuário ja passou mais de 10 solicitações de envio na última hora
    - Se sim, bloqueia de pedir por uma hora
- Verifica se o usuário errou mais de 5 vezes o código na última hora
    - Se sim, bloqueia ele de pedir por uma hora
- Envia o SMS