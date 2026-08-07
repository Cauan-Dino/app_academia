# TreinoPro Mobile

Aplicativo React Native/Expo em JavaScript para Android e iOS. O front consome somente os endpoints atualmente existentes no backend.

## Executar

1. Copie `.env.example` para `.env` e informe o IP local da máquina que executa a API.
2. Execute `npm install`.
3. Execute `npm start` e abra pelo Expo Go ou por um emulador.

No Android Emulator, normalmente a API local é acessada por `http://10.0.2.2:8000`. Em um aparelho físico, use o IP da máquina na mesma rede, como `http://192.168.0.10:8000`.

## Funcionalidades ligadas à API

- Cadastro e reenvio da confirmação de e-mail
- Login e renovação automática dos tokens
- Recuperação e redefinição de senha por link
- Alteração de nome
- Solicitação de alteração de senha estando logado
- Solicitação e reenvio da exclusão de conta
- Logout local

Alunos, horários, reagendamentos e notificações não aparecem porque ainda não existem rotas correspondentes no backend.
