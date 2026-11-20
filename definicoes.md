# Definições operacionais

Regras usadas em todos os scripts e análises. Qualquer mudança é anotada no histórico, no fim do arquivo, e vale para todo o grupo.

Todas as datas e horas estão em UTC, o fuso usado pela API da Wikipédia.

## Coorte

- **Período:** contas criadas de 2025-03-01 00:00:00 a 2025-03-31 23:59:59 (UTC).
- **Entram:** contas do registro `newusers` com ação `create`, `create2` ou `byemail`.
- **Saem:**
  - contas com ação `autocreate` (já editavam em outro projeto da Wikimedia);
  - contas no grupo `bot`;
  - contas sem nenhuma edição visível em artigos (domínio principal, namespace 0).

## Primeira edição

- A primeira edição visível da conta em um artigo (namespace 0), pela data e hora da revisão.

## Reversão da primeira edição

- **Janela:** até 48 horas depois da primeira edição.
- **Critério:** uma revisão posterior da mesma página volta exatamente ao conteúdo anterior à edição do novato (mesmo hash SHA1).
- **Não conta:** reversão feita pelo próprio novato.
- **Conferência:** etiquetas `mw-reverted`, `mw-undo`, `mw-rollback` e `mw-manual-revert`.
- **Quem reverteu:**
  - robô: conta no grupo `bot`;
  - ferramenta: etiqueta ou sumário de ferramenta semiautomática;
  - humano: os demais casos.

## Mensagens na primeira semana

- **Janela:** até 7 dias (168 horas) depois da criação da conta.
- **Fonte:** revisões da página `User talk:<nome>` feitas por outras contas.
- **Tipos:** nenhuma, boas-vindas, aviso, ambas ou outra. A classificação automática usa palavras-chave no sumário; na subamostra, o tom é codificado à mão (acolhedor, neutro ou hostil), conforme o livro de códigos.

## Permanência (variável dependente)

- **Permaneceu:** pelo menos uma edição, em qualquer página, entre o 31º e o 90º dia depois da criação da conta, inclusive.
- Os dias são contados a partir da data e hora de criação da conta.

## Outras variáveis

- **Bloqueada no primeiro mês:** bloqueio registrado até 30 dias depois da criação da conta.
- **Edições apagadas:** `editcount` maior que o número de contribuições visíveis.
- **Controles:**
  - número de edições nas primeiras 24 horas;
  - se a primeira edição criou um artigo novo ou alterou um existente;
  - semana de criação da conta.

## Subamostra qualitativa

- 200 novatos: 100 com a primeira edição revertida e 100 sem, sorteados com semente fixa `42`.

