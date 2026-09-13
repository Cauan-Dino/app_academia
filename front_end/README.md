# TreinoPro Mobile

Aplicativo Expo/React Native integrado à API FastAPI do projeto.

## Executar

```bash
npm install
npm run start
```

Para apontar para outro endereço da API:

```bash
EXPO_PUBLIC_API_URL=http://SEU_IP:8000 npm run start
```

## Funcionalidades ligadas à API

- cadastro, login e renovação automática do token;
- consulta, alteração e exclusão da conta;
- consulta, pesquisa, cadastro, alteração e exclusão de alunos;
- visualização das aulas de cada aluno;
- agenda semanal com cadastro, alteração e exclusão de aulas fixas;
- consulta da ocupação da aula;
- inclusão e remoção de alunos nas aulas.

Reagendamentos e notificações ainda não possuem endpoints próprios no backend atual.
