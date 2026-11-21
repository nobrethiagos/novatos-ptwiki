# Definições operacionais

Regras usadas em todos os scripts e análises. Qualquer mudança é anotada no histórico, no fim do arquivo, e vale para todo o grupo.

Todas as datas e horas estão em UTC, o fuso usado pela API da Wikipédia.

## Hipóteses

- **H1:** novatos de boa-fé cuja primeira edição em artigo foi revertida permanecem menos do que os que não foram revertidos.
- **H2:** novatos que recebem aviso na primeira semana permanecem menos do que os que não recebem.
  - A H2 original ("novatos que recebem boas-vindas permanecem mais") não pôde ser testada. Todos os novatos receberam as boas-vindas automáticas da conta `New user message`, e só 1 das 1.985 mensagens escritas por pessoas na primeira semana era de boas-vindas.
- **Análise da permanência:** ficam de fora as contas bloqueadas até 30 dias depois da criação, porque o bloqueio impede ou interrompe a edição, e os novatos cuja primeira edição em artigo foi feita mais de 7 dias depois da criação, para que a primeira experiência aconteça antes da janela de permanência.

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
- **Ficam fora da comparação:**
  - página nova: a primeira edição criou o artigo, então não há revisão anterior para comparar;
  - autorreversão;
  - revisão indisponível na API.
- **Conferência:** etiquetas `mw-reverted`, `mw-undo`, `mw-rollback` e `mw-manual-revert`.
- **Quem reverteu:**
  - robô: conta no grupo `bot`;
  - ferramenta: etiqueta `diff-tools` ou `huggle`;
  - humano: os demais casos.

## Mensagens na primeira semana

- **Janela:** até 7 dias (168 horas) depois da criação da conta.
- **Fonte:** revisões da página `User talk:<nome>` feitas por outras contas.
- **Boas-vindas automáticas:** a mensagem da conta `New user message`, enviada a cada conta nova, é registrada à parte e não conta como boas-vindas.
- **Não contam:**
  - mensagens desfeitas por outra revisão logo em seguida (por exemplo, avisos duplicados);
  - mensagens de manutenção feitas por robôs.
- **Tipo de cada mensagem:** boas-vindas, aviso, bloqueio ou outra, classificado por palavras-chave no sumário da edição.
- **Recepção na primeira semana (uma por novato):** nenhuma, aviso (inclui bloqueio) ou outra.

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
