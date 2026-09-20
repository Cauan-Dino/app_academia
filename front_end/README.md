# TreinoPro Mobile

Aplicativo Expo/React Native integrado à API FastAPI do projeto. Para entender o sistema como um todo, veja o [README principal](../README.md).

## Executar

```bash
npm install
npx expo start
```

O endereço da API vem da variável `EXPO_PUBLIC_API_URL`, lida do arquivo `.env`:

```
EXPO_PUBLIC_API_URL=http://SEU_IP:8000
```

> Use o **IP da máquina na rede**, não `localhost` — do ponto de vista do celular, `localhost` é o próprio aparelho.

> Variáveis `EXPO_PUBLIC_*` são embutidas no bundle quando o Metro inicia. Depois de alterar o `.env`, **reinicie o `expo start`**, senão o app continua usando o valor antigo.

## Funcionalidades

- cadastro, login e renovação automática do token;
- consulta, alteração e exclusão da conta;
- consulta, pesquisa, cadastro, alteração e exclusão de alunos;
- visualização das aulas de cada aluno;
- agenda semanal com cadastro, alteração e exclusão de aulas fixas;
- consulta da ocupação da aula;
- inclusão e remoção de alunos nas aulas;
- notificações push de pedidos de reagendamento, com aceite ou recusa direto pelo app.

## Notificações push

O push **não funciona no Expo Go** — versões recentes do SDK removeram o suporte a notificações remotas. É preciso gerar um *development build*. A configuração tem três partes:

**1. Projeto EAS**

```bash
npx eas-cli login
npx eas-cli init
```

Isso grava o `extra.eas.projectId` no `app.json`, exigido pelo `getExpoPushTokenAsync()`.

**2. Firebase (FCM)** — obrigatório no Android

No [console do Firebase](https://console.firebase.google.com), crie um projeto e adicione um app Android com o pacote `com.appacademia.treinopro`. Depois:

- baixe o `google-services.json` e salve na raiz do `front_end/` (já referenciado no `app.json`);
- em *Configurações do projeto → Contas de serviço*, gere uma chave privada e envie à EAS:

```bash
npx eas-cli credentials
# Android → Google Service Account → Push Notifications (FCM V1) → informe o caminho do .json
```

**3. Development build**

```bash
npx eas-cli build --profile development --platform android
```

Instale o APK gerado no aparelho e rode o Metro em modo dev client:

```bash
npx expo start --dev-client
```

> Mudanças no `google-services.json` ou no `app.json` exigem um **build novo** — recarregar o JavaScript não basta, porque são configurações nativas.

### Como o token é registrado

`src/notifications.js` pede a permissão de notificação, obtém o token da Expo e o envia a `PATCH /personal/push-token`. Isso acontece em dois momentos: logo após o login e sempre que o app abre com uma sessão válida — assim o registro se mantém correto mesmo se o token mudar (reinstalação do app, por exemplo).

A chamada é disparada sem `await`, em segundo plano: uma falha ao registrar o token não deve atrasar nem impedir a navegação do usuário.

## Estrutura

```
App.js                  navegação e telas de conta
src/api.js              cliente HTTP, sessão e renovação de token
src/notifications.js    permissão, token de push e registro na API
src/students.js         telas de alunos
src/classes.js          telas da agenda
src/components.js       componentes básicos
src/managementComponents.js  componentes das telas de gestão
src/theme.js            cores e estilos
```

## Segredos

`google-services.json` e a chave de Service Account **não vão para o repositório** — ambos estão no `.gitignore`. Cada pessoa que for buildar o app precisa baixá-los do console do Firebase.
