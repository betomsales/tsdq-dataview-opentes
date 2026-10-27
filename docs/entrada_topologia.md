# Entrada de topologias: legado e JSON v2

## Fluxo de carregamento

No Mapa de Rede, o JSON e os bytes originais do CSV passam primeiro pela
verificação SHA-256. Somente um vínculo presente e correspondente permite
carregar o conjunto. Não há geração ou substituição automática do hash no upload.

`load_topology_json` chama `adapt_topology`, em `topology_adapter.py`. O
adaptador legado aceita arquivos sem `version` e com `version: 1`; o adaptador
v2 aceita `version: 2`. Versões explícitas diferentes são rejeitadas. Ambos
produzem os registros usados por `NetworkGraph`, `NetworkNode` e `NetworkEdge`.
As regras da compilação de circuitos OpenDSS em ZIP não foram alteradas.

## Identidades e campos

No v2, a barra usa `name`. Ramos e equipamentos usam a combinação `type` e
`name`; por exemplo, `Line-650632` e `Switch-650632` são entidades diferentes.
A normalização interna remove espaços externos e ignora a capitalização na
comparação, preservando nomes originais para a apresentação. Duplicidades e
referências a barras inexistentes são rejeitadas antes da criação do grafo.

Os três vetores `nodes`, `edges` e `elements` são obrigatórios no v2. Os campos
fixos descritos na especificação são exigidos em cada registro. `edges` e
`elements` podem estar vazios; deve existir ao menos uma barra. `kv_base` aceita
um número finito não negativo ou `null`; coordenadas aceitam números finitos
ou `null`. Uma base desconhecida não é estimada. Coordenadas zero são válidas;
o posicionamento topológico só é marcado como disponível com ambos os eixos.
No legado, uma indicação explícita `coord_defined: false` continua respeitada;
zeros usados como placeholders em arquivos antigos não viram coordenadas reais.

`nodes` e `phases` permanecem separados: uma carga monofásica em delta pode
usar dois nós. Os nós do barramento, e não a quantidade de fases de uma carga,
alimentam a identificação de fases de tensão. `kv_base` é preservado em kV,
sem conversão automática para tensão fase-neutro ou fase-fase.

## Características e classificação visual

Os equipamentos são agrupados por `bus`. Cada barra conserva todos os seus
equipamentos, suas funções e os controles reguladores associados. A prioridade
abaixo escolhe somente o destaque visual principal:

1. Fonte (`Vsource`).
2. Barramento controlado por `regcontrols`.
3. Geração fotovoltaica (`PVSystem`).
4. Armazenamento (`Storage`).
5. Geração convencional (`Generator`).
6. Carga (`Load`).
7. Capacitor (`Capacitor`).
8. Conexão a transformador.
9. Barramento comum.

O inspetor lista os equipamentos e suas conexões independentemente dessa
prioridade. A presença de PV não determina injeção: o estado fotovoltaico
continua dependendo das medições e da convenção de sinais já utilizada.

O estado `open` é topológico, não temporal. Ramos abertos não são removidos;
aparecem tracejados no D3 e no Agraph. O estado também está disponível no
inspetor do ramo e no diagnóstico das conexões. Isso não implementa um novo
cálculo de fluxo ou conectividade elétrica.

## Vínculo com resultados

`vincular_medicoes_rede`, em `measurement_binding.py`, reconhece os prefixos
completos cadastrados na topologia. Entre nomes que compartilham um prefixo,
seleciona a identidade completa mais longa; candidatos conflitantes não são
associados. Assim, `DSS-5.PVSystem-pv-4-P_meas` identifica `pv-4`, e não `pv`.
O número da instância DSS não é fixado em zero.

O mesmo vínculo é utilizado pelos snapshots, pelas séries temporais, pela
estrutura de análise elétrica e pelos frames D3. Variáveis de barras continuam
nas barras; fluxos de ramos ficam nos ramos; medições de equipamentos preservam
seu tipo, nome e barramento. RegControl é vinculado pelo registro de controle.

As convenções legadas `_bus{barra}` continuam aceitas e são verificadas contra
o vínculo do equipamento. O fallback de um único PV é restrito ao legado, sem
cadastro explícito. Ele nunca resolve equipamentos desconhecidos no v2.
Colunas desconhecidas, ambíguas ou conflitantes aparecem no diagnóstico,
inclusive quando seus valores forem NaN no instante selecionado.

Equipamentos sem colunas permanecem apenas no cadastro topológico. O vínculo
de classes adicionais permite identificar medições fornecidas, sem criar
indicadores específicos de armazenamento, perdas ou novos modelos de análise.

## Hash e unidades

O contrato preferido para novas exportações é `results_sha256` na raiz. Os
aliases já aceitos continuam disponíveis: `results_sha256`, `csv_sha256` e
`sha256` em `metadata` ou na raiz, incluindo os envelopes `hash` suportados.
Os valores são comparados após remover espaços externos e normalizar a caixa.

O script independente `scripts/aplicar_hash_topologia.py` escreve o vínculo
na raiz para o v2 e em `metadata` para o legado. Aplicá-lo explicitamente
atualiza também aliases de hash já existentes. A interface não executa esse
script nem altera os arquivos enviados.

Zeros são medições válidas. A ausência por série inteiramente NaN e a ausência
de fase explicitada na topologia mantêm as regras anteriores. Os indicadores
DRP/DRC e suas contribuições de subtensão e sobretensão não foram reformulados.

P_meas e Q_meas continuam com W e var como unidades provisórias. Permanecem
pendentes de confirmação pelo exportador a convenção dessas unidades, a
interpretação elétrica de kv_base e a adoção do campo canônico de hash.
Nenhuma medição de temperatura, irradiância, potência DC ou de inversor é
fabricada a partir do cadastro PVSystem.

## Verificação

`tests/test_topology_v2.py` inclui fixtures completas e sintéticas para as duas
versões, identidades com hífens, classes com nomes iguais, múltiplos PVs,
coordenadas zero, controle de regulação, ramos abertos, fases, conflitos e hash.
Os testes de leitura não modificam arquivos de entrada do usuário. Fixtures
sintéticas não substituem a homologação de um par real exportado pela equipe.
